import json
import shutil
import tempfile
import threading
import traceback
import uuid
from pathlib import Path

# Load .env file so GEMINI_API_KEY and other secrets are available
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from core.geometry import process_model
from sim.engine import SimulationEngine

app = FastAPI(title="Archion Sim API")

# Directory to persist uploaded models so the frontend can fetch them back
UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# Clean up old uploads on startup
for f in UPLOADS_DIR.iterdir():
    f.unlink(missing_ok=True)

# In-memory simulation state
_sim_lock = threading.Lock()
_sim_status: str = "idle"  # idle | running | done | error
_sim_error: str | None = None
_sim_trajectories: dict = {}

# In-memory compliance state
_compliance_lock = threading.Lock()
_compliance_building_type: str = "residential"
_compliance_report: dict | None = None
_compliance_status: str = "idle"  # idle | running | done | error
_compliance_error: str | None = None

# Cached geometry data from last process-model call
_cached_geometry: dict | None = None

# Analytics state
_analytics_lock = threading.Lock()
_analytics_data: dict | None = None
_sim_exit_pos: list[float] | None = None

# Reports directory
REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {".obj", ".glb", ".gltf"}

_VALID_BUILDING_TYPES = [
    "residential", "public_buildings", "hospital",
    "educational", "commercial", "industrial",
]


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "archion-sim-backend"}


@app.post("/api/process-model")
async def process_model_endpoint(file: UploadFile = File(...)):
    global _cached_geometry

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        result = process_model(tmp_path)
    except ValueError as exc:
        Path(tmp_path).unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc))

    # Persist the uploaded file so the frontend can load the original model
    model_id = uuid.uuid4().hex[:12]
    model_filename = f"{model_id}{suffix}"
    dest = UPLOADS_DIR / model_filename
    shutil.move(tmp_path, dest)

    model_format = "glb" if suffix == ".glb" else ("gltf" if suffix == ".gltf" else "obj")

    # Cache geometry for compliance analysis
    _cached_geometry = {
        "wall_segments": result.obstacles,
        "boundary_coords": result.boundaries,
        "raw_boundary_coords": result.raw_boundaries,
        "floor_area": result.floor_area,
        "mesh_vertices": result.mesh_vertices,
    }

    # API response logger
    print(f"[GEOMETRY] Boundary points: {len(result.boundaries)}, "
          f"Raw boundary points: {len(result.raw_boundaries)}, "
          f"Obstacles: {len(result.obstacles)}")
    print(f"[GEOMETRY] Floor area: {result.floor_area:.4f} m²")
    for i, pt in enumerate(result.raw_boundaries[:5]):
        print(f"  raw_boundary[{i}] = ({pt[0]:.4f}, {pt[1]:.4f})")
    if len(result.raw_boundaries) > 5:
        print(f"  ... and {len(result.raw_boundaries) - 5} more points")
    print(f"[GEOMETRY AUDIT] Persisted model as {model_filename} ({model_format})")
    print(f"Mesh Wrap Sync: Simulation area exactly matches {result.floor_area:.2f} "
          f"square meters of floor space. Vertical offset set to 0.0.")

    return {
        "boundaries": result.boundaries,
        "rawBoundaries": result.raw_boundaries,
        "obstacles": result.obstacles,
        "centerOffset": result.center_offset,
        "floorArea": result.floor_area,
        "floorZ": result.floor_z,
        "modelUrl": f"/static/models/{model_filename}",
        "modelFormat": model_format,
    }


# ------------------------------------------------------------------
# Compliance endpoints
# ------------------------------------------------------------------

class ComplianceInitRequest(BaseModel):
    building_type: str = "residential"


@app.post("/api/compliance/init")
async def compliance_init(req: ComplianceInitRequest):
    global _compliance_building_type
    if req.building_type not in _VALID_BUILDING_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid building type '{req.building_type}'. "
                   f"Valid: {_VALID_BUILDING_TYPES}",
        )
    _compliance_building_type = req.building_type
    print(f"[Compliance] Building type set to: {req.building_type}")
    return {"status": "ok", "building_type": req.building_type}


@app.get("/api/compliance/report")
async def get_compliance_report():
    with _compliance_lock:
        if _compliance_status == "running":
            return {"status": "running"}
        if _compliance_status == "error":
            return {"status": "error", "error": _compliance_error}
        if _compliance_status == "idle" or _compliance_report is None:
            return {"status": "idle", "message": "No compliance audit has been run yet"}
        return {"status": "done", "report": _compliance_report}


# ------------------------------------------------------------------
# AI Consultant endpoint
# ------------------------------------------------------------------

class AIConsultantRequest(BaseModel):
    violation_id: str
    building_context: dict = {}


@app.post("/api/ai-consultant")
async def ai_consultant(req: AIConsultantRequest):
    from datetime import datetime, timezone

    # Find the violation in the current report
    with _compliance_lock:
        report = _compliance_report

    if not report or "violations" not in report:
        raise HTTPException(status_code=400, detail="No compliance report available")

    violation = None
    for v in report["violations"]:
        if v["id"] == req.violation_id:
            violation = v
            break

    if violation is None:
        raise HTTPException(status_code=404, detail=f"Violation '{req.violation_id}' not found")

    # Merge building context with defaults from cached geometry
    context = {
        "building_type": _compliance_building_type,
        "total_floor_area_sqm": (_cached_geometry or {}).get("floor_area", 0),
    }
    context.update(req.building_context)

    # Extract geometry for spatial analysis
    wall_segments = (_cached_geometry or {}).get("wall_segments", [])
    boundary_coords = (_cached_geometry or {}).get("raw_boundary_coords") or \
                      (_cached_geometry or {}).get("boundary_coords", [])

    try:
        from core.ai_consultant import get_consultant
        consultant = get_consultant()
        recommendation = consultant.get_compliance_advice(
            violation,
            context,
            wall_segments=wall_segments,
            boundary_coords=boundary_coords,
        )

        return {
            "status": "success",
            "violation_id": req.violation_id,
            "ai_recommendation": recommendation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        traceback.print_exc()
        # Build a clean fallback from knowledge base
        from core.validator import build_fallback_recommendation
        from core.knowledge_base import (
            get_cost_range, classify_deficiency_level, get_time_estimate,
            get_regulation_context,
        )
        vtype = violation.get("type", "")
        measured = float(violation.get("measured_value", 0.0))
        required = float(violation.get("required_value", 0.0))
        building_type = context.get("building_type", "residential")
        deficiency_level = classify_deficiency_level(measured, required, vtype)
        reg = get_regulation_context(vtype, building_type)
        fallback = build_fallback_recommendation(
            violation=violation,
            building_type=building_type,
            kb_cost_range=get_cost_range(vtype, deficiency_level),
            time_estimate=get_time_estimate(vtype, deficiency_level),
            deficiency_level=deficiency_level,
            regulation_ref=reg.get("reference") or violation.get("regulation", ""),
        )
        return {
            "status": "error",
            "violation_id": req.violation_id,
            "error_type": "api_unavailable",
            "fallback_recommendation": fallback,
        }


# ------------------------------------------------------------------
# Simulation endpoints
# ------------------------------------------------------------------

class SimulationRequest(BaseModel):
    boundaries: list[list[float]]
    obstacles: list[list[float]] = []          # [[x1,y1,x2,y2], ...]
    exit_pos: list[float] | None = None
    n_standard: int = 30
    n_specialist: int = 3


def _run_simulation_background(req: SimulationRequest):
    """Run the simulation engine in a background thread, then compliance audit."""
    global _sim_status, _sim_trajectories, _sim_error
    global _compliance_status, _compliance_report, _compliance_error

    try:
        engine = SimulationEngine(
            boundaries=req.boundaries,
            obstacles=req.obstacles,
            exit_pos=req.exit_pos,
            n_standard=req.n_standard,
            n_specialist=req.n_specialist,
        )
        result = engine.run()
        with _sim_lock:
            _sim_trajectories = result
            _sim_status = "done"
        print(f"[Sim] Done — {len(result)} frames")

        # --- Run compliance audit after simulation ---
        with _compliance_lock:
            _compliance_status = "running"

        try:
            from core.compliance import ComplianceChecker

            checker = ComplianceChecker(_compliance_building_type)
            geom = _cached_geometry

            if geom is None:
                raise ValueError("No geometry data cached — upload a model first")

            report = checker.run_full_audit(
                wall_segments=geom["wall_segments"],
                boundary_coords=geom["boundary_coords"],
                mesh_vertices=geom.get("mesh_vertices"),
                trajectories=result,
                floor_area=geom.get("floor_area", 0.0),
            )

            with _compliance_lock:
                _compliance_report = report.model_dump()
                _compliance_status = "done"

        except Exception as exc:
            traceback.print_exc()
            with _compliance_lock:
                _compliance_status = "error"
                _compliance_error = str(exc)

    except Exception as exc:
        traceback.print_exc()
        with _sim_lock:
            _sim_status = "error"
            _sim_error = str(exc)


@app.post("/api/simulation/start")
@app.post("/api/start-simulation")
async def start_simulation_endpoint(req: SimulationRequest):
    global _sim_status, _sim_trajectories, _sim_error
    global _compliance_status, _compliance_report, _compliance_error
    global _sim_exit_pos, _analytics_data

    _sim_exit_pos = req.exit_pos

    with _sim_lock:
        _sim_status = "running"
        _sim_trajectories = {}
        _sim_error = None
    with _compliance_lock:
        _compliance_status = "idle"
        _compliance_report = None
        _compliance_error = None
    with _analytics_lock:
        _analytics_data = None

    # Clear AI recommendation cache for fresh sim
    try:
        from core.ai_consultant import get_consultant
        get_consultant().clear_cache()
    except Exception:
        pass

    # Reset LLM brain call counter so each simulation gets a fresh budget
    try:
        from sim.llm_brain import reset_llm_brain
        reset_llm_brain()
    except Exception:
        pass

    threading.Thread(
        target=_run_simulation_background, args=(req,), daemon=True
    ).start()
    return {"status": "started", "message": "Simulation Started"}


@app.get("/api/simulation/stream")
async def stream_simulation_endpoint(
    n_standard: int = 2,
    n_specialist: int = 0,
    seed: int = 42,
):
    """SSE endpoint: streams simulation frames in real-time as they are computed.
    
    The frontend connects with EventSource and receives one frame per ~100ms.
    Gemini is called every 3 seconds for strategic goals AND immediately when a wall is detected.
    """
    global _cached_geometry

    boundaries = None
    obstacles = []

    if _cached_geometry:
        boundaries = _cached_geometry.get("boundary_coords")
        obstacles = _cached_geometry.get("wall_segments", [])

    if not boundaries:
        boundaries = [[-5, -5], [5, -5], [5, 5], [-5, 5]]

    engine = SimulationEngine(
        boundaries=boundaries,
        obstacles=obstacles,
        n_standard=n_standard,
        n_specialist=n_specialist,
        seed=seed,
    )

    def event_generator():
        global _sim_status, _sim_error, _sim_trajectories
        global _analytics_data, _compliance_status, _compliance_report, _compliance_error
        
        with _sim_lock:
            _sim_status = "running"
            _sim_trajectories.clear()
            _sim_error = None
            
        with _analytics_lock:
            _analytics_data = None
            
        with _compliance_lock:
            _compliance_status = "idle"
            
        local_traj = {}
        try:
            for frame_idx, frame_data in engine.stream():
                local_traj[str(frame_idx)] = frame_data
                payload = json.dumps({"frame": frame_idx, "agents": frame_data})
                yield {"event": "frame", "data": payload}
                
            with _sim_lock:
                _sim_trajectories.update(local_traj)
                _sim_status = "done"

            print("[event_generator] Finished streaming. Running compliance audit...")
            # Run compliance audit immediately after sim completes streaming
            with _compliance_lock:
                _compliance_status = "running"
            from core.compliance import ComplianceChecker
            try:
                checker = ComplianceChecker(_compliance_building_type)
                geom = _cached_geometry
                if geom:
                    print("[event_generator] Starting run_full_audit...")
                    report = checker.run_full_audit(
                        wall_segments=geom["wall_segments"],
                        boundary_coords=geom["boundary_coords"],
                        mesh_vertices=geom.get("mesh_vertices"),
                        trajectories=_sim_trajectories,
                        floor_area=geom.get("floor_area", 0.0),
                    )
                    with _compliance_lock:
                        _compliance_report = report.model_dump()
                        _compliance_status = "done"
                    print("[event_generator] Audit complete. Status = done.")
                else:
                    print("[event_generator] Geometry is None, skipping audit.")
                    with _compliance_lock:
                        _compliance_status = "error"
                        _compliance_error = "No geometry loaded"
            except Exception as exc:
                print(f"[event_generator] Audit crashed: {exc}")
                traceback.print_exc()
                with _compliance_lock:
                    _compliance_error = str(exc)
                    _compliance_status = "error"

        except Exception as e:
            with _sim_lock:
                _sim_status = "error"
                _sim_error = str(e)
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
        finally:
            yield {"event": "done", "data": json.dumps({"frame": "done"})}

    return EventSourceResponse(event_generator())


@app.get("/api/get-trajectories")
async def get_trajectories():
    with _sim_lock:
        if _sim_status == "running":
            return {"status": "running"}
        if _sim_status == "error":
            return {"status": "error", "error": _sim_error}
        return _sim_trajectories

# ------------------------------------------------------------------
# Analytics endpoints
# ------------------------------------------------------------------

@app.get("/api/analytics")
async def get_analytics():
    global _analytics_data

    # Return cached if available
    with _analytics_lock:
        if _analytics_data is not None:
            return {"status": "done", "data": _analytics_data}

    # Need trajectory data
    with _sim_lock:
        if _sim_status != "done" or not _sim_trajectories:
            return {"status": "error", "error": "No simulation data available"}
        traj = _sim_trajectories

    if _cached_geometry is None:
        return {"status": "error", "error": "No geometry data available"}

    try:
        from core.analytics import AnalyticsEngine

        engine = AnalyticsEngine(
            trajectories=traj,
            boundary_coords=_cached_geometry["boundary_coords"],
            exit_pos=_sim_exit_pos,
            floor_area=_cached_geometry.get("floor_area", 0.0),
        )
        result = engine.compute_all()

        with _analytics_lock:
            _analytics_data = result

        return {"status": "done", "data": result}
    except Exception as exc:
        traceback.print_exc()
        return {"status": "error", "error": str(exc)}


class ReportRequest(BaseModel):
    project_name: str = "Building Compliance Audit"


@app.post("/api/generate-report")
async def generate_report(req: ReportRequest | None = None):
    project_name = req.project_name if req else "Building Compliance Audit"

    # Ensure analytics are computed first
    analytics_resp = await get_analytics()
    if analytics_resp.get("status") != "done":
        raise HTTPException(status_code=400, detail="Analytics not available — run simulation first")

    with _compliance_lock:
        report = _compliance_report
    if not report:
        raise HTTPException(status_code=400, detail="No compliance report available")

    try:
        from core.report_gen import ReportGenerator

        # Fetch AI recommendations for top violations (limit to avoid timeout)
        ai_recs: dict = {}
        violations = report.get("violations", [])
        if violations:
            try:
                from core.ai_consultant import get_consultant
                from core.ml_predictor import predict_crowd_risk
                
                consultant = get_consultant()
                building_ctx = {
                    "building_type": _compliance_building_type,
                    "total_floor_area_sqm": (
                        _cached_geometry.get("floor_area", 0.0) if _cached_geometry else 0.0
                    ),
                }
                
                # Fetch Summary for ML Prediction
                summary_stats = analytics_resp.get("data", {}).get("summary", {})
                risk_score = predict_crowd_risk(summary_stats)
                if risk_score is not None:
                    building_ctx["ml_risk_score"] = risk_score
                    print(f"[ML Predictor] Injected Crowd Crush Risk Score: {risk_score}/10")
                # Limit to top 5 violations by severity to keep generation fast
                severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
                top_violations = sorted(
                    violations,
                    key=lambda v: severity_order.get(v.get("severity", "medium"), 2),
                )[:5]
                geom = _cached_geometry or {}
                ai_recs = consultant.get_batch_compliance_advice(
                    top_violations,
                    building_ctx,
                    wall_segments=geom.get("wall_segments", []),
                    boundary_coords=(
                        geom.get("raw_boundary_coords") or geom.get("boundary_coords", [])
                    ),
                )
                print(f"[Report] AI recommendations fetched for {len(ai_recs)} of {len(violations)} violations")
            except Exception as ai_exc:
                print(f"[Report] AI recommendations unavailable: {ai_exc}")

        gen = ReportGenerator(
            compliance_report=report,
            analytics_data=analytics_resp["data"],
            building_type=_compliance_building_type,
            floor_area=_cached_geometry.get("floor_area", 0.0) if _cached_geometry else 0.0,
            ai_recommendations=ai_recs,
        )
        filepath = gen.generate(project_name=project_name)
        filename = Path(filepath).name

        return {
            "status": "done",
            "download_url": f"/static/reports/{filename}",
            "filename": filename,
        }
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/download-report/{filename}")
async def download_report(filename: str):
    from fastapi.responses import FileResponse

    filepath = REPORTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(
        path=str(filepath),
        media_type="application/pdf",
        filename=filename,
    )


@app.get("/api/heatmap-image")
async def get_heatmap_image():
    from fastapi.responses import FileResponse

    analytics_resp = await get_analytics()
    if analytics_resp.get("status") != "done":
        raise HTTPException(status_code=400, detail="Analytics not available")

    heatmap_data = analytics_resp["data"].get("density_heatmap")
    if not heatmap_data or not heatmap_data.get("grid"):
        raise HTTPException(status_code=404, detail="No heatmap data")

    from core.analytics import generate_heatmap_png

    output_path = str(REPORTS_DIR / "heatmap_latest.png")
    generate_heatmap_png(heatmap_data, output_path)

    return FileResponse(path=output_path, media_type="image/png")


# ------------------------------------------------------------------
# MARL inference endpoint (requires trained models in backend/models/)
# ------------------------------------------------------------------

MODELS_DIR = Path(__file__).parent / "models"


class MARLSimRequest(BaseModel):
    boundaries: list[list[float]]
    obstacles: list[list[float]] = []
    exit_pos: list[float] | None = None
    num_agents: int = 2
    max_steps: int = 200


@app.post("/api/simulation/marl")
async def run_marl_simulation(req: MARLSimRequest):
    """Run inference with trained Actor-Critic MARL agents.

    Requires backend/models/agent_0_final.pth … to exist.
    Train them first: cd backend && python -m marl.train
    """
    # Check models exist
    missing = [
        str(MODELS_DIR / f"agent_{i}_final.pth")
        for i in range(req.num_agents)
        if not (MODELS_DIR / f"agent_{i}_final.pth").exists()
    ]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Trained models not found: {missing}. "
                "Run training first: cd backend && python -m marl.train"
            ),
        )

    try:
        import numpy as np
        from shapely.geometry import Polygon
        from marl.gym_environment import BuildingNavEnv
        from marl.networks import A2CAgent

        # Build environment from uploaded floor plan
        coords = [tuple(p[:2]) for p in req.boundaries]
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        floor_poly = Polygon(coords)

        env = BuildingNavEnv(
            floor_polygon=floor_poly,
            wall_segments=req.obstacles,
            num_agents=req.num_agents,
            max_steps=req.max_steps,
        )

        # Load trained agents
        agents = [
            A2CAgent.from_file(str(MODELS_DIR / f"agent_{i}_final.pth"))
            for i in range(req.num_agents)
        ]

        # Run inference
        obs, _ = env.reset(seed=0)
        trajectories: dict = {}

        for step in range(req.max_steps):
            actions = []
            for i, agent in enumerate(agents):
                action, _ = agent.select_action(obs[i])
                actions.append(action)

            obs, _rewards, terminated, truncated, info = env.step(
                np.array(actions, dtype=int)
            )

            frame: dict[str, dict] = {}
            for i in range(req.num_agents):
                pos = info["positions"][i]
                frame[str(i)] = {
                    "pos": [round(pos[0], 4), round(pos[1], 4)],
                    "type": "marl_agent",
                }
            trajectories[str(step)] = frame

            if terminated or truncated:
                break

        return {
            "status": "done",
            "frames": len(trajectories),
            "trajectories": trajectories,
        }

    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"MARL dependencies missing: {exc}. Run: pip install torch>=2.0.0 gymnasium",
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


# Mount static files AFTER all route definitions so /api routes take priority
app.mount("/static/models", StaticFiles(directory=str(UPLOADS_DIR)), name="model-files")
app.mount("/static/reports", StaticFiles(directory=str(REPORTS_DIR)), name="report-files")

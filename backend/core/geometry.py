"""3D-to-2.5D geometry extraction engine.

Extracts walkable navigation boundaries using concave hull on floor vertices.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

import numpy as np
import trimesh
from shapely import concave_hull
from shapely.geometry import MultiPoint, MultiPolygon, Polygon


SLICE_HEIGHT = 0.05  # metres
WALL_BUFFER = 0.3    # metres


@dataclass
class ExtractionResult:
    """Result of slicing a 3D mesh into 2D navigation data."""

    boundaries: list[list[float]]       # buffered exterior shell
    raw_boundaries: list[list[float]]   # exact unbuffered exterior
    obstacles: list[list[float]]        # wall segments
    center_offset: list[float]
    floor_area: float = 0.0
    floor_z: float = 0.0
    mesh_vertices: list | None = None   # centered vertices for compliance analysis


def load_mesh(file_path: str | Path) -> trimesh.Trimesh:
    """Load a 3D mesh from disk and merge scenes, applying transformations."""
    loaded = trimesh.load(str(file_path))
    if isinstance(loaded, trimesh.Scene):
        # dump() applies all node transforms and returns the instanced geometry
        dumped = loaded.dump(concatenate=True)
        if isinstance(dumped, list):
            if not dumped:
                raise ValueError("Scene contains no valid meshes")
            loaded = trimesh.util.concatenate(dumped)
        elif dumped is None:
            raise ValueError("Scene contains no valid meshes")
        else:
            loaded = dumped

    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError(f"Unsupported geometry type: {type(loaded)}")
    return loaded


def _normalize_up_axis(mesh: trimesh.Trimesh, file_path: str | Path) -> None:
    """Rotate Y-up models to Z-up, dynamically based on bounding box extents and file format."""
    extents = mesh.bounds[1] - mesh.bounds[0]
    needs_rotation = False

    file_ext = str(file_path).lower()
    if file_ext.endswith('.glb') or file_ext.endswith('.gltf'):
        # GLTF/GLB formats are strictly Y-up by specification
        needs_rotation = True
        print(f"[GEOMETRY] GLTF/GLB Y-up model detected: {file_path} — rotating to Z-up")
    else:
        # Heuristic: Buildings are usually wider and deeper than they are tall.
        # If Y-extent is significantly smaller than X and Z extents, it's likely a Y-up model.
        if (extents[1] > 0
                and extents[1] < extents[0] * 0.8
                and extents[1] < extents[2] * 0.8):
            needs_rotation = True
            print(
                f"[GEOMETRY] Heuristic Y-up: extents X={extents[0]:.2f} "
                f"Y={extents[1]:.2f} Z={extents[2]:.2f} — rotating to Z-up"
            )

    if needs_rotation:
        rotation = trimesh.transformations.rotation_matrix(
            np.pi / 2, [1, 0, 0],
        )
        mesh.apply_transform(rotation)


def _extract_wall_segments(
    mesh: trimesh.Trimesh,
    cx: float,
    cy: float,
    slice_height: float = 1.5,
    min_length: float = 0.3,
) -> list[list[float]]:
    """Slice the mesh at *slice_height* metres and return wall segments.

    Each segment is ``[x1, y1, x2, y2]`` in the centred coordinate frame
    (after subtracting *cx*, *cy*).
    """
    try:
        section = mesh.section(
            plane_origin=[0, 0, slice_height],
            plane_normal=[0, 0, 1],
        )
    except Exception:
        return []

    if section is None:
        return []

    segments: list[list[float]] = []
    for entity in section.entities:
        pts = section.vertices[entity.points][:, :2]  # X, Y only
        for j in range(len(pts) - 1):
            x1, y1 = float(pts[j][0]) - cx, float(pts[j][1]) - cy
            x2, y2 = float(pts[j + 1][0]) - cx, float(pts[j + 1][1]) - cy
            if np.hypot(x2 - x1, y2 - y1) >= min_length:
                segments.append([
                    round(x1, 4), round(y1, 4),
                    round(x2, 4), round(y2, 4),
                ])

    print(f"[GEOMETRY] Extracted {len(segments)} wall segments at Z={slice_height}m")
    return segments


def process_model(
    file_path: str | Path,
    z: float = SLICE_HEIGHT,
    wall_buffer: float = WALL_BUFFER,
) -> ExtractionResult:
    """Extract floor boundary using concave hull on vertices."""
    print(f"[GEOMETRY] Processing model: {file_path}")
    mesh = load_mesh(file_path)

    # Normalize Y-up models
    _normalize_up_axis(mesh, file_path)

    # Debug: Print Vertex Count
    print(f"[DEBUG] Total mesh vertices: {len(mesh.vertices)}")
    z_min = mesh.vertices[:, 2].min()
    z_max = mesh.vertices[:, 2].max()
    print(f"[DEBUG] Z-height range: {z_min:.2f} to {z_max:.2f}")

    # Floor normalization: shift mesh so its bottom sits at Z=0
    floor_z = float(z_min)
    if abs(floor_z) > 0.001:
        mesh.apply_translation([0, 0, -floor_z])
        print(f"[GEOMETRY] Floor normalized: shifted Z by {-floor_z:.4f}m")
        # Update z vars after shift
        z_min = 0.0
        z_max = mesh.vertices[:, 2].max()

    # --- FIX: Increase Floor Extraction Threshold ---
    # Capture vertices close to the floor to define the footprint
    floor_threshold = z_min + 1.0  # 1.0 meter tolerance as requested
    
    # --- NEW: Robust Floor Footprint Extraction ---
    # Determine the strict building interior by checking walls at 1.5m height
    uncentered_walls = _extract_wall_segments(mesh, 0.0, 0.0, slice_height=1.5, min_length=0.2)
    
    exterior = None
    
    # 1. Primary Strategy: Wall-based footprint extraction
    if uncentered_walls:
        print(f"[GEOMETRY] Building footprint from {len(uncentered_walls)} wall segments...")
        try:
            from shapely.geometry import LineString, MultiLineString, Polygon
            from shapely.ops import unary_union
            
            lines = [LineString([(w[0], w[1]), (w[2], w[3])]) for w in uncentered_walls]
            mls = MultiLineString(lines)
            
            # Buffer walls by 0.6m to close windows and doors between segments
            buffered_walls = mls.buffer(0.6, join_style=2)
            union_poly = unary_union(buffered_walls)
            
            # Select the largest contiguous building block
            if union_poly.geom_type == 'MultiPolygon':
                main_poly = max(union_poly.geoms, key=lambda p: p.area)
            else:
                main_poly = union_poly
                
            if main_poly.geom_type == 'Polygon' and not main_poly.is_empty:
                # We want a filled polygon (no holes). Create it from the exterior boundary.
                footprint = Polygon(main_poly.exterior)
                # Shrink it back by 0.6m so the boundary aligns tightly with the wall surface
                footprint = footprint.buffer(-0.6, join_style=2)
                # Simplify to remove zig-zags from low-poly noise
                exterior = footprint.simplify(0.2)
                print(f"[GEOMETRY] Extracted wall-based footprint (Area: {exterior.area:.2f})")
        except Exception as e:
            print(f"[GEOMETRY] Wall-based footprint failed: {e}")

    # 2. Fallback Strategy: Floor vertices concave hull (if no walls found or failed)
    if exterior is None or exterior.is_empty or exterior.geom_type != "Polygon":
        print("[GEOMETRY] Using fallback point-cloud concave hull for footprint.")
        floor_points_candidates = mesh.vertices[mesh.vertices[:, 2] < floor_threshold][:, [0, 1]]
        points_2d = floor_points_candidates.tolist()
        
        if len(points_2d) < 3:
            print("[GEOMETRY] CRITICAL: Less than 3 points for footprint! Falling back to 10x10 square.")
            points_2d = [(-5, -5), (5, -5), (5, 5), (-5, 5)]

        print(f"[GEOMETRY] Extracting concave hull from {len(points_2d)} points...")
        from shapely.geometry import MultiPoint
        from shapely import concave_hull
        mp = MultiPoint(points_2d)

        exterior = concave_hull(mp, ratio=0.3)

        if exterior.geom_type == "MultiPolygon":
            exterior = max(exterior.geoms, key=lambda p: p.area)
        elif exterior.geom_type != "Polygon" or exterior.is_empty:
            exterior = mp.convex_hull
    
    # --- Centering ---
    minx, miny, maxx, maxy = exterior.bounds
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    center_offset = [round(cx, 6), round(cy, 6)]
    
    from shapely.affinity import translate
    exterior = translate(exterior, xoff=-cx, yoff=-cy)

    # Raw boundaries for rendering
    raw_boundaries = [[round(c[0], 6), round(c[1], 6)] for c in exterior.exterior.coords]
    floor_area = round(exterior.area, 2)

    # Buffer for navigation
    # We use a very small negative buffer for walls (-0.15 instead of -0.3) to avoid pinching off hallways.
    buffered_exterior = exterior.buffer(-0.15)
    if buffered_exterior.is_empty or not buffered_exterior.is_valid:
        buffered_exterior = exterior  # Fallback
    
    # Handle MultiPolygon
    if isinstance(buffered_exterior, MultiPolygon):
        # Instead of taking just one room, we take the convex hull of all the pieces
        # or just fall back to the unbuffered exterior to keep the whole floor plan.
        buffered_exterior = exterior

    boundaries = [[round(c[0], 6), round(c[1], 6)] for c in buffered_exterior.exterior.coords]

    # --- Interior wall extraction via cross-section ---
    # Slice at 1.5m for walls + 0.5m for furniture (sofas, tables, chairs)
    wall_segments = _extract_wall_segments(mesh, cx, cy, slice_height=1.5, min_length=0.3)
    furniture_segments = _extract_wall_segments(mesh, cx, cy, slice_height=0.5, min_length=0.2)
    obstacle_segments = wall_segments + furniture_segments

    # Store centered mesh vertices for compliance analysis (ramp detection)
    centered_verts = mesh.vertices.copy()
    centered_verts[:, 0] -= cx
    centered_verts[:, 1] -= cy
    mesh_verts_list = centered_verts.tolist()

    # Find the actual height of the floor (lowest Z vertex)
    actual_floor_z = round(float(mesh.vertices[:, 2].min()), 4)

    return ExtractionResult(
        boundaries=boundaries,
        raw_boundaries=raw_boundaries,
        obstacles=obstacle_segments,
        center_offset=center_offset,
        floor_area=floor_area,
        floor_z=actual_floor_z,
        mesh_vertices=mesh_verts_list,
    )


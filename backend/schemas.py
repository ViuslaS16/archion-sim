from pydantic import BaseModel


class AgentPosition(BaseModel):
    id: str
    x: float
    y: float
    type: str = "standard"


class Obstacle(BaseModel):
    points: list[list[float]]


class SimulationFrame(BaseModel):
    frame_id: int
    data: dict[str, dict]


class ViolationCoordinate(BaseModel):
    x: float
    y: float
    z: float = 0.0


class Violation(BaseModel):
    id: str
    type: str       # corridor_width | door_width | turning_space | ramp_gradient | bottleneck
    severity: str   # critical | high | medium | low
    coordinate: ViolationCoordinate
    measured_value: float
    required_value: float
    description: str
    regulation: str


class ComplianceReport(BaseModel):
    standard: str
    building_type: str
    total_violations: int
    violations: list[Violation]
    compliance_score: float
    status: str          # "pass" | "fail"
    summary: dict[str, int]

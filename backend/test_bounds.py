import sys
sys.path.append("/Users/visula_s/archion-sim/backend")
from core.geometry import load_mesh, _normalize_up_axis
mesh = load_mesh("/Users/visula_s/archion-sim/backend/static/models/887f7f3a0e74.glb")
print("Original Base Mesh Bounds:")
print(mesh.bounds)
_normalize_up_axis(mesh, "test.glb")
print("Rotated Mesh Bounds:")
print(mesh.bounds)

import sys
from pathlib import Path
sys.path.append("/Users/visula_s/archion-sim/backend")
from core.geometry import process_model, load_mesh

path = "/Users/visula_s/archion-sim/backend/uploads/27a2d8babb4d.glb"
print("Loading model...")
mesh = load_mesh(path)
print("Bounds:")
print(mesh.bounds)
print("Extents:")
print(mesh.bounds[1] - mesh.bounds[0])

result = process_model(path)
print("Center Offset:", result.center_offset)
print("Floor Z:", result.floor_z)
print("Floor Area:", result.floor_area)
print("Boundaries:", result.boundaries)

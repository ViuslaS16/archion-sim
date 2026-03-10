import sys
from pathlib import Path
sys.path.append("/Users/visula_s/archion-sim/backend")
from core.geometry import process_model

path = "/Users/visula_s/archion-sim/backend/uploads/27a2d8babb4d.glb"
try:
    res = process_model(path)
    print("Success!")
    print(f"Boundaries: {len(res.boundaries)}, Obstacles: {len(res.obstacles)}")
    print(f"Area: {res.floor_area}")
except Exception as e:
    import traceback
    traceback.print_exc()

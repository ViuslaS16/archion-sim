import sys
from pathlib import Path
sys.path.append("/Users/visula_s/archion-sim/backend")
from core.geometry import process_model, load_mesh

path = "/Users/visula_s/archion-sim/backend/uploads/27a2d8babb4d.glb"
res = process_model(path)
print("Raw bounds:", min([p[0] for p in res.raw_boundaries]), max([p[0] for p in res.raw_boundaries]))
print("Raw bounds Y:", min([p[1] for p in res.raw_boundaries]), max([p[1] for p in res.raw_boundaries]))

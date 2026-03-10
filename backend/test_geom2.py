import sys
from pathlib import Path
sys.path.append("/Users/visula_s/archion-sim/backend")
from core.geometry import process_model, load_mesh, _extract_wall_segments, _normalize_up_axis
import numpy as np

path = "/Users/visula_s/archion-sim/backend/uploads/27a2d8babb4d.glb"
print("Loading model...")
mesh = load_mesh(path)
_normalize_up_axis(mesh, path)
z_min = mesh.vertices[:, 2].min()
mesh.apply_translation([0, 0, -z_min])

walls = _extract_wall_segments(mesh, 0, 0, slice_height=1.5, min_length=0.3)
walls_np = np.array(walls)
print("Walls X range:", walls_np[:, [0, 2]].min(), walls_np[:, [0, 2]].max())
print("Walls Y range:", walls_np[:, [1, 3]].min(), walls_np[:, [1, 3]].max())

floor_pts = mesh.vertices[mesh.vertices[:, 2] < 1.0][:, [0, 1]]
print("Floor pts X range:", floor_pts[:, 0].min(), floor_pts[:, 0].max())
print("Floor pts Y range:", floor_pts[:, 1].min(), floor_pts[:, 1].max())

from shapely.geometry import LineString, MultiLineString, MultiPoint
from shapely import concave_hull
lines = [LineString([(w[0], w[1]), (w[2], w[3])]) for w in walls]
buffered_walls = MultiLineString(lines).buffer(2.0)
floor_points_mp = MultiPoint(floor_pts.tolist())
filtered_points = floor_points_mp.intersection(buffered_walls)

points_2d = [(p.x, p.y) for p in filtered_points.geoms]
pts_np = np.array(points_2d)
print("Filtered pts X range:", pts_np[:, 0].min(), pts_np[:, 0].max())

mp = MultiPoint(points_2d)
exterior = concave_hull(mp, ratio=0.3)

print("Hull X range:", exterior.bounds[0], exterior.bounds[2])

# test without concave_hull ratio
exterior_convex = mp.convex_hull
print("Convex Hull X range:", exterior_convex.bounds[0], exterior_convex.bounds[2])

import sys
import numpy as np
from pathlib import Path
sys.path.append("/Users/visula_s/archion-sim/backend")
from core.geometry import load_mesh, _extract_wall_segments, _normalize_up_axis
from shapely.geometry import MultiLineString, LineString, Polygon
from shapely.ops import unary_union

path = "/Users/visula_s/archion-sim/backend/uploads/27a2d8babb4d.glb"
print("Loading model...")
mesh = load_mesh(path)
_normalize_up_axis(mesh, path)
z_min = mesh.vertices[:, 2].min()
mesh.apply_translation([0, 0, -z_min])

walls = _extract_wall_segments(mesh, 0, 0, slice_height=1.5, min_length=0.2)
lines = [LineString([(w[0], w[1]), (w[2], w[3])]) for w in walls]
mls = MultiLineString(lines)

# Buffer walls to close doors/windows
buffered_walls = mls.buffer(0.6, join_style=2)

# Unify all intersecting buffered walls
union_poly = unary_union(buffered_walls)

def get_largest_polygon(geom):
    if geom.geom_type == 'Polygon':
        return geom
    elif geom.geom_type == 'MultiPolygon':
        return max(geom.geoms, key=lambda p: p.area)
    return geom

main_poly = get_largest_polygon(union_poly)

# We want the filled area (no holes), just the exterior boundary
if main_poly.geom_type == 'Polygon':
    # Fill holes by creating a polygon just from exterior
    footprint = Polygon(main_poly.exterior)
    # Shrink it back by the buffer amount to get the actual outer wall line
    footprint = footprint.buffer(-0.6, join_style=2)
    # Simplify to remove zig zags
    footprint = footprint.simplify(0.2)
    
    print("Footprint Area:", footprint.area)
    print("Footprint bounds:", footprint.bounds)
    print("Footprint coords count:", len(footprint.exterior.coords))
    
    import matplotlib.pyplot as plt
    x, y = footprint.exterior.xy
    # plt.plot(x, y)
    # plt.savefig('footprint.png')
    

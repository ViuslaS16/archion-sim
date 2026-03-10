import trimesh
mesh = trimesh.load("uploads/27a2d8babb4d.glb", force='mesh')
print("After load:")
print("Bounds:\\n", mesh.bounds)
print("Extents:", mesh.extents)

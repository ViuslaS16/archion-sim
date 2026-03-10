import trimesh
import numpy as np

# Create a Y-up box in trimesh (let's just create a generic box)
box = trimesh.creation.box(extents=[2, 4, 1]) 
box.export("test_box.glb")

# Load and check bounds
loaded_scene = trimesh.load("test_box.glb")
print("\n=== trimesh.load() -> Scene ===")
print("Scene Bounds (Extents):", loaded_scene.extents)

loaded_mesh = trimesh.load("test_box.glb", force='mesh')
print("\n=== trimesh.load(force='mesh') ===")
print("Mesh Bounds (Extents):", loaded_mesh.extents)


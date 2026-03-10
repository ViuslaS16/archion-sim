import numpy as np
from trimesh.transformations import rotation_matrix

def f(x, y, z):
    vec = [x, y, z, 1]
    mat = rotation_matrix(np.pi / 2, [1, 0, 0])
    xb, yb, zb, _ = np.dot(mat, vec)
    
    # We pass xb, yb to frontend
    x_front = xb
    z_front = -yb
    
    # compare
    print(f"Original: {x}, {y}, {z}")
    print(f"Backend 2D: {xb}, {yb}")
    print(f"Frontend 3D: {x_front}, 0, {z_front}")
    
f(10, 5, 20)

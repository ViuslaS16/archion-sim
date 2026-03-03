"""Verify 3D-to-2.5D geometry extraction on a simple cube."""

import tempfile
from pathlib import Path

import numpy as np
import trimesh
import pytest

from core.geometry import (
    SLICE_HEIGHT,
    WALL_BUFFER,
    load_mesh,
    process_model,
)


def _create_cube_obj(size: float = 2.5) -> Path:
    """Create a *size*m cube centred at (size/2, size/2, size/2) and write to a temp .obj file."""
    mesh = trimesh.creation.box(extents=[size, size, size])
    # Shift so the cube sits with its base at z=0
    mesh.apply_translation([size / 2, size / 2, size / 2])
    tmp = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)
    mesh.export(tmp.name, file_type="obj")
    return Path(tmp.name)


def _create_cube_glb(size: float = 2.5) -> Path:
    """Create a *size*m cube as a GLB file (Y-up convention)."""
    mesh = trimesh.creation.box(extents=[size, size, size])
    # GLB uses Y-up: place cube so its base is at Y=0
    mesh.apply_translation([size / 2, size / 2, size / 2])
    tmp = tempfile.NamedTemporaryFile(suffix=".glb", delete=False)
    mesh.export(tmp.name, file_type="glb")
    return Path(tmp.name)


@pytest.fixture
def cube_obj_path():
    path = _create_cube_obj(2.5)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def cube_glb_path():
    path = _create_cube_glb(2.5)
    yield path
    path.unlink(missing_ok=True)


class TestLoadMesh:
    def test_loads_obj(self, cube_obj_path: Path):
        mesh = load_mesh(cube_obj_path)
        assert isinstance(mesh, trimesh.Trimesh)
        assert mesh.is_watertight

    def test_rejects_missing_file(self):
        with pytest.raises(Exception):
            load_mesh("/nonexistent/model.obj")


class TestProcessModelEndToEnd:
    def test_cube_produces_square_boundary(self, cube_obj_path: Path):
        result = process_model(cube_obj_path)

        # Boundaries should form a closed ring (first == last)
        bounds = np.array(result.boundaries)
        assert np.allclose(bounds[0], bounds[-1]), "Boundary ring is not closed"

        # Original cube is 2.5m, inward buffer of 0.3m on each side → ~1.9m
        expected_side = 2.5 - 2 * WALL_BUFFER
        xs = bounds[:, 0]
        ys = bounds[:, 1]
        width = xs.max() - xs.min()
        height = ys.max() - ys.min()
        assert abs(width - expected_side) < 0.15, f"Expected width ~{expected_side}m, got {width}"
        assert abs(height - expected_side) < 0.15, f"Expected height ~{expected_side}m, got {height}"

    def test_cube_has_wall_segments(self, cube_obj_path: Path):
        """A solid cube sliced at wall height should produce outer wall segments."""
        result = process_model(cube_obj_path)
        # Cross-section of a cube produces 4 wall edges
        assert len(result.obstacles) >= 4

    def test_raw_boundaries_larger_than_buffered(self, cube_obj_path: Path):
        result = process_model(cube_obj_path)
        from shapely.geometry import Polygon as ShapelyPolygon

        raw_poly = ShapelyPolygon(result.raw_boundaries)
        nav_poly = ShapelyPolygon(result.boundaries)
        assert raw_poly.area > nav_poly.area, "Raw boundary should be larger than buffered"

    def test_floor_area_positive(self, cube_obj_path: Path):
        result = process_model(cube_obj_path)
        assert result.floor_area > 0

    def test_glb_axis_normalization(self, cube_glb_path: Path):
        """GLB files (Y-up) should produce similar results to OBJ (Z-up)."""
        result = process_model(cube_glb_path)

        # Should still produce a valid boundary
        assert len(result.boundaries) >= 4
        assert result.floor_area > 0

        # The floor area should be roughly the cube's face area (2.5² = 6.25 m²)
        # Convex hull of a cube's footprint is the full face
        assert result.floor_area > 4.0, f"Floor area too small: {result.floor_area}"

    def test_l_shape_boundary_is_concave(self):
        """An L-shaped building should NOT produce a convex boundary."""
        # Build an L: 10×5 box + 5×5 box joined → total ~75 m²
        box_a = trimesh.creation.box(extents=[10, 5, 3])
        box_a.apply_translation([5, 2.5, 1.5])
        box_b = trimesh.creation.box(extents=[5, 5, 3])
        box_b.apply_translation([2.5, 7.5, 1.5])
        mesh = trimesh.util.concatenate([box_a, box_b])

        tmp = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)
        mesh.export(tmp.name, file_type="obj")
        path = Path(tmp.name)

        try:
            result = process_model(path)
            from shapely.geometry import Polygon as ShapelyPolygon

            raw_poly = ShapelyPolygon(result.raw_boundaries)

            # L-shape ≈ 75 m². Convex hull would be ≈ 100 m² (10×10).
            assert raw_poly.area < 90, (
                f"Boundary area {raw_poly.area:.1f} m² is too large — "
                f"expected concave hull for L-shape, not convex"
            )
            assert raw_poly.area > 60, (
                f"Boundary area {raw_poly.area:.1f} m² is too small"
            )
        finally:
            path.unlink(missing_ok=True)

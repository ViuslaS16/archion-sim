"""Verify that agents move toward the exit during simulation."""

import math

import numpy as np
import pytest

from sim.engine import SimulationEngine


EXIT_POS = [5.0, 2.5]


def _distance(pos: list[float], target: list[float]) -> float:
    return math.sqrt((pos[0] - target[0]) ** 2 + (pos[1] - target[1]) ** 2)


@pytest.fixture(scope="module")
def sim_result():
    """Run one simulation shared across all tests in this module."""
    boundaries = [[0, 0], [5, 0], [5, 5], [0, 5], [0, 0]]
    engine = SimulationEngine(
        boundaries=boundaries,
        obstacles=[],
        exit_pos=EXIT_POS,
        n_standard=20,
        n_specialist=2,
        seed=42,
    )
    trajectories = engine.run()
    return trajectories


class TestAgentConvergence:
    """Agents' final positions should be closer to the exit than their starts."""

    def test_standard_agents_move_toward_exit(self, sim_result: dict):
        first_frame = sim_result["0"]
        last_frame = sim_result["599"]

        closer_count = 0
        total = 0
        for aid, data in first_frame.items():
            if data["type"] != "standard":
                continue
            total += 1
            d_start = _distance(data["pos"], EXIT_POS)
            d_end = _distance(last_frame[aid]["pos"], EXIT_POS)
            if d_end < d_start:
                closer_count += 1

        assert total >= 20, f"Expected >=20 standard agents, got {total}"
        ratio = closer_count / total
        assert ratio > 0.5, (
            f"Only {closer_count}/{total} ({ratio:.0%}) standard agents "
            f"moved closer to the exit — expected >50%"
        )

    def test_specialist_agents_move_toward_exit(self, sim_result: dict):
        first_frame = sim_result["0"]
        last_frame = sim_result["599"]

        closer_count = 0
        total = 0
        for aid, data in first_frame.items():
            if data["type"] != "specialist":
                continue
            total += 1
            d_start = _distance(data["pos"], EXIT_POS)
            d_end = _distance(last_frame[aid]["pos"], EXIT_POS)
            if d_end < d_start:
                closer_count += 1

        assert total >= 2, f"Expected >=2 specialist agents, got {total}"
        ratio = closer_count / total
        assert ratio > 0.5, (
            f"Only {closer_count}/{total} ({ratio:.0%}) specialist agents "
            f"moved closer to the exit — expected >50%"
        )


class TestTrajectorySchema:
    """Verify the output matches the expected schema."""

    def test_frame_count(self, sim_result: dict):
        assert len(sim_result) == 600

    def test_agent_count_per_frame(self, sim_result: dict):
        for frame_id in ["0", "299", "599"]:
            frame = sim_result[frame_id]
            n_std = sum(1 for d in frame.values() if d["type"] == "standard")
            n_spc = sum(1 for d in frame.values() if d["type"] == "specialist")
            assert n_std == 20
            assert n_spc == 2

    def test_agent_data_format(self, sim_result: dict):
        for aid, data in sim_result["0"].items():
            assert "pos" in data
            assert "type" in data
            assert isinstance(data["pos"], list)
            assert len(data["pos"]) == 2
            assert data["type"] in ("standard", "specialist")

    def test_positions_are_finite(self, sim_result: dict):
        for frame in sim_result.values():
            for data in frame.values():
                x, y = data["pos"]
                assert math.isfinite(x), f"Non-finite x: {x}"
                assert math.isfinite(y), f"Non-finite y: {y}"


class TestSaveTrajectories:
    def test_save_creates_file(self, tmp_path):
        boundaries = [[0, 0], [3, 0], [3, 3], [0, 3], [0, 0]]
        engine = SimulationEngine(
            boundaries=boundaries,
            obstacles=[],
            exit_pos=[3.0, 1.5],
            n_standard=20,
            n_specialist=2,
            seed=99,
        )
        engine.run()
        out = engine.save(tmp_path / "traj.json")
        assert out.exists()
        import json
        data = json.loads(out.read_text())
        assert "0" in data
        assert "599" in data

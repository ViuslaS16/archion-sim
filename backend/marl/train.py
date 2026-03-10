"""MARL training script — A2C on a generic building floor plan.

Usage (from repo root):
    cd backend
    python -m marl.train
    # or:
    python marl/train.py

The generic 10×10 floor with a central dividing wall is sufficient to learn
goal-directed navigation with agent avoidance.  The resulting policy
generalises to real floor plans via the same observation format.

Outputs
-------
backend/models/agent_0_final.pth
backend/models/agent_1_final.pth
backend/models/training_curve.png   (reward & success plots)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running as `python marl/train.py` from the backend directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

try:
    import torch
except ImportError as exc:
    raise SystemExit("PyTorch not installed. Run: pip install torch>=2.0.0") from exc

try:
    from tqdm import tqdm
    _TQDM = True
except ImportError:
    _TQDM = False

from marl.gym_environment import BuildingNavEnv, make_env
from marl.networks import A2CAgent

# ---------------------------------------------------------------------------
# Training hyper-parameters
# ---------------------------------------------------------------------------

NUM_EPISODES   = 1_000
NUM_AGENTS     = 2
MAX_STEPS      = 500
LEARNING_RATE  = 3e-4
GAMMA          = 0.99
SAVE_EVERY     = 100          # checkpoint every N episodes
PRINT_EVERY    = 100          # console log every N episodes

# Generic floor plan: 10×10 room with a central wall creating two sub-spaces
_FLOOR_BOUNDARIES = [
    [0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0],
]
_WALL_SEGMENTS = [
    [5.0, 0.0,  5.0, 4.0],   # lower half of divider
    [5.0, 6.0,  5.0, 10.0],  # upper half of divider (gap at 4–6 m)
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _moving_average(data: list, window: int) -> list:
    if len(data) < window:
        return data
    ma = np.convolve(data, np.ones(window) / window, mode="valid")
    return ma.tolist()


def _save_plots(
    rewards: list,
    successes: list,
    out_path: str,
) -> None:
    try:
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        axes[0].plot(rewards, alpha=0.3, color="steelblue", label="raw")
        axes[0].plot(
            _moving_average(rewards, 50),
            color="steelblue",
            linewidth=2,
            label="MA-50",
        )
        axes[0].set_title("Episode Reward")
        axes[0].legend()

        axes[1].plot(
            _moving_average(successes, 100),
            color="green",
            linewidth=2,
        )
        axes[1].set_ylim(0, 1)
        axes[1].set_title("Success Rate (MA-100)")

        plt.tight_layout()
        plt.savefig(out_path, dpi=100)
        plt.close(fig)
        print(f"[train] Saved plot → {out_path}")
    except Exception as exc:
        print(f"[train] Could not save plot: {exc}")


# ---------------------------------------------------------------------------
# Main training loop
# ---------------------------------------------------------------------------

def train(num_episodes: int = NUM_EPISODES) -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[train] Device: {device}")

    # Build environment
    env = make_env(
        boundaries=_FLOOR_BOUNDARIES,
        wall_segments=_WALL_SEGMENTS,
        num_agents=NUM_AGENTS,
        max_steps=MAX_STEPS,
    )

    state_dim  = env.observation_space.shape[0]
    action_dim = env.action_space.n
    print(f"[train] obs_dim={state_dim}  action_dim={action_dim}")

    agents = [
        A2CAgent(state_dim, action_dim, lr=LEARNING_RATE, gamma=GAMMA, device=device)
        for _ in range(NUM_AGENTS)
    ]

    models_dir = Path(__file__).resolve().parent.parent / "models"
    models_dir.mkdir(exist_ok=True)

    rewards_history:  list[float] = []
    success_history:  list[float] = []

    ep_iter = range(num_episodes)
    if _TQDM:
        ep_iter = tqdm(ep_iter, desc="Training")

    for ep in ep_iter:
        obs, _ = env.reset(seed=ep)

        # Per-episode rollout buffers (one per agent)
        bufs = [
            {
                "states":      [],
                "rewards":     [],
                "next_states": [],
                "dones":       [],
                "log_probs":   [],
            }
            for _ in range(NUM_AGENTS)
        ]

        ep_rewards = np.zeros(NUM_AGENTS)
        done = False

        while not done:
            actions    = []
            log_probs  = []

            for i in range(NUM_AGENTS):
                action, lp = agents[i].select_action(obs[i])
                actions.append(action)
                log_probs.append(lp)

            next_obs, rewards, terminated, truncated, _ = env.step(
                np.array(actions, dtype=int)
            )
            done = terminated or truncated

            for i in range(NUM_AGENTS):
                bufs[i]["states"].append(obs[i].copy())
                bufs[i]["rewards"].append(float(rewards[i]))
                bufs[i]["next_states"].append(next_obs[i].copy())
                bufs[i]["dones"].append(float(done))
                bufs[i]["log_probs"].append(log_probs[i])
                ep_rewards[i] += rewards[i]

            obs = next_obs

        # Gradient update for each agent
        for i in range(NUM_AGENTS):
            b = bufs[i]
            agents[i].update(
                states      = torch.FloatTensor(np.array(b["states"])),
                actions     = torch.LongTensor([0] * len(b["states"])),  # unused in A2C
                rewards     = torch.FloatTensor(b["rewards"]),
                next_states = torch.FloatTensor(np.array(b["next_states"])),
                dones       = torch.FloatTensor(b["dones"]),
                log_probs   = torch.stack(b["log_probs"]),
            )

        mean_reward = float(ep_rewards.mean())
        success     = 1.0 if ep_rewards.max() > 50.0 else 0.0
        rewards_history.append(mean_reward)
        success_history.append(success)

        # Checkpoint
        if (ep + 1) % SAVE_EVERY == 0:
            for i, agent in enumerate(agents):
                agent.save(str(models_dir / f"agent_{i}_ep{ep+1}.pth"))

        # Console log
        if (ep + 1) % PRINT_EVERY == 0:
            recent_rew = float(np.mean(rewards_history[-50:]))
            recent_suc = float(np.mean(success_history[-100:]))
            print(
                f"[train] ep={ep+1:4d}  "
                f"reward(MA-50)={recent_rew:7.2f}  "
                f"success(MA-100)={recent_suc:.1%}"
            )

    # Save final models
    for i, agent in enumerate(agents):
        agent.save(str(models_dir / f"agent_{i}_final.pth"))
    print(f"[train] Final models saved to {models_dir}/")

    # Plot
    _save_plots(
        rewards_history,
        success_history,
        str(models_dir / "training_curve.png"),
    )

    print("[train] Done.")


if __name__ == "__main__":
    train()

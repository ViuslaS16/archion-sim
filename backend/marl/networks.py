"""Actor-Critic neural networks for MARL building navigation.

Requires: pip install torch>=2.0.0
"""

from __future__ import annotations

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.distributions import Categorical
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


def _require_torch():
    if not _TORCH_AVAILABLE:
        raise ImportError(
            "PyTorch not installed. Run: pip install torch>=2.0.0"
        )


class ActorNetwork(nn.Module):
    """Policy network: state → action probabilities."""

    def __init__(self, state_dim: int, action_dim: int, hidden=(128, 64)):
        _require_torch()
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden[0]),
            nn.ReLU(),
            nn.Linear(hidden[0], hidden[1]),
            nn.ReLU(),
            nn.Linear(hidden[1], action_dim),
        )
        for layer in self.net:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_uniform_(layer.weight)

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        return F.softmax(self.net(state), dim=-1)

    def select_action(self, state: np.ndarray):
        """Sample an action; return (action_int, log_prob_tensor)."""
        t = torch.FloatTensor(state).unsqueeze(0)
        with torch.no_grad():
            probs = self.forward(t)
        dist = Categorical(probs)
        action = dist.sample()
        return action.item(), dist.log_prob(action)


class CriticNetwork(nn.Module):
    """Value network: state → scalar value estimate."""

    def __init__(self, state_dim: int, hidden=(128, 64)):
        _require_torch()
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden[0]),
            nn.ReLU(),
            nn.Linear(hidden[0], hidden[1]),
            nn.ReLU(),
            nn.Linear(hidden[1], 1),
        )
        for layer in self.net:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_uniform_(layer.weight)

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        return self.net(state)


class A2CAgent:
    """Advantage Actor-Critic agent.

    Parameters
    ----------
    state_dim  : observation dimensionality
    action_dim : number of discrete actions
    lr         : learning rate (same for actor and critic)
    gamma      : discount factor
    device     : 'cpu' | 'cuda'
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        lr: float = 3e-4,
        gamma: float = 0.99,
        device: str = "cpu",
    ):
        _require_torch()
        self.device = device
        self.gamma = gamma

        self.actor  = ActorNetwork(state_dim, action_dim).to(device)
        self.critic = CriticNetwork(state_dim).to(device)

        self.actor_opt  = torch.optim.Adam(self.actor.parameters(),  lr=lr)
        self.critic_opt = torch.optim.Adam(self.critic.parameters(), lr=lr)

        self.actor_losses:  list[float] = []
        self.critic_losses: list[float] = []

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def select_action(self, state: np.ndarray):
        """Return (action_int, log_prob_tensor)."""
        return self.actor.select_action(state)

    # ------------------------------------------------------------------
    # Training update
    # ------------------------------------------------------------------

    def update(
        self,
        states:      torch.Tensor,
        actions:     torch.Tensor,
        rewards:     torch.Tensor,
        next_states: torch.Tensor,
        dones:       torch.Tensor,
        log_probs:   torch.Tensor,
    ) -> tuple[float, float]:
        """One gradient step for both actor and critic."""
        states      = states.to(self.device)
        next_states = next_states.to(self.device)
        rewards     = rewards.to(self.device)
        dones       = dones.to(self.device)
        log_probs   = log_probs.to(self.device)

        values      = self.critic(states).squeeze(-1)
        next_values = self.critic(next_states).squeeze(-1).detach()

        td_target  = rewards + self.gamma * next_values * (1.0 - dones)
        advantage  = (td_target - values).detach()

        actor_loss  = -(log_probs * advantage).mean()
        critic_loss = F.mse_loss(values, td_target.detach())

        self.actor_opt.zero_grad()
        actor_loss.backward()
        nn.utils.clip_grad_norm_(self.actor.parameters(), 0.5)
        self.actor_opt.step()

        self.critic_opt.zero_grad()
        critic_loss.backward()
        nn.utils.clip_grad_norm_(self.critic.parameters(), 0.5)
        self.critic_opt.step()

        a_loss = float(actor_loss.item())
        c_loss = float(critic_loss.item())
        self.actor_losses.append(a_loss)
        self.critic_losses.append(c_loss)
        return a_loss, c_loss

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        torch.save(
            {
                "actor":      self.actor.state_dict(),
                "critic":     self.critic.state_dict(),
                "actor_opt":  self.actor_opt.state_dict(),
                "critic_opt": self.critic_opt.state_dict(),
                "state_dim":  self.actor.net[0].in_features,
                "action_dim": self.actor.net[-1].out_features,
            },
            path,
        )
        print(f"[A2CAgent] Saved → {path}")

    def load(self, path: str) -> None:
        ckpt = torch.load(path, map_location=self.device, weights_only=True)
        self.actor.load_state_dict(ckpt["actor"])
        self.critic.load_state_dict(ckpt["critic"])
        self.actor_opt.load_state_dict(ckpt["actor_opt"])
        self.critic_opt.load_state_dict(ckpt["critic_opt"])
        print(f"[A2CAgent] Loaded ← {path}")

    @classmethod
    def from_file(cls, path: str, device: str = "cpu") -> "A2CAgent":
        """Load a saved agent without needing to know state/action dims up-front."""
        _require_torch()
        ckpt = torch.load(path, map_location=device, weights_only=True)
        state_dim  = ckpt["state_dim"]
        action_dim = ckpt["action_dim"]
        agent = cls(state_dim=state_dim, action_dim=action_dim, device=device)
        agent.actor.load_state_dict(ckpt["actor"])
        agent.critic.load_state_dict(ckpt["critic"])
        print(f"[A2CAgent] Loaded from {path} — state_dim={state_dim}, action_dim={action_dim}")
        return agent

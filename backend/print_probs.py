import torch
import torch.nn as nn
import os

class AgentBrain(nn.Module):
    def __init__(self):
        super().__init__()
        self.common = nn.Linear(5, 64) 
        self.actor = nn.Linear(64, 4)  
        self.critic = nn.Linear(64, 1)

    def forward(self, state):
        x = torch.relu(self.common(state))
        action_probs = torch.softmax(self.actor(x), dim=-1)
        state_value = self.critic(x)
        return action_probs, state_value

current_dir = "/Users/visula_s/archion-sim/backend/sim"
model_path = os.path.join(current_dir, "archion_marl_brain_v1.pth")
brain = AgentBrain()
brain.load_state_dict(torch.load(model_path, map_location=torch.device('cpu'), weights_only=True))
brain.eval()

states = torch.FloatTensor([
    [5.0, 5.0, 5.0, 0.0, 0.0],
    [5.0, 2.0, 2.0, 0.0, 0.0],
    [1.0, 1.0, 1.0, 0.0, 0.0],
    [0.1, 0.1, 0.1, 0.0, 0.0],
    [0.2, 5.0, 5.0, 0.0, 0.0]
])

with torch.no_grad():
    probs, val = brain(states)
    print("Action probabilities:")
    print(probs)

"""
Scenario data model and JSON serialization.

A *scenario* is an algorithm-agnostic description of a world:
grid dimensions, obstacle positions, agent starting positions, and
goal positions.  The interpretation of goals (MAPF targets vs MRTA tasks)
depends on the algorithm type chosen later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class SceneData:
    grid_width: int = 10
    grid_height: int = 10
    obstacles: list = field(default_factory=list)       # [(x, y), ...]
    agent_starts: list = field(default_factory=list)     # [(x, y), ...]
    goals: list = field(default_factory=list)            # [(x, y), ...]

    

    def clip_to_bounds(self) -> None:
        """Remove entities that fall outside the current grid bounds."""
        w, h = self.grid_width, self.grid_height
        self.obstacles = [(x, y) for x, y in self.obstacles
                          if 0 <= x < w and 0 <= y < h]
        self.agent_starts = [(x, y) for x, y in self.agent_starts
                             if 0 <= x < w and 0 <= y < h]
        self.goals = [(x, y) for x, y in self.goals
                      if 0 <= x < w and 0 <= y < h]

    # Serialization
    def to_dict(self) -> dict:
        return {
            "grid_width": self.grid_width,
            "grid_height": self.grid_height,
            "obstacles": [list(p) for p in self.obstacles],
            "agent_starts": [list(p) for p in self.agent_starts],
            "goals": [list(p) for p in self.goals],
        }

    @classmethod
    def from_dict(cls, d: dict) -> SceneData:
        return cls(
            grid_width=d["grid_width"],
            grid_height=d["grid_height"],
            obstacles=[tuple(p) for p in d.get("obstacles", [])],
            agent_starts=[tuple(p) for p in d.get("agent_starts", [])],
            goals=[tuple(p) for p in d.get("goals", [])],
        )


def save_scenario(scene: SceneData, path: str) -> None:
    with open(path, "w") as f:
        json.dump(scene.to_dict(), f, indent=2)


def load_scenario(path: str) -> SceneData:
    with open(path) as f:
        return SceneData.from_dict(json.load(f))

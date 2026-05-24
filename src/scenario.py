"""
Scenario data model and JSON serialization.

A *scenario* is an algorithm-agnostic description of a world:
grid dimensions, obstacle positions, agent starting positions, and
goal positions.  The interpretation of goals (MAPF targets vs MRTA tasks)
depends on the algorithm type chosen later.
"""

from __future__ import annotations

import json
import os
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


_PASSABLE = frozenset([".", "G", "S"])


def load_moving_ai_map(path: str) -> SceneData:
    with open(path) as f:
        lines = f.readlines()

    width = height = 0
    map_start = 0
    for i, line in enumerate(lines):
        low = line.strip().lower()
        if low.startswith("width"):
            width = int(low.split()[1])
        elif low.startswith("height"):
            height = int(low.split()[1])
        elif low == "map":
            map_start = i + 1
            break

    obstacles: list[tuple[int, int]] = []
    for row, line in enumerate(lines[map_start:map_start + height]):
        for col, ch in enumerate(line.rstrip("\n")):
            if ch not in _PASSABLE:
                obstacles.append((col, row))

    return SceneData(
        grid_width=width,
        grid_height=height,
        obstacles=obstacles,
        agent_starts=[],
        goals=[],
    )


def load_moving_ai_scen(path: str) -> SceneData:
    agent_starts: list[tuple[int, int]] = []
    goals: list[tuple[int, int]] = []
    map_ref: str | None = None
    map_width = map_height = 0

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.lower().startswith("version"):
                continue
            parts = line.split()
            if len(parts) < 9:
                continue
            if map_ref is None:
                map_ref = parts[1]
            try:
                map_width = max(map_width, int(parts[2]))
                map_height = max(map_height, int(parts[3]))
                sx, sy = int(parts[4]), int(parts[5])
                gx, gy = int(parts[6]), int(parts[7])
            except ValueError:
                continue
            agent_starts.append((sx, sy))
            goals.append((gx, gy))

    obstacles: list[tuple[int, int]] = []
    actual_w, actual_h = map_width, map_height

    if map_ref is not None:
        scen_dir = os.path.dirname(os.path.abspath(path))
        candidates = [
            os.path.join(scen_dir, map_ref),
            os.path.join(scen_dir, os.path.basename(map_ref)),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                try:
                    map_scene = load_moving_ai_map(candidate)
                    obstacles = map_scene.obstacles
                    actual_w = map_scene.grid_width
                    actual_h = map_scene.grid_height
                except Exception:
                    pass
                break

    return SceneData(
        grid_width=actual_w,
        grid_height=actual_h,
        obstacles=obstacles,
        agent_starts=agent_starts,
        goals=goals,
    )


def load_map_file(path: str) -> SceneData:
    if path.endswith(".map"):
        return load_moving_ai_map(path)
    if path.endswith(".scen"):
        return load_moving_ai_scen(path)
    return load_scenario(path)

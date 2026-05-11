"""SceneGenerator — creates SceneData objects for batch experiments.

Supports four placement strategies:
  uniform   — agents and goals placed at uniformly random free cells
  clustered — agents clustered near centre; goals near the perimeter
  counter   — agents on the left half, goals on the right half (opposing flows)
  min_dist  — guarantees a minimum Chebyshev distance between any two starts
"""

from __future__ import annotations

import random
from collections import deque

from batch.config import BatchConfig
from scenario import SceneData, load_scenario


_MAX_RETRIES = 20   # retries for reachability failures


def _build_grid(grid_w: int, grid_h: int,
                density: float, seed: int) -> list[tuple[int, int]]:
    """Return a list of obstacle positions for a w×h grid."""
    rng = random.Random(seed)
    n_obs = int(grid_w * grid_h * max(0.0, min(0.4, density)))
    all_cells = [(x, y) for y in range(grid_h) for x in range(grid_w)]
    return rng.sample(all_cells, n_obs)


def _free_cells(grid_w: int, grid_h: int,
                obstacles: set, exclude: set) -> list[tuple[int, int]]:
    return [
        (x, y)
        for y in range(grid_h)
        for x in range(grid_w)
        if (x, y) not in obstacles and (x, y) not in exclude
    ]



def _place_uniform(grid_w: int, grid_h: int, obstacles: set,
                   n_agents: int, rng: random.Random
                   ) -> tuple[list, list] | None:
    free = _free_cells(grid_w, grid_h, obstacles, set())
    if len(free) < n_agents * 2:
        return None
    chosen = rng.sample(free, n_agents * 2)
    return chosen[:n_agents], chosen[n_agents:]


def _place_clustered(grid_w: int, grid_h: int, obstacles: set,
                     n_agents: int, rng: random.Random
                     ) -> tuple[list, list] | None:
    cx, cy = grid_w // 2, grid_h // 2
    r_inner = min(grid_w, grid_h) // 4
    r_outer = min(grid_w, grid_h) // 2

    inner = [
        (x, y)
        for y in range(grid_h)
        for x in range(grid_w)
        if (x, y) not in obstacles
        and abs(x - cx) <= r_inner and abs(y - cy) <= r_inner
    ]
    outer = [
        (x, y)
        for y in range(grid_h)
        for x in range(grid_w)
        if (x, y) not in obstacles
        and (abs(x - cx) > r_outer or abs(y - cy) > r_outer)
    ]
    if len(inner) < n_agents or len(outer) < n_agents:
        return _place_uniform(grid_w, grid_h, obstacles, n_agents, rng)

    starts = rng.sample(inner, n_agents)
    goals = rng.sample(outer, n_agents)
    return starts, goals


def _place_counter(grid_w: int, grid_h: int, obstacles: set,
                   n_agents: int, rng: random.Random
                   ) -> tuple[list, list] | None:
    left = [
        (x, y)
        for y in range(grid_h)
        for x in range(grid_w // 2)
        if (x, y) not in obstacles
    ]
    right = [
        (x, y)
        for y in range(grid_h)
        for x in range(grid_w // 2, grid_w)
        if (x, y) not in obstacles
    ]
    if len(left) < n_agents or len(right) < n_agents:
        return _place_uniform(grid_w, grid_h, obstacles, n_agents, rng)
    starts = rng.sample(left, n_agents)
    goals = rng.sample(right, n_agents)
    return starts, goals


def _place_min_dist(grid_w: int, grid_h: int, obstacles: set,
                    n_agents: int, rng: random.Random,
                    min_d: int = 3) -> tuple[list, list] | None:
    def _pick_spread(pool: list, n: int, d: int) -> list | None:
        pool = pool[:]
        rng.shuffle(pool)
        chosen = []
        for c in pool:
            if all(abs(c[0] - o[0]) >= d or abs(c[1] - o[1]) >= d
                   for o in chosen):
                chosen.append(c)
            if len(chosen) == n:
                return chosen
        return None

    free = _free_cells(grid_w, grid_h, obstacles, set())
    starts = _pick_spread(free, n_agents, min_d)
    if starts is None:
        return _place_uniform(grid_w, grid_h, obstacles, n_agents, rng)
    used = set(starts)
    remaining = [c for c in free if c not in used]
    goals = _pick_spread(remaining, n_agents, min_d)
    if goals is None:
        return _place_uniform(grid_w, grid_h, obstacles, n_agents, rng)
    return starts, goals



def _bfs_reachable(grid_w: int, grid_h: int, obstacles: set,
                   start: tuple, goal: tuple) -> bool:
    if start == goal:
        return True
    visited = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (x + dx, y + dy)
            if nb == goal:
                return True
            if (nb not in visited
                    and 0 <= nb[0] < grid_w and 0 <= nb[1] < grid_h
                    and nb not in obstacles):
                visited.add(nb)
                q.append(nb)
    return False


def _all_reachable(grid_w: int, grid_h: int, obstacles: set,
                   starts: list, goals: list) -> bool:
    for s, g in zip(starts, goals):
        if not _bfs_reachable(grid_w, grid_h, obstacles, s, g):
            return False
    return True



_PLACEMENT_FNS = {
    "uniform":   _place_uniform,
    "clustered": _place_clustered,
    "counter":   _place_counter,
    "min_dist":  _place_min_dist,
}


class SceneGenerator:
    def generate(self, config: BatchConfig,
                 n_robots: int, seed: int) -> SceneData | None:
        """Generate (or load) one scenario for *n_robots* agents.

        Returns ``None`` if generation failed after all retries.
        """
        if config.imported_maps:
            return self._from_imported(config, n_robots, seed)
        return self._generate_random(config, n_robots, seed)


    def _generate_random(self, config: BatchConfig,
                         n_robots: int, seed: int) -> SceneData | None:
        place_fn = _PLACEMENT_FNS.get(config.placement, _place_uniform)

        for attempt in range(_MAX_RETRIES):
            rng = random.Random(seed + attempt * 1000)
            obstacles_list = _build_grid(
                config.grid_w, config.grid_h,
                config.obstacle_density, seed + attempt * 1000,
            )
            obstacles = set(obstacles_list)

            result = place_fn(
                config.grid_w, config.grid_h, obstacles, n_robots, rng
            )
            if result is None:
                continue
            starts, goals = result

            if config.check_reachability:
                if not _all_reachable(
                        config.grid_w, config.grid_h, obstacles,
                        starts, goals):
                    continue

            return SceneData(
                grid_width=config.grid_w,
                grid_height=config.grid_h,
                obstacles=obstacles_list,
                agent_starts=list(starts),
                goals=list(goals),
            )
        return None


    def _from_imported(self, config: BatchConfig,
                       n_robots: int, seed: int) -> SceneData | None:
        rng = random.Random(seed)
        map_path = rng.choice(config.imported_maps)
        try:
            scene = load_scenario(map_path)
        except Exception:
            return None

        obstacles = set(map(tuple, scene.obstacles))
        n = min(n_robots, len(scene.agent_starts), len(scene.goals))
        if n < n_robots:
            return None

        place_fn = _PLACEMENT_FNS.get(config.placement, _place_uniform)
        for attempt in range(_MAX_RETRIES):
            r = place_fn(
                scene.grid_width, scene.grid_height,
                obstacles, n_robots,
                random.Random(seed + attempt * 1000),
            )
            if r is None:
                continue
            starts, goals = r
            if config.check_reachability:
                if not _all_reachable(
                        scene.grid_width, scene.grid_height, obstacles,
                        starts, goals):
                    continue
            return SceneData(
                grid_width=scene.grid_width,
                grid_height=scene.grid_height,
                obstacles=scene.obstacles,
                agent_starts=list(starts),
                goals=list(goals),
            )
        return None

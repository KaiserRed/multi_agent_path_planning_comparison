"""
Windowed Hierarchical Cooperative A* (WHCA*) for MAPF.

Reference
---------
Silver, D. "Cooperative Pathfinding." AIIDE 2005.

Extension of CA* that limits each planning episode to a sliding time
window of *W* steps.  After the window, positions are updated and agents
re-plan.  This makes the algorithm more scalable than full CA* at the
cost of completeness and optimality.
"""

from mapf.a_star import astar_time
from mapf.planner import MAPFPlanner


def whca_star(world, agents, window=16, max_timestep=1000):
    """Windowed cooperative A*."""
    if not agents:
        return {}

    goals = {a.id: (a.goal_x, a.goal_y) for a in agents}
    positions = {a.id: (a.x, a.y) for a in agents}
    max_time_ext = world.width * world.height * 2

    # Full trajectories built incrementally.
    full_paths: dict = {a.id: [((a.x, a.y), 0)] for a in agents}

    time_offset = 0

    while time_offset < max_timestep:
        if all(positions[a.id] == goals[a.id] for a in agents):
            break

        reserved: set = set()
        window_end = time_offset + window

        for agent in agents:
            start = positions[agent.id]
            goal = goals[agent.id]

            if start == goal:
                wp = [(start, t) for t in range(time_offset, window_end + 1)]
            else:
                wp = astar_time(
                    world, start, goal,
                    start_time=time_offset,
                    reserved=reserved,
                    max_time=window_end,
                )
                if wp is None:
                    wp = astar_time(
                        world, start, goal,
                        start_time=time_offset,
                        reserved=reserved,
                        max_time=time_offset + max_time_ext,
                    )
                if wp is None:
                    return None

            for idx, (pos, t) in enumerate(wp):
                reserved.add((pos[0], pos[1], t))
                # Edge reservation: prevent swap conflicts (A→B while B→A).
                if idx > 0:
                    prev_pos, _ = wp[idx - 1]
                    reserved.add((prev_pos[0], prev_pos[1], t))
            if wp:
                last_pos = wp[-1][0]
                for t in range(wp[-1][1] + 1, window_end + 2):
                    reserved.add((last_pos[0], last_pos[1], t))

            for pos, t in wp:
                if t > time_offset:
                    full_paths[agent.id].append((pos, t))

            positions[agent.id] = wp[-1][0]

        time_offset = window_end

    if not all(positions[a.id] == goals[a.id] for a in agents):
        return None

    return full_paths


class WHCAStarPlanner(MAPFPlanner):
    DISPLAY_NAME = "WHCA*"
    DESCRIPTION = (
        "Windowed Hierarchical Cooperative A*. Plans in a sliding "
        "time window — more scalable than full CA* at the cost of "
        "optimality. Online-capable, centralized."
    )
    IS_CENTRALIZED = True
    IS_ONLINE = True

    def __init__(self, window: int = 16):
        self._window = window

    def plan(self, world, agents):
        return whca_star(world, agents, window=self._window)

"""
Cooperative A* (CA*) / MAPP for Multi-Agent Path Finding.

Reference
---------
Silver, D. "Cooperative Pathfinding." AIIDE 2005.

Agents plan sequentially using time-expanded A*.  Each agent's committed
path is added to a shared reservation table before the next agent plans,
so collisions are prevented by construction.  The result depends on the
planning order (here: agent-id order).
"""

from mapf.a_star import astar_time
from mapf.planner import MAPFPlanner


def cooperative_astar(world, agents, max_time=None):
    """Plan paths one agent at a time, reserving committed trajectories."""
    if not agents:
        return {}

    if max_time is None:
        max_time = world.width * world.height * 2

    reserved: set = set()
    paths: dict = {}

    for agent in agents:
        start = (agent.x, agent.y)
        goal = (agent.goal_x, agent.goal_y)

        path = astar_time(world, start, goal, start_time=0,
                          reserved=reserved, max_time=max_time)
        if path is None:
            return None

        paths[agent.id] = path

        for idx, (pos, t) in enumerate(path):
            reserved.add((pos[0], pos[1], t))
            # Edge reservation: prevent swap conflicts (A→B while B→A).
            if idx > 0:
                prev_pos, _ = path[idx - 1]
                reserved.add((prev_pos[0], prev_pos[1], t))

        # Agent waits at goal indefinitely — reserve that cell.
        if path:
            gx, gy = path[-1][0]
            for t in range(len(path), max_time + 1):
                reserved.add((gx, gy, t))

    return paths


class CAStarPlanner(MAPFPlanner):
    DISPLAY_NAME = "CA*"
    DESCRIPTION = (
        "Cooperative A* (MAPP). Agents plan sequentially — each one "
        "routes around already-committed paths of higher-priority agents. "
        "Fast and simple but planning-order dependent and incomplete."
    )
    IS_CENTRALIZED = True
    IS_ONLINE = False

    def plan(self, world, agents):
        return cooperative_astar(world, agents)

from queue import PriorityQueue

from mapf.a_star import astar_time
from mapf.sipp import sipp as sipp_planner
from mapf.planner import MAPFPlanner


class Conflict:
    def __init__(self, agent1, agent2, time, position):
        self.agent1   = agent1
        self.agent2   = agent2
        self.time     = time
        self.position = position


class CTNode:
    def __init__(self, paths):
        self.paths = paths
        self.cost  = sum(len(p) for p in paths.values() if p)

    def __lt__(self, other):
        return self.cost < other.cost


def _pos_at(path: list, t: int):
    """Position of an agent at time *t*.

    After the path ends the agent waits at its goal, so return
    the last recorded position for any t >= len(path).
    """
    if not path:
        return None
    return path[t][0] if t < len(path) else path[-1][0]


def _detect_first_conflict(paths):
    """
    Detect the first vertex *or* edge (swap) conflict.

    Agents that have finished their paths are treated as permanently
    occupying their goal cell, so a moving agent cannot pass through them.
    """
    if not paths:
        return None

    agent_ids = list(paths.keys())
    max_time  = max(len(p) for p in paths.values() if p)

    for t in range(max_time):
        # Vertex conflicts
        positions: dict = {}
        for aid, path in paths.items():
            if not path:
                continue
            pos = _pos_at(path, t)
            if pos in positions:
                return Conflict(positions[pos], aid, t, pos)
            positions[pos] = aid

        # Swap (edge) conflicts
        if t > 0:
            for i in range(len(agent_ids)):
                for j in range(i + 1, len(agent_ids)):
                    id1, id2 = agent_ids[i], agent_ids[j]
                    p1, p2   = paths[id1], paths[id2]
                    if not p1 or not p2:
                        continue
                    if (_pos_at(p1, t)     == _pos_at(p2, t - 1) and
                            _pos_at(p2, t) == _pos_at(p1, t - 1)):
                        return Conflict(id1, id2, t, _pos_at(p1, t))

    return None


def cbs(world, agents, low_level="astar"):
    """
    Conflict-Based Search (CBS).

    Offline, centralized MAPF algorithm.  Guarantees optimal solution
    for both vertex and swap conflicts.

    Parameters
    ----------
    low_level : {"astar", "sipp"}
        Low-level single-agent planner to use for replanning.
    """
    if low_level == "sipp":
        def _plan_single(w, start, goal, res, mt):
            return sipp_planner(w, start, goal, res, mt)
    else:
        def _plan_single(w, start, goal, res, mt):
            return astar_time(w, start, goal, 0, res, max_time=mt)

    paths: dict = {}
    for agent in agents:
        path = _plan_single(world, (agent.x, agent.y),
                            (agent.goal_x, agent.goal_y), set(), None)
        if path is None:
            return None
        paths[agent.id] = path

    initial_max = max((len(p) for p in paths.values() if p), default=1)
    max_t = max(initial_max * (len(agents) + 2),
                world.width + world.height + 10)

    root     = CTNode(paths)
    open_set: PriorityQueue = PriorityQueue()
    open_set.put(root)

    while not open_set.empty():
        node     = open_set.get()
        conflict = _detect_first_conflict(node.paths)

        if conflict is None:
            return node.paths

        for agent_id in [conflict.agent1, conflict.agent2]:
            new_node = CTNode(dict(node.paths))

            reserved: set = set()
            for other_id, path in node.paths.items():
                if other_id == agent_id:
                    continue
                for idx, (pos, t) in enumerate(path):
                    reserved.add((pos[0], pos[1], t))
                    if idx > 0:
                        prev_pos, _ = path[idx - 1]
                        reserved.add((prev_pos[0], prev_pos[1], t))

                if path:
                    gx, gy = path[-1][0]
                    for extra_t in range(len(path), max_t + 1):
                        reserved.add((gx, gy, extra_t))

            agent    = next(a for a in agents if a.id == agent_id)
            new_path = _plan_single(
                world,
                (agent.x, agent.y),
                (agent.goal_x, agent.goal_y),
                reserved,
                max_t,
            )

            if new_path:
                new_node.paths[agent_id] = new_path
                open_set.put(new_node)

    return None


class CBSPlanner(MAPFPlanner):
    DISPLAY_NAME = "CBS (A*)"
    DESCRIPTION = (
        "Conflict-Based Search with time-expanded A* low-level planner. "
        "Optimal, centralized, offline MAPF algorithm that resolves "
        "conflicts via a constraint tree."
    )
    IS_CENTRALIZED = True
    IS_ONLINE      = False

    def plan(self, world, agents):
        return cbs(world, agents, low_level="astar")


class CBSSIPPPlanner(MAPFPlanner):
    DISPLAY_NAME = "CBS (SIPP)"
    DESCRIPTION = (
        "Conflict-Based Search with SIPP low-level planner. Same optimality "
        "guarantees as CBS (A*) but replanning is faster because SIPP works "
        "on safe intervals rather than full time expansion."
    )
    IS_CENTRALIZED = True
    IS_ONLINE      = False

    def plan(self, world, agents):
        return cbs(world, agents, low_level="sipp")

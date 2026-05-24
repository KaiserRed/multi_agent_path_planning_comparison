from queue import PriorityQueue

from mapf.a_star import astar_time
from mapf.sipp import sipp as sipp_planner
from mapf.planner import MAPFPlanner


class Conflict:
    def __init__(self, agent1, agent2, time, position,
                 kind="vertex", prev1=None, prev2=None):
        self.agent1   = agent1
        self.agent2   = agent2
        self.time     = time
        self.position = position
        self.kind     = kind    # "vertex" | "swap"
        self.prev1    = prev1   # agent1 position at time-1 (swap only)
        self.prev2    = prev2   # agent2 position at time-1 (swap only)


class CTNode:
    def __init__(self, paths, constraints=None):
        self.paths = paths
        self.cost  = sum(len(p) for p in paths.values() if p)
        self.constraints = constraints if constraints is not None else {}

    def __lt__(self, other):
        return self.cost < other.cost


def _pos_at(path: list, t: int):
    """Position of an agent at time *t*.

    Works for both time-expanded A* paths (every timestep stored, index==time)
    and SIPP compressed paths (arrival times may skip waiting steps).
    The agent waits at its last recorded position after the path ends.
    """
    if not path:
        return None
    if t >= path[-1][1]:
        return path[-1][0]
    pos = path[0][0]
    for p, arr in path:
        if arr > t:
            break
        pos = p
    return pos


def _detect_first_conflict(paths):
    """
    Detect the first vertex or edge (swap) conflict.

    Returns a :class:`Conflict` with ``kind="vertex"`` or ``kind="swap"``.
    Swap conflicts carry ``prev1`` / ``prev2`` for building edge constraints.
    """
    if not paths:
        return None

    agent_ids = list(paths.keys())
    max_time  = max(p[-1][1] if p else 0 for p in paths.values())

    for t in range(max_time + 1):
        # Vertex conflicts
        positions: dict = {}
        for aid, path in paths.items():
            if not path:
                continue
            pos = _pos_at(path, t)
            if pos in positions:
                return Conflict(positions[pos], aid, t, pos, kind="vertex")
            positions[pos] = aid

        # Swap (edge) conflicts
        if t > 0:
            for i in range(len(agent_ids)):
                for j in range(i + 1, len(agent_ids)):
                    id1, id2 = agent_ids[i], agent_ids[j]
                    p1, p2   = paths[id1], paths[id2]
                    if not p1 or not p2:
                        continue
                    pos1_t    = _pos_at(p1, t)
                    pos2_t    = _pos_at(p2, t)
                    pos1_prev = _pos_at(p1, t - 1)
                    pos2_prev = _pos_at(p2, t - 1)
                    if pos1_t == pos2_prev and pos2_t == pos1_prev:
                        return Conflict(
                            id1, id2, t, pos1_t,
                            kind="swap",
                            prev1=pos1_prev,
                            prev2=pos2_prev,
                        )

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
        def _plan_single(w, start, goal, res, mt,
                         edge_res=None, perm=None):
            return sipp_planner(w, start, goal, res, mt, permanent_after=perm)
    else:
        def _plan_single(w, start, goal, res, mt,
                         edge_res=None, perm=None):
            return astar_time(w, start, goal, 0, res,
                              max_time=mt,
                              edge_reserved=edge_res if edge_res else None,
                              permanent_after=perm if perm else None)

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
            new_constraints = {
                aid: {'vertex': set(c['vertex']), 'edge': set(c['edge'])}
                for aid, c in node.constraints.items()
            }
            agent_cons = new_constraints.setdefault(
                agent_id, {'vertex': set(), 'edge': set()}
            )
            if conflict.kind == "swap":
                if agent_id == conflict.agent1:
                    if low_level == "astar":
                        agent_cons['edge'].add(
                            (conflict.prev1, conflict.position, conflict.time)
                        )
                    else:
                        agent_cons['vertex'].add(
                            (conflict.position[0], conflict.position[1], conflict.time)
                        )
                else:
                    if low_level == "astar":
                        agent_cons['edge'].add(
                            (conflict.prev2, conflict.prev1, conflict.time)
                        )
                    else:
                        agent_cons['vertex'].add(
                            (conflict.prev1[0], conflict.prev1[1], conflict.time)
                        )
            else:  # vertex conflict
                agent_cons['vertex'].add(
                    (conflict.position[0], conflict.position[1], conflict.time)
                )

            # Build reservation sets from other agents' paths
            reserved: set = set()
            permanent_after: dict = {}

            for other_id, path in node.paths.items():
                if other_id == agent_id:
                    continue
                for pos, t in path:
                    reserved.add((pos[0], pos[1], t))
                if path:
                    gx, gy = path[-1][0]
                    st = len(path)
                    curr = permanent_after.get((gx, gy))
                    if curr is None or st < curr:
                        permanent_after[(gx, gy)] = st

            # Apply every accumulated constraint for this agent
            reserved.update(agent_cons['vertex'])
            edge_reserved = set(agent_cons['edge'])

            agent    = next(a for a in agents if a.id == agent_id)
            start    = (agent.x, agent.y)
            goal     = (agent.goal_x, agent.goal_y)

            # Dynamic max_t: retry with doubling horizon on failure
            new_path = None
            for mult in (1, 2, 4, 8):
                new_path = _plan_single(
                    world, start, goal,
                    reserved, max_t * mult,
                    edge_res=edge_reserved if edge_reserved else None,
                    perm=permanent_after if permanent_after else None,
                )
                if new_path is not None:
                    break

            if new_path:
                new_node = CTNode(
                    {k: list(v) for k, v in node.paths.items()},
                    constraints=new_constraints,
                )
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

"""
Explicit Estimation CBS (EECBS) for MAPF.

Reference
---------
Li J., Ruml W., Koenig S.
"EECBS: A Bounded-Suboptimal Search for Multi-Agent Path Finding."
AAAI 2021.

EECBS extends ECBS with *online learning* of an inadmissible cost
estimator.  Instead of selecting the focal node with the fewest raw
conflicts (as ECBS does), EECBS maintains an estimate of the cost
increase per conflict resolution and picks the node with the lowest
*estimated total cost*.  This focuses the search more effectively and
typically expands far fewer CT nodes than ECBS.
"""

from __future__ import annotations

from heapq import heappush, heappop

from mapf.a_star import astar_time, heuristic as manhattan
from mapf.planner import MAPFPlanner


# Low-level: focal A*
def _focal_astar(world, start, goal, reserved, other_paths, w,
                 start_time=0, max_time=None):
    """Bounded-suboptimal A* with focal search (conflict-aware)."""
    if max_time is None:
        max_time = start_time + world.width * world.height * 2

    if not world.is_free(goal[0], goal[1]):
        return None

    other_occ: set = set()
    path_end = max((len(p) for p in other_paths.values() if p), default=0) + 20
    for path in other_paths.values():
        if path:
            for pos, t in path:
                other_occ.add((pos[0], pos[1], t))
            last = path[-1][0]
            for t2 in range(len(path), min(path_end, max_time + 1)):
                other_occ.add((last[0], last[1], t2))

    def h(pos):
        return manhattan(pos, goal)

    g_score: dict = {}
    conf: dict = {}
    came_from: dict = {}
    closed: set = set()

    init = (start, start_time)
    g_score[init] = 0
    conf[init] = 0

    counter = 0
    f_heap: list = []
    heappush(f_heap, (h(start), counter, init))
    open_states: set = {init}

    while open_states:
        while f_heap and f_heap[0][2] not in open_states:
            heappop(f_heap)
        if not f_heap:
            break

        f_min = f_heap[0][0]
        threshold = w * f_min

        best = None
        best_conf = float("inf")
        best_f = float("inf")

        for state in open_states:
            f_val = g_score[state] + h(state[0])
            if f_val <= threshold + 1e-9:
                c = conf[state]
                if c < best_conf or (c == best_conf and f_val < best_f):
                    best_conf = c
                    best_f = f_val
                    best = state

        if best is None:
            break

        state = best
        open_states.discard(state)
        closed.add(state)

        pos, t = state
        if pos == goal:
            path: list = []
            s = state
            while s in came_from:
                path.append(s)
                s = came_from[s]
            path.append(init)
            path.reverse()
            return path

        x, y = pos
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            nt = t + 1
            if nt > max_time:
                continue
            if not world.is_free(nx, ny):
                continue
            if (nx, ny, nt) in reserved:
                continue

            nstate = ((nx, ny), nt)
            if nstate in closed:
                continue

            new_g = g_score[state] + 1
            if new_g < g_score.get(nstate, float("inf")):
                g_score[nstate] = new_g
                came_from[nstate] = state
                conf[nstate] = conf[state] + (
                    1 if (nx, ny, nt) in other_occ else 0
                )
                counter += 1
                heappush(f_heap, (new_g + h((nx, ny)), counter, nstate))
                open_states.add(nstate)

    return None


# Conflict helpers
def _pos_at(path, t):
    if not path:
        return None
    return path[t][0] if t < len(path) else path[-1][0]


def _detect_first_conflict(paths):
    if not paths:
        return None
    ids = list(paths.keys())
    max_t = max((len(p) for p in paths.values() if p), default=0)
    for t in range(max_t):
        positions: dict = {}
        for aid in ids:
            p = paths.get(aid)
            if not p:
                continue
            pos = _pos_at(p, t)
            if pos in positions:
                return (positions[pos], aid, t, pos)
            positions[pos] = aid
        if t > 0:
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    p1, p2 = paths[ids[i]], paths[ids[j]]
                    if not p1 or not p2:
                        continue
                    if (_pos_at(p1, t) == _pos_at(p2, t - 1) and
                            _pos_at(p2, t) == _pos_at(p1, t - 1)):
                        return (ids[i], ids[j], t, _pos_at(p1, t))
    return None


def _count_conflicts(paths):
    if not paths:
        return 0
    ids = list(paths.keys())
    max_t = max((len(p) for p in paths.values() if p), default=0)
    count = 0
    for t in range(max_t):
        positions: dict = {}
        for aid in ids:
            p = paths.get(aid)
            if not p:
                continue
            pos = _pos_at(p, t)
            if pos in positions:
                count += 1
            else:
                positions[pos] = aid
        if t > 0:
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    p1, p2 = paths[ids[i]], paths[ids[j]]
                    if not p1 or not p2:
                        continue
                    if (_pos_at(p1, t) == _pos_at(p2, t - 1) and
                            _pos_at(p2, t) == _pos_at(p1, t - 1)):
                        count += 1
    return count


# High-level EECBS
class _CTNode:
    __slots__ = ("paths", "cost", "conflicts")

    def __init__(self, paths):
        self.paths = paths
        self.cost = sum(len(p) for p in paths.values() if p)
        self.conflicts = _count_conflicts(paths)


def eecbs(world, agents, w=1.5):
    """
    EECBS with explicit cost estimation.

    Three-list node selection:
      * **OPEN** — all open CT nodes, ordered by admissible cost.
      * **FOCAL** — nodes with cost ≤ ``w * cost_min``, ordered by
        estimated true cost ``ĉ = cost + α · conflicts``.
      * **CLEANUP** — fallback ordered by ``ĉ``, guaranteeing convergence.

    The scaling factor ``α`` (cost per conflict) is updated on-line after
    every CT expansion.
    """
    if not agents:
        return {}

    init_paths: dict = {}
    for agent in agents:
        path = astar_time(world, (agent.x, agent.y),
                          (agent.goal_x, agent.goal_y))
        if path is None:
            return None
        init_paths[agent.id] = path

    initial_max = max((len(p) for p in init_paths.values()), default=1)
    max_t = max(initial_max * (len(agents) + 2),
                world.width + world.height + 10)

    root = _CTNode(init_paths)
    open_nodes: list[_CTNode] = [root]

    alpha = 1.0          # learned cost-per-conflict
    iterations = 0
    max_iter = 50_000

    def _estimate(n: _CTNode) -> float:
        return n.cost + alpha * n.conflicts

    while open_nodes and iterations < max_iter:
        iterations += 1

        cost_min = min(n.cost for n in open_nodes)
        focal_bound = w * cost_min

        focal = [n for n in open_nodes if n.cost <= focal_bound + 1e-9]

        if focal:
            node = min(focal, key=_estimate)
        else:
            node = min(open_nodes, key=_estimate)

        open_nodes.remove(node)

        conflict = _detect_first_conflict(node.paths)
        if conflict is None:
            return node.paths

        agent1, agent2, _ct, _cpos = conflict

        for agent_id in [agent1, agent2]:
            reserved: set = set()
            other_paths: dict = {}

            for other_id, path in node.paths.items():
                if other_id == agent_id:
                    continue
                other_paths[other_id] = path
                for idx, (pos, t) in enumerate(path):
                    reserved.add((pos[0], pos[1], t))
                    if idx > 0:
                        prev_pos = path[idx - 1][0]
                        reserved.add((prev_pos[0], prev_pos[1], t))
                if path:
                    gx, gy = path[-1][0]
                    for extra_t in range(len(path), max_t + 1):
                        reserved.add((gx, gy, extra_t))

            agent = next(a for a in agents if a.id == agent_id)
            new_path = _focal_astar(
                world,
                (agent.x, agent.y),
                (agent.goal_x, agent.goal_y),
                reserved, other_paths, w,
                max_time=max_t,
            )

            if new_path:
                new_paths = dict(node.paths)
                new_paths[agent_id] = new_path
                child = _CTNode(new_paths)
                open_nodes.append(child)

                resolved = node.conflicts - child.conflicts
                if resolved > 0:
                    sample = (child.cost - node.cost) / resolved
                    alpha = 0.8 * alpha + 0.2 * max(0.0, sample)

    return None


class EECBSPlanner(MAPFPlanner):
    DISPLAY_NAME = "EECBS"
    DESCRIPTION = (
        "Explicit Estimation CBS. Extends ECBS with on-line learning "
        "of an inadmissible cost estimator — focuses the search more "
        "effectively and typically expands fewer CT nodes."
    )
    IS_CENTRALIZED = True
    IS_ONLINE = False

    def __init__(self, w: float = 1.5):
        self._w = w

    def plan(self, world, agents):
        return eecbs(world, agents, w=self._w)

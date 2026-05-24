"""
Enhanced Conflict-Based Search (ECBS) for MAPF.

Reference
---------
Barer M., Sharon G., Stern R., Felner A.
"Suboptimal Variants of the Conflict-Based Search Algorithm for the
Multi-Agent Pathfinding Problem."  SoCS 2014.

ECBS is a bounded-suboptimal variant of CBS.  At both levels of the
search (constraint tree and low-level pathfinding) a *focal search* is
used: among all nodes whose lower-bound cost is within ``w * LB_min``,
the one with the fewest conflicts is expanded first.  This trades
optimality for a large speed-up while maintaining a ``w``-suboptimality
guarantee.
"""

from __future__ import annotations

from heapq import heappush, heappop

from mapf.a_star import astar_time
from mapf.focal_a_star import focal_astar
from mapf.planner import MAPFPlanner


# Conflict detection

class _Conflict:
    __slots__ = ("agent1", "agent2", "time", "pos", "kind", "prev1", "prev2")

    def __init__(self, agent1, agent2, t, pos, kind="vertex", prev1=None, prev2=None):
        self.agent1 = agent1
        self.agent2 = agent2
        self.time = t
        self.pos = pos
        self.kind = kind    # "vertex" | "swap"
        self.prev1 = prev1  # position of agent1 at t-1 (swap only)
        self.prev2 = prev2  # position of agent2 at t-1 (swap only)


def _pos_at(path, t):
    if not path:
        return None
    return path[t][0] if t < len(path) else path[-1][0]


def _detect_first_conflict(paths):
    """Return first vertex or swap conflict, or None."""
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
                return _Conflict(positions[pos], aid, t, pos, kind="vertex")
            positions[pos] = aid
        if t > 0:
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    p1, p2 = paths[ids[i]], paths[ids[j]]
                    if not p1 or not p2:
                        continue
                    pos1_t = _pos_at(p1, t)
                    pos2_t = _pos_at(p2, t)
                    pos1_prev = _pos_at(p1, t - 1)
                    pos2_prev = _pos_at(p2, t - 1)
                    if pos1_t == pos2_prev and pos2_t == pos1_prev:
                        return _Conflict(
                            ids[i], ids[j], t, pos1_t,
                            kind="swap",
                            prev1=pos1_prev,
                            prev2=pos2_prev,
                        )
    return None


def _count_conflicts_with(paths, agent_id):
    """Count conflicts where *agent_id* is one of the two parties."""
    if not paths or agent_id not in paths:
        return 0
    target = paths[agent_id]
    if not target:
        return 0
    count = 0
    max_t = max((len(p) for p in paths.values() if p), default=0)
    for other_id, other in paths.items():
        if other_id == agent_id or not other:
            continue
        for t in range(max_t):
            tp = _pos_at(target, t)
            op = _pos_at(other, t)
            if tp == op:
                count += 1
            if t > 0:
                tp_prev = _pos_at(target, t - 1)
                op_prev = _pos_at(other, t - 1)
                if tp == op_prev and op == tp_prev:
                    count += 1
    return count


def _count_conflicts(paths):
    """Full O(T·N²) conflict count — used only for the root node."""
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


class _CTNode:
    """
    Constraint-tree node.

    Attributes
    ----------
    paths : dict[agent_id → path]
    cost : int
        Sum of path lengths (actual cost).
    per_agent_lb : dict[agent_id → int]
        Per-agent lower bounds (path length from unconstrained optimal).
    lb : int
        Sum of per-agent lower bounds.  Used as the focal threshold key
        (``w * lb_min``) to maintain the w-suboptimality guarantee.
    conflicts : int
        Number of pairwise conflicts — focal tie-breaker.
    constraints : dict[agent_id → {'vertex': set, 'edge': set}]
        All constraints accumulated from root to this node.
    """
    __slots__ = ("paths", "cost", "per_agent_lb", "lb", "conflicts", "constraints")

    def __init__(self, paths, per_agent_lb=None, conflicts=None, constraints=None):
        self.paths = paths
        self.cost = sum(len(p) for p in paths.values() if p)
        if per_agent_lb is None:
            # Root node: unconstrained paths are optimal → lb = cost
            self.per_agent_lb = {aid: len(p) for aid, p in paths.items() if p}
            self.lb = self.cost
        else:
            self.per_agent_lb = per_agent_lb
            self.lb = sum(per_agent_lb.values())
        self.conflicts = _count_conflicts(paths) if conflicts is None else conflicts
        self.constraints = constraints if constraints is not None else {}


# High-level ECBS

def ecbs(world, agents, w=1.3):
    """Enhanced CBS with suboptimality bound *w*."""
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

    # Two-heap open/focal with lazy deletion
    ctr = 0
    open_heap: list = []   # (lb, ctr, node)
    focal_heap: list = []  # (conflicts, cost, ctr, node)
    expanded: set = set()  # counters of expanded nodes

    heappush(open_heap, (root.lb, ctr, root))
    heappush(focal_heap, (root.conflicts, root.cost, ctr, root))
    last_lb_min = root.lb
    ctr = 1

    iterations = 0
    max_iter = 50_000

    while open_heap and iterations < max_iter:
        iterations += 1

        # Current lb_min
        while open_heap and open_heap[0][1] in expanded:
            heappop(open_heap)
        if not open_heap:
            break
        lb_min = open_heap[0][0]
        focal_bound = w * lb_min

        # When lb_min increased, scan open_heap for newly eligible nodes
        if lb_min > last_lb_min + 1e-9:
            for lb_val, nc, n in open_heap:
                if nc not in expanded and n.lb <= focal_bound + 1e-9:
                    heappush(focal_heap, (n.conflicts, n.cost, nc, n))
            last_lb_min = lb_min

        # Pop best from focal_heap (lazy-delete expanded)
        node = None
        node_ctr = -1
        while focal_heap:
            _c, _cost, nc, n = focal_heap[0]
            heappop(focal_heap)
            if nc in expanded:
                continue
            node = n
            node_ctr = nc
            break

        if node is None:
            break
        expanded.add(node_ctr)

        conflict = _detect_first_conflict(node.paths)
        if conflict is None:
            return node.paths

        for agent_id in [conflict.agent1, conflict.agent2]:
            # --- Accumulate constraints (deep-copy parent + add new) ----------
            new_constraints = {
                aid: {'vertex': set(c['vertex']), 'edge': set(c['edge'])}
                for aid, c in node.constraints.items()
            }
            agent_cons = new_constraints.setdefault(
                agent_id, {'vertex': set(), 'edge': set()}
            )
            if conflict.kind == "swap":
                if agent_id == conflict.agent1:
                    agent_cons['edge'].add((conflict.prev1, conflict.pos, conflict.time))
                else:
                    agent_cons['edge'].add((conflict.prev2, conflict.prev1, conflict.time))
            else:  # vertex conflict
                agent_cons['vertex'].add(
                    (conflict.pos[0], conflict.pos[1], conflict.time)
                )

            reserved: set = set()
            permanent_after: dict = {}
            other_paths: dict = {}

            for other_id, path in node.paths.items():
                if other_id == agent_id:
                    continue
                other_paths[other_id] = path
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

            agent = next(a for a in agents if a.id == agent_id)
            start = (agent.x, agent.y)
            goal = (agent.goal_x, agent.goal_y)

            # Dynamic max_t: retry with doubling horizon if A* fails
            new_path = None
            for mult in (1, 2, 4, 8):
                new_path = focal_astar(
                    world, start, goal,
                    reserved, other_paths, w,
                    edge_reserved=edge_reserved if edge_reserved else None,
                    permanent_after=permanent_after if permanent_after else None,
                    max_time=max_t * mult,
                )
                if new_path is not None:
                    break

            if new_path:
                new_paths = {k: list(v) for k, v in node.paths.items()}
                new_paths[agent_id] = new_path

                # Incremental LB: only update the replanned agent
                new_per_agent_lb = dict(node.per_agent_lb)
                old_lb_i = node.per_agent_lb.get(agent_id, 0)
                new_per_agent_lb[agent_id] = max(old_lb_i, len(new_path))

                # Incremental conflicts: recount only for replanned agent
                old_conf_i = _count_conflicts_with(node.paths, agent_id)
                new_conf_i = _count_conflicts_with(new_paths, agent_id)
                new_conflicts = node.conflicts - old_conf_i + new_conf_i

                child = _CTNode(new_paths,
                                per_agent_lb=new_per_agent_lb,
                                conflicts=new_conflicts,
                                constraints=new_constraints)
                child_ctr = ctr
                ctr += 1
                heappush(open_heap, (child.lb, child_ctr, child))
                if child.lb <= focal_bound + 1e-9:
                    heappush(focal_heap, (child.conflicts, child.cost, child_ctr, child))

    return None


class ECBSPlanner(MAPFPlanner):
    DISPLAY_NAME = "ECBS"
    DESCRIPTION = (
        "Enhanced CBS. Bounded-suboptimal variant of CBS that uses "
        "focal search at both levels — much faster than optimal CBS "
        "with a tunable quality bound (w ≈ 1.3)."
    )
    IS_CENTRALIZED = True
    IS_ONLINE = False

    def __init__(self, w: float = 1.3):
        self._w = w

    def plan(self, world, agents):
        return ecbs(world, agents, w=self._w)

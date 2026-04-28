"""
Bounded-suboptimal A* using focal search.

Among all reachable paths with cost ≤ ``w * f_min``, returns the one
whose trajectory has the fewest *soft* conflicts with the current paths
of other agents (given by *other_paths*).

Implementation uses two heaps — OPEN sorted by f-value and FOCAL sorted
by conflict count — with lazy deletion, giving O(log N) amortised
expansion time instead of the naïve O(N) scan.
"""
from __future__ import annotations

from heapq import heappush, heappop

from mapf.a_star import heuristic as manhattan


def focal_astar(
    world,
    start,
    goal,
    reserved,
    other_paths,
    w,
    start_time: int = 0,
    max_time: int | None = None,
    edge_reserved: set | None = None,
    permanent_after: dict | None = None,
):
    """
    Time-expanded focal A*.

    Parameters
    ----------
    reserved : set
        Hard vertex constraints ``(x, y, t)``.
    other_paths : dict
        Other agents' paths used for *soft* conflict counting.
    w : float
        Suboptimality bound — nodes with ``f ≤ w * f_min`` are eligible.
    edge_reserved : set | None
        Hard edge constraints ``((x, y), (nx, ny), t)`` — agent cannot
        traverse that directed edge arriving at time ``t``.
    permanent_after : dict | None
        ``(x, y) → t_start``: cell permanently occupied from ``t_start``
        onward.  Replaces the O(max_t) goal-extension reservation loop.
    """
    if max_time is None:
        max_time = start_time + world.width * world.height * 2

    if not world.is_free(goal[0], goal[1]):
        return None

    last_goal_reserved: int = max(
        (t for (x, y, t) in reserved if (x, y) == goal),
        default=-1,
    )

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

    f_init = h(start)
    ctr = 0

    f_heap: list = []   # OPEN:  (f, ctr, state)
    c_heap: list = []   # FOCAL: (conf, f, ctr, state)
    open_states: dict = {init: 0}   # state → original insertion ctr
    in_focal: set = {init}

    heappush(f_heap, (f_init, ctr, init))
    heappush(c_heap, (0, f_init, ctr, init))
    last_f_min = f_init
    ctr = 1

    while open_states:
        # Compute current f_min from OPEN (lazy-delete expanded states)
        while f_heap and f_heap[0][2] not in open_states:
            heappop(f_heap)
        if not f_heap:
            break

        f_min = f_heap[0][0]
        threshold = w * f_min

        # When f_min increases, scan OPEN for newly eligible states.
        # Sort by original insertion counter to get deterministic FIFO order.
        if f_min > last_f_min + 1e-9:
            for s, orig_ctr in sorted(open_states.items(), key=lambda x: x[1]):
                if s not in in_focal:
                    fv = g_score[s] + h(s[0])
                    if fv <= threshold + 1e-9:
                        heappush(c_heap, (conf[s], fv, orig_ctr, s))
                        in_focal.add(s)
            last_f_min = f_min

        # Pop best node from FOCAL heap (lazy-delete stale entries)
        state = None
        while c_heap:
            _conf, _f, _ctr, s = c_heap[0]
            heappop(c_heap)
            if s not in open_states:
                in_focal.discard(s)
                continue
            state = s
            in_focal.discard(state)
            break

        if state is None:
            # Fallback: linear scan when FOCAL is exhausted (rare)
            best, best_c, best_f_val = None, float("inf"), float("inf")
            for s in open_states:
                fv = g_score[s] + h(s[0])
                if fv <= threshold + 1e-9:
                    c = conf[s]
                    if c < best_c or (c == best_c and fv < best_f_val):
                        best_c, best_f_val, best = c, fv, s
            if best is None:
                break
            state = best

        open_states.pop(state, None)
        closed.add(state)

        pos, t = state
        if pos == goal and t > last_goal_reserved:
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
            # Same early-goal guard as astar_time: don't approach goal before
            # it can be permanently occupied.
            if (nx, ny) == goal and nt <= last_goal_reserved:
                continue
            if (nx, ny, nt) in reserved:
                continue
            if edge_reserved and ((x, y), (nx, ny), nt) in edge_reserved:
                continue
            if permanent_after and (nx, ny) in permanent_after and nt >= permanent_after[(nx, ny)]:
                continue

            nstate = ((nx, ny), nt)
            if nstate in closed:
                continue

            new_g = g_score[state] + 1
            if new_g < g_score.get(nstate, float("inf")):
                g_score[nstate] = new_g
                came_from[nstate] = state
                new_conf = conf[state] + (1 if (nx, ny, nt) in other_occ else 0)
                conf[nstate] = new_conf
                new_f = new_g + h((nx, ny))
                heappush(f_heap, (new_f, ctr, nstate))
                if nstate not in open_states:
                    open_states[nstate] = ctr
                if new_f <= threshold + 1e-9:
                    heappush(c_heap, (new_conf, new_f, ctr, nstate))
                    in_focal.add(nstate)
                ctr += 1

    return None

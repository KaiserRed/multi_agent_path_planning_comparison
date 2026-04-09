"""
Safe Interval Path Planning (SIPP).

Reference
---------
Phillips, M. & Likhachev, M. "SIPP: Safe Interval Path Planning for Dynamic
Environments." ICRA 2011.

Instead of expanding every (position, time) state like time-expanded A*,
SIPP groups consecutive free timesteps at each cell into *safe intervals*
[t_start, t_end] and searches over (position, safe_interval) states.  This
keeps the state space proportional to the number of reservations rather than
to max_time, which makes it significantly faster when reservation density is low.

A safe interval for cell C is a maximal range [a, b] such that C is NOT
reserved at any timestep t in [a, b].  An agent may arrive at C at any time
within the interval and wait there until the end of the interval before moving.

Interface
---------
``sipp(world, start, goal, reserved, max_time)`` mirrors ``astar_time`` so
it can be used as a drop-in replacement inside CBS.
"""

from __future__ import annotations

import heapq
from collections import defaultdict


def _build_intervals(
    reserved: set,
    max_time: int,
) -> dict[tuple[int, int], list[tuple[int, int]]]:
    """Build safe-interval lists for every cell that appears in *reserved*.

    Returns a dict mapping ``(x, y)`` → sorted list of ``(start, end)``
    non-reserved intervals within ``[0, max_time]``.

    Cells that never appear in *reserved* implicitly have a single interval
    ``(0, max_time)`` — handled lazily in ``_intervals_for``.
    """
    # Collect every blocked timestep per cell
    blocked: dict[tuple[int, int], set[int]] = defaultdict(set)
    for x, y, t in reserved:
        if 0 <= t <= max_time:
            blocked[(x, y)].add(t)

    intervals: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for cell, times in blocked.items():
        ivs: list[tuple[int, int]] = []
        start: int | None = None
        for t in range(0, max_time + 1):
            if t not in times:
                if start is None:
                    start = t
            else:
                if start is not None:
                    ivs.append((start, t - 1))
                    start = None
        if start is not None:
            ivs.append((start, max_time))
        intervals[cell] = ivs

    return intervals


def _intervals_for(
    cell: tuple[int, int],
    precomputed: dict,
    max_time: int,
) -> list[tuple[int, int]]:
    """Return safe intervals for *cell*, falling back to [(0, max_time)]."""
    return precomputed.get(cell, [(0, max_time)])


def _interval_index(intervals: list[tuple[int, int]], t: int) -> int:
    """Return index of the safe interval containing time *t*, or -1."""
    for i, (a, b) in enumerate(intervals):
        if a <= t <= b:
            return i
    return -1


def sipp(world, start, goal, reserved: set | None = None, max_time: int | None = None):
    """SIPP path planner — drop-in replacement for ``astar_time``.

    Returns a path as a list of ``((x, y), t)`` tuples (same format as
    ``astar_time``), or ``None`` if no path exists within *max_time*.
    """
    if reserved is None:
        reserved = set()
    if max_time is None:
        max_time = world.width * world.height

    if not world.is_free(goal[0], goal[1]):
        return None

    # Quick BFS reachability check (same as in astar_time)
    from mapf.a_star import _is_reachable
    if not _is_reachable(world, start, goal):
        return None

    def heuristic(pos):
        return abs(pos[0] - goal[0]) + abs(pos[1] - goal[1])

    # Precompute safe intervals for all reserved cells
    safe_intervals = _build_intervals(reserved, max_time)

    last_goal_reserved = max(
        (t for (x, y, t) in reserved if (x, y) == goal),
        default=-1,
    )

    # State: (f, g, pos, interval_index)
    # g = earliest arrival time at pos within that safe interval
    start_ivs = _intervals_for(start, safe_intervals, max_time)
    start_iv_idx = _interval_index(start_ivs, 0)
    if start_iv_idx == -1:
        return None  # start cell is blocked at t=0

    # (f_score, g_score, position, interval_idx)
    open_heap: list = []
    heapq.heappush(open_heap, (heuristic(start), 0, start, start_iv_idx))

    best: dict[tuple, int] = {(start, start_iv_idx): 0}

    # For path reconstruction: (pos, iv_idx) - (prev_pos, prev_iv_idx, arrival_t)
    came_from: dict[tuple, tuple] = {}

    DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))

    while open_heap:
        f, g, pos, iv_idx = heapq.heappop(open_heap)

        # Skip stale entries
        if best.get((pos, iv_idx), max_time + 1) < g:
            continue

        if pos == goal and g > last_goal_reserved:
            # Reconstruct path
            path: list = []
            cur_pos, cur_iv = pos, iv_idx
            cur_t = g
            while (cur_pos, cur_iv) in came_from:
                path.append((cur_pos, cur_t))
                prev_pos, prev_iv, prev_t = came_from[(cur_pos, cur_iv)]
                cur_pos, cur_iv, cur_t = prev_pos, prev_iv, prev_t
            path.append((start, 0))
            path.reverse()
            return path

        x, y = pos
        pos_ivs = _intervals_for(pos, safe_intervals, max_time)
        iv_end = pos_ivs[iv_idx][1]

        # Expand neighbours
        for dx, dy in DIRS:
            nx, ny = x + dx, y + dy
            if not world.is_free(nx, ny):
                continue

            nb = (nx, ny)
            nb_ivs = _intervals_for(nb, safe_intervals, max_time)

            for nb_iv_idx, (nb_iv_start, nb_iv_end) in enumerate(nb_ivs):
                earliest_arrival = max(g + 1, nb_iv_start)
                if earliest_arrival > nb_iv_end:
                    continue  

                departure = earliest_arrival - 1
                if departure > iv_end:
                    continue  
                arrival = earliest_arrival
                if arrival > max_time:
                    continue

                nb_state = (nb, nb_iv_idx)
                if best.get(nb_state, max_time + 1) <= arrival:
                    continue

                best[nb_state] = arrival
                came_from[nb_state] = (pos, iv_idx, g)
                f_new = arrival + heuristic(nb)
                heapq.heappush(open_heap, (f_new, arrival, nb, nb_iv_idx))

    return None

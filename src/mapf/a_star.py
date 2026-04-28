from queue import PriorityQueue


def heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar_time(
    world,
    start,
    goal,
    start_time: int = 0,
    reserved: set | None = None,
    max_time: int | None = None,
    edge_reserved: set | None = None,
    permanent_after: dict | None = None,
):
    """
    Time-expanded A*.

    Finds the shortest path from ``start`` (at ``start_time``) to ``goal``
    respecting hard vertex constraints, directed edge constraints, and
    permanent cell occupations.

    The five-direction move set — N/S/E/W plus *wait* (dx=dy=0) — lets the
    agent linger at any cell, including the goal, until all reservations on
    it have passed.

    Parameters
    ----------
    reserved : set | None
        Vertex constraints ``(x, y, t)``.
    max_time : int | None
        Hard cap on the time dimension.  Defaults to
        ``world.width * world.height``.
    edge_reserved : set | None
        Directed edge constraints ``((x, y), (nx, ny), t)`` — the agent
        cannot traverse that edge arriving at time ``t``.
    permanent_after : dict | None
        ``(x, y) → t_start``: the cell is permanently occupied from
        ``t_start`` onward.  One dict entry replaces an O(max_t) reservation
        loop in the caller.

    Notes
    -----
    Goal-settling condition
        The agent may only *terminate* at the goal at time ``t`` if
        ``t > last_goal_reserved``, ensuring it can remain there forever
        without conflicting with any previously planned path.  If the goal
        is temporarily reserved, the agent waits (via the wait action) until
        the last reservation clears.

    Correctness properties
        * **Closed set**: each state ``(pos, t)`` is expanded at most once,
          so the algorithm terminates in O(|S| log |S|) where |S| = cells × T.
        * **Stale-entry detection**: the priority queue stores ``g`` alongside
          ``f``; entries whose recorded ``g`` no longer matches
          ``g_score[(pos, t)]`` are discarded on extraction without expansion.
    """
    if reserved is None:
        reserved = set()
    if max_time is None:
        max_time = start_time + world.width * world.height

    if not world.is_free(goal[0], goal[1]):
        return None
    if not _is_reachable(world, start, goal):
        return None
    last_goal_reserved = max(
        (t for (x, y, t) in reserved if (x, y) == goal),
        default=start_time - 1,
    )

    _ctr: int = 0
    open_set = PriorityQueue()
    open_set.put((heuristic(start, goal), 0, start_time, _ctr, start))
    _ctr = 1

    came_from: dict = {}
    g_score: dict = {(start, start_time): 0}
    closed: set = set()

    while not open_set.empty():
        f, queued_g, current_time, _, current_pos = open_set.get()

        state = (current_pos, current_time)

        if state in closed:
            continue

        if g_score.get(state, float("inf")) < queued_g:
            continue

        closed.add(state)

        if current_pos == goal and current_time > last_goal_reserved:
            path: list = []
            pos, t = current_pos, current_time
            while (pos, t) in came_from:
                path.append((pos, t))
                pos, t = came_from[(pos, t)]
            path.append((start, start_time))
            path.reverse()
            return path

        x, y = current_pos
        current_g = g_score[state]

        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            new_pos = (x + dx, y + dy)
            new_time = current_time + 1

            if new_time > max_time:
                continue
            if not world.is_free(new_pos[0], new_pos[1]):
                continue
            if new_pos == goal and new_time <= last_goal_reserved:
                continue
            if (new_pos[0], new_pos[1], new_time) in reserved:
                continue
            if edge_reserved and ((x, y), new_pos, new_time) in edge_reserved:
                continue
            if (permanent_after and new_pos in permanent_after
                    and new_time >= permanent_after[new_pos]):
                continue

            new_state = (new_pos, new_time)
            if new_state in closed:
                continue

            tentative_g = current_g + 1
            if tentative_g < g_score.get(new_state, float("inf")):
                came_from[new_state] = state
                g_score[new_state] = tentative_g
                f_new = tentative_g + heuristic(new_pos, goal)
                open_set.put((f_new, tentative_g, new_time, _ctr, new_pos))
                _ctr += 1

    return None


def _is_reachable(world, start, goal) -> bool:
    """BFS on the static grid (no time) to check basic reachability."""
    if start == goal:
        return True
    from collections import deque
    visited = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (x + dx, y + dy)
            if nb == goal:
                return True
            if nb not in visited and world.is_free(nb[0], nb[1]):
                visited.add(nb)
                q.append(nb)
    return False

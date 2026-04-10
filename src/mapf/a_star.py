from queue import PriorityQueue

def heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar_time(world, start, goal, start_time=0, reserved=None, max_time=None):
    """
    Time-expanded A*.

    Parameters
    ----------
    max_time : int | None
        Hard cap on the time dimension.  States with ``time > max_time`` are
        skipped.  Defaults to ``world.width * world.height * 4``, which is
        large enough for any feasible path on practical grids while preventing
        an infinite loop when the goal is unreachable (physically blocked or
        reservation-deadlocked).
    """
    if reserved is None:
        reserved = set()
    if max_time is None:
        max_time = start_time + world.width * world.height

    # Fast reachability pre-check: if goal is physically unreachable
    if not world.is_free(goal[0], goal[1]):
        return None
    if not _is_reachable(world, start, goal):
        return None

    open_set = PriorityQueue()
    open_set.put((heuristic(start, goal), start_time, start))

    came_from = {}
    g_score = {(start, start_time): 0}

    last_goal_reserved = max(
        (t for (x, y, t) in reserved if (x, y) == goal),
        default=start_time - 1,
    )

    while not open_set.empty():
        _, current_time, current_pos = open_set.get()

        if current_pos == goal and current_time > last_goal_reserved:
            path = []
            pos, t = current_pos, current_time
            while (pos, t) in came_from:
                path.append((pos, t))
                pos, t = came_from[(pos, t)]
            path.append((start, start_time))
            path.reverse()
            return path

        x, y = current_pos

        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            new_pos = (x + dx, y + dy)
            new_time = current_time + 1

            if new_time > max_time:
                continue

            if not world.is_free(new_pos[0], new_pos[1]):
                continue

            if (new_pos[0], new_pos[1], new_time) in reserved:
                continue

            state = (new_pos, new_time)
            tentative_g = g_score[(current_pos, current_time)] + 1

            if state not in g_score or tentative_g < g_score[state]:
                came_from[state] = (current_pos, current_time)
                g_score[state] = tentative_g
                f_score = tentative_g + heuristic(new_pos, goal)
                open_set.put((f_score, new_time, new_pos))

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
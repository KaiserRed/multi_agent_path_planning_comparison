from queue import PriorityQueue

def heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def astar_time(world, start, goal, start_time=0, reserved=None):
    if reserved is None:
        reserved = set()

    open_set = PriorityQueue()
    open_set.put((heuristic(start, goal), start_time, start))

    came_from = {}
    g_score = {(start, start_time): 0}

    while not open_set.empty():
        _, current_time, current_pos = open_set.get()

        if current_pos == goal:
            path = []
            pos, t = current_pos, current_time
            while (pos, t) in came_from:
                path.append((pos, t))
                pos, t = came_from[(pos, t)]
            path.append((start, start_time))
            path.reverse()
            return path

        x, y = current_pos
        moves = [(0, 0), (1,0), (-1,0), (0,1), (0,-1)]

        for dx, dy in moves:
            new_pos = (x + dx, y + dy)
            new_time = current_time + 1

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
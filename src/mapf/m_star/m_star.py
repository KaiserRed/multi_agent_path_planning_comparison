"""
M* algorithm for Multi-Agent Path Finding.

Key idea (subdimensional expansion):
  1. Precompute individual optimal policies via backward Dijkstra from each goal.
  2. Search in the joint configuration space, but initially let each agent
     follow only its individually-optimal moves (decoupled expansion).
  3. When a conflict is detected in a proposed transition, mark the conflicting
     agents as "coupled" at the current state and re-expand with full joint
     moves for those agents.  Coupling propagates backward through came_from.

This is centralized and offline.  Optimal when individual optimal policies
are used and the backpropagation is complete.
"""

from heapq import heappush, heappop
from itertools import product

from mapf.planner import MAPFPlanner


# Individual optimal policy
def _backward_dijkstra(world, goal: tuple) -> dict:
    """BFS/Dijkstra backwards from *goal* → cost-to-go for every reachable cell."""
    dist: dict = {goal: 0}
    queue = [(0, goal)]

    while queue:
        d, pos = heappop(queue)
        if d > dist.get(pos, float("inf")):
            continue
        x, y = pos
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = x + dx, y + dy
            if world.is_free(nx, ny):
                nd = d + 1
                if nd < dist.get((nx, ny), float("inf")):
                    dist[(nx, ny)] = nd
                    heappush(queue, (nd, (nx, ny)))

    return dist


def _policy_moves(pos: tuple, goal: tuple, policy: dict) -> list:
    """
    Return moves that keep the agent on its individually-optimal path
    (i.e. strictly reduce cost-to-go).  If the agent is at the goal, wait.
    """
    if pos == goal:
        return [pos]

    d = policy.get(pos, float("inf"))
    moves = []
    x, y = pos
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        nx, ny = x + dx, y + dy
        if policy.get((nx, ny), float("inf")) < d:
            moves.append((nx, ny))

    return moves if moves else [pos]


def _all_moves(pos: tuple, world) -> list:
    """All valid moves from *pos* (including wait)."""
    x, y = pos
    moves = [pos]  # wait
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        nx, ny = x + dx, y + dy
        if world.is_free(nx, ny):
            moves.append((nx, ny))
    return moves


def _find_conflicts(state: tuple, next_state: tuple) -> frozenset:
    """Return frozenset of agent indices involved in vertex or edge conflicts."""
    conflicts: set = set()
    n = len(state)
    for i in range(n):
        for j in range(i + 1, n):
            # Vertex conflict: two agents at the same cell
            if next_state[i] == next_state[j]:
                conflicts.add(i)
                conflicts.add(j)
            # Edge conflict: agents swap positions
            if state[i] == next_state[j] and state[j] == next_state[i]:
                conflicts.add(i)
                conflicts.add(j)
    return frozenset(conflicts)


# M* search
def mstar(world, agents, max_iter: int = 200_000):
    n = len(agents)
    if n == 0:
        return {}

    goals = tuple((a.goal_x, a.goal_y) for a in agents)
    initial = tuple((a.x, a.y) for a in agents)

    # Precompute individual optimal policies
    policies = []
    for a in agents:
        pol = _backward_dijkstra(world, (a.goal_x, a.goal_y))
        # Check reachability
        if (a.x, a.y) not in pol and (a.x, a.y) != (a.goal_x, a.goal_y):
            return None
        policies.append(pol)

    def heuristic(state):
        return sum(policies[i].get(state[i], 0) for i in range(n))

    g_cost: dict = {initial: 0}
    came_from: dict = {}
    # Per-state set of coupled agent indices
    coupling: dict = {initial: frozenset()}

    counter = 0
    open_set = [(heuristic(initial), counter, initial)]

    for _ in range(max_iter):
        if not open_set:
            break

        f, _, state = heappop(open_set)
        g = g_cost.get(state, float("inf"))

        # Skip stale entries
        if f > g + heuristic(state) + 1e-9:
            continue

        # Goal check
        if state == goals:
            return _reconstruct(came_from, state, initial, agents)

        coupled = coupling.get(state, frozenset())

        # Build per-agent move sets
        agent_moves = []
        for i in range(n):
            if i in coupled:
                agent_moves.append(_all_moves(state[i], world))
            else:
                agent_moves.append(_policy_moves(state[i], goals[i], policies[i]))

        needs_reexpansion = False

        for next_positions in product(*agent_moves):
            next_state = tuple(next_positions)
            conflicts = _find_conflicts(state, next_state)

            if conflicts:
                new_coupling = coupling.get(state, frozenset()) | conflicts
                if new_coupling != coupling.get(state, frozenset()):
                    coupling[state] = new_coupling
                    needs_reexpansion = True
                continue

            new_g = g + 1
            if new_g < g_cost.get(next_state, float("inf")):
                g_cost[next_state] = new_g
                came_from[next_state] = state
                if next_state not in coupling:
                    coupling[next_state] = frozenset()
                counter += 1
                heappush(
                    open_set,
                    (new_g + heuristic(next_state), counter, next_state),
                )

        if needs_reexpansion:
            counter += 1
            heappush(open_set, (g + heuristic(state), counter, state))

    return None  # no solution


def _reconstruct(came_from: dict, goal_state: tuple, initial: tuple, agents) -> dict:
    path_states = []
    cur = goal_state
    while cur in came_from:
        path_states.append(cur)
        cur = came_from[cur]
    path_states.append(initial)
    path_states.reverse()

    result = {}
    for i, agent in enumerate(agents):
        result[agent.id] = [(joint[i], t) for t, joint in enumerate(path_states)]
    return result


class MStarPlanner(MAPFPlanner):
    DISPLAY_NAME = "M*"
    DESCRIPTION = (
        "Subdimensional expansion MAPF algorithm. "
        "Starts decoupled and couples agents only on conflict — "
        "very efficient when agents rarely interact."
    )
    IS_CENTRALIZED = True
    IS_ONLINE = False

    def plan(self, world, agents):
        return mstar(world, agents)

"""
Hungarian algorithm (Kuhn–Munkres) for MRTA task assignment.

Given a cost matrix C where C[i][j] = cost of assigning agent i to task j,
returns the minimum-cost perfect matching as a list of (agent_idx, task_idx).

Implementation uses the O(n³) potential method (standard competitive-programming
variant), padded to a square matrix so it handles rectangular inputs.
"""

from mrta.planner import MRTAPlanner


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------

def hungarian(cost_matrix: list[list[float]]) -> list[tuple[int, int]]:
    """
    Solve the linear assignment problem.

    Parameters
    ----------
    cost_matrix : list[list[float]]
        n_agents × n_tasks matrix of assignment costs.

    Returns
    -------
    list of (agent_idx, task_idx) pairs representing the optimal assignment.
    """
    if not cost_matrix or not cost_matrix[0]:
        return []

    n_rows = len(cost_matrix)
    n_cols = len(cost_matrix[0])
    size = max(n_rows, n_cols)

    INF = float("inf")
    BIG = 1e18  # cost for padding cells

    # 1-indexed square cost matrix
    C: list[list[float]] = [[BIG] * (size + 1) for _ in range(size + 1)]
    for i in range(n_rows):
        for j in range(n_cols):
            C[i + 1][j + 1] = float(cost_matrix[i][j])

    # Potentials
    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    # p[j] = row (1-indexed) assigned to column j; 0 means unassigned
    p = [0] * (size + 1)
    way = [0] * (size + 1)

    for i in range(1, size + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (size + 1)
        used = [False] * (size + 1)

        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = 0

            for j in range(1, size + 1):
                if not used[j]:
                    cur = C[i0][j] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j

            for j in range(size + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta

            j0 = j1
            if p[j0] == 0:
                break

        while j0:
            p[j0] = p[way[j0]]
            j0 = way[j0]

    # Extract valid assignments (within original matrix bounds)
    result = []
    for j in range(1, size + 1):
        row = p[j]
        if 1 <= row <= n_rows and 1 <= j <= n_cols:
            result.append((row - 1, j - 1))

    return result


# ---------------------------------------------------------------------------
# Planner wrapper
# ---------------------------------------------------------------------------

class HungarianPlanner(MRTAPlanner):
    DISPLAY_NAME = "Hungarian"
    DESCRIPTION = (
        "Hungarian algorithm (Kuhn–Munkres). Finds the globally optimal "
        "one-to-one task assignment minimising total travel distance. "
        "Runs in O(n³). Online mode: reassigns on each agent completion."
    )
    IS_CENTRALIZED = True
    IS_ONLINE = False
    ASSIGNMENT_MODE = "online"

    def plan(self, world, agents, tasks):
        """
        Assign each agent to exactly one task (min(agents, tasks) matches).

        Returns dict[agent_id -> list[Task]] where each list has one element.
        Cost = Manhattan distance from agent position to task location.
        """
        if not agents or not tasks:
            return {}

        cost = [
            [abs(a.x - t.x) + abs(a.y - t.y) for t in tasks]
            for a in agents
        ]

        assignment = hungarian(cost)

        result = {}
        for agent_idx, task_idx in assignment:
            result[agents[agent_idx].id] = [tasks[task_idx]]

        return result

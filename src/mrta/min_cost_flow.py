"""
Min-Cost Flow for MRTA — queue (horizon) assignment mode.

Models multi-task assignment as a minimum-cost flow problem on a network
that allows each agent to receive up to *H* tasks (the horizon):

    source → agent_slots → tasks → sink

where each agent node is expanded into H "slot" nodes (agent_0_slot_1,
agent_0_slot_2, …).  A task assigned to slot k of agent i means it is
the k-th task in that agent's execution chain.  The cost of assigning
a task to slot k depends on the virtual position of the agent after
completing slots 1..k-1, so the cost matrix captures the true sequential
travel cost.

Because slot ordering matters, we solve iteratively: assign slot 1 for
all agents (standard bipartite MCF), update virtual positions, assign
slot 2, and so on until no tasks remain or the horizon is exhausted.
Each iteration is a standard unit-capacity MCF — O(T · SSP(n,m)) total.

Reference
---------
Bertsekas, D. P. "Network Optimization: Continuous and Discrete Models", 1998.
"""

from __future__ import annotations

from collections import deque

from mrta.planner import MRTAPlanner


# Core unit-capacity MCF (Successive Shortest Paths)

def _min_cost_flow(n_agents: int, n_tasks: int, costs: list[list[float]]):
    """
    Solve a unit-capacity bipartite assignment via Successive Shortest Paths.

    Returns dict[agent_idx -> task_idx] for the minimum-cost matching.
    """
    if n_agents == 0 or n_tasks == 0:
        return {}

    N = 2 + n_agents + n_tasks
    source = 0
    sink = N - 1

    adj: list[list] = [[] for _ in range(N)]

    def _add_edge(u, v, cap, cost):
        adj[u].append([v, cap, cost, len(adj[v])])
        adj[v].append([u, 0, -cost, len(adj[u]) - 1])

    for i in range(n_agents):
        _add_edge(source, i + 1, 1, 0)
    for i in range(n_agents):
        for j in range(n_tasks):
            _add_edge(i + 1, n_agents + 1 + j, 1, costs[i][j])
    for j in range(n_tasks):
        _add_edge(n_agents + 1 + j, sink, 1, 0)

    INF = float("inf")

    while True:
        dist = [INF] * N
        dist[source] = 0.0
        in_queue = [False] * N
        prev_node = [-1] * N
        prev_edge = [-1] * N

        q: deque = deque([source])
        in_queue[source] = True

        while q:
            u = q.popleft()
            in_queue[u] = False
            for idx, (v, cap, cost, _) in enumerate(adj[u]):
                if cap > 0 and dist[u] + cost < dist[v] - 1e-9:
                    dist[v] = dist[u] + cost
                    prev_node[v] = u
                    prev_edge[v] = idx
                    if not in_queue[v]:
                        q.append(v)
                        in_queue[v] = True

        if dist[sink] >= INF:
            break

        v = sink
        while v != source:
            u = prev_node[v]
            e = adj[u][prev_edge[v]]
            e[1] -= 1
            adj[v][e[3]][1] += 1
            v = u

    assignment: dict = {}
    for i in range(n_agents):
        for edge in adj[i + 1]:
            v, cap, _cost, _ = edge
            if n_agents + 1 <= v <= n_agents + n_tasks and cap == 0:
                assignment[i] = v - n_agents - 1
                break

    return assignment


# Planner wrapper

class MinCostFlowPlanner(MRTAPlanner):
    DISPLAY_NAME = "Min-Cost Flow"
    DESCRIPTION = (
        "Minimum-cost flow with planning horizon H. Assigns up to H tasks "
        "per agent by solving H successive bipartite MCF problems, each "
        "using virtual positions from the previous round. Finds the globally "
        "optimal task chains within the horizon. Queue mode."
    )
    IS_CENTRALIZED = True
    IS_ONLINE = False
    ASSIGNMENT_MODE = "queue"

    def __init__(self, horizon: int = 0):
        # horizon=0 means "assign all tasks" (unlimited horizon)
        self._horizon = horizon

    def plan(self, world, agents, tasks):
        """
        Build ordered task chains for each agent via iterative MCF rounds.

        Returns dict[agent_id -> list[Task]].
        """
        if not agents or not tasks:
            return {}

        # Virtual positions start at each agent's actual position.
        virtual_pos: dict = {a.id: (a.x, a.y) for a in agents}
        chains: dict = {a.id: [] for a in agents}

        remaining = list(tasks)
        horizon = self._horizon if self._horizon > 0 else len(tasks)

        for _slot in range(horizon):
            if not remaining:
                break

            # Build cost matrix: agent × remaining-task, using virtual pos.
            cost_matrix = [
                [abs(virtual_pos[a.id][0] - t.x) +
                 abs(virtual_pos[a.id][1] - t.y)
                 for t in remaining]
                for a in agents
            ]

            raw = _min_cost_flow(len(agents), len(remaining), cost_matrix)
            if not raw:
                break

            assigned_task_ids: set = set()
            for agent_idx, task_idx in raw.items():
                aid = agents[agent_idx].id
                task = remaining[task_idx]
                chains[aid].append(task)
                virtual_pos[aid] = (task.x, task.y)
                assigned_task_ids.add(task.id)

            remaining = [t for t in remaining if t.id not in assigned_task_ids]

        return {aid: chain for aid, chain in chains.items() if chain}

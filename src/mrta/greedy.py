"""
Greedy Nearest-Task assignment for MRTA.

Repeatedly picks the globally closest (agent, task) pair and assigns
them until no more assignments can be made.  Very fast — O(A·T) per
round — but produces no optimality guarantees.
"""

from mrta.planner import MRTAPlanner


def greedy_nearest(agents, tasks):
    """
    Greedy nearest-task assignment.

    Returns
    -------
    dict[agent_id, Task]
    """
    if not agents or not tasks:
        return {}

    free_agents = set(a.id for a in agents)
    free_tasks = set(t.id for t in tasks)
    agent_map = {a.id: a for a in agents}
    task_map = {t.id: t for t in tasks}

    assignment: dict = {}

    while free_agents and free_tasks:
        best_dist = float("inf")
        best_aid = None
        best_tid = None

        for aid in free_agents:
            a = agent_map[aid]
            for tid in free_tasks:
                t = task_map[tid]
                d = abs(a.x - t.x) + abs(a.y - t.y)
                if d < best_dist:
                    best_dist = d
                    best_aid = aid
                    best_tid = tid

        if best_aid is None:
            break

        assignment[best_aid] = [task_map[best_tid]]
        free_agents.discard(best_aid)
        free_tasks.discard(best_tid)

    return assignment


class GreedyPlanner(MRTAPlanner):
    DISPLAY_NAME = "Greedy"
    DESCRIPTION = (
        "Greedy nearest-task assignment. Repeatedly assigns the closest "
        "(agent, task) pair. Very fast but provides no optimality guarantee. "
        "Online mode: reassigns on each agent completion."
    )
    IS_CENTRALIZED = True
    IS_ONLINE = False
    ASSIGNMENT_MODE = "online"

    def plan(self, world, agents, tasks):
        return greedy_nearest(agents, tasks)

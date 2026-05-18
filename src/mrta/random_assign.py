"""
Random task assignment for MRTA.

Shuffles agents and tasks with a fixed seed, then zips them one-to-one.
Useful as a baseline to isolate the MAPF component: the assignment
quality is intentionally zero so any performance difference between runs
is purely due to the navigation planner.
"""

import random

from mrta.planner import MRTAPlanner


def random_assignment(agents, tasks, seed: int = 0):
    """Return a random 1-to-1 agent→task assignment.

    If there are more tasks than agents some tasks are left unassigned;
    if there are more agents than tasks some agents get no task.

    Parameters
    ----------
    seed : int
        Fixed seed so results are reproducible across runs.
    """
    if not agents or not tasks:
        return {}

    rng = random.Random(seed)
    shuffled_agents = list(agents)
    shuffled_tasks = list(tasks)
    rng.shuffle(shuffled_agents)
    rng.shuffle(shuffled_tasks)

    return {
        a.id: [t]
        for a, t in zip(shuffled_agents, shuffled_tasks)
    }


class RandomPlanner(MRTAPlanner):
    DISPLAY_NAME = "Random"
    DESCRIPTION = (
        "Random task assignment. Shuffles agents and tasks, then pairs them "
        "one-to-one. Useful as a MAPF-only baseline — any performance "
        "difference is due to navigation, not task allocation."
    )
    IS_CENTRALIZED = True
    IS_ONLINE = False
    ASSIGNMENT_MODE = "online"

    def plan(self, world, agents, tasks):
        return random_assignment(agents, tasks)

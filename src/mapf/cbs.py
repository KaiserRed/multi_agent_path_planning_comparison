from queue import PriorityQueue
from copy import deepcopy
from mapf.a_star import astar_time
from mapf.planner import MAPFPlanner

class Conflict:
    def __init__(self, agent1, agent2, time, position):
        self.agent1 = agent1
        self.agent2 = agent2
        self.time = time
        self.position = position

class CTNode:
    def __init__(self, constraints, paths):
        self.constraints = constraints
        self.paths = paths
        self.cost = sum(len(p) for p in paths.values() if p)

    def __lt__(self, other):
        return self.cost < other.cost

def detect_first_conflict(paths):
    max_time = max(len(p) for p in paths.values() if p)

    for t in range(max_time):
        positions = {}

        for agent_id, path in paths.items():
            if t < len(path):
                pos = path[t][0]
                if pos in positions:
                    return Conflict(positions[pos], agent_id, t, pos)
                positions[pos] = agent_id

    return None

def cbs(world, agents):
    paths = {}

    for agent in agents:
        path = astar_time(world, (agent.x, agent.y),
                          (agent.goal_x, agent.goal_y))
        if path is None:
            return None
        paths[agent.id] = path

    root = CTNode([], paths)
    open_set = PriorityQueue()
    open_set.put(root)

    while not open_set.empty():
        node = open_set.get()
        conflict = detect_first_conflict(node.paths)

        if conflict is None:
            return node.paths

        for agent_id in [conflict.agent1, conflict.agent2]:
            new_node = CTNode(deepcopy(node.constraints),
                              deepcopy(node.paths))

            reserved = set()

            for other_id, path in node.paths.items():
                if other_id != agent_id:
                    for pos, t in path:
                        reserved.add((pos[0], pos[1], t))

            agent = next(a for a in agents if a.id == agent_id)

            new_path = astar_time(
                world,
                (agent.x, agent.y),
                (agent.goal_x, agent.goal_y),
                0,
                reserved
            )

            if new_path:
                new_node.paths[agent_id] = new_path
                open_set.put(new_node)

    return None

class CBSPlanner(MAPFPlanner):
    def plan(self, world, agents):
        return cbs(world, agents)
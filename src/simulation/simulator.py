class Simulator:
    def __init__(self, world, agents, planner):
        self.world = world
        self.agents = agents
        self.planner = planner

        self.time = 0
        self.planned = False

    def plan(self):
        """Запуск MAPF алгоритма"""
        paths = self.planner(self.world, self.agents)

        if paths is None:
            print("Пути не найдены")
            return False

        for agent in self.agents:
            if agent.id in paths:
                path_positions = [pos for pos, t in paths[agent.id]]
                agent.set_path(path_positions)

        self.planned = True
        print("Планирование завершено")
        return True

    def step(self):
        """Один шаг симуляции"""
        if not self.planned:
            return False

        any_moved = False

        for agent in self.agents:
            if agent.has_path():
                step = agent.next_step()
                if step:
                    agent.x, agent.y = step
                    any_moved = True

        if any_moved:
            self.time += 1

        return any_moved

    def reset(self):
        """Сброс симуляции"""
        self.time = 0
        self.planned = False

        for agent in self.agents:
            if agent.path:
                agent.x, agent.y = agent.path[0]
                agent.path_index = 0
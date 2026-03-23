class Agent:
    def __init__(self, agent_id, x, y, goal_x, goal_y):
        self.id = agent_id
        self.x = x
        self.y = y
        self.goal_x = goal_x
        self.goal_y = goal_y
        self.path = []
        self.path_with_time = []
        self.path_index = 0
        self.color = self._generate_color(agent_id)

    def _generate_color(self, agent_id):
        colors = [
            (255, 0, 0),
            (0, 0, 255),
            (255, 165, 0),
            (128, 0, 128),
            (0, 255, 0),
            (255, 0, 255),
            (0, 255, 255),
            (255, 255, 0),
        ]
        return colors[agent_id % len(colors)]

    def set_path(self, path, path_with_time=None):
        self.path = path
        self.path_with_time = path_with_time if path_with_time else []
        self.path_index = 0 if path else -1

    def has_path(self):
        return self.path and self.path_index < len(self.path)

    def next_step(self):
        if self.has_path():
            step = self.path[self.path_index]
            self.path_index += 1
            return step
        return None
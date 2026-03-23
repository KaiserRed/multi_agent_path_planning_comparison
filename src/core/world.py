import numpy as np

class World:
    """Класс мира – сетка с препятствиями."""
    def __init__(self, width, height, obstacles=[]):
        self.width = width
        self.height = height
        self.grid = np.zeros((height, width), dtype=int)
        for (x, y) in obstacles:
            if 0 <= x < width and 0 <= y < height:
                self.grid[y, x] = 1

    def is_free(self, x, y, time=None, reserved=None):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        if self.grid[y, x] == 1:
            return False
        if reserved and (x, y, time) in reserved:
            return False
        return True
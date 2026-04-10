"""
Lazy BFS distance table used by PIBT.

All coordinates are in (row, col) = (y, x) format.
``grid[y, x] = True``  →  free cell.
``grid[y, x] = False`` →  obstacle.
"""

from collections import deque

import numpy as np


class DistTable:
    """
    On-demand BFS from ``goal`` to every reachable cell.

    Distances are computed lazily: a BFS frontier is advanced only as far as
    needed to answer each ``get`` query, and results are cached.

    Parameters
    ----------
    grid : np.ndarray
        Boolean 2-D array (shape ``[height, width]``), True = free.
    goal : tuple[int, int]
        Goal position in ``(y, x)`` order.
    """

    def __init__(self, grid: np.ndarray, goal: tuple) -> None:
        self.grid = grid
        self.goal = goal
        self._Q: deque = deque([goal])
        self._table: np.ndarray = np.full(grid.shape, grid.size, dtype=np.int32)
        self._table[goal] = 0


    def get(self, target: tuple) -> int:
        """
        Return the shortest-path distance from *goal* to *target*.

        Returns ``grid.size`` (effectively ∞) if *target* is out-of-bounds,
        an obstacle, or unreachable.
        """
        r, c = target
        h, w = self.grid.shape
        if not (0 <= r < h and 0 <= c < w and self.grid[r, c]):
            return int(self.grid.size)

        # Already computed
        if self._table[target] < self._table.size:
            return int(self._table[target])

        # Advance BFS until target is settled
        while self._Q:
            u = self._Q.popleft()
            d = int(self._table[u])
            for v in self._neighbors(u):
                if d + 1 < self._table[v]:
                    self._table[v] = d + 1
                    self._Q.append(v)
            if u == target:
                return d

        return int(self.grid.size)  # unreachable


    def _neighbors(self, pos: tuple) -> list:
        r, c = pos
        h, w = self.grid.shape
        result = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and self.grid[nr, nc]:
                result.append((nr, nc))
        return result

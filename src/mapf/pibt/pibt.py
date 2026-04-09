"""
Priority Inheritance with Backtracking (PIBT) for MAPF.

Reference
---------
Okumura K., Machida M., Défago X., Tamura Y.
"Priority inheritance with backtracking for iterative multi-agent path finding."
Artificial Intelligence Journal, 2022.
https://kei18.github.io/pibt2/

Coordinate convention (internal)
---------------------------------
All positions are ``(row, col)`` = ``(y, x)`` tuples, matching the
standard MAPF benchmark convention.  The ``PIBTPlanner`` wrapper converts
from/to the ``(x, y)`` convention used in the rest of the application.
"""

from __future__ import annotations

import numpy as np

from mapf.planner import MAPFPlanner
from mapf.pibt.dist_table import DistTable


# Core algorithm
class PIBT:
    """
    PIBT core: one-step-at-a-time collision-free planning.

    Parameters
    ----------
    grid : np.ndarray
        Boolean grid (True = free), shape ``(height, width)``.
    starts : list[tuple[int,int]]
        Starting positions in ``(y, x)`` order, one per agent.
    goals : list[tuple[int,int]]
        Goal positions in ``(y, x)`` order, one per agent.
    seed : int
        Random seed for tie-breaking (default 0).
    """

    def __init__(
        self,
        grid: np.ndarray,
        starts: list,
        goals: list,
        seed: int = 0,
    ) -> None:
        self.grid   = grid
        self.starts = starts
        self.goals  = goals
        self.N      = len(starts)

        self.dist_tables = [DistTable(grid, g) for g in goals]

        # Sentinels
        self.NIL       = self.N           # no agent
        self.NIL_COORD = grid.shape       # no position (out-of-bounds)

        # Per-cell occupation state (reused across steps)
        self.occupied_now = np.full(grid.shape, self.NIL, dtype=np.int32)
        self.occupied_nxt = np.full(grid.shape, self.NIL, dtype=np.int32)

        self.rng = np.random.default_rng(seed)

    
    # Helpers
    def _neighbors(self, pos: tuple) -> list:
        r, c = pos
        h, w = self.grid.shape
        result = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and self.grid[nr, nc]:
                result.append((nr, nc))
        return result

    
    # Core PIBT function (recursive)
    def _funcPIBT(self, Q_from: list, Q_to: list, i: int) -> bool:
        """
        Try to assign a next position to agent *i*.

        Modifies ``Q_to`` and the occupation tables in-place.

        Returns True on success, False if the agent must stay put.
        """
        candidates: list = [Q_from[i]] + self._neighbors(Q_from[i])
        self.rng.shuffle(candidates)                          # random tie-break
        candidates.sort(key=lambda u: self.dist_tables[i].get(u))  # prefer closer

        for v in candidates:
            # vertex conflict: cell already reserved for next step
            if self.occupied_nxt[v] != self.NIL:
                continue

            j = int(self.occupied_now[v])   # agent currently at v

            # edge (swap) conflict: i and j would exchange positions
            if j != self.NIL and Q_to[j] == Q_from[i]:
                continue

            # Tentatively assign i → v
            Q_to[i] = v
            self.occupied_nxt[v] = i

            # Priority inheritance: if j hasn't been planned yet, plan it now
            if (
                j != self.NIL
                and Q_to[j] == self.NIL_COORD
                and not self._funcPIBT(Q_from, Q_to, j)
            ):
                # j couldn't move out of v → backtrack and try next candidate
                # (j's failure left occupied_nxt[v] = j, which will be
                #  cleaned up by j's entry in step's cleanup loop)
                continue

            return True

        # No valid move found: agent stays in place
        Q_to[i] = Q_from[i]
        self.occupied_nxt[Q_from[i]] = i
        return False

    
    # Single timestep
    def step(self, Q_from: list, priorities: list) -> list:
        """
        Advance all agents by one timestep.

        Parameters
        ----------
        Q_from : list[tuple]
            Current positions (one per agent).
        priorities : list[float]
            Planning priority for each agent (higher = planned first).

        Returns
        -------
        list[tuple]
            Next positions for all agents.
        """
        N    = len(Q_from)
        Q_to = [self.NIL_COORD] * N

        for i, v in enumerate(Q_from):
            self.occupied_now[v] = i

        order = sorted(range(N), key=lambda i: priorities[i], reverse=True)
        for i in order:
            if Q_to[i] == self.NIL_COORD:
                self._funcPIBT(Q_from, Q_to, i)

        # Reset occupation tables for next call
        for q_f, q_t in zip(Q_from, Q_to):
            self.occupied_now[q_f] = self.NIL
            self.occupied_nxt[q_t] = self.NIL

        return Q_to

    
    def run(self, max_timestep: int = 1000) -> list:
        """
        Run PIBT until all agents reach their goals or *max_timestep* steps.

        Returns
        -------
        list[list[tuple]]
            Sequence of configurations.  ``configs[t][i]`` is agent *i*'s
            position at time *t* in ``(y, x)`` order.
        """
        priorities: list[float] = [
            self.dist_tables[i].get(self.starts[i]) / self.grid.size
            for i in range(self.N)
        ]

        configs: list = [list(self.starts)]

        while len(configs) <= max_timestep:
            Q = self.step(configs[-1], priorities)
            configs.append(Q)

            all_done = True
            for i in range(self.N):
                if Q[i] != self.goals[i]:
                    all_done = False
                    priorities[i] += 1
                else:
                    priorities[i] -= float(np.floor(priorities[i]))

            if all_done:
                break

        return configs


class PIBTPlanner(MAPFPlanner):
    """
    PIBT wrapped in the application's ``MAPFPlanner`` interface.

    Coordinate bridge
    -----------------
    * Agents and paths in the application use ``(x, y)`` tuples.
    * PIBT operates in ``(row, col) = (y, x)`` format internally.
    Conversion happens only at the ``plan`` boundary.

    PIBT is an **online** algorithm: it plans one step at a time without
    look-ahead.  Here we run the full trajectory upfront (offline mode)
    by calling :meth:`PIBT.run`, which is valid because PIBT does not
    rely on external observations between steps.
    """

    DISPLAY_NAME   = "PIBT"
    DESCRIPTION    = (
        "Priority Inheritance with Backtracking.  "
        "Online, centralized.  Computes moves one step at a time using "
        "priority queues and backtracking — very fast even for many agents."
    )
    IS_CENTRALIZED = True
    IS_ONLINE      = True

    def __init__(self, max_timestep: int = 2000, seed: int = 0) -> None:
        self._max_timestep = max_timestep
        self._seed         = seed

    def plan(self, world, agents) -> dict | None:
        """
        Plan collision-free paths for all agents.

        Parameters
        ----------
        world : World
            Grid world (``world.grid[y, x] == 0`` means free).
        agents : list[Agent]
            Agents with ``.x``, ``.y``, ``.goal_x``, ``.goal_y``, ``.id``.

        Returns
        -------
        dict[int, list[tuple]] or None
            ``{agent.id: [((x, y), t), ...]}`` on success, or ``None``
            if PIBT could not reach all goals within *max_timestep*.
        """
        if not agents:
            return {}

        n = len(agents)

        # World grid: True = free, shape (height, width)
        bool_grid: np.ndarray = (world.grid == 0)

        # Convert (x, y) → (y, x) for PIBT
        starts_yx = [(a.y, a.x)           for a in agents]
        goals_yx  = [(a.goal_y, a.goal_x) for a in agents]

        pibt    = PIBT(bool_grid, starts_yx, goals_yx, seed=self._seed)
        configs = pibt.run(max_timestep=self._max_timestep)

        # Verify all agents reached their goals
        final = configs[-1]
        if any(final[i] != goals_yx[i] for i in range(n)):
            return None

        # Convert (y, x) → (x, y) and build path dict
        result: dict = {}
        for i, agent in enumerate(agents):
            result[agent.id] = [
                ((configs[t][i][1], configs[t][i][0]), t)
                for t in range(len(configs))
            ]

        return result

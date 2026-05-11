import time as _time
import tracemalloc
from collections import deque

from mapf.a_star import astar_time


def _expand_path(path: list) -> list:
    """Convert a planner path to one position per timestep.

    Planners like A* already emit one ``(pos, t)`` entry per step, so the
    list is already dense.  SIPP emits a *compressed* path where only
    position-changes are recorded and waiting periods are implicit.
    This helper expands such paths so each timestep gets its own entry,
    making them interchangeable with A* output for the simulator.
    """
    if not path:
        return []
    expanded: list = []
    for i in range(len(path) - 1):
        pos, t = path[i]
        next_t = path[i + 1][1]
        for _ in range(next_t - t):
            expanded.append(pos)
    expanded.append(path[-1][0])
    return expanded


class Simulator:
    """
    Unified simulator for both MAPF and MRTA scenarios.

    MAPF mode
        planner.plan(world, agents) → collision-free paths dict.

    MRTA mode — two sub-modes determined by planner.ASSIGNMENT_MODE:

    "online"  (Hungarian, Greedy)
        planner.plan returns dict[agent_id -> list[Task]] with ONE task per
        agent.  Whenever an agent completes its task the planner is called
        again for just that agent with the remaining unassigned tasks.

    "queue"  (Sequential Auction, Min-Cost Flow, Combinatorial Auction)
        planner.plan returns dict[agent_id -> list[Task]] with a full ordered
        chain per agent.  The simulator executes each chain without
        re-planning: upon task completion the next task in the chain is
        popped and the agent navigates to it immediately.

    Metrics collected
    -----------------
    computation_s   : total planning wall time
    plan_mrta_s     : time spent in MRTA assignment algorithm
    plan_mapf_s     : time spent building navigation paths (all legs)
    memory_peak_mb  : peak Python memory during planning
    makespan        : simulation timesteps until all tasks done
    soc             : Sum-of-Costs — total moves across all agents
    """

    def __init__(self, world, agents, planner, tasks=None, nav_planner=None):
        self.world = world
        self.agents = agents
        self.planner = planner
        self.tasks = tasks or []
        self.mode: str = getattr(planner, "ALGORITHM_TYPE", "MAPF")
        self._assignment_mode: str = getattr(planner, "ASSIGNMENT_MODE", "online")

        # Optional MAPF planner used for navigation in MRTA mode.
        # Falls back to plain A* when None.
        self._nav_planner = nav_planner

        self.time: int = 0
        self.planned: bool = False
        self.failed: bool = False

        self._initial = [
            (a.id, a.x, a.y, a.goal_x, a.goal_y) for a in agents
        ]
        self._initial_tasks = [
            (t.id, t.x, t.y, t.priority) for t in self.tasks
        ]

        self.metrics: dict = {
            "computation_s": 0.0,
            "plan_mrta_s": 0.0,
            "plan_mapf_s": 0.0,
            "memory_peak_mb": 0.0,
            "makespan": 0,
            "soc": 0,
        }

        # MRTA state
        self._pending_tasks: list = []
        self._task_queue: dict = {}   # agent_id -> deque[Task]

        # Internal timing accumulators (reset at each plan() call)
        self._mrta_s: float = 0.0
        self._mapf_nav_s: float = 0.0

    # Navigation helpers
    def _nav_all(self, agents_with_goals: list) -> dict | None:
        """Plan collision-free paths for several agents at once.

        When a nav_planner is configured it is called with all agents
        together.  Without a nav_planner agents are routed sequentially
        (CA*-style) using plain A* and a shared reservation table.

        Returns dict[agent_id -> list[(x,y)]] (start cell excluded),
        or None if any agent has no valid path.

        Navigation time is accumulated into ``_mapf_nav_s``.
        """
        if not agents_with_goals:
            return {}

        t0 = _time.perf_counter()

        if self._nav_planner is not None:
            paths = self._nav_planner.plan(self.world, agents_with_goals)
            self._mapf_nav_s += _time.perf_counter() - t0
            if paths is None:
                return None
            result: dict = {}
            for agent in agents_with_goals:
                if agent.id not in paths:
                    return None
                raw = _expand_path(paths[agent.id])
                result[agent.id] = raw[1:] if len(raw) > 1 else []
            return result

        # Sequential CA*-style fallback
        max_time = self.world.width * self.world.height * 2
        reserved: set = set()
        result = {}
        for agent in agents_with_goals:
            path = astar_time(
                self.world,
                (agent.x, agent.y),
                (agent.goal_x, agent.goal_y),
                reserved=reserved,
                max_time=max_time,
            )
            if path is None:
                self._mapf_nav_s += _time.perf_counter() - t0
                return None
            for idx, (pos, t) in enumerate(path):
                reserved.add((pos[0], pos[1], t))
                if idx > 0:
                    prev_pos, _ = path[idx - 1]
                    reserved.add((prev_pos[0], prev_pos[1], t))
            if path:
                gx, gy = path[-1][0]
                reservation_end = min(len(path) + 100, max_time)
                for t in range(len(path), reservation_end + 1):
                    reserved.add((gx, gy, t))
            raw = [pos for pos, _ in path]
            result[agent.id] = raw[1:] if len(raw) > 1 else []

        self._mapf_nav_s += _time.perf_counter() - t0
        return result

    def _path_to_single(self, agent, goal: tuple) -> list | None:
        """Plan a single agent's path while treating other agents' remaining
        paths as reservations (CA*-style).

        Navigation time is accumulated into ``_mapf_nav_s``.
        Returns a list of (x, y) positions (start cell excluded), or None.
        """
        t0 = _time.perf_counter()

        max_time = self.world.width * self.world.height * 2
        reserved: set = set()

        for other in self.agents:
            if other.id == agent.id or not other.path:
                continue
            remaining = other.path[other.path_index:]
            for t, pos in enumerate(remaining):
                reserved.add((pos[0], pos[1], t))
                if t > 0:
                    prev_pos = remaining[t - 1]
                    reserved.add((prev_pos[0], prev_pos[1], t))
            if remaining:
                gx, gy = remaining[-1]
                reservation_end = min(len(remaining) + 100, max_time)
                for t in range(len(remaining), reservation_end + 1):
                    reserved.add((gx, gy, t))

        path = astar_time(
            self.world, (agent.x, agent.y), goal,
            reserved=reserved, max_time=max_time,
        )
        self._mapf_nav_s += _time.perf_counter() - t0
        if path is None:
            return None
        raw = [pos for pos, _ in path]
        return raw[1:] if len(raw) > 1 else []

    # Planning
    def plan(self) -> bool:
        self._mrta_s = 0.0
        self._mapf_nav_s = 0.0

        tracemalloc.start()
        try:
            t0 = _time.perf_counter()

            if self.mode == "MAPF":
                success = self._plan_mapf()
            else:
                success = self._plan_mrta()

            total = _time.perf_counter() - t0
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        self.metrics["computation_s"] = total
        self.metrics["plan_mrta_s"] = self._mrta_s
        self.metrics["plan_mapf_s"] = (
            total if self.mode == "MAPF" else self._mapf_nav_s
        )
        self.metrics["memory_peak_mb"] = peak / (1024 * 1024)

        self.planned = success
        self.failed = not success
        return success

    def _plan_mapf(self) -> bool:
        paths = self.planner.plan(self.world, self.agents)
        if paths is None:
            return False
        for agent in self.agents:
            if agent.id in paths:
                raw = _expand_path(paths[agent.id])
                agent.set_path(raw[1:] if len(raw) > 1 else [])
        return True

    def _plan_mrta(self) -> bool:
        t0 = _time.perf_counter()
        assignment = self.planner.plan(self.world, self.agents, self.tasks)
        self._mrta_s = _time.perf_counter() - t0

        if not assignment:
            return False

        if self._assignment_mode == "queue":
            return self._apply_queue_assignment(assignment)
        else:
            return self._apply_online_assignment(assignment)

    #  Queue mode 
    def _apply_queue_assignment(self, assignment) -> bool:
        assigned_ids: set = set()
        self._task_queue = {}

        agents_to_nav: list = []
        for agent in self.agents:
            chain = assignment.get(agent.id, [])
            if not chain:
                continue
            first_task = chain[0]
            first_task.assigned_to = agent.id
            assigned_ids.add(first_task.id)
            agent.goal_x, agent.goal_y = first_task.x, first_task.y
            agents_to_nav.append(agent)
            remainder = chain[1:]
            for t in remainder:
                assigned_ids.add(t.id)
            self._task_queue[agent.id] = deque(remainder)

        nav_paths = self._nav_all(agents_to_nav)
        if nav_paths is None:
            return False
        for agent in agents_to_nav:
            agent.set_path(nav_paths[agent.id])
        return True

    def _pop_next_queued_task(self, agent) -> None:
        q = self._task_queue.get(agent.id)
        if not q:
            return
        task = q.popleft()
        task.assigned_to = agent.id
        agent.goal_x, agent.goal_y = task.x, task.y
        if self._nav_planner is not None:
            nav = self._nav_all([agent])
            steps = nav[agent.id] if nav else None
        else:
            steps = self._path_to_single(agent, (task.x, task.y))
        if steps is None:
            return
        agent.set_path(steps)

    #  Online mode 
    def _apply_online_assignment(self, assignment) -> bool:
        assigned_ids: set = set()
        agents_to_nav: list = []
        for agent in self.agents:
            task_list = assignment.get(agent.id, [])
            if not task_list:
                continue
            task = task_list[0]
            task.assigned_to = agent.id
            assigned_ids.add(task.id)
            agent.goal_x, agent.goal_y = task.x, task.y
            agents_to_nav.append(agent)

        nav_paths = self._nav_all(agents_to_nav)
        if nav_paths is None:
            return False
        for agent in agents_to_nav:
            agent.set_path(nav_paths[agent.id])
        self._pending_tasks = [t for t in self.tasks if t.id not in assigned_ids]
        return True

    def _try_assign_next_online(self, agent) -> None:
        if not self._pending_tasks:
            return

        t0 = _time.perf_counter()
        assignment = self.planner.plan(self.world, [agent], self._pending_tasks)
        self._mrta_s += _time.perf_counter() - t0

        if not assignment or agent.id not in assignment:
            return
        task_list = assignment[agent.id]
        if not task_list:
            return
        task = task_list[0]
        task.assigned_to = agent.id
        self._pending_tasks = [t for t in self._pending_tasks
                               if t.id != task.id]
        agent.goal_x, agent.goal_y = task.x, task.y
        if self._nav_planner is not None:
            nav = self._nav_all([agent])
            steps = nav[agent.id] if nav else None
        else:
            steps = self._path_to_single(agent, (task.x, task.y))
        if steps is None:
            return
        agent.set_path(steps)

    # Stepping
    def step(self) -> bool:
        if not self.planned:
            return False

        any_moved = False
        for agent in self.agents:
            if agent.has_path():
                nxt = agent.next_step()
                if nxt is not None:
                    agent.x, agent.y = nxt
                    any_moved = True
                    # SOC: count every individual move
                    self.metrics["soc"] += 1

        if any_moved:
            self.time += 1

        if self.mode == "MRTA":
            for task in self.tasks:
                if task.assigned_to is not None and not task.completed:
                    agent = next(
                        (a for a in self.agents if a.id == task.assigned_to),
                        None,
                    )
                    if agent and agent.x == task.x and agent.y == task.y:
                        task.completed = True
                        if self._assignment_mode == "queue":
                            self._pop_next_queued_task(agent)
                        else:
                            self._try_assign_next_online(agent)

        return any_moved

    def is_done(self) -> bool:
        if not self.planned:
            return False
        agents_idle = not any(a.has_path() for a in self.agents)
        if self.mode == "MRTA":
            if self._assignment_mode == "queue":
                queues_empty = all(
                    not q for q in self._task_queue.values()
                )
                return agents_idle and queues_empty
            else:
                return agents_idle and not self._pending_tasks
        return agents_idle

    # Metrics
    def get_metrics(self) -> dict:
        if self.is_done() and self.metrics["makespan"] == 0 and self.time > 0:
            self.metrics["makespan"] = self.time
        # Update split timings in case online MRTA added more after plan()
        self.metrics["plan_mrta_s"] = self._mrta_s
        self.metrics["plan_mapf_s"] = (
            self.metrics["computation_s"]
            if self.mode == "MAPF"
            else self._mapf_nav_s
        )
        return self.metrics

    # Reset
    def reset(self):
        self.time = 0
        self.planned = False
        self.failed = False
        self._mrta_s = 0.0
        self._mapf_nav_s = 0.0
        self.metrics = {
            "computation_s": 0.0,
            "plan_mrta_s": 0.0,
            "plan_mapf_s": 0.0,
            "memory_peak_mb": 0.0,
            "makespan": 0,
            "soc": 0,
        }

        self._pending_tasks = []
        self._task_queue = {}

        for agent_id, x, y, gx, gy in self._initial:
            agent = next(a for a in self.agents if a.id == agent_id)
            agent.x, agent.y = x, y
            agent.goal_x, agent.goal_y = gx, gy
            agent.path = []
            agent.path_with_time = []
            agent.path_index = 0

        for task in self.tasks:
            task.assigned_to = None
            task.completed = False

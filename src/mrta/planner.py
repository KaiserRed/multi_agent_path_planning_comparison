class MRTAPlanner:
    """
    Base class for all MRTA (Multi-Robot Task Assignment) planners.

    To add a new algorithm: subclass this, override `plan`, and set the
    class-level metadata attributes.

    Assignment modes
    ----------------
    "online"
        The planner assigns **one task per agent** and is called again
        whenever an agent becomes free (completes its task).  Suitable for
        fast, reactive algorithms (Hungarian, Greedy).

    "queue"
        The planner assigns an **ordered list of tasks per agent** in a
        single call, building a full task chain for each robot.  Suitable
        for algorithms whose value comes from global optimisation over all
        tasks at once (Sequential Auction, Min-Cost Flow, Combinatorial
        Auction).  The simulator follows the queue without re-planning.
    """

    ALGORITHM_TYPE: str = "MRTA"
    DISPLAY_NAME: str = "MRTA Planner"
    DESCRIPTION: str = ""
    IS_CENTRALIZED: bool = True
    IS_ONLINE: bool = False
    ASSIGNMENT_MODE: str = "online"   # "online" | "queue"

    def plan(self, world, agents, tasks) -> dict | None:
        """
        Assign tasks to agents.

        Returns
        -------
        dict[agent_id -> list[Task]]
            Each value is an ordered list of tasks for that agent.
            Online planners return single-element lists; queue planners
            return multi-element chains.
            Returns None (or empty dict) on failure.
        """
        raise NotImplementedError

    def name(self) -> str:
        return self.DISPLAY_NAME

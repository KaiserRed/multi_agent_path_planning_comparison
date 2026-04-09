class MAPFPlanner:
    """
    Base class for all MAPF (Multi-Agent Path Finding) planners.

    To add a new algorithm subclass this, override `plan`, and set the
    class-level metadata attributes.
    """

    ALGORITHM_TYPE: str = "MAPF"
    DISPLAY_NAME: str = "MAPF Planner"
    DESCRIPTION: str = ""
    IS_CENTRALIZED: bool = True
    IS_ONLINE: bool = False

    def plan(self, world, agents) -> dict | None:
        """
        Compute collision-free paths for all agents.

        Returns
        -------
        dict[agent_id -> list[(pos, time)]] or None if no solution found.
        """
        raise NotImplementedError

    def name(self) -> str:
        return self.DISPLAY_NAME

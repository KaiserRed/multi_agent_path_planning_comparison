class Task:
    """A task (target location) for MRTA planners."""

    def __init__(self, task_id: int, x: int, y: int, priority: int = 1):
        self.id = task_id
        self.x = x
        self.y = y
        self.priority = priority
        self.assigned_to: int | None = None
        self.completed: bool = False

    def __repr__(self) -> str:
        return f"Task(id={self.id}, pos=({self.x},{self.y}), agent={self.assigned_to})"

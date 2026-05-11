"""BatchConfig — all settings for a batch experiment."""

from dataclasses import dataclass, field


@dataclass
class BatchConfig:
    mapf_algos: list[str] = field(default_factory=list)
    mrta_algos: list[str] = field(default_factory=list)

    robot_min: int = 2
    robot_max: int = 8
    robot_step: int = 2

    # Map / scenario generation
    scenarios_per_n: int = 3          
    grid_w: int = 12
    grid_h: int = 12
    obstacle_density: float = 0.15
    placement: str = "uniform"        # "uniform"|"clustered"|"counter"|"min_dist"
    check_reachability: bool = True

    imported_maps: list[str] = field(default_factory=list)

    timeout_s: float = 60.0           # 0 = no timeout (simulation phase)
    plan_timeout_s: float = 30.0      # 0 = no timeout (planning phase)

    # Output
    output_dir: str = "batch_results"

"""BatchConfig — all settings for a batch experiment."""

from dataclasses import dataclass, field


@dataclass
class BatchConfig:
    # Algorithm selection
    mapf_algos: list[str] = field(default_factory=list)
    mrta_algos: list[str] = field(default_factory=list)

    # Robot count sweep
    robot_min: int = 2
    robot_max: int = 8
    robot_step: int = 2

    # Map / scenario generation
    scenarios_per_n: int = 3          # random seeds per robot count
    grid_w: int = 12
    grid_h: int = 12
    obstacle_density: float = 0.15    # 0–0.4
    placement: str = "uniform"        # "uniform"|"clustered"|"counter"|"min_dist"
    check_reachability: bool = True

    # Imported maps (if non-empty, used instead of random generation)
    imported_maps: list[str] = field(default_factory=list)

    # Run control
    timeout_s: float = 60.0           # 0 = no timeout

    # Output
    output_dir: str = "batch_results"

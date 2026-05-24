"""BatchRunner — headless execution of MAPF+MRTA experiments.

Each run gets its own Simulator instance.  Timeout is enforced via a
threading.Timer that sets a flag; the simulation loop checks it and
aborts early.
"""

from __future__ import annotations

import csv
import gc
import os
import random as _rnd
import threading
import time as _time
from typing import Callable

import pandas as pd

from batch.config import BatchConfig
from batch.generator import SceneGenerator
from core.agent import Agent
from core.task import Task
from core.world import World
from registry import ALGORITHMS, get_planner
from simulation.simulator import Simulator


_GENERATOR = SceneGenerator()

COLUMNS = [
    "mrta_algo", "mapf_algo", "n_robots", "scenario_seed",
    "map_width", "map_height", "obstacle_density", "placement",
    "scene_source",
    "success", "makespan", "soc",
    "plan_total_s", "plan_mrta_s", "plan_mapf_s", "memory_mb",
]


def _build_scene(scene_data, algo_type: str):
    """Reuse the same logic as main.py._build_scene."""
    from scenario import SceneData
    world = World(scene_data.grid_width, scene_data.grid_height,
                  scene_data.obstacles)
    agents: list[Agent] = []
    tasks: list[Task] = []

    if algo_type == "MAPF":
        n = min(len(scene_data.agent_starts), len(scene_data.goals))
        for i in range(n):
            sx, sy = scene_data.agent_starts[i]
            gx, gy = scene_data.goals[i]
            agents.append(Agent(i, sx, sy, gx, gy))
    else:
        for i, (sx, sy) in enumerate(scene_data.agent_starts):
            agents.append(Agent(i, sx, sy, sx, sy))
        for i, (gx, gy) in enumerate(scene_data.goals):
            tasks.append(Task(i, gx, gy))

    return world, agents, tasks


def _run_single(
    scene_data,
    mrta_name: str,
    mapf_name: str,
    timeout_s: float,
    plan_timeout_s: float = 0.0,
) -> dict:
    """Run one scenario and return a result-row dict."""
    row: dict = {
        "mrta_algo": mrta_name,
        "mapf_algo": mapf_name,
        "n_robots": len(scene_data.agent_starts),
        "success": False,
        "makespan": 0,
        "soc": 0,
        "plan_total_s": 0.0,
        "plan_mrta_s": 0.0,
        "plan_mapf_s": 0.0,
        "memory_mb": 0.0,
    }

    try:
        mrta_planner = get_planner("MRTA", mrta_name)
        nav_planner = get_planner("MAPF", mapf_name)

        world, agents, tasks = _build_scene(scene_data, "MRTA")
        sim = Simulator(world, agents, mrta_planner, tasks,
                        nav_planner=nav_planner)

        plan_result: list = [False]
        plan_exc:    list = [None]

        def _do_plan():
            try:
                plan_result[0] = sim.plan()
            except Exception as exc: 
                plan_exc[0] = exc

        plan_thread = threading.Thread(target=_do_plan, daemon=True)
        plan_thread.start()
        join_t = plan_timeout_s if plan_timeout_s > 0 else None
        plan_thread.join(timeout=join_t)

        if plan_thread.is_alive():
            return row

        if plan_exc[0] is not None:
            raise plan_exc[0]

        success = plan_result[0]

        timed_out = threading.Event()
        timer = None
        if timeout_s > 0:
            def _timeout():
                timed_out.set()
            timer = threading.Timer(timeout_s, _timeout)
            timer.start()

        if success:
            max_steps = world.width * world.height * len(agents) * 4
            step_count = 0
            while not sim.is_done() and step_count < max_steps:
                if timed_out.is_set():
                    success = False
                    break
                sim.step()
                step_count += 1

            if sim.is_done():
                success = True
            else:
                success = False

        if timer is not None:
            timer.cancel()

        m = sim.get_metrics()
        row["success"] = success
        row["makespan"] = sim.time if success else 0
        row["soc"] = m.get("soc", 0)
        row["plan_total_s"] = m.get("computation_s", 0.0)
        row["plan_mrta_s"] = m.get("plan_mrta_s", 0.0)
        row["plan_mapf_s"] = m.get("plan_mapf_s", 0.0)
        row["memory_mb"] = m.get("memory_peak_mb", 0.0)

    except Exception:
        row["success"] = False
        row["makespan"] = 0

    return row


class BatchRunner:
    """Run all combinations and report progress via a callback."""

    def run(
        self,
        config: BatchConfig,
        progress_cb: Callable[[float, str], None] | None = None,
    ) -> pd.DataFrame:
        """Execute the full batch.

        *progress_cb(fraction, current_label)* is called after every
        individual run (0.0 → 1.0).

        Returns a pandas DataFrame with columns defined in ``COLUMNS``.
        """
        mapf_algos = config.mapf_algos or [
            p.DISPLAY_NAME for p in ALGORITHMS["MAPF"]
        ]
        mrta_algos = config.mrta_algos or [
            p.DISPLAY_NAME for p in ALGORITHMS["MRTA"]
        ]

        robot_counts = list(range(
            config.robot_min, config.robot_max + 1, config.robot_step
        ))
        if not robot_counts:
            robot_counts = [config.robot_min]

        combos = [
            (mrta, mapf)
            for mrta in mrta_algos
            for mapf in mapf_algos
        ]

        total = (
            len(combos)
            * len(robot_counts)
            * config.scenarios_per_n
        )
        completed = 0

        rows: list[dict] = []

        os.makedirs(config.output_dir, exist_ok=True)
        partial_path = os.path.join(config.output_dir, "_partial.csv")
        partial_file = open(partial_path, "w", newline="", encoding="utf-8")
        writer = csv.DictWriter(partial_file, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()

        try:
            for mrta_name, mapf_name in combos:
                for n_robots in robot_counts:
                    for seed in range(config.scenarios_per_n):
                        label = (
                            f"{mrta_name} + {mapf_name} | "
                            f"robots={n_robots} seed={seed}"
                        )

                        scene = _GENERATOR.generate(config, n_robots, seed)

                        if config.scen_files:
                            _picked = _rnd.Random(seed).choice(config.scen_files)
                            scene_source = f"scen:{os.path.basename(_picked)}"
                            placement_label = "scen"
                        elif config.imported_maps:
                            scene_source = "imported"
                            placement_label = "imported"
                        else:
                            scene_source = "random"
                            placement_label = config.placement

                        if scene is None:
                            row = {
                                "mrta_algo": mrta_name,
                                "mapf_algo": mapf_name,
                                "n_robots": n_robots,
                                "scenario_seed": seed,
                                "map_width": 0,
                                "map_height": 0,
                                "obstacle_density": 0.0,
                                "placement": placement_label,
                                "scene_source": scene_source,
                                "success": False,
                                "makespan": 0,
                                "soc": 0,
                                "plan_total_s": 0.0,
                                "plan_mrta_s": 0.0,
                                "plan_mapf_s": 0.0,
                                "memory_mb": 0.0,
                            }
                        else:
                            row = _run_single(
                                scene, mrta_name, mapf_name,
                                config.timeout_s,
                                config.plan_timeout_s,
                            )
                            row["scenario_seed"] = seed
                            row["n_robots"] = n_robots
                            w, h = scene.grid_width, scene.grid_height
                            row["map_width"] = w
                            row["map_height"] = h
                            row["obstacle_density"] = round(
                                len(scene.obstacles) / (w * h), 4
                            ) if w * h > 0 else 0.0
                            row["placement"] = placement_label
                            row["scene_source"] = scene_source

                        gc.collect()

                        rows.append(row)
                        writer.writerow(row)
                        partial_file.flush()
                        completed += 1

                        if progress_cb is not None:
                            progress_cb(completed / total, label)
        finally:
            partial_file.close()
            try:
                os.remove(partial_path)
            except OSError:
                pass

        df = pd.DataFrame(rows, columns=COLUMNS)
        return df

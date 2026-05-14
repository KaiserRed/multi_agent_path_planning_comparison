"""
Entry point.

Flow
----
1. Main menu  →  Create / Load / Batch
2. Editor     →  design the world (obstacles, agents, goals)
3. Algo Select →  pick MAPF or MRTA algorithm
4. Simulation  →  watch agents move
   [ESC] from simulation returns to Algo Select (map preserved).
   [ESC] from Algo Select returns to Editor (map preserved).
   [ESC] / Cancel from Editor returns to Main Menu.
"""

from __future__ import annotations

import sys

import pygame

from core.agent import Agent
from core.task import Task
from core.world import World
from registry import get_planner
from scenario import SceneData, load_map_file, load_scenario
from simulation.simulator import Simulator
from ui.algo_select import AlgoSelect
from ui.batch_ui import (
    BatchAlgoScreen, BatchMapScreen, BatchProgressScreen,
    BATCH_W, BATCH_H,
)
from ui.editor import WorldEditor, SIDE_W as EDITOR_SIDE_W, _fit_cell
from ui.menu import MainMenu, MENU_W, MENU_H
from visualization.render import draw_simulation, _SIDE_W as SIM_SIDE_W


# Helpers
def _editor_win_size(scene: SceneData) -> tuple[int, int]:
    cs = _fit_cell(scene.grid_width, scene.grid_height, 720, 660)
    w = max(scene.grid_width * cs + EDITOR_SIDE_W + 20, 640)
    h = max(scene.grid_height * cs + 20, 520)
    return w, h


def _sim_win_size(world: World) -> tuple[int, int]:
    cs = _cell_size(world)
    w = world.width * cs + SIM_SIDE_W
    h = max(world.height * cs, 360)
    return w, h


def _cell_size(world: World) -> int:
    avail = max(world.width * 16 + SIM_SIDE_W, 520)
    return max(16, min(60,
                       (avail - SIM_SIDE_W) // world.width,
                       max(world.height * 16, 360) // world.height))


def _build_scene(scene: SceneData, algo_type: str):
    """Convert algorithm-agnostic SceneData into (World, agents, tasks)."""
    world = World(scene.grid_width, scene.grid_height, scene.obstacles)
    agents: list[Agent] = []
    tasks: list[Task] = []

    if algo_type == "MAPF":
        n = min(len(scene.agent_starts), len(scene.goals))
        for i in range(n):
            sx, sy = scene.agent_starts[i]
            gx, gy = scene.goals[i]
            agents.append(Agent(i, sx, sy, gx, gy))
    else:
        for i, (sx, sy) in enumerate(scene.agent_starts):
            agents.append(Agent(i, sx, sy, sx, sy))
        for i, (gx, gy) in enumerate(scene.goals):
            tasks.append(Task(i, gx, gy))

    return world, agents, tasks


def _load_file_dialog() -> str | None:
    """Open a native file-open dialog (tkinter) and return the chosen path."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title="Load Map",
            filetypes=[
                ("Map files", "*.json *.map *.scen"),
                ("JSON files", "*.json"),
                ("MovingAI maps", "*.map"),
                ("MovingAI scenarios", "*.scen"),
                ("All files", "*.*"),
            ],
        )
        root.destroy()
        return path if path else None
    except Exception:
        return None


# Screen runners
def run_menu(clock: pygame.time.Clock) -> str | None:
    """
    Show the main menu.  Returns ``"create"``, ``"load"``, or ``None`` (quit).
    """
    screen = pygame.display.set_mode((MENU_W, MENU_H))
    pygame.display.set_caption("Multi-Robot System Evaluator")
    menu = MainMenu(screen)

    while True:
        clock.tick(60)
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT:
                return None

        result = menu.handle_events(events)
        menu.update()
        menu.draw()

        if result in ("create", "load", "batch", "quit"):
            return result


def run_editor(
    clock: pygame.time.Clock,
    scene: SceneData | None = None,
) -> SceneData | None:
    """
    Open the editor.  Returns ``SceneData`` on Done, ``None`` on Cancel.
    """
    if scene is None:
        scene = SceneData()

    win_w, win_h = _editor_win_size(scene)
    screen = pygame.display.set_mode((win_w, win_h))
    pygame.display.set_caption("World Editor")

    editor = WorldEditor(screen, scene)

    while True:
        dt = clock.tick(60)
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        result = editor.handle_events(events)
        editor.update(dt)
        editor.draw()

        if result == "done":
            return editor.get_scene_data()
        if result == "cancel":
            return None


def run_algo_select(
    clock: pygame.time.Clock,
    scene: SceneData,
) -> dict | str | None:
    """
    Returns ``{"algo_type": ..., "algo_name": ..., "nav_algo_name": ...}``
    on START, ``"back"`` when user wants to return to editor,
    or ``None`` on window close.
    """
    win_w, win_h = _editor_win_size(scene)
    screen = pygame.display.set_mode((win_w, win_h))
    pygame.display.set_caption("Select Algorithm")

    selector = AlgoSelect(screen, scene)

    while True:
        clock.tick(60)
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        result = selector.handle_events(events)
        selector.update()
        selector.draw()

        if isinstance(result, dict):
            return result
        if result == "back":
            return "back"


def run_simulation(
    clock: pygame.time.Clock,
    scene: SceneData,
    algo_type: str,
    algo_name: str,
    nav_algo_name: str = "",
) -> None:
    """Run the simulation.  Returns when the user presses ESC."""
    world, agents, tasks = _build_scene(scene, algo_type)
    planner = get_planner(algo_type, algo_name)

    nav_planner = None
    if algo_type == "MRTA" and nav_algo_name:
        try:
            nav_planner = get_planner("MAPF", nav_algo_name)
        except KeyError:
            nav_planner = None

    simulator = Simulator(world, agents, planner, tasks, nav_planner=nav_planner)

    cs = _cell_size(world)
    win_w, win_h = _sim_win_size(world)
    screen = pygame.display.set_mode((win_w, win_h))
    pygame.display.set_caption(f"Simulation — {algo_name}")

    font_h = pygame.font.SysFont("Arial", 14, bold=True)
    font_b = pygame.font.SysFont("Arial", 13)
    font_s = pygame.font.SysFont("Arial", 12)

    simulator.plan()

    paused = False
    show_paths = True
    step_delay = 250
    last_step = pygame.time.get_ticks()

    while True:
        dt = clock.tick(60)
        now = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return

                elif event.key == pygame.K_SPACE:
                    paused = not paused

                elif event.key == pygame.K_r:
                    simulator.reset()
                    simulator.plan()
                    paused = False
                    last_step = pygame.time.get_ticks()

                elif event.key == pygame.K_p:
                    show_paths = not show_paths

                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS,
                                   pygame.K_KP_PLUS):
                    step_delay = max(50, step_delay - 50)

                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    step_delay = min(2000, step_delay + 100)

        if (not paused
                and simulator.planned
                and not simulator.is_done()
                and now - last_step >= step_delay):
            simulator.step()
            last_step = now

        draw_simulation(
            screen, world, agents, tasks, cs,
            planner, simulator,
            font_h, font_b, font_s,
            show_paths=show_paths,
        )


# Batch runner
def run_batch(clock: pygame.time.Clock) -> None:
    """Three-screen Batch Mode flow."""
    screen = pygame.display.set_mode((BATCH_W, BATCH_H))
    pygame.display.set_caption("Batch Mode")

    #  Screen 1: algorithm selection 
    algo_screen = BatchAlgoScreen(screen)
    while True:
        clock.tick(60)
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        result = algo_screen.handle_events(events)
        algo_screen.update()
        algo_screen.draw()
        if result == "back":
            return
        if result == "next":
            break

    mapf_algos, mrta_algos = algo_screen.get_selection()

    #  Screen 2: map / parameters 
    map_screen = BatchMapScreen(screen, mapf_algos, mrta_algos)
    while True:
        dt = clock.tick(60)
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        result = map_screen.handle_events(events)
        map_screen.update(dt)
        map_screen.draw()
        if result == "back":
            # Return to algo screen
            algo_screen = BatchAlgoScreen(screen)
            while True:
                clock.tick(60)
                events = pygame.event.get()
                for e in events:
                    if e.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                result2 = algo_screen.handle_events(events)
                algo_screen.update()
                algo_screen.draw()
                if result2 == "back":
                    return
                if result2 == "next":
                    break
            mapf_algos, mrta_algos = algo_screen.get_selection()
            map_screen = BatchMapScreen(screen, mapf_algos, mrta_algos)
            continue
        if result == "run":
            break

    config = map_screen.build_config()

    #  Screen 3: progress 
    progress_screen = BatchProgressScreen(screen, config)
    while True:
        clock.tick(30)
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        result = progress_screen.handle_events(events)
        progress_screen.update()
        progress_screen.draw()
        if result == "menu":
            return


# Main loop
def main():
    pygame.init()
    pygame.font.init()
    clock = pygame.time.Clock()

    while True:
        # Main menu 
        action = run_menu(clock)

        if action is None or action == "quit":
            break

        if action == "batch":
            run_batch(clock)
            continue

        # Determine initial scene 
        scene: SceneData | None = None
        if action == "load":
            path = _load_file_dialog()
            if path:
                try:
                    scene = load_map_file(path)
                except Exception:
                    scene = None
            if scene is None:
                continue

        scene = run_editor(clock, scene)
        if scene is None:
            continue

        while True:
            result = run_algo_select(clock, scene)
            if result == "back" or result is None:
                scene = run_editor(clock, scene)
                if scene is None:
                    break
                continue

            run_simulation(
                clock, scene,
                result["algo_type"],
                result["algo_name"],
                result.get("nav_algo_name", ""),
            )

    pygame.quit()


if __name__ == "__main__":
    main()

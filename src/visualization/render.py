"""
Pygame rendering for the simulation view.

Layout
------
Left area  : grid (world + agents + goals/tasks + paths)
Right panel: algorithm info, metrics, controls
"""

import pygame
from ui.widgets import COLORS

_SIDE_W = 240


def _draw_grid(surface, world, cell_size):
    for y in range(world.height):
        for x in range(world.width):
            rect = pygame.Rect(x * cell_size, y * cell_size, cell_size, cell_size)
            bg = COLORS["grid_obstacle"] if world.grid[y, x] == 1 else COLORS["grid_free"]
            pygame.draw.rect(surface, bg, rect)
            pygame.draw.rect(surface, COLORS["grid_border"], rect, 1)


def _draw_paths(surface, agents, cell_size):
    for agent in agents:
        if not agent.path:
            continue
        for i in range(agent.path_index, len(agent.path)):
            px, py = agent.path[i]
            cx = px * cell_size + cell_size // 2
            cy = py * cell_size + cell_size // 2
            pygame.draw.circle(
                surface, (*agent.color, 100), (cx, cy), max(2, cell_size // 8),
            )


def _draw_goals_mapf(surface, agents, cell_size):
    for agent in agents:
        cx = agent.goal_x * cell_size + cell_size // 2
        cy = agent.goal_y * cell_size + cell_size // 2
        r = max(3, cell_size // 3)
        pygame.draw.circle(surface, agent.color, (cx, cy), r, 2)
        pygame.draw.line(surface, agent.color,
                         (cx - r + 2, cy), (cx + r - 2, cy), 1)
        pygame.draw.line(surface, agent.color,
                         (cx, cy - r + 2), (cx, cy + r - 2), 1)


def _draw_tasks(surface, tasks, cell_size, font):
    for task in tasks:
        cx = task.x * cell_size + cell_size // 2
        cy = task.y * cell_size + cell_size // 2
        half = max(4, cell_size // 3)
        color = (100, 100, 100) if task.completed else COLORS["task"]
        diamond = [
            (cx,        cy - half),
            (cx + half, cy),
            (cx,        cy + half),
            (cx - half, cy),
        ]
        pygame.draw.polygon(surface, color, diamond)
        if font and not task.completed:
            t = font.render(str(task.id), True, (0, 0, 0))
            surface.blit(t, t.get_rect(center=(cx, cy)))


def _draw_agents(surface, agents, cell_size, font):
    pad = max(2, cell_size // 8)
    for agent in agents:
        rect = pygame.Rect(
            agent.x * cell_size + pad,
            agent.y * cell_size + pad,
            cell_size - pad * 2,
            cell_size - pad * 2,
        )
        pygame.draw.rect(surface, agent.color, rect, border_radius=4)
        if font:
            t = font.render(str(agent.id), True, (255, 255, 255))
            surface.blit(t, t.get_rect(center=rect.center))


def _draw_side_panel(surface, planner, simulator, font_h, font_b, font_s):
    W, H = surface.get_size()
    grid_w = W - _SIDE_W
    px, py, pw, ph = grid_w + 5, 5, _SIDE_W - 10, H - 10

    s = pygame.Surface((pw, ph), pygame.SRCALPHA)
    s.fill((*COLORS["panel"], 220))
    surface.blit(s, (px, py))
    pygame.draw.rect(surface, COLORS["border"], (px, py, pw, ph), 1,
                     border_radius=8)

    oy = py + 12
    cx = px + pw // 2

    def line(text, font, color=COLORS["text"], center=True):
        nonlocal oy
        surf = font.render(text, True, color)
        if center:
            surface.blit(surf, surf.get_rect(centerx=cx, y=oy))
        else:
            surface.blit(surf, (px + 10, oy))
        oy += surf.get_height() + 4

    def sep():
        nonlocal oy
        oy += 4
        pygame.draw.line(surface, COLORS["border"],
                         (px + 8, oy), (px + pw - 8, oy))
        oy += 8

    # Algorithm info
    line(planner.DISPLAY_NAME, font_h, COLORS["accent"])
    ctype = "Centralized" if planner.IS_CENTRALIZED else "Decentralized"
    mode = "Online" if planner.IS_ONLINE else "Offline"
    line(f"{planner.ALGORITHM_TYPE}  ·  {ctype}", font_s, COLORS["text_muted"])
    line(mode, font_s, COLORS["text_muted"])

    sep()

    # Status
    if simulator.failed:
        status, sc = "FAILED", COLORS["error"]
    elif simulator.is_done():
        status, sc = "DONE", COLORS["success"]
    elif simulator.planned:
        status, sc = "RUNNING", COLORS["accent"]
    else:
        status, sc = "PLANNING...", COLORS["text_muted"]
    line(status, font_h, sc)

    sep()

    # Metrics
    line("METRICS", font_h, COLORS["accent"])
    oy += 2
    m = simulator.metrics
    line(f"Makespan: {simulator.time}", font_b, center=False)
    if m.get("soc"):
        line(f"SOC:      {m['soc']}", font_b, center=False)
    line(f"Calc:     {m['computation_s']:.4f}s", font_b, center=False)
    if m.get("plan_mrta_s"):
        line(f"  MRTA:   {m['plan_mrta_s']:.4f}s", font_b, center=False)
    if m.get("plan_mapf_s"):
        line(f"  MAPF:   {m['plan_mapf_s']:.4f}s", font_b, center=False)
    line(f"Memory:   {m.get('memory_peak_mb', 0):.2f} MB", font_b, center=False)

    sep()

    # Controls
    line("CONTROLS", font_h, COLORS["accent"])
    for key, action in [("[SPACE]", "Pause / Resume"),
                        ("[R]",     "Restart"),
                        ("[P]",     "Toggle paths"),
                        ("[ESC]",   "Back"),
                        ("[+/-]",   "Speed")]:
        oy += 2
        ks = font_s.render(key, True, COLORS["accent"])
        surface.blit(ks, (px + 10, oy))
        vs = font_s.render(action, True, COLORS["text_muted"])
        surface.blit(vs, (px + 10 + ks.get_width() + 6, oy))
        oy += ks.get_height() + 5


def draw_simulation(surface: pygame.Surface, world, agents, tasks,
                    cell_size: int, planner, simulator,
                    font_h, font_b, font_s, show_paths: bool = True):
    surface.fill(COLORS["bg"])
    _draw_grid(surface, world, cell_size)

    if show_paths:
        _draw_paths(surface, agents, cell_size)

    if tasks:
        _draw_tasks(surface, tasks, cell_size, font_s)
    else:
        _draw_goals_mapf(surface, agents, cell_size)

    _draw_agents(surface, agents, cell_size, font_b)
    _draw_side_panel(surface, planner, simulator, font_h, font_b, font_s)

    if simulator.is_done():
        W, H = surface.get_size()
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 80))
        surface.blit(overlay, (0, 0))
        msg = font_h.render(
            "Simulation complete — press [R] to restart",
            True, COLORS["success"],
        )
        surface.blit(msg, msg.get_rect(
            centerx=(W - _SIDE_W) // 2, centery=H // 2,
        ))

    pygame.display.flip()

"""
Interactive world editor.

The editor is **algorithm-agnostic**: it exposes four tools —
Obstacle, Agent Start, Goal, Erase — and produces a
:class:`scenario.SceneData` object.  The interpretation of *goals*
(MAPF per-agent targets vs MRTA tasks) is decided later when the user
picks an algorithm.

Controls
--------
Left-click / drag  : apply current tool
Right-click / drag : erase whatever is on the cell
1-4                : quick tool selection
[ESC]              : cancel (back to main menu)
"""

from __future__ import annotations

import pygame

from scenario import SceneData, load_map_file, save_scenario
from ui.dialogs import open_file, save_file
from ui.widgets import COLORS, Button, NumberInput, draw_panel

AGENT_COLORS = [
    (255,   0,   0),
    (  0,   0, 255),
    (255, 165,   0),
    (128,   0, 128),
    (  0, 200,   0),
    (255,   0, 255),
    (  0, 220, 220),
    (200, 200,   0),
]

GOAL_COLOR = (100, 220, 100)

SIDE_W   = 240
MIN_CELL = 12
MAX_CELL = 64


def _fit_cell(grid_w: int, grid_h: int, avail_w: int, avail_h: int) -> int:
    return max(MIN_CELL, min(MAX_CELL, avail_w // max(grid_w, 1),
                             avail_h // max(grid_h, 1)))



def draw_scene_preview(
    surface: pygame.Surface,
    grid_w: int, grid_h: int,
    obstacles, agent_starts, goals,
    cs: int, ox: int, oy: int,
    font_small: pygame.font.Font | None = None,
    hover_cell: tuple | None = None,
):
    """Render the grid, obstacles, goals, and agent starts."""
    for gy in range(grid_h):
        for gx in range(grid_w):
            rx, ry = ox + gx * cs, oy + gy * cs
            rect = pygame.Rect(rx, ry, cs, cs)
            bg = (52, 57, 80) if (gx, gy) in obstacles else (28, 38, 65)
            pygame.draw.rect(surface, bg, rect)
            pygame.draw.rect(surface, (46, 59, 96), rect, 1)

    goal_set = set() if isinstance(goals, set) else goals
    for idx, (gx, gy) in enumerate(goals):
        cx = ox + gx * cs + cs // 2
        cy = oy + gy * cs + cs // 2
        h = max(4, cs // 3)
        diamond = [(cx, cy - h), (cx + h, cy), (cx, cy + h), (cx - h, cy)]
        pygame.draw.polygon(surface, GOAL_COLOR, diamond)
        if cs >= 20 and font_small:
            t = font_small.render(f"G{idx}", True, (20, 20, 20))
            surface.blit(t, t.get_rect(center=(cx, cy)))

    pad = max(2, cs // 7)
    for idx, (sx, sy) in enumerate(agent_starts):
        color = AGENT_COLORS[idx % len(AGENT_COLORS)]
        rect = pygame.Rect(
            ox + sx * cs + pad, oy + sy * cs + pad,
            cs - pad * 2, cs - pad * 2,
        )
        pygame.draw.rect(surface, color, rect, border_radius=4)
        if cs >= 20 and font_small:
            t = font_small.render(f"A{idx}", True, (255, 255, 255))
            surface.blit(t, t.get_rect(center=rect.center))

    if hover_cell:
        rx = ox + hover_cell[0] * cs
        ry = oy + hover_cell[1] * cs
        hl = pygame.Surface((cs, cs), pygame.SRCALPHA)
        hl.fill((255, 255, 255, 28))
        surface.blit(hl, (rx, ry))

class WorldEditor:
    """
    handle_events() returns:
      ``"done"``   → proceed to algorithm selection
      ``"cancel"`` → back to main menu
      ``None``     → keep looping
    """

    TOOLS = ["Obstacle", "Agent Start", "Goal", "Erase"]

    def __init__(self, screen: pygame.Surface,
                 scene: SceneData | None = None):
        self.screen = screen

        pygame.font.init()
        self._fh = pygame.font.SysFont("Arial", 15, bold=True)
        self._fb = pygame.font.SysFont("Arial", 13)
        self._fs = pygame.font.SysFont("Arial", 12)
        self._ft = pygame.font.SysFont("Arial", 11)

        if scene:
            self.grid_w = scene.grid_width
            self.grid_h = scene.grid_height
            self.obstacles: set = set(tuple(p) for p in scene.obstacles)
            self.agent_starts: list = [tuple(p) for p in scene.agent_starts]
            self.goals: list = [tuple(p) for p in scene.goals]
        else:
            self.grid_w = 10
            self.grid_h = 10
            self.obstacles = set()
            self.agent_starts = []
            self.goals = []

        self.tool = self.TOOLS[0]

        self._layout()
        self._build_widgets()

        self._dragging = False
        self._drag_right = False
        self._drag_last = None
        self._error: str | None = None
        self._saved_msg: str | None = None
        self._saved_timer: int = 0

        self._view_scale: float = 1.0
        self._view_pan: list[float] = [0.0, 0.0]
        self._pan_dragging: bool = False
        self._pan_last: tuple[int, int] = (0, 0)

    def _layout(self):
        W, H = self.screen.get_size()
        avail_w = W - SIDE_W - 10
        avail_h = H - 10
        self.cs = _fit_cell(self.grid_w, self.grid_h, avail_w, avail_h)
        self.ox = max(5, (avail_w - self.cs * self.grid_w) // 2)
        self.oy = max(5, (avail_h - self.cs * self.grid_h) // 2)

    def reflow(self):
        """Recompute grid layout and rebuild all widgets after window resize."""
        self._layout()
        self._build_widgets()

    def _build_widgets(self):
        W, H = self.screen.get_size()
        sx = W - SIDE_W + 10
        sw = SIDE_W - 20

        half = (sw - 30) // 2
        self._w_input = NumberInput(
            (sx, 38, half, 28), self.grid_w, self._fs, 3, 1000,
        )
        self._h_input = NumberInput(
            (sx + half + 30, 38, half, 28), self.grid_h, self._fs, 3, 1000,
        )
        self._apply_btn = Button(
            (sx, 72, sw, 28), "Apply Size", self._ft,
        )

        self._tool_btns: list[Button] = []
        for i, name in enumerate(self.TOOLS):
            btn = Button((sx, 120 + i * 38, sw, 32), name, self._fb)
            btn.active = (name == self.tool)
            self._tool_btns.append(btn)

        self._cancel_btn = Button((sx, H - 42, sw, 30), "Cancel", self._fs)
        self._done_btn = Button(
            (sx, H - 80, sw, 34), "Done", self._fb, primary=True,
        )
        self._clear_btn = Button((sx, H - 118, sw, 30), "Clear All", self._fs)
        self._save_btn = Button((sx, H - 154, sw, 30), "Save JSON", self._fs)
        self._load_btn = Button((sx, H - 190, sw, 30), "Load Map", self._fs)

        self._inputs = [self._w_input, self._h_input]

    def _effective_layout(self) -> tuple[int, int, int]:
        """Return (effective_cell_size, effective_ox, effective_oy) with zoom/pan."""
        ecs = max(1, int(self.cs * self._view_scale))
        eox = self.ox + int(self._view_pan[0])
        eoy = self.oy + int(self._view_pan[1])
        return ecs, eox, eoy

    def _reset_view(self):
        self._view_scale = 1.0
        self._view_pan = [0.0, 0.0]

    def _cell_at(self, mx: int, my: int) -> tuple | None:
        ecs, eox, eoy = self._effective_layout()
        if ecs < 1:
            return None
        gx = (mx - eox) // ecs
        gy = (my - eoy) // ecs
        if 0 <= gx < self.grid_w and 0 <= gy < self.grid_h:
            return (int(gx), int(gy))
        return None

    def _is_empty(self, cell: tuple) -> bool:
        return (cell not in self.obstacles
                and cell not in self.agent_starts
                and cell not in self.goals)

    def _erase(self, cell: tuple):
        self.obstacles.discard(cell)
        if cell in self.agent_starts:
            self.agent_starts.remove(cell)
        if cell in self.goals:
            self.goals.remove(cell)

    def _apply(self, cell: tuple, right: bool):
        if right:
            self._erase(cell)
            return
        if self.tool == "Obstacle":
            if cell in self.obstacles:
                self.obstacles.discard(cell)
            elif self._is_empty(cell):
                self.obstacles.add(cell)
        elif self.tool == "Erase":
            self._erase(cell)
        elif self.tool == "Agent Start":
            if self._is_empty(cell) and len(self.agent_starts) < 50:
                self.agent_starts.append(cell)
        elif self.tool == "Goal":
            if self._is_empty(cell) and len(self.goals) < 50:
                self.goals.append(cell)

    def _apply_resize(self):
        new_w = self._w_input.get_value()
        new_h = self._h_input.get_value()
        if new_w == self.grid_w and new_h == self.grid_h:
            return
        self.grid_w = new_w
        self.grid_h = new_h
        self.obstacles = {
            (x, y) for x, y in self.obstacles if x < new_w and y < new_h
        }
        self.agent_starts = [
            (x, y) for x, y in self.agent_starts if x < new_w and y < new_h
        ]
        self.goals = [
            (x, y) for x, y in self.goals if x < new_w and y < new_h
        ]
        self._layout()

    def _do_load(self):
        path = open_file(
            title="Load Map",
            filetypes=[
                ("Map files", "*.json *.map *.scen"),
                ("JSON files", "*.json"),
                ("MovingAI maps", "*.map"),
                ("MovingAI scenarios", "*.scen"),
                ("All files", "*"),
            ],
        )
        if not path:
            return
        try:
            scene = load_map_file(path)
        except Exception as exc:
            self._error = f"Load failed: {exc}"
            return

        self.grid_w = scene.grid_width
        self.grid_h = scene.grid_height
        self.obstacles = set(tuple(p) for p in scene.obstacles)
        starts = [tuple(p) for p in scene.agent_starts]
        gs = [tuple(p) for p in scene.goals]
        self.agent_starts = starts[:50]
        self.goals = gs[:50]
        self._error = None
        self._layout()
        self._build_widgets()

    def _do_save(self):
        path = save_file(
            title="Save Scenario",
            filetypes=[("JSON files", "*.json")],
            default_ext=".json",
        )
        if path:
            save_scenario(self.get_scene_data(), path)
            self._saved_msg = "Saved!"
            self._saved_timer = 2000

    def get_scene_data(self) -> SceneData:
        return SceneData(
            grid_width=self.grid_w,
            grid_height=self.grid_h,
            obstacles=list(self.obstacles),
            agent_starts=list(self.agent_starts),
            goals=list(self.goals),
        )

    def handle_events(self, events: list) -> str | None:
        any_input_active = any(inp.active for inp in self._inputs)
        W, H = self.screen.get_size()
        grid_right = W - SIDE_W 

        for event in events:
            # Zoom
            if event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if mx < grid_right:
                    factor = 1.15 if event.y > 0 else (1.0 / 1.15)
                    old_scale = self._view_scale
                    new_scale = max(0.15, min(10.0, old_scale * factor))
                    if new_scale != old_scale:
                        old_pan_x, old_pan_y = self._view_pan
                        ratio = new_scale / old_scale
                        self._view_pan[0] = mx - self.ox - (mx - self.ox - old_pan_x) * ratio
                        self._view_pan[1] = my - self.oy - (my - self.oy - old_pan_y) * ratio
                        self._view_scale = new_scale

            # Pan
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
                if event.pos[0] < grid_right:
                    self._pan_dragging = True
                    self._pan_last = event.pos
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                self._pan_dragging = False
            elif event.type == pygame.MOUSEMOTION and self._pan_dragging:
                dx = event.pos[0] - self._pan_last[0]
                dy = event.pos[1] - self._pan_last[1]
                self._view_pan[0] += dx
                self._view_pan[1] += dy
                self._pan_last = event.pos

            if event.type == pygame.KEYDOWN and not any_input_active:
                if event.key == pygame.K_ESCAPE:
                    return "cancel"
                if event.key in (pygame.K_0, pygame.K_KP0, pygame.K_HOME):
                    self._reset_view()
                for i, name in enumerate(self.TOOLS):
                    if event.unicode == str(i + 1):
                        self._select_tool(name)

            for inp in self._inputs:
                inp.handle_event(event)

            if self._apply_btn.handle_event(event):
                self._apply_resize()

            for btn in self._tool_btns:
                if btn.handle_event(event):
                    self._select_tool(btn.text)

            if self._load_btn.handle_event(event):
                self._do_load()

            if self._save_btn.handle_event(event):
                self._do_save()

            if self._clear_btn.handle_event(event):
                self.obstacles.clear()
                self.agent_starts.clear()
                self.goals.clear()
                self._error = None

            if self._done_btn.handle_event(event):
                self._error = self._validate()
                if self._error is None:
                    return "done"

            if self._cancel_btn.handle_event(event):
                return "cancel"

            if event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
                if not self._pan_dragging and event.pos[0] < grid_right:
                    cell = self._cell_at(*event.pos)
                    if cell:
                        self._dragging = True
                        self._drag_right = (event.button == 3)
                        self._drag_last = cell
                        self._apply(cell, self._drag_right)
            elif event.type == pygame.MOUSEBUTTONUP and event.button in (1, 3):
                self._dragging = False
                self._drag_last = None
            elif event.type == pygame.MOUSEMOTION and self._dragging and not self._pan_dragging:
                cell = self._cell_at(*event.pos)
                if cell and cell != self._drag_last:
                    self._drag_last = cell
                    self._apply(cell, self._drag_right)

        return None

    def _select_tool(self, name: str):
        self.tool = name
        for btn in self._tool_btns:
            btn.active = (btn.text == name)

    def _validate(self) -> str | None:
        if not self.agent_starts:
            return "Place at least one Agent Start"
        if not self.goals:
            return "Place at least one Goal"
        return None

    def update(self, dt_ms: int = 16):
        for btn in self._tool_btns:
            btn.update()
        self._apply_btn.update()
        self._load_btn.update()
        self._save_btn.update()
        self._clear_btn.update()
        self._done_btn.update()
        self._cancel_btn.update()
        for inp in self._inputs:
            inp.update(dt_ms)

        if self._saved_timer > 0:
            self._saved_timer -= dt_ms
            if self._saved_timer <= 0:
                self._saved_msg = None

    def draw(self):
        self.screen.fill(COLORS["bg"])
        mx, my = pygame.mouse.get_pos()
        hover = self._cell_at(mx, my)

        ecs, eox, eoy = self._effective_layout()

        W, H = self.screen.get_size()
        self.screen.set_clip(pygame.Rect(0, 0, W - SIDE_W, H))
        draw_scene_preview(
            self.screen,
            self.grid_w, self.grid_h,
            self.obstacles, self.agent_starts, self.goals,
            ecs, eox, eoy,
            self._ft, hover,
        )
        self.screen.set_clip(None)

        self._draw_side_panel()
        pygame.display.flip()

    def _draw_side_panel(self):
        W, H = self.screen.get_size()
        sx = W - SIDE_W

        draw_panel(self.screen, (sx, 0, SIDE_W, H), alpha=235, radius=0)
        cx = sx + SIDE_W // 2

        t = self._fh.render("EDITOR", True, COLORS["accent"])
        self.screen.blit(t, t.get_rect(centerx=cx, y=10))

        self.screen.blit(
            self._fs.render("Grid size:", True, COLORS["text_muted"]),
            (sx + 10, 28),
        )
        self._w_input.draw(self.screen)
        xsign = self._w_input.rect.right + 5
        self.screen.blit(
            self._fs.render("×", True, COLORS["text_muted"]),
            (xsign, 42),
        )
        self._h_input.draw(self.screen)
        self._apply_btn.draw(self.screen)

        lbl = self._fh.render("TOOLS", True, COLORS["accent"])
        self.screen.blit(lbl, (sx + 10, 106))
        for btn in self._tool_btns:
            btn.draw(self.screen)

        hy = 120 + len(self.TOOLS) * 38 + 4
        for i, name in enumerate(self.TOOLS):
            s = self._ft.render(f"[{i + 1}] {name}", True, COLORS["text_muted"])
            self.screen.blit(s, (sx + 10, hy + i * 15))

        cnt_y = hy + len(self.TOOLS) * 15 + 12
        self.screen.blit(
            self._fh.render("PLACED", True, COLORS["accent"]),
            (sx + 10, cnt_y),
        )
        cnt_y += 20
        lines = [
            ("Agents", len(self.agent_starts), AGENT_COLORS[0]),
            ("Goals", len(self.goals), GOAL_COLOR),
            ("Obstacles", len(self.obstacles), COLORS["text_muted"]),
        ]
        for label, count, color in lines:
            s = self._fs.render(f"{label}:  {count}", True, color)
            self.screen.blit(s, (sx + 10, cnt_y))
            cnt_y += 18

        cnt_y += 8
        self.screen.blit(
            self._fh.render("COLORS", True, COLORS["accent"]),
            (sx + 10, cnt_y),
        )
        cnt_y += 18
        for i in range(min(len(self.agent_starts), 8)):
            col = AGENT_COLORS[i % len(AGENT_COLORS)]
            pygame.draw.rect(
                self.screen, col,
                pygame.Rect(sx + 10, cnt_y + i * 16, 12, 12),
                border_radius=2,
            )
            s = self._ft.render(f"Agent {i}", True, COLORS["text_muted"])
            self.screen.blit(s, (sx + 28, cnt_y + i * 16))

        if self._saved_msg:
            sm = self._fs.render(self._saved_msg, True, COLORS["success"])
            self.screen.blit(sm, sm.get_rect(centerx=cx, y=H - 170))

        if self._error:
            err = self._fs.render(self._error, True, COLORS["error"])
            self.screen.blit(err, err.get_rect(centerx=cx, y=H - 170))

        self._load_btn.draw(self.screen)
        self._save_btn.draw(self.screen)
        self._clear_btn.draw(self.screen)
        self._done_btn.draw(self.screen)
        self._cancel_btn.draw(self.screen)

        hint = self._ft.render(
            "LMB: place  ·  RMB: erase  ·  Drag: paint",
            True, COLORS["text_muted"],
        )
        self.screen.blit(hint, hint.get_rect(x=5, bottom=H - 14))
        hint2 = self._ft.render(
            "Scroll: zoom  ·  MMB drag: pan  ·  0/Home: reset",
            True, COLORS["text_muted"],
        )
        self.screen.blit(hint2, hint2.get_rect(x=5, bottom=H - 2))

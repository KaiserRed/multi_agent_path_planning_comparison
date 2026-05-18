"""
Algorithm selection screen.

Shows a read-only grid preview on the left and an algorithm picker
panel on the right.  The user chooses MAPF or MRTA, picks an algorithm,
and clicks START.  Validation ensures the scene is compatible with
the chosen algorithm type.
"""

from __future__ import annotations

import pygame

from scenario import SceneData
from registry import ALGORITHMS
from ui.widgets import Button, RadioGroup, COLORS, draw_panel
from ui.editor import (
    draw_scene_preview, SIDE_W, MIN_CELL, MAX_CELL, _fit_cell,
    AGENT_COLORS, GOAL_COLOR,
)


class AlgoSelect:
    """
    handle_events() returns:
      dict  → ``{"algo_type": str, "algo_name": str}``  (start simulation)
      ``"back"``  → return to editor
      ``None``    → keep looping
    """

    def __init__(self, screen: pygame.Surface, scene: SceneData):
        self.screen = screen
        self.scene = scene

        pygame.font.init()
        self._fh = pygame.font.SysFont("Arial", 15, bold=True)
        self._fb = pygame.font.SysFont("Arial", 13)
        self._fs = pygame.font.SysFont("Arial", 12)
        self._ft = pygame.font.SysFont("Arial", 11)

        self._sel_type: str = "MAPF"
        self._sel_algo: int = 0
        self._sel_mapf_algo: int = 0
        self._start_error: str | None = None

        self._layout()
        self._build_widgets()

    def _layout(self):
        W, H = self.screen.get_size()
        avail_w = W - SIDE_W - 10
        avail_h = H - 10
        self.cs = _fit_cell(
            self.scene.grid_width, self.scene.grid_height,
            avail_w, avail_h,
        )
        self.ox = max(5, (avail_w - self.cs * self.scene.grid_width) // 2)
        self.oy = max(5, (avail_h - self.cs * self.scene.grid_height) // 2)

    def reflow(self):
        """Recompute layout and rebuild widgets after window resize."""
        self._layout()
        self._build_widgets()

    def _build_widgets(self):
        W, H = self.screen.get_size()
        sx = W - SIDE_W + 10
        sw = SIDE_W - 20

        types = list(ALGORITHMS.keys())
        self._type_radio = RadioGroup(
            types, (sx, 40, sw, 32), self._fb,
            selected=types.index(self._sel_type),
        )

        self._algo_btns: list[Button] = []
        self._rebuild_algo_btns()

        self._start_btn = Button(
            (sx, H - 70, sw, 40), "START", self._fb, primary=True,
        )
        self._back_btn = Button(
            (sx, H - 30, sw, 26), "Back to Editor", self._ft,
        )

    def _rebuild_algo_btns(self):
        W, H = self.screen.get_size()
        sx = W - SIDE_W + 10
        sw = SIDE_W - 20

        algos = ALGORITHMS.get(self._sel_type, [])
        self._algo_btns = []
        for i, algo in enumerate(algos):
            btn = Button((sx, 100 + i * 40, sw, 34), algo.DISPLAY_NAME, self._fb)
            btn.active = (i == self._sel_algo)
            self._algo_btns.append(btn)

    def _validate(self) -> str | None:
        """
        Returns a *blocking* error string, or None if the configuration is valid.
        """
        na = len(self.scene.agent_starts)
        ng = len(self.scene.goals)

        if na == 0:
            return "No agents in scene"
        if ng == 0:
            return "No goals / tasks in scene"

        if self._sel_type == "MAPF":
            # MAPF: each agent needs exactly one goal
            if ng != na:
                return f"MAPF requires goals = agents  ({ng} ≠ {na})"

        # MRTA: the algorithm assigns tasks itself — any counts are allowed.
        # (Hungarian handles n_tasks > n_agents: assigns every agent one task,
        #  leaves excess tasks unassigned.  If n_tasks < n_agents some agents
        #  sit idle — also valid, just less efficient.)
        return None

    def _warning(self) -> str | None:
        """
        Returns a non-blocking informational warning string, or None.
        Shown in yellow regardless of whether START was pressed.
        """
        if self._sel_type != "MRTA":
            return None
        na = len(self.scene.agent_starts)
        ng = len(self.scene.goals)
        if ng < na:
            return f"⚠  {ng} tasks < {na} agents — {na - ng} agent(s) will idle"
        return None

    def handle_events(self, events: list) -> dict | str | None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "back"

            if self._type_radio.handle_event(event):
                new_type = self._type_radio.get_value()
                if self._sel_type == "MAPF":
                    self._sel_mapf_algo = self._sel_algo
                self._sel_type = new_type
                self._sel_algo = (self._sel_mapf_algo
                                  if new_type == "MAPF" else 0)
                self._start_error = None
                self._rebuild_algo_btns()

            for i, btn in enumerate(self._algo_btns):
                if btn.handle_event(event):
                    self._sel_algo = i
                    if self._sel_type == "MAPF":
                        self._sel_mapf_algo = i
                    self._start_error = None
                    for j, b in enumerate(self._algo_btns):
                        b.active = (j == i)

            if self._start_btn.handle_event(event):
                err = self._validate()
                if err is None:
                    algos = ALGORITHMS.get(self._sel_type, [])
                    mapf_algos = ALGORITHMS.get("MAPF", [])
                    nav_name = (mapf_algos[self._sel_mapf_algo].DISPLAY_NAME
                                if mapf_algos else "")
                    return {
                        "algo_type": self._sel_type,
                        "algo_name": algos[self._sel_algo].DISPLAY_NAME,
                        "nav_algo_name": nav_name,
                    }
                self._start_error = err

            if self._back_btn.handle_event(event):
                return "back"

        return None

    def update(self):
        for btn in self._algo_btns:
            btn.update()
        self._start_btn.update()
        self._back_btn.update()


    def draw(self):
        self.screen.fill(COLORS["bg"])

        draw_scene_preview(
            self.screen,
            self.scene.grid_width, self.scene.grid_height,
            set(self.scene.obstacles),
            self.scene.agent_starts,
            self.scene.goals,
            self.cs, self.ox, self.oy,
            self._ft,
        )

        self._draw_side_panel()
        pygame.display.flip()

    def _draw_side_panel(self):
        W, H = self.screen.get_size()
        sx = W - SIDE_W
        cx = sx + SIDE_W // 2

        draw_panel(self.screen, (sx, 0, SIDE_W, H), alpha=235, radius=0)

        # Title
        t = self._fh.render("SELECT ALGORITHM", True, COLORS["accent"])
        self.screen.blit(t, t.get_rect(centerx=cx, y=10))

        # Type radio
        self.screen.blit(
            self._fs.render("Type:", True, COLORS["text_muted"]),
            (sx + 10, 30),
        )
        self._type_radio.draw(self.screen)

        # Algorithm buttons
        self.screen.blit(
            self._fs.render("Algorithm:", True, COLORS["text_muted"]),
            (sx + 10, 82),
        )
        for btn in self._algo_btns:
            btn.draw(self.screen)

        # Info about selected algorithm
        algos = ALGORITHMS.get(self._sel_type, [])
        if algos and self._sel_algo < len(algos):
            algo = algos[self._sel_algo]
            info_y = 100 + len(algos) * 40 + 4
            ctype = "Centralized" if algo.IS_CENTRALIZED else "Decentralized"
            mode = "Online" if algo.IS_ONLINE else "Offline"

            self.screen.blit(
                self._fh.render("INFO", True, COLORS["accent"]),
                (sx + 10, info_y),
            )
            info_y += 18
            self.screen.blit(
                self._ft.render(f"{ctype}  ·  {mode}", True, COLORS["text_muted"]),
                (sx + 10, info_y),
            )
            info_y += 16
            desc = algo.DESCRIPTION
            for line in _wrap(desc, 34):
                self.screen.blit(
                    self._ft.render(line, True, COLORS["text_muted"]),
                    (sx + 10, info_y),
                )
                info_y += 14

        # Scene summary
        sum_y = H - 190
        self.screen.blit(
            self._fh.render("SCENE", True, COLORS["accent"]),
            (sx + 10, sum_y),
        )
        sum_y += 20
        na = len(self.scene.agent_starts)
        ng = len(self.scene.goals)
        gw, gh = self.scene.grid_width, self.scene.grid_height

        goal_label = "Tasks" if self._sel_type == "MRTA" else "Goals"
        for label in [f"Grid: {gw}×{gh}", f"Agents: {na}",
                      f"{goal_label}: {ng}"]:
            self.screen.blit(
                self._fs.render(label, True, COLORS["text"]),
                (sx + 10, sum_y),
            )
            sum_y += 17

        # MRTA: show navigation algorithm and hint
        if self._sel_type == "MRTA":
            sum_y += 4
            for hint_line in ["Goals = tasks to assign.", "Algorithm decides"]:
                self.screen.blit(
                    self._ft.render(hint_line, True, COLORS["text_muted"]),
                    (sx + 10, sum_y),
                )
                sum_y += 13
            sum_y += 6
            mapf_algos = ALGORITHMS.get("MAPF", [])
            nav_name = (mapf_algos[self._sel_mapf_algo].DISPLAY_NAME
                        if mapf_algos else "A*")
            self.screen.blit(
                self._fs.render("Navigation:", True, COLORS["accent"]),
                (sx + 10, sum_y),
            )
            sum_y += 16
            self.screen.blit(
                self._fs.render(nav_name, True, COLORS["text"]),
                (sx + 10, sum_y),
            )
            sum_y += 14
            self.screen.blit(
                self._ft.render("(set on MAPF tab)", True, COLORS["text_muted"]),
                (sx + 10, sum_y),
            )

        # Non-blocking warning (yellow)
        warn = self._warning()
        if warn:
            wm = self._ft.render(warn, True, COLORS["task"])
            self.screen.blit(wm, wm.get_rect(centerx=cx, y=H - 110))

        # Blocking error (red) — shown only after START is clicked
        if self._start_error:
            em = self._fs.render(self._start_error, True, COLORS["error"])
            self.screen.blit(em, em.get_rect(centerx=cx, y=H - 96))

        # Buttons
        self._start_btn.draw(self.screen)
        self._back_btn.draw(self.screen)


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    if cur:
        lines.append(cur)
    return lines

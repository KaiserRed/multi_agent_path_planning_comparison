"""Batch Mode UI — three Pygame screens.

BatchAlgoScreen  — choose MAPF and MRTA algorithms to compare
BatchMapScreen   — map / generation parameters
BatchProgressScreen — live progress bar + results
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading

import pygame

from batch.config import BatchConfig
from registry import ALGORITHMS
from ui.dialogs import open_files
from ui.widgets import Button, RadioGroup, NumberInput, COLORS, draw_panel


BATCH_W, BATCH_H = 1000, 700
_COL1_X = 30
_COL2_X = 340
_COL3_X = 650



def _checkbox(surface, rect, checked: bool, font, label: str):
    """Draw a simple checkbox with a label."""
    x, y, w, h = rect
    box = pygame.Rect(x, y + (h - 16) // 2, 16, 16)
    pygame.draw.rect(surface, COLORS["panel_light"], box, border_radius=3)
    pygame.draw.rect(surface, COLORS["border"], box, 1, border_radius=3)
    if checked:
        pygame.draw.line(surface, COLORS["accent"],
                         (box.x + 3, box.centery), (box.x + 7, box.y + 12), 2)
        pygame.draw.line(surface, COLORS["accent"],
                         (box.x + 7, box.y + 12), (box.x + 13, box.y + 3), 2)
    lbl = font.render(label, True, COLORS["text"])
    surface.blit(lbl, (x + 22, y + (h - lbl.get_height()) // 2))
    return box


def _section(surface, font, text: str, x: int, y: int, color=None):
    c = color or COLORS["accent"]
    s = font.render(text, True, c)
    surface.blit(s, (x, y))
    return y + s.get_height() + 4


def _label(surface, font, text: str, x: int, y: int):
    s = font.render(text, True, COLORS["text_muted"])
    surface.blit(s, (x, y))
    return y + s.get_height() + 2


# Screen 1 – Algorithm Selection
class BatchAlgoScreen:
    """
    Two checkbox columns (MAPF left, MRTA right).
    Returns ``"next"`` → proceed, ``"back"`` → main menu.
    """

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._fh = pygame.font.SysFont("Arial", 16, bold=True)
        self._fb = pygame.font.SysFont("Arial", 14)
        self._fs = pygame.font.SysFont("Arial", 12)

        self._mapf_names = [p.DISPLAY_NAME for p in ALGORITHMS["MAPF"]]
        self._mrta_names = [p.DISPLAY_NAME for p in ALGORITHMS["MRTA"]]

        self._mapf_sel = [True] * len(self._mapf_names)
        self._mrta_sel = [True] * len(self._mrta_names)

        dummy = pygame.Rect(0, 0, 1, 1)
        self._next_btn = Button(dummy, "Next →", self._fb, primary=True)
        self._back_btn = Button(dummy, "← Back", self._fb)
        self.reflow()

        self._mapf_rects: list[pygame.Rect] = []
        self._mrta_rects: list[pygame.Rect] = []

    def reflow(self):
        W, H = self.screen.get_size()
        self._next_btn.rect = pygame.Rect(W - 200, H - 56, 170, 42)
        self._back_btn.rect = pygame.Rect(30, H - 56, 120, 42)

    def handle_events(self, events: list) -> str | None:
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                return "back"
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for i, r in enumerate(self._mapf_rects):
                    if r.collidepoint(e.pos):
                        self._mapf_sel[i] = not self._mapf_sel[i]
                for i, r in enumerate(self._mrta_rects):
                    if r.collidepoint(e.pos):
                        self._mrta_sel[i] = not self._mrta_sel[i]
            if self._next_btn.handle_event(e):
                if any(self._mapf_sel) and any(self._mrta_sel):
                    return "next"
            if self._back_btn.handle_event(e):
                return "back"
        return None

    def update(self):
        self._next_btn.update()
        self._back_btn.update()

    def get_selection(self) -> tuple[list[str], list[str]]:
        mapf = [n for n, s in zip(self._mapf_names, self._mapf_sel) if s]
        mrta = [n for n, s in zip(self._mrta_names, self._mrta_sel) if s]
        return mapf, mrta

    def draw(self):
        W, H = self.screen.get_size()
        self.screen.fill(COLORS["bg"])
        draw_panel(self.screen, (10, 10, W - 20, H - 76), alpha=200)

        t = self._fh.render("BATCH MODE — Select Algorithms", True, COLORS["accent"])
        self.screen.blit(t, t.get_rect(centerx=W // 2, y=22))

        col2 = max(_COL2_X, W // 3)

        # MAPF column
        y = 70
        y = _section(self.screen, self._fb, "MAPF Algorithms", _COL1_X, y)
        self._mapf_rects = []
        for i, name in enumerate(self._mapf_names):
            box = _checkbox(self.screen,
                            (_COL1_X, y, col2 - _COL1_X - 10, 28),
                            self._mapf_sel[i],
                            self._fs, name)
            self._mapf_rects.append(box)
            y += 30

        # MRTA column
        y = 70
        y = _section(self.screen, self._fb, "MRTA Algorithms", col2, y)
        self._mrta_rects = []
        for i, name in enumerate(self._mrta_names):
            box = _checkbox(self.screen,
                            (col2, y, W - col2 - 30, 28),
                            self._mrta_sel[i],
                            self._fs, name)
            self._mrta_rects.append(box)
            y += 30

        n_mapf = sum(self._mapf_sel)
        n_mrta = sum(self._mrta_sel)
        combo_s = self._fb.render(
            f"Combinations: {n_mapf} × {n_mrta} = {n_mapf * n_mrta}",
            True, COLORS["text"],
        )
        self.screen.blit(combo_s, combo_s.get_rect(centerx=W // 2, y=H - 80))

        self._next_btn.draw(self.screen)
        self._back_btn.draw(self.screen)
        pygame.display.flip()


# Screen 2 – Map / Generation Parameters
class BatchMapScreen:
    """
    Returns ``"run"`` → start batch, ``"back"`` → algo screen.

    When ``.scen`` files are loaded the random-generation controls (grid
    size, obstacle density, placement strategy, reachability check) are
    rendered dimmed and ignored — the map geometry comes from the file.
    """

    _PLACEMENT_OPTS = ["uniform", "clustered", "counter", "min_dist"]

    def __init__(self, screen: pygame.Surface,
                 mapf_algos: list[str], mrta_algos: list[str]):
        self.screen = screen
        self._mapf_algos = mapf_algos
        self._mrta_algos = mrta_algos

        self._fh = pygame.font.SysFont("Arial", 15, bold=True)
        self._fb = pygame.font.SysFont("Arial", 13)
        self._fs = pygame.font.SysFont("Arial", 12)

        W, H = BATCH_W, BATCH_H

        ni = lambda x, y, v, lo, hi: NumberInput(
            (x, y, 72, 28), v, self._fs, min_val=lo, max_val=hi
        )
        col = _COL1_X
        self._grid_w  = ni(col + 100, 78,  12, 4, 1000)
        self._grid_h  = ni(col + 190, 78,  12, 4, 1000)
        self._rob_min = ni(col + 100, 115,  2, 1, 1000)
        self._rob_max = ni(col + 190, 115,  8, 1, 1000)
        self._rob_step= ni(col + 280, 115,  2, 1, 100)
        self._scen_n  = ni(col + 160, 150,  3, 1, 100)
        self._obs_pct      = ni(col + 160, 186, 15, 0, 70)
        self._timeout      = ni(col + 160, 222, 60, 0, 3600)
        self._plan_timeout = ni(col + 160, 258, 30, 0, 3600)

        self._inputs_always = [
            self._rob_min, self._rob_max, self._rob_step,
            self._scen_n, self._timeout, self._plan_timeout,
        ]
        self._inputs_gen = [
            self._grid_w, self._grid_h, self._obs_pct,
        ]

        self._placement_radio = RadioGroup(
            self._PLACEMENT_OPTS,
            (col, 300, 560, 28),
            self._fs,
        )

        self._check_reach = True
        self._reach_box_rect: pygame.Rect | None = None


        self._import_btn = Button((col, 366, 210, 32),
                                  "Import Maps (JSON/.map)", self._fs)
        self._scen_btn   = Button((col + 220, 366, 180, 32),
                                  "Import .scen", self._fs)

        self._imported: list[str] = []
        self._scen_files: list[str] = []

        self._clear_imported_btn = Button((col + 440, 366, 60, 32),
                                          "Clear", self._fs)
        self._clear_scen_btn     = Button((col + 440, 366, 60, 32),
                                          "Clear", self._fs)

        dummy = pygame.Rect(0, 0, 1, 1)
        self._run_btn  = Button(dummy, "▶ Run", self._fb, primary=True)
        self._back_btn = Button(dummy, "← Back", self._fb)
        self.reflow()

    def reflow(self):
        W, H = self.screen.get_size()
        col = _COL1_X
        self._run_btn.rect  = pygame.Rect(W - 200, H - 56, 170, 42)
        self._back_btn.rect = pygame.Rect(col, H - 56, 120, 42)

    @property
    def _scen_mode(self) -> bool:
        """True when .scen files are loaded — disables random-gen controls."""
        return bool(self._scen_files)


    def handle_events(self, events: list) -> str | None:
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                return "back"

            for inp in self._inputs_always:
                inp.handle_event(e)

            if not self._scen_mode:
                for inp in self._inputs_gen:
                    inp.handle_event(e)
                self._placement_radio.handle_event(e)
                if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                        and self._reach_box_rect
                        and self._reach_box_rect.collidepoint(e.pos)):
                    self._check_reach = not self._check_reach

            if self._import_btn.handle_event(e):
                self._open_import_dialog()

            if self._scen_btn.handle_event(e):
                self._open_scen_dialog()

            if self._imported and self._clear_imported_btn.handle_event(e):
                self._imported = []
            if self._scen_files and self._clear_scen_btn.handle_event(e):
                self._scen_files = []

            if self._run_btn.handle_event(e):
                return "run"

            if self._back_btn.handle_event(e):
                return "back"

        return None

    def update(self, dt: int = 0):
        for inp in self._inputs_always + self._inputs_gen:
            inp.update(dt)
        self._import_btn.update()
        self._scen_btn.update()
        self._clear_imported_btn.update()
        self._clear_scen_btn.update()
        self._run_btn.update()
        self._back_btn.update()


    def _open_import_dialog(self):
        paths = open_files(
            title="Select map files",
            filetypes=[
                ("Map files", "*.json *.map"),
                ("JSON files", "*.json"),
                ("MovingAI maps", "*.map"),
                ("All files", "*"),
            ],
        )
        if paths:
            self._imported = paths
            self._scen_files = []

    def _open_scen_dialog(self):
        paths = open_files(
            title="Select MovingAI .scen files",
            filetypes=[
                ("MovingAI scenarios", "*.scen"),
                ("All files", "*"),
            ],
        )
        if paths:
            self._scen_files = paths
            self._imported = []


    def build_config(self) -> BatchConfig:
        return BatchConfig(
            mapf_algos=self._mapf_algos,
            mrta_algos=self._mrta_algos,
            robot_min=self._rob_min.get_value(),
            robot_max=self._rob_max.get_value(),
            robot_step=self._rob_step.get_value(),
            scenarios_per_n=self._scen_n.get_value(),
            grid_w=self._grid_w.get_value(),
            grid_h=self._grid_h.get_value(),
            obstacle_density=self._obs_pct.get_value() / 100.0,
            placement=self._placement_radio.get_value(),
            check_reachability=self._check_reach,
            imported_maps=self._imported,
            scen_files=self._scen_files,
            timeout_s=float(self._timeout.get_value()),
            plan_timeout_s=float(self._plan_timeout.get_value()),
            output_dir="batch_results",
        )


    def draw(self):
        W, H = self.screen.get_size()
        self.screen.fill(COLORS["bg"])
        draw_panel(self.screen, (10, 10, W - 20, H - 76), alpha=200)

        t = self._fh.render("BATCH MODE — Map & Parameters", True, COLORS["accent"])
        self.screen.blit(t, t.get_rect(centerx=W // 2, y=20))

        col = _COL1_X

        lbl_gen  = COLORS["text_muted"] if self._scen_mode else COLORS["text_muted"]
        lbl_dim  = (80, 85, 110)   

        def _lbl(text, x, y, dimmed=False):
            c = lbl_dim if dimmed else COLORS["text_muted"]
            s = self._fs.render(text, True, c)
            self.screen.blit(s, (x, y))

        _lbl("Grid W:", col, 78 + 7, self._scen_mode)
        self._grid_w.draw(self.screen)
        _lbl("H:", col + 185, 78 + 7, self._scen_mode)
        self._grid_h.draw(self.screen)

        _lbl("Robots  min:", col, 115 + 7)
        self._rob_min.draw(self.screen)
        _lbl("max:", col + 185, 115 + 7)
        self._rob_max.draw(self.screen)
        _lbl("step:", col + 275, 115 + 7)
        self._rob_step.draw(self.screen)

        _lbl("Scenarios / N:", col, 150 + 7)
        self._scen_n.draw(self.screen)

        _lbl("Obstacle density %:", col, 186 + 7, self._scen_mode)
        self._obs_pct.draw(self.screen)

        _lbl("Sim timeout per run (s):", col, 222 + 7)
        self._timeout.draw(self.screen)
        _lbl("0 = no limit", col + 240, 222 + 7)

        _lbl("Plan timeout per run (s):", col, 258 + 7)
        self._plan_timeout.draw(self.screen)
        _lbl("0 = no limit", col + 240, 258 + 7)

        plac_color = lbl_dim if self._scen_mode else COLORS["text_muted"]
        self.screen.blit(
            self._fs.render("Placement strategy:", True, plac_color),
            (col, 286),
        )
        self._placement_radio.draw(self.screen)

        reach_color = lbl_dim if self._scen_mode else COLORS["text_muted"]
        self._reach_box_rect = _checkbox(
            self.screen,
            (col, 336, 300, 24),
            self._check_reach,
            self._fs,
            "Check goal reachability (BFS)",
        )
        if self._scen_mode:
            dim_surf = pygame.Surface((300, 24), pygame.SRCALPHA)
            dim_surf.fill((0, 0, 0, 100))
            self.screen.blit(dim_surf, (col, 336))

        src_y = 366
        self._import_btn.draw(self.screen)
        self._scen_btn.draw(self.screen)

        y_info = src_y + 38

        if self._imported:
            self._clear_imported_btn.rect = pygame.Rect(col + 440, src_y, 60, 32)
            self._clear_imported_btn.draw(self.screen)
            n_shown = min(3, len(self._imported))
            for i in range(n_shown):
                name = os.path.basename(self._imported[i])
                self.screen.blit(
                    self._fs.render(f"  • {name}", True, COLORS["text_muted"]),
                    (col + 10, y_info),
                )
                y_info += 15
            if len(self._imported) > n_shown:
                self.screen.blit(
                    self._fs.render(
                        f"  … and {len(self._imported) - n_shown} more",
                        True, COLORS["text_muted"],
                    ),
                    (col + 10, y_info),
                )
                y_info += 15

        if self._scen_files:
            self._clear_scen_btn.rect = pygame.Rect(col + 440, src_y, 60, 32)
            self._clear_scen_btn.draw(self.screen)
            n_shown = min(3, len(self._scen_files))
            for i in range(n_shown):
                name = os.path.basename(self._scen_files[i])
                self.screen.blit(
                    self._fs.render(f"  • {name}", True, COLORS["accent"]),
                    (col + 10, y_info),
                )
                y_info += 15
            if len(self._scen_files) > n_shown:
                self.screen.blit(
                    self._fs.render(
                        f"  … and {len(self._scen_files) - n_shown} more",
                        True, COLORS["accent"],
                    ),
                    (col + 10, y_info),
                )
                y_info += 15
            self.screen.blit(
                self._fs.render(
                    "  Grid size / obstacles taken from .scen file",
                    True, (120, 180, 120),
                ),
                (col + 10, y_info),
            )

        cfg = self.build_config()
        nc = len(cfg.mapf_algos) * len(cfg.mrta_algos)
        nr = len(list(range(cfg.robot_min, cfg.robot_max + 1, cfg.robot_step)))
        total = nc * nr * cfg.scenarios_per_n
        summary = self._fb.render(
            f"Total runs: {nc} combos × {nr} robot counts × "
            f"{cfg.scenarios_per_n} seeds = {total}",
            True, COLORS["text"],
        )
        W2, H2 = self.screen.get_size()
        self.screen.blit(summary, summary.get_rect(centerx=W2 // 2, y=H2 - 80))

        self._run_btn.draw(self.screen)
        self._back_btn.draw(self.screen)
        pygame.display.flip()


# Screen 3 – Progress & Results
class BatchProgressScreen:
    """
    Spawns BatchRunner in a background thread.
    Returns ``"menu"`` when user clicks Back to Menu.
    """

    def __init__(self, screen: pygame.Surface, config: BatchConfig):
        self.screen = screen
        self.config = config

        self._fh = pygame.font.SysFont("Arial", 16, bold=True)
        self._fb = pygame.font.SysFont("Arial", 14)
        self._fs = pygame.font.SysFont("Arial", 12)

        dummy = pygame.Rect(0, 0, 1, 1)
        self._menu_btn = Button(dummy, "Back to Menu", self._fb)
        self._open_btn = Button(dummy, "Open Folder", self._fs)
        self.reflow()

        self._fraction: float = 0.0
        self._current_label: str = "Initializing…"
        self._done: bool = False
        self._output_dir: str = ""
        self._error: str = ""
        self._lock = threading.Lock()

        self._start_runner()

    def reflow(self):
        W, H = self.screen.get_size()
        self._menu_btn.rect = pygame.Rect(W // 2 - 90,  H - 60, 180, 42)
        self._open_btn.rect = pygame.Rect(W // 2 + 100, H - 60, 160, 42)

    def _start_runner(self):
        def _target():
            try:
                from batch.runner import BatchRunner
                from batch.plotter import save_results
                runner = BatchRunner()
                df = runner.run(self.config, self._on_progress)
                out = save_results(df, self.config.output_dir)
                with self._lock:
                    self._output_dir = out
                    self._done = True
                    self._current_label = f"Done! Results saved to: {out}"
            except Exception as exc:
                with self._lock:
                    self._error = str(exc)
                    self._done = True
                    self._current_label = f"Error: {exc}"

        t = threading.Thread(target=_target, daemon=True)
        t.start()

    def _on_progress(self, fraction: float, label: str):
        with self._lock:
            self._fraction = fraction
            self._current_label = label

    def handle_events(self, events: list) -> str | None:
        for e in events:
            if self._menu_btn.handle_event(e):
                return "menu"
            if self._open_btn.handle_event(e):
                self._open_folder()
        return None

    def update(self):
        self._menu_btn.update()
        self._open_btn.update()

    def _open_folder(self):
        if not self._output_dir:
            return
        try:
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", self._output_dir])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self._output_dir])
            elif sys.platform.startswith("win"):
                os.startfile(self._output_dir)  # type: ignore[attr-defined]
        except Exception:
            pass

    def draw(self):
        W, H = self.screen.get_size()
        self.screen.fill(COLORS["bg"])
        draw_panel(self.screen, (10, 10, W - 20, H - 76), alpha=200)

        with self._lock:
            frac = self._fraction
            label = self._current_label
            done = self._done
            error = self._error

        # Title
        t = self._fh.render("BATCH MODE — Running", True, COLORS["accent"])
        self.screen.blit(t, t.get_rect(centerx=W // 2, y=20))

        # Progress bar
        bar_x, bar_y, bar_w, bar_h = 40, 80, W - 80, 30
        pygame.draw.rect(self.screen, COLORS["panel_light"],
                         (bar_x, bar_y, bar_w, bar_h), border_radius=8)
        fill_w = int(bar_w * min(frac, 1.0))
        if fill_w > 0:
            color = COLORS["success"] if done and not error else COLORS["accent"]
            pygame.draw.rect(self.screen, color,
                             (bar_x, bar_y, fill_w, bar_h), border_radius=8)
        pygame.draw.rect(self.screen, COLORS["border"],
                         (bar_x, bar_y, bar_w, bar_h), 1, border_radius=8)

        # Percentage
        pct = self._fb.render(f"{frac * 100:.0f}%", True, COLORS["text"])
        self.screen.blit(pct, pct.get_rect(centerx=W // 2, y=bar_y + 5))

        # Current label
        lbl = self._fs.render(label, True,
                              COLORS["error"] if error else COLORS["text_muted"])
        self.screen.blit(lbl, lbl.get_rect(centerx=W // 2, y=120))

        if done:
            if error:
                msg = self._fb.render("Run failed — see label above.",
                                      True, COLORS["error"])
            else:
                msg = self._fb.render(
                    "Batch complete!  CSV + 4 plots saved.",
                    True, COLORS["success"],
                )
            self.screen.blit(msg, msg.get_rect(centerx=W // 2, y=160))
            self._open_btn.draw(self.screen)

        self._menu_btn.draw(self.screen)
        pygame.display.flip()

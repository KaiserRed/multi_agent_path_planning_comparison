"""
Main menu — the first screen the user sees.

Three options:
  • Create Scenario → opens the world editor
  • Load Scenario   → file dialog, then editor (pre-populated)
  • Batch Mode      → placeholder for future work
"""

import pygame

from ui.widgets import Button, COLORS, draw_panel

MENU_W, MENU_H = 620, 480


class MainMenu:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen

        self._f_title = pygame.font.SysFont("Arial", 26, bold=True)
        self._f_sub = pygame.font.SysFont("Arial", 14)
        self._f_btn = pygame.font.SysFont("Arial", 16)
        self._f_small = pygame.font.SysFont("Arial", 12)

        cx = MENU_W // 2
        bw = 280

        self._create_btn = Button(
            (cx - bw // 2, 190, bw, 50),
            "Create Scenario", self._f_btn, primary=True,
        )
        self._load_btn = Button(
            (cx - bw // 2, 258, bw, 50),
            "Load Scenario", self._f_btn,
        )
        self._batch_btn = Button(
            (cx - bw // 2, 326, bw, 50),
            "Batch Mode", self._f_btn,
        )
        self._quit_btn = Button(
            (cx - bw // 2, 394, bw, 40),
            "Quit", self._f_btn,
        )
        self._btns = [self._create_btn, self._load_btn,
                      self._batch_btn, self._quit_btn]

    # ------------------------------------------------------------------

    def handle_events(self, events: list) -> str | None:
        """
        Returns ``"create"``, ``"load"``, ``"batch"``, ``"quit"`` or ``None``.
        """
        for event in events:
            if self._create_btn.handle_event(event):
                return "create"
            if self._load_btn.handle_event(event):
                return "load"
            if self._batch_btn.handle_event(event):
                return "batch"
            if self._quit_btn.handle_event(event):
                return "quit"
        return None

    def update(self):
        for btn in self._btns:
            btn.update()

    def draw(self):
        W, H = MENU_W, MENU_H
        self.screen.fill(COLORS["bg"])

        # Title
        t = self._f_title.render(
            "MULTI-ROBOT SYSTEM EVALUATOR", True, COLORS["text"]
        )
        self.screen.blit(t, t.get_rect(centerx=W // 2, y=40))

        sub = self._f_sub.render(
            "Algorithm Benchmarking for MAPF & MRTA",
            True, COLORS["text_muted"],
        )
        self.screen.blit(sub, sub.get_rect(centerx=W // 2, y=78))

        # Panel
        draw_panel(self.screen, (W // 2 - 165, 162, 330, 298))

        for btn in self._btns:
            btn.draw(self.screen)

        # "coming soon" under Batch Mode
        hint = self._f_small.render("(coming soon)", True, COLORS["text_muted"])
        self.screen.blit(hint, hint.get_rect(centerx=W // 2, y=382))

        pygame.display.flip()

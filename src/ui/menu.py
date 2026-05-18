"""
Main menu — the first screen the user sees.

Three options:
  • Create Scenario → opens the world editor
  • Load Scenario   → file dialog, then editor (pre-populated)
  • Batch Mode      → batch experiment mode
"""

import pygame

from ui.widgets import Button, COLORS, draw_panel

MENU_W, MENU_H = 720, 540


class MainMenu:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen

        self._f_title = pygame.font.SysFont("Arial", 26, bold=True)
        self._f_sub = pygame.font.SysFont("Arial", 14)
        self._f_btn = pygame.font.SysFont("Arial", 16)
        self._f_small = pygame.font.SysFont("Arial", 12)

        bw = 280
        dummy = pygame.Rect(0, 0, bw, 50)
        self._create_btn = Button(dummy, "Create Scenario", self._f_btn, primary=True)
        self._load_btn   = Button(dummy, "Load Scenario",   self._f_btn)
        self._batch_btn  = Button(dummy, "Batch Mode",      self._f_btn)
        self._quit_btn   = Button(pygame.Rect(0, 0, bw, 40), "Quit", self._f_btn)
        self._btns = [self._create_btn, self._load_btn,
                      self._batch_btn, self._quit_btn]
        self.reflow()

    def reflow(self):
        """Recompute button positions from current window size."""
        W, H = self.screen.get_size()
        bw = 280
        cx = W // 2
        base_y = max(160, int(H * 0.33))
        step    = max(52, int(H * 0.11))
        self._create_btn.rect = pygame.Rect(cx - bw // 2, base_y,           bw, 50)
        self._load_btn.rect   = pygame.Rect(cx - bw // 2, base_y + step,    bw, 50)
        self._batch_btn.rect  = pygame.Rect(cx - bw // 2, base_y + step*2,  bw, 50)
        self._quit_btn.rect   = pygame.Rect(cx - bw // 2, base_y + step*3,  bw, 40)


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
        W, H = self.screen.get_size()
        self.screen.fill(COLORS["bg"])

        t = self._f_title.render(
            "MULTI-ROBOT SYSTEM EVALUATOR", True, COLORS["text"]
        )
        self.screen.blit(t, t.get_rect(centerx=W // 2, y=max(30, int(H * 0.07))))

        sub = self._f_sub.render(
            "Algorithm Benchmarking for MAPF & MRTA",
            True, COLORS["text_muted"],
        )
        self.screen.blit(sub, sub.get_rect(centerx=W // 2, y=max(60, int(H * 0.13))))

        r = self._create_btn.rect
        panel_x = r.x - 20
        panel_y = r.y - 18
        panel_w = r.w + 40
        panel_h = self._quit_btn.rect.bottom - r.top + 28
        draw_panel(self.screen, (panel_x, panel_y, panel_w, panel_h))

        for btn in self._btns:
            btn.draw(self.screen)

        pygame.display.flip()

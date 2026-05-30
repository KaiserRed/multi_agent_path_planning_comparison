"""
Reusable Pygame UI widgets for the main menu.
"""

import pygame


_DARK: dict = {
    "bg":            (13,  17,  36),
    "panel":         (22,  30,  58),
    "panel_light":   (32,  44,  80),
    "accent":        (72, 149, 255),
    "accent_dark":   (45, 105, 210),
    "text":          (225, 232, 255),
    "text_muted":    (130, 148, 195),
    "selected":      (45,  105, 210),
    "hover":         (38,  55,  95),
    "border":        (55,  75, 130),
    "success":       (55, 195,  95),
    "error":         (220,  65,  65),
    "task":          (255, 195,  50),
    # Grid
    "grid_free":     (28,  38,  65),
    "grid_obstacle": (52,  57,  80),
    "grid_border":   (46,  59,  96),
}

_LIGHT: dict = {
    "bg":            (238, 242, 252),
    "panel":         (255, 255, 255),
    "panel_light":   (224, 230, 246),
    "accent":        (38, 110, 225),
    "accent_dark":   (22,  80, 185),
    "text":          (18,  22,  50),
    "text_muted":    (88, 104, 148),
    "selected":      (22,  80, 185),
    "hover":         (208, 218, 242),
    "border":        (172, 190, 228),
    "success":       (25, 148,  58),
    "error":         (198,  38,  38),
    "task":          (186, 118,   0),
    # Grid
    "grid_free":     (212, 220, 242),
    "grid_obstacle": (128, 136, 162),
    "grid_border":   (182, 193, 218),
}


COLORS: dict = dict(_DARK)

_dark_active: bool = True


def set_theme(dark: bool) -> None:
    """Switch between dark (default) and light theme."""
    global _dark_active
    _dark_active = dark
    COLORS.clear()
    COLORS.update(_DARK if dark else _LIGHT)


def is_dark_theme() -> bool:
    return _dark_active



class Button:
    def __init__(self, rect, text: str, font, primary: bool = False):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.primary = primary
        self.active = False
        self.hovered = False
        self._click_frames = 0

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._click_frames = 4
                return True
        return False

    def update(self):
        if self._click_frames > 0:
            self._click_frames -= 1

    def draw(self, surface: pygame.Surface):
        if self.primary:
            bg = COLORS["accent"] if self.hovered else COLORS["accent_dark"]
        elif self.active:
            bg = COLORS["accent_dark"]
        else:
            bg = COLORS["hover"] if self.hovered else COLORS["panel"]

        if self._click_frames > 0:
            bg = COLORS["accent"]

        pygame.draw.rect(surface, bg, self.rect, border_radius=8)
        pygame.draw.rect(surface, COLORS["border"], self.rect, 1, border_radius=8)

        surf = self.font.render(self.text, True, COLORS["text"])
        surface.blit(surf, surf.get_rect(center=self.rect.center))


class RadioGroup:
    def __init__(self, options: list[str], rect, font, selected: int = 0):
        self.options = options
        self.selected = selected
        self.font = font
        self.x, self.y, self.w, self.h = rect
        self._btn_w = self.w // len(options)

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i in range(len(self.options)):
                r = pygame.Rect(self.x + i * self._btn_w, self.y,
                                self._btn_w - 2, self.h)
                if r.collidepoint(event.pos):
                    self.selected = i
                    return True
        return False

    def get_value(self) -> str:
        return self.options[self.selected]

    def draw(self, surface: pygame.Surface):
        for i, opt in enumerate(self.options):
            r = pygame.Rect(self.x + i * self._btn_w, self.y,
                            self._btn_w - 2, self.h)
            bg = COLORS["accent_dark"] if i == self.selected else COLORS["panel"]
            if i != self.selected:
                mx, my = pygame.mouse.get_pos()
                if r.collidepoint(mx, my):
                    bg = COLORS["hover"]
            pygame.draw.rect(surface, bg, r, border_radius=7)
            pygame.draw.rect(surface, COLORS["border"], r, 1, border_radius=7)
            txt = self.font.render(opt, True, COLORS["text"])
            surface.blit(txt, txt.get_rect(center=r.center))


class Slider:
    def __init__(self, rect, min_val: float, max_val: float,
                 value: float, font, label: str = ""):
        self.rect = pygame.Rect(rect)
        self.min_val = min_val
        self.max_val = max_val
        self.value = float(value)
        self.font = font
        self.label = label
        self._dragging = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._dragging = True
                self._set(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP:
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            self._set(event.pos[0])

    def _set(self, x: int):
        ratio = (x - self.rect.x) / max(self.rect.width, 1)
        ratio = max(0.0, min(1.0, ratio))
        self.value = self.min_val + ratio * (self.max_val - self.min_val)

    def get_value(self) -> float:
        return self.value

    def draw(self, surface: pygame.Surface):
        if self.label:
            lbl = self.font.render(
                f"{self.label}: {self.value:.0f}%", True, COLORS["text_muted"]
            )
            surface.blit(lbl, (self.rect.x, self.rect.y - 20))

        track = pygame.Rect(self.rect.x, self.rect.centery - 3,
                            self.rect.width, 6)
        pygame.draw.rect(surface, COLORS["panel_light"], track, border_radius=3)

        ratio = (self.value - self.min_val) / max(self.max_val - self.min_val, 1)
        fw = int(ratio * self.rect.width)
        if fw > 0:
            fill = pygame.Rect(self.rect.x, self.rect.centery - 3, fw, 6)
            pygame.draw.rect(surface, COLORS["accent"], fill, border_radius=3)

        tx = self.rect.x + fw
        pygame.draw.circle(surface, COLORS["accent"], (tx, self.rect.centery), 10)
        pygame.draw.circle(surface, COLORS["text"], (tx, self.rect.centery), 6)


class NumberInput:
    def __init__(self, rect, value: int, font,
                 min_val: int = 1, max_val: int = 999):
        self.rect = pygame.Rect(rect)
        self.value = value
        self.font = font
        self.min_val = min_val
        self.max_val = max_val
        self._text = str(value)
        self.active = False
        self._cursor_timer = 0
        self._cursor_vis = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            was = self.active
            self.active = self.rect.collidepoint(event.pos)
            if self.active and not was:
                self._text = str(self.value)

        if self.active and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self._text = self._text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.active = False
                self._commit()
            elif event.unicode.isdigit() and len(self._text) < 4:
                self._text += event.unicode
            self._commit()

    def _commit(self):
        try:
            v = int(self._text) if self._text else self.min_val
            self.value = max(self.min_val, min(self.max_val, v))
        except ValueError:
            pass

    def update(self, dt_ms: int):
        if self.active:
            self._cursor_timer += dt_ms
            if self._cursor_timer >= 500:
                self._cursor_vis = not self._cursor_vis
                self._cursor_timer = 0
        else:
            self._cursor_vis = False
            self._cursor_timer = 0

    def get_value(self) -> int:
        return self.value

    def draw(self, surface: pygame.Surface):
        bg = COLORS["accent_dark"] if self.active else COLORS["panel"]
        border = COLORS["accent"] if self.active else COLORS["border"]
        pygame.draw.rect(surface, bg, self.rect, border_radius=6)
        pygame.draw.rect(surface, border, self.rect, 1, border_radius=6)

        display = (self._text if self.active else str(self.value))
        if self.active and self._cursor_vis:
            display += "|"

        txt = self.font.render(display, True, COLORS["text"])
        surface.blit(txt, txt.get_rect(center=self.rect.center))


def draw_panel(surface: pygame.Surface, rect, alpha: int = 210, radius: int = 10):
    """Draw a semi-transparent rounded panel."""
    s = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    r = pygame.Rect(0, 0, rect[2], rect[3])
    pygame.draw.rect(s, (*COLORS["panel"], alpha), r, border_radius=radius)
    surface.blit(s, (rect[0], rect[1]))
    pygame.draw.rect(surface, COLORS["border"], rect, 1, border_radius=radius)

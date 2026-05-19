"""
Cross-platform file dialogs.

Priority on Linux:
  1. zenity  (GTK, works on both Wayland and X11)
  2. kdialog (KDE / Plasma)
  3. tkinter (fallback, may look out-of-place on some setups)

On Windows / macOS tkinter is used directly (it's native there).

Public API
----------
open_file(title, filetypes)    → str | None
open_files(title, filetypes)   → list[str]
save_file(title, filetypes, default_ext) → str | None

filetypes format: list of (label, pattern_string) tuples, e.g.
    [("Map files", "*.json *.map"), ("All files", "*")]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path



def _zenity_available() -> bool:
    try:
        subprocess.run(["zenity", "--version"],
                       capture_output=True, check=True, timeout=3)
        return True
    except Exception:
        return False


def _kdialog_available() -> bool:
    try:
        subprocess.run(["kdialog", "--version"],
                       capture_output=True, check=True, timeout=3)
        return True
    except Exception:
        return False


def _zenity_filters(filetypes: list[tuple[str, str]]) -> list[str]:
    args = []
    for name, pattern in filetypes:
        exts = pattern.split()
        if exts:
            args.append(f"--file-filter={name} | {' '.join(exts)}")
    return args


def _kdialog_filter(filetypes: list[tuple[str, str]]) -> str:
    if not filetypes:
        return ""
    parts = []
    for name, pattern in filetypes:
        exts = " ".join(pattern.split())
        parts.append(f"{name} ({exts})")
    return " | ".join(parts)



def open_file(
    title: str = "Open File",
    filetypes: list[tuple[str, str]] | None = None,
) -> str | None:
    """Return a single selected file path, or None if cancelled."""
    filetypes = filetypes or []

    if sys.platform.startswith("linux"):
        if _zenity_available():
            try:
                cmd = ["zenity", "--file-selection", f"--title={title}"]
                cmd += _zenity_filters(filetypes)
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=120)
                path = r.stdout.strip()
                return path if path else None
            except Exception:
                pass

        if _kdialog_available():
            try:
                cmd = ["kdialog", f"--title={title}",
                       "--getopenfilename", str(Path.cwd()),
                       _kdialog_filter(filetypes)]
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=120)
                path = r.stdout.strip()
                return path if path and path != "cancel" else None
            except Exception:
                pass

    return _tk_open_file(title, filetypes)



def open_files(
    title: str = "Open Files",
    filetypes: list[tuple[str, str]] | None = None,
) -> list[str]:
    """Return a list of selected file paths (may be empty)."""
    filetypes = filetypes or []

    if sys.platform.startswith("linux"):
        if _zenity_available():
            try:
                cmd = ["zenity", "--file-selection", "--multiple",
                       "--separator=\n", f"--title={title}"]
                cmd += _zenity_filters(filetypes)
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=120)
                raw = r.stdout.strip()
                return [p for p in raw.splitlines() if p] if raw else []
            except Exception:
                pass

        if _kdialog_available():
            try:
                cmd = ["kdialog", f"--title={title}",
                       "--getopenfilename", str(Path.cwd()),
                       _kdialog_filter(filetypes), "--multiple"]
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=120)
                raw = r.stdout.strip()
                if not raw or raw == "cancel":
                    return []
                return [p.strip() for p in raw.splitlines() if p.strip()]
            except Exception:
                pass

    return _tk_open_files(title, filetypes)



def save_file(
    title: str = "Save File",
    filetypes: list[tuple[str, str]] | None = None,
    default_ext: str = "",
) -> str | None:
    """Return a save path chosen by the user, or None if cancelled."""
    filetypes = filetypes or []

    if sys.platform.startswith("linux"):
        if _zenity_available():
            try:
                cmd = ["zenity", "--file-selection", "--save",
                       "--confirm-overwrite", f"--title={title}"]
                cmd += _zenity_filters(filetypes)
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=120)
                path = r.stdout.strip()
                if not path:
                    return None
                # Append extension if missing
                if default_ext and not Path(path).suffix:
                    path += default_ext
                return path
            except Exception:
                pass

        if _kdialog_available():
            try:
                cmd = ["kdialog", f"--title={title}",
                       "--getsavefilename", str(Path.cwd()),
                       _kdialog_filter(filetypes)]
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=120)
                path = r.stdout.strip()
                if not path or path == "cancel":
                    return None
                if default_ext and not Path(path).suffix:
                    path += default_ext
                return path
            except Exception:
                pass

    # tkinter fallback
    return _tk_save_file(title, filetypes, default_ext)



def _tk_filetypes(filetypes: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Convert format to tkinter format (each ext as separate entry or tuple)."""
    result = []
    for name, pattern in filetypes:
        exts = pattern.split()
        if len(exts) == 1:
            result.append((name, exts[0]))
        else:
            result.append((name, " ".join(exts)))
    return result


def _tk_open_file(title: str, filetypes: list[tuple[str, str]]) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title=title, filetypes=_tk_filetypes(filetypes)
        )
        root.destroy()
        return path if path else None
    except Exception:
        return None


def _tk_open_files(title: str, filetypes: list[tuple[str, str]]) -> list[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        paths = filedialog.askopenfilenames(
            title=title, filetypes=_tk_filetypes(filetypes)
        )
        root.destroy()
        return list[str](paths) if paths else []
    except Exception:
        return []


def _tk_save_file(
    title: str,
    filetypes: list[tuple[str, str]],
    default_ext: str,
) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.asksaveasfilename(
            title=title,
            filetypes=_tk_filetypes(filetypes),
            defaultextension=default_ext,
        )
        root.destroy()
        return path if path else None
    except Exception:
        return None

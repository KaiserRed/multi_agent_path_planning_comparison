# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Multi-Robot System Evaluator.

Build commands
--------------
Linux:
    pyinstaller mrse.spec

Windows (run from Windows with the repo cloned):
    pyinstaller mrse.spec
"""

import sys
from pathlib import Path

SRC = Path("src").resolve()

a = Analysis(
    [str(SRC / "main.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # MAPF planners
        "mapf.planner",
        "mapf.a_star",
        "mapf.focal_a_star",
        "mapf.cbs",
        "mapf.cbs.cbs",
        "mapf.ecbs",
        "mapf.ecbs.ecbs",
        "mapf.eecbs",
        "mapf.eecbs.eecbs",
        "mapf.m_star",
        "mapf.m_star.m_star",
        "mapf.pibt",
        "mapf.pibt.pibt",
        "mapf.pibt.dist_table",
        "mapf.ca_star",
        "mapf.ca_star.ca_star",
        "mapf.whca_star",
        "mapf.whca_star.whca_star",
        "mapf.sipp",
        "mapf.sipp.sipp",
        # MRTA planners
        "mrta.planner",
        "mrta.hungarian",
        "mrta.min_cost_flow",
        "mrta.sequential_auction",
        "mrta.greedy",
        "mrta.combinatorial_auction",
        "mrta.random_assign",
        # Batch mode
        "batch.config",
        "batch.generator",
        "batch.plotter",
        "batch.runner",
        # Core
        "core.agent",
        "core.task",
        "core.world",
        # Other
        "registry",
        "scenario",
        "simulation.simulator",
        "ui.algo_select",
        "ui.batch_ui",
        "ui.dialogs",
        "ui.editor",
        "ui.menu",
        "ui.widgets",
        "visualization.render",
        # stdlib / third-party that PyInstaller may miss
        "tkinter",
        "tkinter.filedialog",
        "queue",
        "heapq",
        "collections",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["IPython", "jupyter"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="mrse",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # One single file — no dist/ folder needed.
    onefile=True,
    console=False,       # no terminal window on Windows / Linux desktop
    # Windows-specific: show a console for debugging with console=True above.
    # icon="assets/icon.ico",   # uncomment and provide an .ico to set app icon
)
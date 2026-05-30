"""Batch results export — CSV file and 4 matplotlib plots."""

from __future__ import annotations

import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


_PLOT_STYLE = {
    "figure.facecolor": "#ffffff",
    "axes.facecolor":   "#f5f7fc",
    "axes.edgecolor":   "#b0b8cc",
    "axes.labelcolor":  "#1a1e32",
    "xtick.color":      "#4a5068",
    "ytick.color":      "#4a5068",
    "text.color":       "#1a1e32",
    "grid.color":       "#d0d6e8",
    "grid.linestyle":   "--",
    "grid.alpha":       0.7,
    "lines.linewidth":  2.0,
    "legend.facecolor": "#ffffff",
    "legend.edgecolor": "#b0b8cc",
    "legend.framealpha": 0.95,
}

_MRTA_MARKERS: dict[str, str] = {
    "Hungarian":             "o",   # кружок
    "Greedy":                "s",   # квадрат
    "Sequential Auction":    "D",   # ромб
    "Min-Cost Flow":         "^",   # треугольник вверх
    "Combinatorial Auction": "v",   # треугольник вниз
}
_MARKER_DEFAULT = "P" 

_MAPF_COLORS: dict[str, str] = {
    "CBS (A*)":   "#1a6fcc",  # синий
    "CBS (SIPP)": "#d95f02",  # оранжевый
    "ECBS":       "#1b9e4a",  # зелёный
    "EECBS":      "#b8860b",  # тёмно-жёлтый
    "M*":         "#7b2d8b",  # фиолетовый
    "CA*":        "#cc2222",  # красный
    "WHCA*":      "#0891b2",  # голубой
    "PIBT":       "#c2185b",  # розовый
}
_COLOR_FALLBACK = [
    "#2e7d32", "#1565c0", "#e65100", "#6a1b9a",
    "#00695c", "#f9a825", "#4e342e", "#880e4f",
]


def _combo_label(row_key) -> str:
    """Human-readable label for a (mrta_algo, mapf_algo) combo."""
    mrta, mapf = row_key
    return f"{mrta} / {mapf}"


def _make_timestamped_dir(base_dir: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(base_dir, ts)
    os.makedirs(out, exist_ok=True)
    return out


def _plot_metric(
    ax,
    grouped: pd.DataFrame,
    combos: list,
    metric_col: str,
    y_label: str,
    title: str,
):
    """Draw one line per combo onto *ax*."""
    unknown_mapf: list[str] = []

    def _color(mapf_name: str) -> str:
        if mapf_name in _MAPF_COLORS:
            return _MAPF_COLORS[mapf_name]
        if mapf_name not in unknown_mapf:
            unknown_mapf.append(mapf_name)
        return _COLOR_FALLBACK[unknown_mapf.index(mapf_name) % len(_COLOR_FALLBACK)]

    for combo in combos:
        if combo not in grouped.groups:
            continue
        grp = grouped.get_group(combo)
        ns = grp["n_robots"]
        mean = grp[metric_col]

        mrta_name, mapf_name = combo
        marker = _MRTA_MARKERS.get(mrta_name, _MARKER_DEFAULT)
        color  = _color(mapf_name)

        ax.plot(ns, mean, label=_combo_label(combo),
                color=color, marker=marker, markersize=6)

    ax.set_xlabel("Number of robots")
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.grid(True)
    if combos:
        n_cols = max(1, min(len(combos), 3))
        ax.legend(
            fontsize=8,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.18),
            ncol=n_cols,
            borderaxespad=0,
        )


def save_results(df: pd.DataFrame, output_dir: str) -> str:
    """Save CSV and 4 plot PNGs into a timestamped sub-folder.

    Returns the path to the output folder.
    """
    out = _make_timestamped_dir(output_dir)

    csv_path = os.path.join(out, "results.csv")
    df.to_csv(csv_path, index=False)

    success_df = df[df["success"]].copy()

    if success_df.empty:
        success_df = df.copy()
        success_df["makespan"] = 0
        success_df["soc"] = 0

    combos = list(df.groupby(["mrta_algo", "mapf_algo"]).groups.keys())

    def _agg(source: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        g = source.groupby(["mrta_algo", "mapf_algo", "n_robots"])
        mean = g[cols].mean().reset_index()
        std = g[cols].std().reset_index()
        for c in cols:
            mean[c + "_std"] = std[c]
        return mean

    success_agg = _agg(success_df, ["makespan", "soc",
                                     "plan_total_s", "plan_mrta_s",
                                     "plan_mapf_s"])

    sr_agg = (
        df.groupby(["mrta_algo", "mapf_algo", "n_robots"])["success"]
        .mean()
        .reset_index()
        .rename(columns={"success": "success_rate"})
    )
    sr_agg["success_rate_std"] = (
        df.groupby(["mrta_algo", "mapf_algo", "n_robots"])["success"]
        .std()
        .reset_index()["success"]
    )

    with plt.style.context(_PLOT_STYLE):
        def _save(fig, name: str):
            fig.tight_layout()
            fig.subplots_adjust(bottom=0.30)
            fig.savefig(os.path.join(out, name), dpi=150, bbox_inches="tight")
            plt.close(fig)

        # 1. Makespan vs robots
        fig, ax = plt.subplots(figsize=(10, 6))
        _plot_metric(
            ax,
            success_agg.groupby(["mrta_algo", "mapf_algo"]),
            combos,
            "makespan",
            "Makespan (steps)",
            "Makespan vs Number of Robots",
        )
        _save(fig, "makespan_vs_robots.png")

        # 2. SOC vs robots
        fig, ax = plt.subplots(figsize=(10, 6))
        _plot_metric(
            ax,
            success_agg.groupby(["mrta_algo", "mapf_algo"]),
            combos,
            "soc",
            "Sum of Costs",
            "Sum of Costs vs Number of Robots",
        )
        _save(fig, "soc_vs_robots.png")

        # 3. Planning time vs robots
        fig, ax = plt.subplots(figsize=(10, 6))
        _plot_metric(
            ax,
            success_agg.groupby(["mrta_algo", "mapf_algo"]),
            combos,
            "plan_total_s",
            "Planning time (s)",
            "Planning Time vs Number of Robots",
        )
        _save(fig, "planning_time_vs_robots.png")

        # 4. Success rate vs robots
        fig, ax = plt.subplots(figsize=(10, 6))
        _plot_metric(
            ax,
            sr_agg.groupby(["mrta_algo", "mapf_algo"]),
            combos,
            "success_rate",
            "Success rate",
            "Success Rate vs Number of Robots",
        )
        ax.set_ylim(0, 1.05)
        _save(fig, "success_rate_vs_robots.png")

    return out


def replot_csv(csv_path: str) -> str:
    """Regenerate all 4 plots from an existing results CSV.

    Saves the new PNGs into the same folder as the CSV.
    Returns that folder path.
    """
    df = pd.read_csv(csv_path)
    df["success"] = df["success"].astype(bool)

    out = os.path.dirname(os.path.abspath(csv_path))

    success_df = df[df["success"]].copy()
    if success_df.empty:
        success_df = df.copy()
        success_df["makespan"] = 0
        success_df["soc"] = 0

    combos = list(df.groupby(["mrta_algo", "mapf_algo"]).groups.keys())

    def _agg(source: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        g = source.groupby(["mrta_algo", "mapf_algo", "n_robots"])
        mean = g[cols].mean().reset_index()
        std  = g[cols].std().reset_index()
        for c in cols:
            mean[c + "_std"] = std[c]
        return mean

    success_agg = _agg(success_df, ["makespan", "soc",
                                     "plan_total_s", "plan_mrta_s",
                                     "plan_mapf_s"])
    sr_agg = (
        df.groupby(["mrta_algo", "mapf_algo", "n_robots"])["success"]
        .mean().reset_index().rename(columns={"success": "success_rate"})
    )
    sr_agg["success_rate_std"] = (
        df.groupby(["mrta_algo", "mapf_algo", "n_robots"])["success"]
        .std().reset_index()["success"]
    )

    def _save(fig, name: str):
        fig.tight_layout()
        fig.subplots_adjust(bottom=0.30)
        fig.savefig(os.path.join(out, name), dpi=150, bbox_inches="tight")
        plt.close(fig)

    with plt.style.context(_PLOT_STYLE):
        fig, ax = plt.subplots(figsize=(10, 6))
        _plot_metric(ax, success_agg.groupby(["mrta_algo", "mapf_algo"]),
                     combos, "makespan", "Makespan (steps)",
                     "Makespan vs Number of Robots")
        _save(fig, "makespan_vs_robots.png")

        fig, ax = plt.subplots(figsize=(10, 6))
        _plot_metric(ax, success_agg.groupby(["mrta_algo", "mapf_algo"]),
                     combos, "soc", "Sum of Costs",
                     "Sum of Costs vs Number of Robots")
        _save(fig, "soc_vs_robots.png")

        fig, ax = plt.subplots(figsize=(10, 6))
        _plot_metric(ax, success_agg.groupby(["mrta_algo", "mapf_algo"]),
                     combos, "plan_total_s", "Planning time (s)",
                     "Planning Time vs Number of Robots")
        _save(fig, "planning_time_vs_robots.png")

        fig, ax = plt.subplots(figsize=(10, 6))
        _plot_metric(ax, sr_agg.groupby(["mrta_algo", "mapf_algo"]),
                     combos, "success_rate", "Success rate",
                     "Success Rate vs Number of Robots")
        ax.set_ylim(0, 1.05)
        _save(fig, "success_rate_vs_robots.png")

    print(f"Plots saved to: {out}")
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python -m batch.plotter <path/to/results.csv>")
        sys.exit(1)
    replot_csv(sys.argv[1])

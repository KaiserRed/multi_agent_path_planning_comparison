"""Batch results export — CSV file and 4 matplotlib plots."""

from __future__ import annotations

import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")   # headless, no display required
import matplotlib.pyplot as plt
import pandas as pd


_PLOT_STYLE = {
    "figure.facecolor": "#0d1124",
    "axes.facecolor": "#16204a",
    "axes.edgecolor": "#37497c",
    "axes.labelcolor": "#e1e8ff",
    "xtick.color": "#8294c3",
    "ytick.color": "#8294c3",
    "text.color": "#e1e8ff",
    "grid.color": "#2b3a68",
    "grid.linestyle": "--",
    "grid.alpha": 0.5,
    "lines.linewidth": 2.0,
    "legend.facecolor": "#16204a",
    "legend.edgecolor": "#37497c",
}


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
    cmap = plt.colormaps.get_cmap("tab20")
    colors = [cmap(i / max(len(combos), 1)) for i in range(len(combos))]

    for i, combo in enumerate(combos):
        key = combo
        if key not in grouped.groups:
            continue
        grp = grouped.get_group(key)
        ns = grp["n_robots"]
        mean = grp[metric_col]
        std = grp.get(metric_col + "_std", None)

        ax.plot(ns, mean, label=_combo_label(combo),
                color=colors[i], marker="o", markersize=5)
        if std is not None:
            ax.fill_between(ns, mean - std, mean + std,
                            alpha=0.15, color=colors[i])

    ax.set_xlabel("Number of robots")
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.grid(True)
    if combos:
        ax.legend(fontsize=8, loc="best",
                  ncol=max(1, len(combos) // 10))


def save_results(df: pd.DataFrame, output_dir: str) -> str:
    """Save CSV and 4 plot PNGs into a timestamped sub-folder.

    Returns the path to the output folder.
    """
    out = _make_timestamped_dir(output_dir)

    # CSV
    csv_path = os.path.join(out, "results.csv")
    df.to_csv(csv_path, index=False)

    # Aggregate: filter successes only for makespan/soc metrics
    success_df = df[df["success"]].copy()

    if success_df.empty:
        # Still save success-rate chart using all data
        success_df = df.copy()
        success_df["makespan"] = 0
        success_df["soc"] = 0

    combos = list(df.groupby(["mrta_algo", "mapf_algo"]).groups.keys())

    # Build aggregated DataFrame: mean + std per (combo, n_robots)
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

    # Success rate aggregation (uses full df)
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
        fig.tight_layout()
        fig.savefig(os.path.join(out, "makespan_vs_robots.png"), dpi=150)
        plt.close(fig)

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
        fig.tight_layout()
        fig.savefig(os.path.join(out, "soc_vs_robots.png"), dpi=150)
        plt.close(fig)

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
        fig.tight_layout()
        fig.savefig(os.path.join(out, "planning_time_vs_robots.png"), dpi=150)
        plt.close(fig)

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
        fig.tight_layout()
        fig.savefig(os.path.join(out, "success_rate_vs_robots.png"), dpi=150)
        plt.close(fig)

    return out

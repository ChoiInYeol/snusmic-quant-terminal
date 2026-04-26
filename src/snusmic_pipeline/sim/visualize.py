"""Matplotlib renderers for :class:`SimulationResult`.

Two figures:

* ``plot_equity_curves`` — line chart of equity over time, one line per
  persona, plus a dashed line of cumulative contributions to make
  net-of-deposit performance obvious.
* ``plot_net_profit_bars`` — final-day net profit per persona, sorted.

Each figure is saved at the requested path. The callers (CLI / tests) own
choosing where artifacts land — this module never picks paths.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # always headless; CI and CLI use the same backend.

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from .contracts import SimulationResult  # noqa: E402

PERSONA_COLORS = {
    "oracle": "#16a34a",
    "weak_oracle": "#2563eb",
    "smic_follower": "#f59e0b",
    "smic_follower_v2": "#dc2626",
    "all_weather": "#475569",
}


def plot_equity_curves(result: SimulationResult, out_path: Path) -> Path:
    """Equity-curve overlay; one subplot, one line per persona."""
    if not result.equity_points:
        raise ValueError("SimulationResult has no equity points to plot.")
    by_persona: dict[str, list[tuple[date, float]]] = defaultdict(list)
    contributions: list[tuple[date, float]] = []
    contribution_seen: set[date] = set()
    for ep in result.equity_points:
        by_persona[ep.persona].append((ep.date, ep.equity_krw))
        if ep.date not in contribution_seen:
            contributions.append((ep.date, ep.contributed_capital_krw))
            contribution_seen.add(ep.date)
    contributions.sort(key=lambda x: x[0])

    fig, ax = plt.subplots(figsize=(12, 6))
    persona_labels = {s.persona: s.label for s in result.summaries}
    for persona, points in by_persona.items():
        points.sort(key=lambda x: x[0])
        xs = [p[0] for p in points]
        ys = [p[1] / 1e6 for p in points]  # KRW → M KRW
        ax.plot(
            xs,
            ys,
            label=persona_labels.get(persona, persona),
            color=PERSONA_COLORS.get(persona),
            linewidth=1.6,
        )
    if contributions:
        cx = [c[0] for c in contributions]
        cy = [c[1] / 1e6 for c in contributions]
        ax.plot(cx, cy, label="Cumulative deposits", color="black", linestyle="--", linewidth=1.0)

    ax.set_yscale("log")
    ax.set_title("Persona equity curves (log scale, M KRW)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity (M KRW, log)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)
    fig.autofmt_xdate()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


def plot_net_profit_bars(result: SimulationResult, out_path: Path) -> Path:
    """Bar chart of final net profit per persona (sorted ascending)."""
    if not result.summaries:
        raise ValueError("SimulationResult has no summaries to plot.")
    summaries = sorted(result.summaries, key=lambda s: s.net_profit_krw)
    labels = [s.label for s in summaries]
    values = [s.net_profit_krw / 1e6 for s in summaries]
    colors = [PERSONA_COLORS.get(s.persona, "#6b7280") for s in summaries]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.barh(labels, values, color=colors)
    for bar, value in zip(bars, values, strict=True):
        ax.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            f" {value:,.1f}M",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=9,
        )
    ax.axvline(0, color="black", linewidth=0.6)
    ax.set_title("Persona net profit (M KRW) — final equity − total contributed")
    ax.set_xlabel("Net Profit (M KRW)")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


def plot_portfolio_composition(
    result: SimulationResult,
    out_path: Path,
    *,
    top_k: int = 8,
) -> Path:
    """Stacked-area chart of every persona's month-end portfolio composition.

    One subplot per persona, each showing the top ``top_k`` holdings by
    end-of-sim weight as named bands plus an "others" band. The Y axis
    is the share of the invested book (cash excluded), so each subplot's
    bands always sum to 1.0 on any given month-end.
    """
    if not result.monthly_holdings:
        raise ValueError("SimulationResult has no monthly_holdings to plot.")
    persona_labels = {s.persona: s.label for s in result.summaries}
    rows = [m.model_dump() for m in result.monthly_holdings]
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("monthly_holdings rendered an empty frame.")
    personas = sorted(
        df["persona"].unique(), key=lambda p: -result.summaries[0].final_equity_krw if False else 0
    )
    personas = list(df["persona"].unique())
    n = len(personas)
    fig, axes = plt.subplots(n, 1, figsize=(13, 3.0 * n), sharex=True)
    if n == 1:
        axes = [axes]
    for ax, persona in zip(axes, personas, strict=True):
        sub = df[df["persona"] == persona].copy()
        # Pick the top_k symbols by their FINAL-month weight.
        last_month = sub["month_end"].max()
        last_slice = sub[sub["month_end"] == last_month]
        top_symbols = list(
            last_slice.sort_values("weight_in_portfolio", ascending=False)["symbol"].head(top_k)
        )
        # Pivot to wide: index=month_end, columns=symbol, values=weight.
        wide = sub.pivot_table(
            index="month_end", columns="symbol", values="weight_in_portfolio", aggfunc="sum"
        ).fillna(0.0)
        wide = wide.sort_index()
        if wide.empty:
            continue
        # Group anything not in ``top_symbols`` as "Others".
        others_cols = [c for c in wide.columns if c not in top_symbols]
        if others_cols:
            others_sum = wide[others_cols].sum(axis=1)
            wide = wide.drop(columns=others_cols)
            wide["Others"] = others_sum
        # Re-order so Others is last.
        column_order = [c for c in top_symbols if c in wide.columns]
        if "Others" in wide.columns:
            column_order.append("Others")
        wide = wide[column_order]
        # Use company names as labels where available.
        sym_to_company = {row["symbol"]: row["company"] for row in rows if row["company"]}
        labels = []
        for col in wide.columns:
            if col == "Others":
                labels.append("Others")
            else:
                comp = sym_to_company.get(col, "")
                labels.append(f"{col} {comp[:14]}" if comp else col)
        ax.stackplot(wide.index, wide.values.T, labels=labels, alpha=0.85)
        ax.set_title(persona_labels.get(persona, persona))
        ax.set_ylim(0, 1)
        ax.set_ylabel("Weight")
        ax.legend(loc="upper left", fontsize=7, ncol=2, framealpha=0.85)
        ax.grid(True, alpha=0.3)
    axes[-1].set_xlabel("Month-end")
    fig.suptitle("Portfolio composition over time (top holdings, weight share of invested book)", y=1.0)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


def plot_drawdowns(result: SimulationResult, out_path: Path) -> Path:
    """Drawdown curve (= equity / running peak − 1) per persona."""
    if not result.equity_points:
        raise ValueError("SimulationResult has no equity points to plot.")
    fig, ax = plt.subplots(figsize=(12, 5))
    by_persona: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for ep in result.equity_points:
        by_persona[ep.persona].append((ep.date, ep.equity_krw))
    persona_labels = {s.persona: s.label for s in result.summaries}
    for persona, points in by_persona.items():
        points.sort(key=lambda x: x[0])
        xs, equity = zip(*points, strict=True)
        peak = 0.0
        dd: list[float] = []
        for value in equity:
            peak = max(peak, value)
            if peak <= 0:
                dd.append(0.0)
            else:
                dd.append((value - peak) / peak * 100.0)
        ax.plot(
            xs,
            dd,
            label=persona_labels.get(persona, persona),
            color=PERSONA_COLORS.get(persona),
            linewidth=1.4,
        )
    ax.set_title("Drawdown (%) by persona")
    ax.set_ylabel("Drawdown (%)")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left", fontsize=9)
    fig.autofmt_xdate()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path

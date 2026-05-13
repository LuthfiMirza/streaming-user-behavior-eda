"""Generate publication-style static visuals for the streaming EDA story.

The script reads the processed master dataset and writes seven standalone PNG
charts to the visuals directory using a consistent dark theme.
"""

from __future__ import annotations

from pathlib import Path
import warnings
import os

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/mplconfig")
os.environ.setdefault("XDG_CACHE_HOME", "/private/tmp")

import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "master_dataset.csv"
VISUALS_DIR = PROJECT_ROOT / "visuals"

DARK = "#0F0F0F"
ACCENT = "#1DB954"
SECONDARY = "#FF6B6B"
TEXT = "#F5F5F5"
MUTED = "#BDBDBD"
GRID = "#333333"
FONT = "DejaVu Sans"
DEFAULT_FIGSIZE = (12, 6)
DPI = 150


def load_data() -> pd.DataFrame:
    """Load the master dataset and add compatibility columns if needed."""
    df = pd.read_csv(DATA_PATH)
    if "play_count" not in df.columns:
        df["play_count"] = 1
    if "skip_count" not in df.columns:
        df["skip_count"] = df["skipped"].astype(int) if "skipped" in df.columns else 0
    if "is_completed" in df.columns:
        df["is_completed"] = df["is_completed"].astype(bool)
    return df


def require_columns(df: pd.DataFrame, columns: list[str], chart_name: str) -> bool:
    """Return whether all required columns exist, warning when not."""
    missing = [column for column in columns if column not in df.columns]
    if missing:
        warnings.warn(f"Skipping {chart_name}: missing columns {missing}")
        return False
    return True


def apply_theme() -> None:
    """Apply the shared dark publication style."""
    plt.rcParams.update({
        "figure.facecolor": DARK,
        "axes.facecolor": DARK,
        "savefig.facecolor": DARK,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "text.color": TEXT,
        "font.family": FONT,
        "axes.titleweight": "bold",
        "axes.titlesize": 18,
        "axes.labelsize": 11,
        "legend.facecolor": DARK,
        "legend.edgecolor": GRID,
        "grid.color": GRID,
    })
    sns.set_theme(style="darkgrid", rc={"figure.facecolor": DARK, "axes.facecolor": DARK})


def save_fig(path: Path) -> None:
    """Save the active Matplotlib figure with standard output settings."""
    plt.tight_layout()
    plt.savefig(path, dpi=DPI, bbox_inches="tight", facecolor=DARK)
    plt.close()
    print(f"Saved {path.relative_to(PROJECT_ROOT)}")


def genre_heatmap(df: pd.DataFrame) -> None:
    """Create average session-duration heatmap by top genre and daypart."""
    if not require_columns(df, ["genre", "time_of_day", "session_duration_minutes"], "genre_heatmap"):
        return
    top_genres = df.groupby("genre")["session_duration_minutes"].sum().nlargest(8).index
    order = ["morning", "afternoon", "evening", "night"]
    matrix = (
        df[df["genre"].isin(top_genres)]
        .pivot_table(index="genre", columns="time_of_day", values="session_duration_minutes", aggfunc="mean")
        .reindex(index=top_genres, columns=order)
    )
    plt.figure(figsize=DEFAULT_FIGSIZE)
    ax = sns.heatmap(matrix, annot=True, fmt=".1f", cmap="Greens", linewidths=0.5, linecolor=GRID, cbar_kws={"label": "Avg minutes"})
    ax.set_title("When Do Listeners Tune In by Genre?", pad=16)
    ax.set_xlabel("Time of Day")
    ax.set_ylabel("Genre")
    save_fig(VISUALS_DIR / "genre_heatmap.png")


def retention_cohort(df: pd.DataFrame) -> None:
    """Create simulated D1/D7/D30 retention curves by tenure cohort."""
    if not require_columns(df, ["user_tenure_days", "is_completed"], "retention_cohort"):
        return
    tenure_max = max(float(df["user_tenure_days"].max()), 28)
    cohorts = pd.cut(df["user_tenure_days"], bins=[-1, 7, 14, 21, tenure_max + 1], labels=["Week 1", "Week 2", "Week 3", "Week 4+"])
    base = df.assign(cohort=cohorts).groupby("cohort", observed=False)["is_completed"].mean().fillna(0)
    milestones = ["D1", "D7", "D30"]
    decay = np.linspace(1.0, 0.62, len(milestones))
    plt.figure(figsize=DEFAULT_FIGSIZE)
    palette = [ACCENT, "#55D98B", "#FFB86B", SECONDARY]
    for color, (cohort, value) in zip(palette, base.items()):
        plt.plot(milestones, value * decay, marker="o", linewidth=3, markersize=8, label=cohort, color=color)
    plt.title("Retention Curves by User Cohort", pad=16)
    plt.xlabel("Retention Milestone")
    plt.ylabel("Retention Proxy: Avg Completion Rate")
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    plt.legend(title="Cohort")
    save_fig(VISUALS_DIR / "retention_cohort.png")


def safe_qcut(series: pd.Series, labels: list[int]) -> pd.Series:
    """Quantile score with fallback for low-variance synthetic samples."""
    ranked = series.rank(method="first")
    try:
        return pd.qcut(ranked, q=len(labels), labels=labels).astype(int)
    except ValueError:
        return np.ceil(ranked.rank(pct=True) * len(labels)).clip(1, len(labels)).astype(int)


def rfm_bubble(df: pd.DataFrame) -> None:
    """Create an RFM bubble chart at user grain."""
    if not require_columns(df, ["user_id", "user_tenure_days", "play_count", "session_duration_minutes"], "rfm_bubble"):
        return
    users = df.groupby("user_id").agg(
        recency_raw=("user_tenure_days", "max"),
        frequency=("play_count", "sum"),
        monetary=("session_duration_minutes", "sum"),
    ).reset_index()
    users["recency"] = users["recency_raw"].max() - users["recency_raw"]
    users["frequency_score"] = safe_qcut(users["frequency"], [1, 2, 3])
    users["monetary_score"] = safe_qcut(users["monetary"], [1, 2, 3])
    users["recency_score"] = 4 - safe_qcut(users["recency"], [1, 2, 3])

    def segment(row: pd.Series) -> str:
        if (row.recency_score, row.frequency_score, row.monetary_score) == (3, 3, 3):
            return "Champions"
        if row.recency_score >= 2 and row.frequency_score >= 2 and row.monetary_score >= 2:
            return "Loyal"
        if row.recency_score == 1 and (row.frequency_score >= 2 or row.monetary_score >= 2):
            return "At Risk"
        if row.recency_score == 1 and row.frequency_score == 1:
            return "Lost"
        return "New"

    users["segment"] = users.apply(segment, axis=1)
    users["bubble_size"] = (users["recency_score"] + 1) * 110
    colors = {"Champions": ACCENT, "Loyal": "#55D98B", "At Risk": "#FFB86B", "Lost": SECONDARY, "New": "#7AA2FF"}
    plt.figure(figsize=DEFAULT_FIGSIZE)
    ax = sns.scatterplot(data=users, x="frequency_score", y="monetary_score", size="bubble_size", hue="segment", palette=colors, sizes=(120, 900), alpha=0.78, edgecolor=TEXT, linewidth=0.6)
    ax.set_title("User Segments — RFM Bubble Chart", pad=16)
    ax.set_xlabel("Frequency Score")
    ax.set_ylabel("Monetary Score")
    ax.set_xticks([1, 2, 3])
    ax.set_yticks([1, 2, 3])
    ax.legend(title="Segment", bbox_to_anchor=(1.02, 1), loc="upper left")
    save_fig(VISUALS_DIR / "rfm_bubble.png")


def session_funnel(df: pd.DataFrame) -> None:
    """Create a horizontal consumption funnel with drop-off annotations."""
    if not require_columns(df, ["session_duration_minutes", "duration_minutes", "is_completed"], "session_funnel"):
        return
    ratio = np.where(df["duration_minutes"] > 0, df["session_duration_minutes"] / df["duration_minutes"], 0)
    stages = ["Started", "Played 10%", "Played 50%", "Completed"]
    values = np.array([len(df), (ratio > 0.10).sum(), (ratio > 0.50).sum(), df["is_completed"].sum()], dtype=float)
    colors = [ACCENT, "#8FE388", "#FFB86B", SECONDARY]
    plt.figure(figsize=DEFAULT_FIGSIZE)
    ax = sns.barplot(x=values, y=stages, palette=colors, orient="h")
    for index, value in enumerate(values):
        ax.text(value + max(values) * 0.02, index, f"{int(value):,}", va="center", color=TEXT, fontweight="bold")
        if index > 0 and values[index - 1] > 0:
            drop = 1 - value / values[index - 1]
            ax.text(max(values) * 0.52, index - 0.48, f"↓ {drop:.1%} drop-off", color=SECONDARY, fontsize=10)
    ax.set_title("Content Consumption Funnel", pad=16)
    ax.set_xlabel("Events")
    ax.set_ylabel("Funnel Stage")
    save_fig(VISUALS_DIR / "session_funnel.png")


def skip_rate_by_category(df: pd.DataFrame) -> None:
    """Create horizontal bar chart of average skip count by genre."""
    if not require_columns(df, ["genre", "skip_count"], "skip_rate_by_category"):
        return
    skip = df.groupby("genre")["skip_count"].mean().sort_values(ascending=False).reset_index()
    colors = [SECONDARY if index < 3 else ACCENT for index in range(len(skip))]
    plt.figure(figsize=DEFAULT_FIGSIZE)
    ax = sns.barplot(data=skip, x="skip_count", y="genre", palette=colors)
    for patch in ax.patches:
        width = patch.get_width()
        ax.text(width + max(skip["skip_count"].max(), 0.05) * 0.03, patch.get_y() + patch.get_height() / 2, f"{width:.2f}", va="center", color=TEXT)
    ax.set_title("Skip Rate by Content Genre", pad=16)
    ax.set_xlabel("Average Skip Count")
    ax.set_ylabel("Genre")
    save_fig(VISUALS_DIR / "skip_rate_by_category.png")


def duration_vs_completion(df: pd.DataFrame) -> None:
    """Create duration-bin completion bar chart with trend overlay."""
    if not require_columns(df, ["duration_minutes", "is_completed"], "duration_vs_completion"):
        return
    max_length = max(float(df["duration_minutes"].max()), 45)
    labels = ["0–10", "10–25", "25–45", "45+"]
    bins = [0, 10, 25, 45, max_length + 1]
    summary = df.assign(duration_bin=pd.cut(df["duration_minutes"], bins=bins, labels=labels, include_lowest=True, right=False)).groupby("duration_bin", observed=False)["is_completed"].mean().fillna(0).reset_index()
    sweet_idx = int(summary["is_completed"].idxmax())
    plt.figure(figsize=DEFAULT_FIGSIZE)
    ax = sns.barplot(data=summary, x="duration_bin", y="is_completed", color=ACCENT)
    ax.plot(summary["duration_bin"].astype(str), summary["is_completed"], color=SECONDARY, marker="o", linewidth=3)
    for patch, value in zip(ax.patches, summary["is_completed"]):
        ax.text(patch.get_x() + patch.get_width() / 2, value + 0.02, f"{value:.0%}", ha="center", color=TEXT, fontweight="bold")
    ax.annotate("Sweet spot", xy=(sweet_idx, summary.loc[sweet_idx, "is_completed"]), xytext=(sweet_idx, min(summary["is_completed"].max() + 0.18, 1.05)), arrowprops={"arrowstyle": "->", "color": SECONDARY, "lw": 2}, color=SECONDARY, fontsize=12, fontweight="bold", ha="center")
    ax.set_title("Content Length vs Completion Rate", pad=16)
    ax.set_xlabel("Content Duration Bin (minutes)")
    ax.set_ylabel("Average Completion Rate")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax.set_ylim(0, max(1.0, summary["is_completed"].max() + 0.25))
    save_fig(VISUALS_DIR / "duration_vs_completion.png")


def creator_loyalty_index(df: pd.DataFrame) -> None:
    """Create top content repeat-listener loyalty index chart."""
    if not require_columns(df, ["content_id", "user_id"], "creator_loyalty_index"):
        return
    plays = df.groupby(["content_id", "user_id"]).size().rename("plays").reset_index()
    loyalty = plays.groupby("content_id").agg(repeat_users=("plays", lambda values: (values > 1).sum()), unique_users=("user_id", "nunique")).reset_index()
    loyalty["loyalty_score"] = np.where(loyalty["unique_users"] > 0, loyalty["repeat_users"] / loyalty["unique_users"], 0)
    loyalty = loyalty.sort_values("loyalty_score", ascending=False).head(10).sort_values("loyalty_score", ascending=True)
    cmap = LinearSegmentedColormap.from_list("loyalty", ["#154D2B", ACCENT])
    norm_values = loyalty["loyalty_score"] / max(loyalty["loyalty_score"].max(), 1e-9)
    plt.figure(figsize=DEFAULT_FIGSIZE)
    ax = sns.barplot(data=loyalty, x="loyalty_score", y="content_id", palette=[cmap(v) for v in norm_values])
    for patch in ax.patches:
        width = patch.get_width()
        ax.text(width + 0.015, patch.get_y() + patch.get_height() / 2, f"{width:.0%}", va="center", color=TEXT)
    ax.set_title("Creator Loyalty Index — Top 10 Content", pad=16)
    ax.set_xlabel("Repeat Listener Rate")
    ax.set_ylabel("Content ID")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax.set_xlim(0, max(1.0, loyalty["loyalty_score"].max() + 0.15))
    save_fig(VISUALS_DIR / "creator_loyalty_index.png")


def main() -> None:
    """Generate all visuals."""
    VISUALS_DIR.mkdir(parents=True, exist_ok=True)
    apply_theme()
    df = load_data()
    genre_heatmap(df)
    retention_cohort(df)
    rfm_bubble(df)
    session_funnel(df)
    skip_rate_by_category(df)
    duration_vs_completion(df)
    creator_loyalty_index(df)


if __name__ == "__main__":
    main()

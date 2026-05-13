"""Interactive Streamlit dashboard for the NOICE-style EDA project."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "master_dataset.csv"
VISUALS_DIR = PROJECT_ROOT / "visuals"

ACCENT = "#1DB954"
SECONDARY = "#FF6B6B"
DARK = "#0F0F0F"

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_ORDER = ["morning", "afternoon", "evening", "night"]
DURATION_LABELS = ["0–10", "10–25", "25–45", "45+"]


st.set_page_config(
    page_title="NOICE Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def apply_global_styles() -> None:
    """Inject small CSS helpers for KPI cards and footer styling."""
    st.markdown(
        """
        <style>
        .metric-card {
            background: #1A1A1A;
            border: 1px solid #2A2A2A;
            border-radius: 14px;
            padding: 18px 18px;
            min-height: 116px;
        }
        .metric-label { color: #BDBDBD; font-size: 0.9rem; margin-bottom: 8px; }
        .metric-value { color: #FFFFFF; font-size: 1.85rem; font-weight: 700; }
        .small-note { color: #BDBDBD; font-size: 0.85rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def generate_synthetic_data(n_users: int = 200, n_content: int = 80, n_events: int = 2000) -> pd.DataFrame:
    """Generate NOICE-style synthetic streaming data inline for cloud demos."""
    rng = np.random.default_rng(42)

    genres = ["Pop", "Rock", "Jazz", "Talk Show", "Tech", "Comedy", "News", "EDM", "R&B", "Classical"]
    formats = ["podcast", "music", "livestream"]
    devices = ["mobile", "desktop", "tablet"]
    channels = ["search", "recommendation", "browse", "social"]
    times_of_day = ["morning", "afternoon", "evening", "night"]
    days = DAY_ORDER
    plans = ["free", "premium", "family"]

    user_ids = [f"U{str(index).zfill(4)}" for index in range(n_users)]
    content_ids = [f"C{str(index).zfill(4)}" for index in range(n_content)]

    rows = []
    for _ in range(n_events):
        user_id = rng.choice(user_ids)
        content_id = rng.choice(content_ids)
        duration_minutes = int(rng.choice([5, 15, 30, 60], p=[0.3, 0.4, 0.2, 0.1]))
        session_duration = min(duration_minutes * rng.uniform(0.3, 1.1), duration_minutes)
        timestamp = pd.Timestamp("2024-01-01") + pd.Timedelta(days=int(rng.integers(0, 90)), hours=int(rng.integers(0, 24)))

        rows.append({
            "user_id": user_id,
            "content_id": content_id,
            "session_id": f"S{rng.integers(100000, 999999)}",
            "timestamp": timestamp,
            "started_at": timestamp,
            "genre": rng.choice(genres),
            "format": rng.choice(formats, p=[0.4, 0.4, 0.2]),
            "duration_minutes": duration_minutes,
            "session_duration_minutes": round(float(session_duration), 2),
            "is_completed": bool(session_duration >= duration_minutes * 0.8),
            "skip_count": int(rng.poisson(1.5)),
            "device": rng.choice(devices, p=[0.6, 0.3, 0.1]),
            "acquisition_channel": rng.choice(channels),
            "time_of_day": rng.choice(times_of_day),
            "day_of_week": rng.choice(days),
            "user_tenure_days": int(rng.integers(0, 90)),
            "subscription_plan": rng.choice(plans, p=[0.5, 0.4, 0.1]),
            "monthly_searches": int(rng.integers(10, 500)),
            "play_count": int(rng.integers(1, 20)),
        })

    df = pd.DataFrame(rows)
    total_playtime = df.groupby("user_id")["session_duration_minutes"].sum()
    threshold = total_playtime.quantile(0.8)
    power_users = total_playtime[total_playtime >= threshold].index
    df["is_power_user"] = df["user_id"].isin(power_users)
    return df


@st.cache_data(show_spinner=False)
def load_or_generate_data() -> pd.DataFrame:
    """Load the committed dataset when available, otherwise generate demo data."""
    if DATA_PATH.exists():
        df = pd.read_csv(DATA_PATH)
    else:
        st.info("⚙️ Generating synthetic dataset for demo...")
        df = generate_synthetic_data()

    if "play_count" not in df.columns:
        df["play_count"] = 1
    if "skip_count" not in df.columns:
        df["skip_count"] = df["skipped"].astype(int) if "skipped" in df.columns else 0
    if "is_completed" in df.columns:
        df["is_completed"] = df["is_completed"].astype(bool)
    for date_column in ["timestamp", "started_at"]:
        if date_column in df.columns:
            df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    return df


def require_columns(df: pd.DataFrame, columns: list[str]) -> bool:
    """Show a Streamlit warning if required columns are unavailable."""
    missing = [column for column in columns if column not in df.columns]
    if missing:
        st.warning(f"Skipping this section because these columns are missing: {', '.join(missing)}")
        return False
    return True


def metric_card(label: str, value: str) -> None:
    """Render a custom KPI card."""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def add_duration_bins(df: pd.DataFrame) -> pd.DataFrame:
    """Add standard content-duration bins."""
    output = df.copy()
    max_duration = max(float(output["duration_minutes"].max()), 45)
    output["duration_bin"] = pd.cut(
        output["duration_minutes"],
        bins=[0, 10, 25, 45, max_duration + 1],
        labels=DURATION_LABELS,
        include_lowest=True,
        right=False,
    )
    return output


def safe_qcut(series: pd.Series, labels: list[int]) -> pd.Series:
    """Create quantile scores with fallback for low-variance samples."""
    ranked = series.rank(method="first")
    try:
        return pd.qcut(ranked, q=len(labels), labels=labels).astype(int)
    except ValueError:
        return np.ceil(ranked.rank(pct=True) * len(labels)).clip(1, len(labels)).astype(int)


def build_rfm(df: pd.DataFrame) -> pd.DataFrame:
    """Build user-level RFM segments for dashboard tables."""
    users = (
        df.groupby("user_id")
        .agg(
            last_tenure_day=("user_tenure_days", "max"),
            frequency=("play_count", "sum"),
            total_duration_minutes=("session_duration_minutes", "sum"),
            avg_skip_count=("skip_count", "mean"),
        )
        .reset_index()
    )
    users["recency"] = users["last_tenure_day"].max() - users["last_tenure_day"]
    users["recency_score"] = 4 - safe_qcut(users["recency"], [1, 2, 3])
    users["frequency_score"] = safe_qcut(users["frequency"], [1, 2, 3])
    users["monetary_score"] = safe_qcut(users["total_duration_minutes"], [1, 2, 3])

    def label_segment(row: pd.Series) -> str:
        if (row["recency_score"], row["frequency_score"], row["monetary_score"]) == (3, 3, 3):
            return "Champions"
        if row["recency_score"] >= 2 and row["frequency_score"] >= 2 and row["monetary_score"] >= 2:
            return "Loyal"
        if row["recency_score"] == 1 and (row["frequency_score"] >= 2 or row["monetary_score"] >= 2):
            return "At Risk"
        if row["recency_score"] == 1 and row["frequency_score"] == 1:
            return "Lost"
        return "New Users"

    users["segment"] = users.apply(label_segment, axis=1)
    return users


def overview_page(df: pd.DataFrame) -> None:
    """Render the overview page."""
    st.title("Overview")
    st.caption("High-level platform health snapshot from the processed master dataset.")

    total_users = df["user_id"].nunique()
    total_sessions = df["session_id"].nunique()
    avg_completion = df["is_completed"].mean()
    power_share = df.loc[df["is_power_user"], "session_duration_minutes"].sum() / df["session_duration_minutes"].sum()

    cols = st.columns(4)
    with cols[0]:
        metric_card("Total Users", f"{total_users:,}")
    with cols[1]:
        metric_card("Total Sessions", f"{total_sessions:,}")
    with cols[2]:
        metric_card("Avg Completion Rate", f"{avg_completion:.0%}")
    with cols[3]:
        metric_card("Power User %", f"{power_share:.0%}")

    st.divider()
    chart_cols = st.columns(2)
    with chart_cols[0]:
        if require_columns(df, ["day_of_week", "session_id"]):
            daily = df.groupby("day_of_week")["session_id"].nunique().reindex(DAY_ORDER).fillna(0).reset_index()
            fig = px.line(daily, x="day_of_week", y="session_id", markers=True, title="Session Volume by Day of Week")
            fig.update_traces(line_color=ACCENT)
            fig.update_layout(template="plotly_dark", yaxis_title="Sessions", xaxis_title="Day")
            st.plotly_chart(fig, use_container_width=True)
    with chart_cols[1]:
        if require_columns(df, ["format"]):
            format_share = df.groupby("format")["play_count"].sum().reset_index()
            fig = px.pie(format_share, names="format", values="play_count", hole=0.35, title="Content Format Breakdown")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    date_column = "started_at" if "started_at" in df.columns else "timestamp" if "timestamp" in df.columns else None
    freshness = df[date_column].max().date() if date_column and df[date_column].notna().any() else "unknown"
    if not DATA_PATH.exists():
        st.caption("📌 Running on auto-generated demo data (200 users, 2000 events)")
    st.markdown(f'<p class="small-note">Data freshness: latest event date = <b>{freshness}</b>. Source: <code>{DATA_PATH.name if DATA_PATH.exists() else "inline demo generator"}</code>.</p>', unsafe_allow_html=True)


def content_page(df: pd.DataFrame) -> None:
    """Render the content analysis page."""
    st.title("Content Analysis")
    st.caption("Explore which genres, formats, and content lengths drive engagement.")

    if not require_columns(df, ["genre", "duration_minutes", "session_duration_minutes", "is_completed"]):
        return

    selected_genres = st.multiselect("Filter genres", sorted(df["genre"].dropna().unique()), default=sorted(df["genre"].dropna().unique()))
    filtered = df[df["genre"].isin(selected_genres)] if selected_genres else df

    genre_summary = (
        filtered.groupby("genre")["session_duration_minutes"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )
    fig = px.bar(genre_summary, x="session_duration_minutes", y="genre", orientation="h", title="Top Genres by Listening Minutes")
    fig.update_traces(marker_color=ACCENT)
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(template="plotly_dark", xaxis_title="Session Duration Minutes", yaxis_title="Genre")
    st.plotly_chart(fig, use_container_width=True)

    filtered = add_duration_bins(filtered)
    duration_summary = filtered.groupby("duration_bin", observed=False)["is_completed"].mean().fillna(0).reset_index()
    best_row = duration_summary.sort_values("is_completed", ascending=False).iloc[0]
    fig = px.bar(duration_summary, x="duration_bin", y="is_completed", text="is_completed", title="Completion Rate by Duration Bin")
    fig.update_traces(marker_color=ACCENT, texttemplate="%{text:.0%}", textposition="outside")
    fig.update_layout(template="plotly_dark", yaxis_tickformat=".0%", xaxis_title="Duration Bin", yaxis_title="Completion Rate")
    st.plotly_chart(fig, use_container_width=True)

    st.success(f"Best completion bin: {best_row['duration_bin']} minutes with {best_row['is_completed']:.0%} completion rate.")
    image_path = VISUALS_DIR / "duration_vs_completion.png"
    if image_path.exists():
        st.image(str(image_path), caption="Reference export: Content Length vs Completion Rate")


def users_page(df: pd.DataFrame) -> None:
    """Render the user segmentation page."""
    st.title("User Segmentation")
    st.caption("Understand high-value listeners and when they are most engaged.")

    power_only = st.toggle("Power Users only", value=False)
    filtered = df[df["is_power_user"]] if power_only else df

    image_path = VISUALS_DIR / "rfm_bubble.png"
    if image_path.exists():
        st.image(str(image_path), caption="RFM segment bubble chart")

    if require_columns(filtered, ["user_id", "user_tenure_days", "play_count", "session_duration_minutes", "skip_count"]):
        rfm = build_rfm(filtered)
        segment_summary = (
            rfm.groupby("segment")
            .agg(
                users=("user_id", "nunique"),
                avg_frequency=("frequency", "mean"),
                avg_duration_minutes=("total_duration_minutes", "mean"),
                avg_skip_count=("avg_skip_count", "mean"),
            )
            .sort_values("users", ascending=False)
            .reset_index()
        )
        st.dataframe(segment_summary, use_container_width=True, hide_index=True)

    if require_columns(filtered, ["time_of_day", "day_of_week", "session_duration_minutes"]):
        heatmap = (
            filtered.pivot_table(index="time_of_day", columns="day_of_week", values="session_duration_minutes", aggfunc="mean")
            .reindex(index=TIME_ORDER, columns=DAY_ORDER)
            .fillna(0)
        )
        fig = go.Figure(data=go.Heatmap(z=heatmap.values, x=heatmap.columns, y=heatmap.index, colorscale="Greens", text=np.round(heatmap.values, 1), texttemplate="%{text}"))
        fig.update_layout(template="plotly_dark", title="Peak Listening Heatmap", xaxis_title="Day of Week", yaxis_title="Time of Day")
        st.plotly_chart(fig, use_container_width=True)


def retention_page(df: pd.DataFrame) -> None:
    """Render the retention and churn page."""
    st.title("Retention & Churn")
    st.caption("Find drop-off points, skip-heavy genres, and users with early churn risk.")

    image_path = VISUALS_DIR / "session_funnel.png"
    if image_path.exists():
        st.image(str(image_path), caption="Content consumption funnel")

    if require_columns(df, ["genre", "skip_count"]):
        skip_summary = df.groupby("genre")["skip_count"].mean().sort_values(ascending=False).head(10).reset_index()
        fig = px.bar(skip_summary, x="skip_count", y="genre", orientation="h", title="Top 10 Genres by Avg Skip Count")
        fig.update_traces(marker_color=SECONDARY)
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(template="plotly_dark", xaxis_title="Avg Skip Count", yaxis_title="Genre")
        st.plotly_chart(fig, use_container_width=True)

    if require_columns(df, ["user_id", "skip_count", "user_tenure_days", "session_duration_minutes", "play_count"]):
        risk = (
            df[(df["skip_count"] > 3) & (df["user_tenure_days"] < 7)]
            .groupby("user_id")
            .agg(total_skip_count=("skip_count", "sum"), early_events=("play_count", "sum"), total_duration_minutes=("session_duration_minutes", "sum"), max_tenure=("user_tenure_days", "max"))
            .sort_values("total_skip_count", ascending=False)
            .reset_index()
        )
        st.warning(f"{risk['user_id'].nunique()} users at high churn risk")
        st.dataframe(risk, use_container_width=True, hide_index=True)


def main() -> None:
    """Run the Streamlit app."""
    apply_global_styles()
    st.sidebar.title("📊 NOICE Analytics")
    page = st.sidebar.radio("Navigate", ["Overview", "Content", "Users", "Retention"])
    st.sidebar.divider()
    st.sidebar.caption("Built by Luthfi Mirza Darsono | Gunadarma University")

    df = load_or_generate_data()

    required_base = ["user_id", "content_id", "session_id", "session_duration_minutes", "is_completed", "is_power_user"]
    if not require_columns(df, required_base):
        return

    if page == "Overview":
        overview_page(df)
    elif page == "Content":
        content_page(df)
    elif page == "Users":
        users_page(df)
    else:
        retention_page(df)


if __name__ == "__main__":
    main()

"""Generate synthetic streaming-platform datasets for EDA storytelling.

The generated data simulates NOICE-style user behavior across audio formats,
content metadata, search demand, sessions, and subscription events.
"""

from __future__ import annotations

from pathlib import Path
import argparse

import numpy as np
import pandas as pd

try:
    from faker import Faker
except ModuleNotFoundError:  # Allows quick local smoke tests before installing requirements.
    Faker = None

RAW_DIR = Path(__file__).resolve().parent / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent / "processed"

GENRES = [
    "Comedy", "Talk Show", "Tech", "News", "Music", "Horror", "Sports",
    "Business", "Education", "Lifestyle", "Drama", "Religion",
]
FORMATS = ["podcast", "music", "live_stream", "audiobook"]
CHANNELS = ["recommendation", "search", "browse", "push_notification", "social_share"]
DEVICES = ["android", "ios", "desktop", "mobile_web"]
ACQUISITION_CHANNELS = ["organic", "paid_social", "referral", "influencer", "app_store"]
SUBSCRIPTION_PLANS = ["free", "premium", "student", "family"]
CITY_FALLBACKS = ["Jakarta", "Bandung", "Surabaya", "Yogyakarta", "Medan", "Makassar"]
TITLE_FALLBACKS = [
    "Morning Insight", "Creator Deep Dive", "Late Night Stories", "Tech Talk",
    "Daily Brief", "Weekend Laughs", "Growth Notes", "Mystery Hour",
]


def _weighted_choice(rng: np.random.Generator, values: list[str], weights: list[float], size: int) -> np.ndarray:
    return rng.choice(values, p=np.array(weights) / np.sum(weights), size=size)


def generate_users(fake: Faker, rng: np.random.Generator, n_users: int) -> pd.DataFrame:
    signup_dates = pd.to_datetime(rng.choice(pd.date_range("2024-01-01", "2024-12-31"), n_users))
    return pd.DataFrame({
        "user_id": [f"U{idx:05d}" for idx in range(1, n_users + 1)],
        "signup_date": signup_dates,
        "country": _weighted_choice(rng, ["Indonesia", "Malaysia", "Singapore", "Philippines"], [0.82, 0.08, 0.05, 0.05], n_users),
        "city": [fake.city() if fake else rng.choice(CITY_FALLBACKS) for _ in range(n_users)],
        "age_group": _weighted_choice(rng, ["18-24", "25-34", "35-44", "45+"], [0.32, 0.41, 0.19, 0.08], n_users),
        "gender": _weighted_choice(rng, ["female", "male", "unknown"], [0.47, 0.45, 0.08], n_users),
        "acquisition_channel": _weighted_choice(rng, ACQUISITION_CHANNELS, [0.32, 0.24, 0.16, 0.18, 0.10], n_users),
        "subscription_plan": _weighted_choice(rng, SUBSCRIPTION_PLANS, [0.68, 0.21, 0.07, 0.04], n_users),
    })


def generate_content(fake: Faker, rng: np.random.Generator, n_items: int) -> pd.DataFrame:
    formats = _weighted_choice(rng, FORMATS, [0.48, 0.28, 0.16, 0.08], n_items)
    genres = _weighted_choice(rng, GENRES, [0.11, 0.07, 0.06, 0.11, 0.14, 0.08, 0.08, 0.07, 0.08, 0.08, 0.07, 0.05], n_items)
    duration = []
    for content_format in formats:
        if content_format == "music":
            duration.append(rng.integers(3, 7))
        elif content_format == "live_stream":
            duration.append(rng.integers(35, 121))
        elif content_format == "audiobook":
            duration.append(rng.integers(45, 181))
        else:
            duration.append(rng.integers(8, 61))
    return pd.DataFrame({
        "content_id": [f"C{idx:05d}" for idx in range(1, n_items + 1)],
        "title": [fake.catch_phrase() if fake else f"{rng.choice(TITLE_FALLBACKS)} #{idx}" for idx in range(1, n_items + 1)],
        "creator_id": [f"CR{rng.integers(1, 151):04d}" for _ in range(n_items)],
        "format": formats,
        "genre": genres,
        "duration_minutes": duration,
        "release_date": pd.to_datetime(rng.choice(pd.date_range("2023-01-01", "2024-12-31"), n_items)),
    })


def generate_interactions(users: pd.DataFrame, content: pd.DataFrame, rng: np.random.Generator, n_events: int) -> pd.DataFrame:
    user_ids = rng.choice(users["user_id"], n_events)
    content_rows = content.sample(n_events, replace=True, random_state=42).reset_index(drop=True)
    started_at = pd.to_datetime(rng.choice(pd.date_range("2024-07-01", "2025-03-31", freq="30min"), n_events))
    base_completion = np.where(content_rows["duration_minutes"] <= 25, 0.78, 0.56)
    format_adjustment = content_rows["format"].map({"music": 0.12, "podcast": 0.0, "live_stream": -0.08, "audiobook": -0.12}).to_numpy()
    completion_rate = np.clip(rng.normal(base_completion + format_adjustment, 0.18), 0.02, 1.0)
    listened_minutes = np.maximum(1, np.round(content_rows["duration_minutes"].to_numpy() * completion_rate, 1))
    skipped = (completion_rate < 0.2) | (rng.random(n_events) < 0.08)
    liked = (~skipped) & (rng.random(n_events) < np.clip(completion_rate * 0.32, 0.02, 0.38))
    return pd.DataFrame({
        "event_id": [f"E{idx:07d}" for idx in range(1, n_events + 1)],
        "user_id": user_ids,
        "content_id": content_rows["content_id"],
        "started_at": started_at,
        "device": _weighted_choice(rng, DEVICES, [0.48, 0.34, 0.11, 0.07], n_events),
        "discovery_channel": _weighted_choice(rng, CHANNELS, [0.41, 0.23, 0.19, 0.11, 0.06], n_events),
        "listened_minutes": listened_minutes,
        "completion_rate": np.round(completion_rate, 3),
        "skipped": skipped,
        "liked": liked,
        "session_id": [f"S{uid}_{date:%Y%m%d%H}" for uid, date in zip(user_ids, started_at)],
    })


def generate_search_demand(rng: np.random.Generator) -> pd.DataFrame:
    demand_weights = {
        "Comedy": 0.11, "Talk Show": 0.16, "Tech": 0.14, "News": 0.10,
        "Music": 0.12, "Horror": 0.07, "Sports": 0.08, "Business": 0.08,
        "Education": 0.06, "Lifestyle": 0.04, "Drama": 0.03, "Religion": 0.01,
    }
    rows = []
    for genre, weight in demand_weights.items():
        rows.append({
            "genre": genre,
            "monthly_searches": int(rng.normal(80_000 * weight, 1_500)),
            "content_supply_items": int(rng.normal(900 * (0.05 + weight * rng.uniform(0.45, 0.95)), 20)),
        })
    return pd.DataFrame(rows)


def build_processed(interactions: pd.DataFrame, users: pd.DataFrame, content: pd.DataFrame) -> pd.DataFrame:
    merged = interactions.merge(users, on="user_id", how="left").merge(content, on="content_id", how="left")
    merged["started_at"] = pd.to_datetime(merged["started_at"])
    merged["date"] = merged["started_at"].dt.date
    merged["hour"] = merged["started_at"].dt.hour
    merged["is_short_form"] = merged["duration_minutes"] <= 25
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic streaming data.")
    parser.add_argument("--users", type=int, default=5000)
    parser.add_argument("--content", type=int, default=1200)
    parser.add_argument("--events", type=int, default=75000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    fake = Faker("id_ID") if Faker else None
    if Faker:
        Faker.seed(args.seed)
    rng = np.random.default_rng(args.seed)

    users = generate_users(fake, rng, args.users)
    content = generate_content(fake, rng, args.content)
    interactions = generate_interactions(users, content, rng, args.events)
    search_demand = generate_search_demand(rng)
    processed = build_processed(interactions, users, content)

    users.to_csv(RAW_DIR / "users.csv", index=False)
    content.to_csv(RAW_DIR / "content.csv", index=False)
    interactions.to_csv(RAW_DIR / "interactions.csv", index=False)
    search_demand.to_csv(RAW_DIR / "search_demand.csv", index=False)
    processed.to_csv(PROCESSED_DIR / "streaming_interactions_enriched.csv", index=False)

    print(f"Generated {len(users):,} users, {len(content):,} content items, {len(interactions):,} interactions.")
    print(f"Raw data: {RAW_DIR}")
    print(f"Processed data: {PROCESSED_DIR}")


if __name__ == "__main__":
    main()

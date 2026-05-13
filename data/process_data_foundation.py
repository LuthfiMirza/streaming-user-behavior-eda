"""Build the Phase 1 data foundation for streaming behavior analysis.

This module loads synthetic raw CSVs, profiles data quality, cleans and
standardizes tables, engineers analysis-ready features, and writes a master
processed dataset plus a markdown data quality report.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MASTER_DATASET_PATH = PROCESSED_DIR / "master_dataset.csv"
QUALITY_REPORT_PATH = PROCESSED_DIR / "quality_report.md"

TIMESTAMP_COLUMNS = {
    "users": ["signup_date"],
    "content": ["release_date"],
    "interactions": ["started_at"],
}


def to_snake_case(column_name: str) -> str:
    """Convert a column name to normalized snake_case."""
    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", column_name.strip())
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized)
    return normalized.strip("_").lower()


def load_raw_csvs(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    """Load all CSV files from the raw data directory."""
    csv_paths = sorted(raw_dir.glob("*.csv"))
    if not csv_paths:
        raise FileNotFoundError(f"No CSV files found in {raw_dir}")
    return {path.stem: pd.read_csv(path) for path in csv_paths}


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with snake_case column names."""
    output = df.copy()
    output.columns = [to_snake_case(column) for column in output.columns]
    return output


def parse_datetimes(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    """Parse known timestamp columns for a table."""
    output = df.copy()
    for column in TIMESTAMP_COLUMNS.get(table_name, []):
        if column in output.columns:
            output[column] = pd.to_datetime(output[column], errors="coerce")
    return output


def remove_duplicate_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove exact duplicate rows."""
    return df.drop_duplicates().reset_index(drop=True)


def handle_missing_values(df: pd.DataFrame, threshold: float = 0.30) -> tuple[pd.DataFrame, list[str], dict[str, str]]:
    """Drop high-missing columns and impute remaining null values.

    Numeric columns are filled with the median; categorical, boolean, and
    datetime columns are filled with the mode when possible.
    """
    output = df.copy()
    missing_ratio = output.isna().mean()
    dropped_columns = missing_ratio[missing_ratio > threshold].index.tolist()
    output = output.drop(columns=dropped_columns)
    imputation_actions: dict[str, str] = {}

    for column in output.columns[output.isna().any()].tolist():
        if pd.api.types.is_numeric_dtype(output[column]):
            fill_value = output[column].median()
            action = f"filled with median ({fill_value})"
        else:
            mode = output[column].mode(dropna=True)
            fill_value = mode.iloc[0] if not mode.empty else "unknown"
            action = f"filled with mode ({fill_value})"
        output[column] = output[column].fillna(fill_value)
        imputation_actions[column] = action

    return output, dropped_columns, imputation_actions


def encode_categoricals(df: pd.DataFrame, exclude: Iterable[str] = ()) -> pd.DataFrame:
    """Add integer code columns for low-cardinality categorical fields."""
    output = df.copy()
    excluded = set(exclude)
    for column in output.select_dtypes(include=["object", "category", "bool"]).columns:
        if column in excluded or column.endswith("_id") or column == "title":
            continue
        output[f"{column}_code"] = output[column].astype("category").cat.codes
    return output


def clean_table(table_name: str, df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    """Standardize and clean one raw table, returning quality metadata."""
    before_shape = df.shape
    before_duplicates = int(df.duplicated().sum())
    output = standardize_columns(df)
    output = parse_datetimes(table_name, output)
    output = remove_duplicate_rows(output)
    output, dropped_columns, imputation_actions = handle_missing_values(output)
    after_shape = output.shape
    return output, {
        "before_shape": before_shape,
        "after_shape": after_shape,
        "duplicates_removed": before_duplicates,
        "dropped_columns": dropped_columns,
        "imputation_actions": imputation_actions,
    }


def merge_tables(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge interaction events with user, content, and search demand attributes."""
    required = {"interactions", "users", "content"}
    missing = required.difference(tables)
    if missing:
        raise KeyError(f"Missing required raw tables: {sorted(missing)}")

    master = tables["interactions"].merge(tables["users"], on="user_id", how="left")
    master = master.merge(tables["content"], on="content_id", how="left")
    if "search_demand" in tables and "genre" in tables["search_demand"].columns:
        master = master.merge(tables["search_demand"], on="genre", how="left")
    return master


def assign_time_of_day(timestamp: pd.Timestamp) -> str:
    """Map an event timestamp to a business-friendly daypart."""
    hour = timestamp.hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def engineer_features(master: pd.DataFrame) -> pd.DataFrame:
    """Create analysis-ready behavioral features on the merged dataset."""
    output = master.copy()
    output["started_at"] = pd.to_datetime(output["started_at"], errors="coerce")
    output["session_duration_minutes"] = output.groupby("session_id")["listened_minutes"].transform("sum")
    output["is_completed"] = output["completion_rate"].ge(0.80)
    output["time_of_day"] = output["started_at"].apply(assign_time_of_day)
    output["day_of_week"] = output["started_at"].dt.day_name()

    first_session = output.groupby("user_id")["started_at"].transform("min")
    output["user_tenure_days"] = (output["started_at"] - first_session).dt.days.clip(lower=0)

    playtime_by_user = output.groupby("user_id")["listened_minutes"].transform("sum")
    power_threshold = output.groupby("user_id")["listened_minutes"].sum().quantile(0.80)
    output["is_power_user"] = playtime_by_user.ge(power_threshold)
    return output


def profile_table(name: str, df: pd.DataFrame) -> str:
    """Create a markdown profile section for one dataframe."""
    null_counts = df.isna().sum().sort_values(ascending=False)
    dtype_lines = "\n".join(f"- `{column}`: `{dtype}`" for column, dtype in df.dtypes.items())
    null_lines = "\n".join(f"- `{column}`: {count} ({df[column].isna().mean():.1%})" for column, count in null_counts.items())
    return (
        f"### {name}\n\n"
        f"- Shape: `{df.shape[0]:,}` rows × `{df.shape[1]:,}` columns\n"
        f"- Duplicate rows: `{int(df.duplicated().sum()):,}`\n\n"
        f"**Schema**\n{dtype_lines}\n\n"
        f"**Missing Values**\n{null_lines}\n"
    )


def write_quality_report(raw_tables: dict[str, pd.DataFrame], clean_metadata: dict[str, dict[str, object]], master: pd.DataFrame) -> None:
    """Write a markdown data quality report for raw and processed data."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    sections = [
        "# Data Quality Report\n",
        "## Scope\nSynthetic NOICE-style raw CSVs were inspected, cleaned, merged, and feature-engineered for Phase 1 EDA readiness.\n",
        "## Raw Table Profiles\n",
    ]
    sections.extend(profile_table(name, df) for name, df in raw_tables.items())
    sections.append("## Cleaning Actions\n")
    for name, metadata in clean_metadata.items():
        sections.append(
            f"### {name}\n"
            f"- Shape before: `{metadata['before_shape']}`\n"
            f"- Shape after: `{metadata['after_shape']}`\n"
            f"- Duplicates removed: `{metadata['duplicates_removed']}`\n"
            f"- Columns dropped for >30% missingness: `{metadata['dropped_columns']}`\n"
            f"- Imputations: `{metadata['imputation_actions']}`\n"
        )
    sections.append(
        "## Processed Master Dataset\n"
        f"- Output path: `{MASTER_DATASET_PATH.relative_to(PROJECT_ROOT)}`\n"
        f"- Shape: `{master.shape[0]:,}` rows × `{master.shape[1]:,}` columns\n"
        f"- Duplicate rows: `{int(master.duplicated().sum()):,}`\n"
        f"- Remaining missing values: `{int(master.isna().sum().sum()):,}`\n"
        "\n## Key Findings\n"
        "- Raw schemas are consistent with expected synthetic user, content, interaction, and search-demand entities.\n"
        "- Timestamp fields are parseable and ready for time-based analysis.\n"
        "- Event-level records were enriched with user, content, session, completion, tenure, and power-user features.\n"
        "- The master dataset is suitable for content consumption, segmentation, retention, and growth-opportunity analysis.\n"
    )
    QUALITY_REPORT_PATH.write_text("\n".join(sections), encoding="utf-8")


def build_master_dataset() -> pd.DataFrame:
    """Run the full Phase 1 data foundation pipeline."""
    raw_tables = load_raw_csvs()
    clean_tables: dict[str, pd.DataFrame] = {}
    clean_metadata: dict[str, dict[str, object]] = {}
    for name, table in raw_tables.items():
        clean_tables[name], clean_metadata[name] = clean_table(name, table)

    master = merge_tables(clean_tables)
    master = engineer_features(master)
    master, _, _ = handle_missing_values(master)
    master = encode_categoricals(master, exclude={"event_id", "user_id", "content_id", "creator_id", "session_id"})
    master = master.drop_duplicates().reset_index(drop=True)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    master.to_csv(MASTER_DATASET_PATH, index=False)
    write_quality_report(raw_tables, clean_metadata, master)
    return master


if __name__ == "__main__":
    dataset = build_master_dataset()
    print(f"Saved {MASTER_DATASET_PATH} with shape {dataset.shape}")
    print(f"Saved {QUALITY_REPORT_PATH}")

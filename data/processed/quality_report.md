# Data Quality Report

## Scope
Synthetic NOICE-style raw CSVs were inspected, cleaned, merged, and feature-engineered for Phase 1 EDA readiness.

## Raw Table Profiles

### content

- Shape: `500` rows × `7` columns
- Duplicate rows: `0`

**Schema**
- `content_id`: `object`
- `title`: `object`
- `creator_id`: `object`
- `format`: `object`
- `genre`: `object`
- `duration_minutes`: `int64`
- `release_date`: `object`

**Missing Values**
- `content_id`: 0 (0.0%)
- `title`: 0 (0.0%)
- `creator_id`: 0 (0.0%)
- `format`: 0 (0.0%)
- `genre`: 0 (0.0%)
- `duration_minutes`: 0 (0.0%)
- `release_date`: 0 (0.0%)

### interactions

- Shape: `50,000` rows × `11` columns
- Duplicate rows: `0`

**Schema**
- `event_id`: `object`
- `user_id`: `object`
- `content_id`: `object`
- `started_at`: `object`
- `device`: `object`
- `discovery_channel`: `object`
- `listened_minutes`: `float64`
- `completion_rate`: `float64`
- `skipped`: `bool`
- `liked`: `bool`
- `session_id`: `object`

**Missing Values**
- `event_id`: 0 (0.0%)
- `user_id`: 0 (0.0%)
- `content_id`: 0 (0.0%)
- `started_at`: 0 (0.0%)
- `device`: 0 (0.0%)
- `discovery_channel`: 0 (0.0%)
- `listened_minutes`: 0 (0.0%)
- `completion_rate`: 0 (0.0%)
- `skipped`: 0 (0.0%)
- `liked`: 0 (0.0%)
- `session_id`: 0 (0.0%)

### search_demand

- Shape: `12` rows × `3` columns
- Duplicate rows: `0`

**Schema**
- `genre`: `object`
- `monthly_searches`: `int64`
- `content_supply_items`: `int64`

**Missing Values**
- `genre`: 0 (0.0%)
- `monthly_searches`: 0 (0.0%)
- `content_supply_items`: 0 (0.0%)

### users

- Shape: `2,000` rows × `8` columns
- Duplicate rows: `0`

**Schema**
- `user_id`: `object`
- `signup_date`: `object`
- `country`: `object`
- `city`: `object`
- `age_group`: `object`
- `gender`: `object`
- `acquisition_channel`: `object`
- `subscription_plan`: `object`

**Missing Values**
- `user_id`: 0 (0.0%)
- `signup_date`: 0 (0.0%)
- `country`: 0 (0.0%)
- `city`: 0 (0.0%)
- `age_group`: 0 (0.0%)
- `gender`: 0 (0.0%)
- `acquisition_channel`: 0 (0.0%)
- `subscription_plan`: 0 (0.0%)

## Cleaning Actions

### content
- Shape before: `(500, 7)`
- Shape after: `(500, 7)`
- Duplicates removed: `0`
- Columns dropped for >30% missingness: `[]`
- Imputations: `{}`

### interactions
- Shape before: `(50000, 11)`
- Shape after: `(50000, 11)`
- Duplicates removed: `0`
- Columns dropped for >30% missingness: `[]`
- Imputations: `{}`

### search_demand
- Shape before: `(12, 3)`
- Shape after: `(12, 3)`
- Duplicates removed: `0`
- Columns dropped for >30% missingness: `[]`
- Imputations: `{}`

### users
- Shape before: `(2000, 8)`
- Shape after: `(2000, 8)`
- Duplicates removed: `0`
- Columns dropped for >30% missingness: `[]`
- Imputations: `{}`

## Processed Master Dataset
- Output path: `data/processed/master_dataset.csv`
- Shape: `50,000` rows × `48` columns
- Duplicate rows: `0`
- Remaining missing values: `0`

## Key Findings
- Raw schemas are consistent with expected synthetic user, content, interaction, and search-demand entities.
- Timestamp fields are parseable and ready for time-based analysis.
- Event-level records were enriched with user, content, session, completion, tenure, and power-user features.
- The master dataset is suitable for content consumption, segmentation, retention, and growth-opportunity analysis.

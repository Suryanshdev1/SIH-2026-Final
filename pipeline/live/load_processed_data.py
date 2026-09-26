import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://paridhilalwani@localhost:5432/sih26_ntro_db"
)

engine = create_engine(DATABASE_URL)

ML_DIR = BASE_DIR / "data" / "live_ml_input"


def find_latest_ml_file():

    files = sorted(
        ML_DIR.glob("firms_ml_input_*.csv")
    )

    if not files:
        raise FileNotFoundError(
            "No live ML input file found."
        )

    return files[-1]


def run_loader():

    print("=" * 70)
    print("LOAD LIVE ML INPUT INTO POSTGRESQL")
    print("=" * 70)

    input_file = find_latest_ml_file()

    print(f"ML input: {input_file}")

    df = pd.read_csv(input_file)

    if df.empty:
        raise ValueError(
            "ML input file is empty."
        )

    required_columns = [
        "detection_count",
        "mean_frp",
        "max_frp",
        "mean_brightness",
        "max_brightness",
        "unique_detection_days",
        "observation_window_days",
        "spatial_spread_km",
        "temporal_recurrence",
        "duration_score",
        "detection_frequency",
        "spatial_consistency",
        "persistence_score",
        "land_cover_code",
        "is_cropland",
        "is_tree_cover",
        "is_built_up",
        "cropland_percentage",
        "tree_cover_percentage",
        "built_up_percentage",
        "grassland_percentage",
        "shrubland_percentage",
        "bare_sparse_percentage",
        "nearest_industrial_distance_km",
        "nearby_industrial_facility_count",
        "nearby_industrial_capacity_mw",
        "fire_class",
        "cluster_id",
        "centroid_lat",
        "centroid_lon"
    ]

    missing = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing columns: {missing}"
        )

    # Keep exact 30-column contract
    df = df[required_columns].copy()

    # Replace NaN with None for PostgreSQL
    df = df.where(
        pd.notna(df),
        None
    )

    records = df.to_dict(
        orient="records"
    )

    insert_sql = text("""
        INSERT INTO processed_data (
            detection_count,
            mean_frp,
            max_frp,
            mean_brightness,
            max_brightness,
            unique_detection_days,
            observation_window_days,
            spatial_spread_km,
            temporal_recurrence,
            duration_score,
            detection_frequency,
            spatial_consistency,
            persistence_score,
            land_cover_code,
            is_cropland,
            is_tree_cover,
            is_built_up,
            cropland_percentage,
            tree_cover_percentage,
            built_up_percentage,
            grassland_percentage,
            shrubland_percentage,
            bare_sparse_percentage,
            nearest_industrial_distance_km,
            nearby_industrial_facility_count,
            nearby_industrial_capacity_mw,
            fire_class,
            cluster_id,
            centroid_lat,
            centroid_lon
        )
        VALUES (
            :detection_count,
            :mean_frp,
            :max_frp,
            :mean_brightness,
            :max_brightness,
            :unique_detection_days,
            :observation_window_days,
            :spatial_spread_km,
            :temporal_recurrence,
            :duration_score,
            :detection_frequency,
            :spatial_consistency,
            :persistence_score,
            :land_cover_code,
            :is_cropland,
            :is_tree_cover,
            :is_built_up,
            :cropland_percentage,
            :tree_cover_percentage,
            :built_up_percentage,
            :grassland_percentage,
            :shrubland_percentage,
            :bare_sparse_percentage,
            :nearest_industrial_distance_km,
            :nearby_industrial_facility_count,
            :nearby_industrial_capacity_mw,
            :fire_class,
            :cluster_id,
            :centroid_lat,
            :centroid_lon
        )
    """)

    with engine.begin() as conn:

        # processed_data represents the latest
        # model-ready snapshot.
        conn.execute(
            text("TRUNCATE TABLE processed_data")
        )

        conn.execute(
            insert_sql,
            records
        )

    print(
        f"Rows loaded: {len(df)}"
    )

    print(
        "processed_data updated successfully."
    )

    print("=" * 70)


if __name__ == "__main__":
    run_loader()

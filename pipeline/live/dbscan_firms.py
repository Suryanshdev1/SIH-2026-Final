import os
from pathlib import Path
import glob

import pandas as pd
from sklearn.cluster import DBSCAN
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://paridhilalwani@localhost:5432/sih26_ntro_db"
)

engine = create_engine(DATABASE_URL)

EPS = 0.01
MIN_SAMPLES = 2

CLEAN_DIR = BASE_DIR / "data" / "live_clean"
OUTPUT_DIR = BASE_DIR / "data" / "live_clustered"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def find_latest_clean_file():

    files = sorted(
        CLEAN_DIR.glob("firms_clean_*.csv")
    )

    if not files:
        raise FileNotFoundError(
            "No cleaned FIRMS file found."
        )

    return files[-1]


def run_dbscan():

    print("=" * 70)
    print("LIVE FIRMS DBSCAN")
    print("=" * 70)

    input_file = find_latest_clean_file()

    print(f"Clean input: {input_file}")

    df = pd.read_csv(input_file)

    print(f"Input detections: {len(df)}")

    if df.empty:
        raise ValueError(
            "Latest cleaned FIRMS file is empty."
        )

    coordinates = df[
        ["latitude", "longitude"]
    ].values

    dbscan = DBSCAN(
        eps=EPS,
        min_samples=MIN_SAMPLES,
        metric="euclidean"
    )

    labels = dbscan.fit_predict(
        coordinates
    )

    df["cluster_id"] = labels

    clustered = df[
        df["cluster_id"] != -1
    ].copy()

    noise = df[
        df["cluster_id"] == -1
    ].copy()

    clusters_found = (
        clustered["cluster_id"].nunique()
        if not clustered.empty
        else 0
    )

    print(f"EPS: {EPS}")
    print(f"MIN_SAMPLES: {MIN_SAMPLES}")
    print(f"Clusters found: {clusters_found}")
    print(f"Clustered detections: {len(clustered)}")
    print(f"Noise/unclustered: {len(noise)}")

    # ---------------------------------------------------------
    # Update cluster IDs ONLY for this current batch
    # ---------------------------------------------------------

    with engine.begin() as conn:

        for _, row in df.iterrows():

            event_hash = row.get(
                "event_hash"
            )

            if pd.isna(event_hash):
                continue

            conn.execute(
                text("""
                    UPDATE firms_raw_data
                    SET cluster_id = :cluster_id
                    WHERE event_hash = :event_hash
                """),
                {
                    "cluster_id":
                        int(row["cluster_id"]),
                    "event_hash":
                        str(event_hash)
                }
            )

    timestamp = pd.Timestamp.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_file = (
        OUTPUT_DIR
        / f"firms_clustered_{timestamp}.csv"
    )

    df.to_csv(
        output_file,
        index=False
    )

    print(f"Clustered backup: {output_file}")

    print("=" * 70)
    print("LIVE DBSCAN COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_dbscan()
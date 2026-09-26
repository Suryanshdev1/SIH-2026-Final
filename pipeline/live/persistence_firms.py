import os
from pathlib import Path
import math

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://paridhilalwani@localhost:5432/sih26_ntro_db"
)

engine = create_engine(DATABASE_URL)

CLUSTERED_DIR = BASE_DIR / "data" / "live_clustered"
OUTPUT_DIR = BASE_DIR / "data" / "live_persistence"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

# Maximum distance for matching a new DBSCAN cluster
# to an existing historical hotspot.
MATCH_RADIUS_KM = 5.0


# ============================================================
# HELPERS
# ============================================================

def find_latest_clustered_file():

    files = sorted(
        CLUSTERED_DIR.glob("firms_clustered_*.csv")
    )

    if not files:
        raise FileNotFoundError(
            "No clustered FIRMS file found."
        )

    return files[-1]


def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2
):

    R = 6371.0

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    dlat = lat2 - lat1
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return (
        2
        * R
        * math.asin(math.sqrt(a))
    )


# ============================================================
# MAIN
# ============================================================

def run_persistence():

    print("=" * 70)
    print("LIVE FIRMS PERSISTENCE + HISTORICAL HOTSPOT MATCHING")
    print("=" * 70)

    # --------------------------------------------------------
    # LOAD ONLY CURRENT DBSCAN RUN
    # --------------------------------------------------------

    input_file = find_latest_clustered_file()

    print(f"Clustered input: {input_file}")

    df = pd.read_csv(input_file)

    if df.empty:
        raise ValueError(
            "Latest clustered FIRMS file is empty."
        )

    # Ignore DBSCAN noise
    df = df[
        df["cluster_id"] != -1
    ].copy()

    if df.empty:
        raise ValueError(
            "No usable DBSCAN clusters in current run."
        )

    # --------------------------------------------------------
    # Normalize dates
    # --------------------------------------------------------

    df["acq_date"] = pd.to_datetime(
        df["acq_date"],
        errors="coerce"
    )

    df = df.dropna(
        subset=[
            "latitude",
            "longitude",
            "acq_date",
            "cluster_id"
        ]
    )

    print(
        f"Clustered detections available: {len(df)}"
    )

    # ========================================================
    # CURRENT RUN CLUSTERS
    # ========================================================

    current_clusters = []

    for cluster_id, group in df.groupby(
        "cluster_id"
    ):

        centroid_lat = group["latitude"].mean()
        centroid_lon = group["longitude"].mean()

        current_clusters.append({
            "cluster_id": int(cluster_id),
            "centroid_lat": float(centroid_lat),
            "centroid_lon": float(centroid_lon)
        })

    print(
        f"Current DBSCAN clusters: "
        f"{len(current_clusters)}"
    )

    # ========================================================
    # LOAD HISTORICAL HOTSPOTS
    # ========================================================

    with engine.connect() as conn:

        hotspots = pd.read_sql(
            text("""
                SELECT
                    hotspot_id,
                    centroid_lat,
                    centroid_lon,
                    first_detection,
                    last_detection
                FROM persistent_hotspots
                ORDER BY hotspot_id
            """),
            conn
        )

    print(
        f"Historical hotspots: {len(hotspots)}"
    )

    # ========================================================
    # MATCH CURRENT CLUSTERS
    # ========================================================

    cluster_to_hotspot = {}

    new_hotspots = 0
    matched_hotspots = 0

    with engine.begin() as conn:

        for cluster in current_clusters:

            cluster_id = cluster["cluster_id"]
            lat = cluster["centroid_lat"]
            lon = cluster["centroid_lon"]

            best_hotspot_id = None
            best_distance = float("inf")

            # ------------------------------------------------
            # Find nearest historical hotspot
            # ------------------------------------------------

            for _, hotspot in hotspots.iterrows():

                distance = haversine_km(
                    lat,
                    lon,
                    float(hotspot["centroid_lat"]),
                    float(hotspot["centroid_lon"])
                )

                if (
                    distance <= MATCH_RADIUS_KM
                    and
                    distance < best_distance
                ):

                    best_distance = distance
                    best_hotspot_id = int(
                        hotspot["hotspot_id"]
                    )

            # ------------------------------------------------
            # Existing hotspot
            # ------------------------------------------------

            if best_hotspot_id is not None:

                hotspot_id = best_hotspot_id

                # Get the current cluster's detection date range.
                cluster_group = df[
                    df["cluster_id"] == cluster_id
                ]

                current_first_date = (
                    cluster_group["acq_date"]
                    .min()
                    .date()
                )

                current_last_date = (
                    cluster_group["acq_date"]
                    .max()
                    .date()
                )

                # Update the persistent hotspot's latest
                # observed detection date.
                conn.execute(
                    text("""
                        UPDATE persistent_hotspots
                        SET
                            last_detection = GREATEST(
                                last_detection,
                                :last_detection
                            ),
                            updated_at = NOW()
                        WHERE hotspot_id = :hotspot_id
                    """),
                    {
                        "hotspot_id": hotspot_id,
                        "last_detection": current_last_date
                    }
                )

                # Keep the in-memory history consistent so
                # later clusters in this same run see the
                # updated hotspot state.
                hotspots.loc[
                    hotspots["hotspot_id"] == hotspot_id,
                    "last_detection"
                ] = current_last_date

                matched_hotspots += 1

                print(
                    f"Cluster {cluster_id} -> "
                    f"Hotspot {hotspot_id} "
                    f"({best_distance:.3f} km)"
                )

            # ------------------------------------------------
            # New hotspot
            # ------------------------------------------------

            else:

                cluster_group = df[
                    df["cluster_id"] == cluster_id
                ]

                first_date = (
                    cluster_group["acq_date"]
                    .min()
                    .date()
                )

                last_date = (
                    cluster_group["acq_date"]
                    .max()
                    .date()
                )

                result = conn.execute(
                    text("""
                        INSERT INTO persistent_hotspots (
                            centroid_lat,
                            centroid_lon,
                            first_detection,
                            last_detection
                        )
                        VALUES (
                            :lat,
                            :lon,
                            :first_detection,
                            :last_detection
                        )
                        RETURNING hotspot_id
                    """),
                    {
                        "lat": lat,
                        "lon": lon,
                        "first_detection": first_date,
                        "last_detection": last_date
                    }
                )

                hotspot_id = int(
                    result.scalar_one()
                )

                new_hotspots += 1

                print(
                    f"Cluster {cluster_id} -> "
                    f"NEW Hotspot {hotspot_id}"
                )

                # Add newly created hotspot to the
                # in-memory list so another cluster in
                # this same run can match it.
                hotspots = pd.concat(
                    [
                        hotspots,
                        pd.DataFrame([{
                            "hotspot_id": hotspot_id,
                            "centroid_lat": lat,
                            "centroid_lon": lon,
                            "first_detection": first_date,
                            "last_detection": last_date
                        }])
                    ],
                    ignore_index=True
                )

            cluster_to_hotspot[
                cluster_id
            ] = hotspot_id

    # ========================================================
    # STORE CURRENT DETECTIONS
    # ========================================================

    with engine.begin() as conn:

        for _, row in df.iterrows():

            cluster_id = int(
                row["cluster_id"]
            )

            hotspot_id = cluster_to_hotspot[
                cluster_id
            ]

            event_hash = row.get(
                "event_hash"
            )

            if pd.isna(event_hash):
                continue

            conn.execute(
                text("""
                    INSERT INTO hotspot_detections (
                        hotspot_id,
                        event_hash,
                        latitude,
                        longitude,
                        acq_date,
                        frp,
                        cluster_id
                    )
                    VALUES (
                        :hotspot_id,
                        :event_hash,
                        :latitude,
                        :longitude,
                        :acq_date,
                        :frp,
                        :cluster_id
                    )
                    ON CONFLICT (event_hash)
                    DO NOTHING
                """),
                {
                    "hotspot_id": hotspot_id,
                    "event_hash": str(event_hash),
                    "latitude": float(
                        row["latitude"]
                    ),
                    "longitude": float(
                        row["longitude"]
                    ),
                    "acq_date": row[
                        "acq_date"
                    ].date(),
                    "frp": (
                        float(row["frp"])
                        if pd.notna(row["frp"])
                        else None
                    ),
                    "cluster_id": cluster_id
                }
            )

    # ========================================================
    # RELOAD HOTSPOT HISTORY
    # ========================================================

    history_query = """
        SELECT
            hd.hotspot_id,
            hd.latitude,
            hd.longitude,
            hd.acq_date,
            hd.frp,
            hd.cluster_id
        FROM hotspot_detections hd
        ORDER BY
            hd.hotspot_id,
            hd.acq_date;
    """

    history = pd.read_sql(
        text(history_query),
        engine
    )

    if history.empty:
        raise ValueError(
            "No hotspot history available."
        )

    history["acq_date"] = pd.to_datetime(
        history["acq_date"]
    )

    # ========================================================
    # CALCULATE PERSISTENCE
    # ========================================================

    results = []

    for hotspot_id, group in history.groupby(
        "hotspot_id"
    ):

        group = group.sort_values(
            "acq_date"
        )

        detection_count = len(group)

        unique_days = (
            group["acq_date"]
            .dt.date
            .nunique()
        )

        first_detection = (
            group["acq_date"].min()
        )

        last_detection = (
            group["acq_date"].max()
        )

        observation_window_days = (
            last_detection - first_detection
        ).days + 1

        if observation_window_days <= 0:
            observation_window_days = 1

        temporal_recurrence = (
            unique_days
            /
            observation_window_days
        )

        detection_frequency = (
            detection_count
            /
            observation_window_days
        )

        # ----------------------------------------------------
        # FRP
        # ----------------------------------------------------

        mean_frp = (
            group["frp"]
            .mean()
            if group["frp"].notna().any()
            else 0.0
        )

        max_frp = (
            group["frp"]
            .max()
            if group["frp"].notna().any()
            else 0.0
        )

        # ----------------------------------------------------
        # Brightness is unavailable in hotspot history
        # here, so use 0 as the live-stage placeholder.
        # ----------------------------------------------------

        mean_brightness = 0.0
        max_brightness = 0.0

        # ----------------------------------------------------
        # Spatial spread
        # ----------------------------------------------------

        centroid_lat = group[
            "latitude"
        ].mean()

        centroid_lon = group[
            "longitude"
        ].mean()

        distances = []

        for _, row in group.iterrows():

            distances.append(
                haversine_km(
                    centroid_lat,
                    centroid_lon,
                    float(row["latitude"]),
                    float(row["longitude"])
                )
            )

        spatial_spread_km = (
            max(distances)
            if distances
            else 0.0
        )

        # ----------------------------------------------------
        # Persistence features
        # ----------------------------------------------------

        duration_score = min(
            observation_window_days / 30.0,
            1.0
        )

        spatial_consistency = 1.0 / (
            1.0 + spatial_spread_km
        )

        persistence_score = (
            0.30 * temporal_recurrence
            +
            0.25 * duration_score
            +
            0.25 * spatial_consistency
            +
            0.20 * min(
                detection_frequency,
                1.0
            )
        ) * 100.0

        # ----------------------------------------------------
        # Current run cluster ID
        # ----------------------------------------------------

        latest_cluster_id = int(
            group.sort_values(
                "acq_date"
            ).iloc[-1]["cluster_id"]
        )

        # ----------------------------------------------------
        # Persistence label
        # ----------------------------------------------------

        if persistence_score >= 70:

            persistence_label = (
                "HIGH/PERSISTENT"
            )

        elif persistence_score >= 40:

            persistence_label = (
                "MEDIUM/RECURRENT"
            )

        else:

            persistence_label = (
                "LOW/TRANSIENT"
            )

        results.append({

            "hotspot_id":
                int(hotspot_id),

            "detection_count":
                float(detection_count),

            "mean_frp":
                float(mean_frp),

            "max_frp":
                float(max_frp),

            "mean_brightness":
                float(mean_brightness),

            "max_brightness":
                float(max_brightness),

            "unique_detection_days":
                float(unique_days),

            "observation_window_days":
                float(observation_window_days),

            "spatial_spread_km":
                float(spatial_spread_km),

            "temporal_recurrence":
                float(temporal_recurrence),

            "duration_score":
                float(duration_score),

            "detection_frequency":
                float(detection_frequency),

            "spatial_consistency":
                float(spatial_consistency),

            "persistence_score":
                float(persistence_score),

            "cluster_id":
                latest_cluster_id,

            "centroid_lat":
                float(centroid_lat),

            "centroid_lon":
                float(centroid_lon),

            "first_detection":
                first_detection.date(),

            "last_detection":
                last_detection.date(),

            "persistence_label":
                persistence_label
        })

    persistence_df = pd.DataFrame(
        results
    )

    # ========================================================
    # SAVE
    # ========================================================

    timestamp = pd.Timestamp.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_file = (
        OUTPUT_DIR
        /
        f"firms_persistence_{timestamp}.csv"
    )

    persistence_df.to_csv(
        output_file,
        index=False
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 70)
    print("PERSISTENCE COMPLETE")
    print("=" * 70)

    print(
        f"Current clusters: "
        f"{len(current_clusters)}"
    )

    print(
        f"Matched historical hotspots: "
        f"{matched_hotspots}"
    )

    print(
        f"New persistent hotspots: "
        f"{new_hotspots}"
    )

    print(
        f"Total historical hotspots: "
        f"{len(persistence_df)}"
    )

    print(
        persistence_df[
            "persistence_label"
        ].value_counts()
        .to_string()
    )

    print(
        f"Saved: {output_file}"
    )

    print("=" * 70)

    return output_file


if __name__ == "__main__":
    run_persistence()

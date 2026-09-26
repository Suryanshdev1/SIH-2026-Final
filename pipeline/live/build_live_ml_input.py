import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[2]

PERSISTENCE_DIR = BASE_DIR / "data/live_persistence"
WORLDCOVER_DIR = BASE_DIR / "data/live_worldcover"
OSM_DIR = BASE_DIR / "data/live_osm"
INDUSTRIAL_DIR = BASE_DIR / "data/live_industrial_proximity"
OUTPUT_DIR = BASE_DIR / "data/live_ml_input"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_COLUMNS = [
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
    "centroid_lon",
]


def latest_file(directory, pattern):
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(
            f"No files found in {directory} matching {pattern}"
        )
    return files[-1]


def main():
    print("=" * 70)
    print("BUILD LIVE 30-COLUMN ML INPUT")
    print("=" * 70)

    persistence_file = latest_file(
        PERSISTENCE_DIR, "firms_persistence_*.csv"
    )

    worldcover_file = latest_file(
        WORLDCOVER_DIR, "*.csv"
    )

    industrial_file = latest_file(
        INDUSTRIAL_DIR, "*.csv"
    )

    print(f"Persistence : {persistence_file.name}")
    print(f"WorldCover  : {worldcover_file.name}")
    print(f"Industrial  : {industrial_file.name}")

    persistence = pd.read_csv(persistence_file)
    worldcover = pd.read_csv(worldcover_file)
    industrial = pd.read_csv(industrial_file)

    print(f"\nPersistence rows: {len(persistence)}")
    print(f"WorldCover rows : {len(worldcover)}")
    print(f"Industrial rows : {len(industrial)}")

    # ------------------------------------------------------------
    # Normalize coordinate column names
    # ------------------------------------------------------------
    for df in [persistence, worldcover, industrial]:
        if "centroid_lat" not in df.columns:
            if "latitude" in df.columns:
                df["centroid_lat"] = df["latitude"]

        if "centroid_lon" not in df.columns:
            if "longitude" in df.columns:
                df["centroid_lon"] = df["longitude"]

    # ------------------------------------------------------------
    # Merge WorldCover using cluster_id when available.
    # Otherwise use nearest centroid.
    # ------------------------------------------------------------
    if "cluster_id" in worldcover.columns and "cluster_id" in persistence.columns:
        wc_cols = [
            c for c in worldcover.columns
            if c in [
                "cluster_id",
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
            ]
        ]

        worldcover_small = worldcover[wc_cols].drop_duplicates("cluster_id")

        merged = persistence.merge(
            worldcover_small,
            on="cluster_id",
            how="left",
            suffixes=("", "_wc")
        )
    else:
        merged = persistence.copy()

    # ------------------------------------------------------------
    # Add WorldCover fields if they are not already present
    # ------------------------------------------------------------
    wc_fields = [
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
    ]

    for col in wc_fields:
        if col not in merged.columns:
            merged[col] = 0

    # ------------------------------------------------------------
    # Merge industrial proximity
    # ------------------------------------------------------------
    if "cluster_id" in industrial.columns and "cluster_id" in merged.columns:
        ind_cols = [
            c for c in industrial.columns
            if c in [
                "cluster_id",
                "nearest_industrial_distance_km",
                "nearby_industrial_facility_count",
                "nearby_industrial_capacity_mw",
            ]
        ]

        industrial_small = industrial[ind_cols].drop_duplicates("cluster_id")

        merged = merged.merge(
            industrial_small,
            on="cluster_id",
            how="left",
            suffixes=("", "_ind")
        )

    ind_fields = [
        "nearest_industrial_distance_km",
        "nearby_industrial_facility_count",
        "nearby_industrial_capacity_mw",
    ]

    for col in ind_fields:
        if col not in merged.columns:
            merged[col] = 0

    # ------------------------------------------------------------
    # Resolve duplicate suffixed columns
    # ------------------------------------------------------------
    for col in EXPECTED_COLUMNS:
        alt_wc = f"{col}_wc"
        alt_ind = f"{col}_ind"

        if col not in merged.columns:
            if alt_wc in merged.columns:
                merged[col] = merged[alt_wc]
            elif alt_ind in merged.columns:
                merged[col] = merged[alt_ind]

        if alt_wc in merged.columns:
            merged[col] = merged[col].fillna(merged[alt_wc])

        if alt_ind in merged.columns:
            merged[col] = merged[col].fillna(merged[alt_ind])

    # ------------------------------------------------------------
    # Fire class
    # ------------------------------------------------------------
    if "fire_class" not in merged.columns:
        merged["fire_class"] = "UNKNOWN"

    # ------------------------------------------------------------
    # Numeric cleanup
    # ------------------------------------------------------------
    numeric_columns = [
        c for c in EXPECTED_COLUMNS
        if c not in ["fire_class"]
    ]

    for col in numeric_columns:
        merged[col] = pd.to_numeric(
            merged[col],
            errors="coerce"
        )

    # Keep fire class as string
    merged["fire_class"] = merged["fire_class"].fillna("UNKNOWN").astype(str)

    # ------------------------------------------------------------
    # Fill missing numeric values
    # ------------------------------------------------------------
    merged[numeric_columns] = merged[numeric_columns].fillna(0)

    # ------------------------------------------------------------
    # Exact 30-column contract
    # ------------------------------------------------------------
    missing = [c for c in EXPECTED_COLUMNS if c not in merged.columns]

    if missing:
        raise ValueError(
            f"Missing required ML columns: {missing}"
        )

    output = merged[EXPECTED_COLUMNS].copy()

    # Remove accidental duplicate rows
    output = output.drop_duplicates()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_file = (
        OUTPUT_DIR /
        f"firms_ml_input_{timestamp}.csv"
    )

    output.to_csv(output_file, index=False)

    print("\n" + "=" * 70)
    print("LIVE ML INPUT COMPLETE")
    print("=" * 70)
    print(f"Rows    : {len(output)}")
    print(f"Columns : {len(output.columns)}")
    print(f"Output  : {output_file}")
    print("\nColumn validation:")

    if list(output.columns) == EXPECTED_COLUMNS:
        print("✓ EXACT 30-COLUMN CONTRACT")
    else:
        print("✗ COLUMN CONTRACT MISMATCH")
        print(list(output.columns))
        raise ValueError("ML input column order mismatch")

    print("\nMissing values:")
    print(int(output.isna().sum().sum()))

    print("=" * 70)


if __name__ == "__main__":
    main()

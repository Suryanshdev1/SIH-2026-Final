import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

RAW_DIR = BASE_DIR / "data" / "live_raw"
OUTPUT_DIR = BASE_DIR / "data" / "live_clean"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def find_latest_raw_file():
    files = sorted(RAW_DIR.glob("firms_*.csv"))

    if not files:
        raise FileNotFoundError("No raw FIRMS poll file found.")

    return files[-1]


def run_cleaning():

    print("=" * 70)
    print("LIVE FIRMS CLEANING")
    print("=" * 70)

    input_file = find_latest_raw_file()

    print(f"Raw input: {input_file}")

    df = pd.read_csv(input_file)

    print(f"Raw detections: {len(df)}")

    if df.empty:
        raise ValueError("Latest FIRMS file is empty.")

    # Normalize column names
    df.columns = [
        c.strip().lower()
        for c in df.columns
    ]

    # FIRMS NRT compatibility
    if "bright_ti4" in df.columns:
        df["brightness"] = df["bright_ti4"]

    if "bright_ti5" in df.columns:
        df["bright_t31"] = df["bright_ti5"]

    # Required columns
    required = [
        "latitude",
        "longitude",
        "acq_date",
        "frp"
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    # Numeric conversion
    for col in [
        "latitude",
        "longitude",
        "brightness",
        "bright_t31",
        "frp",
        "scan",
        "track"
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

    # Date
    df["acq_date"] = pd.to_datetime(
        df["acq_date"],
        errors="coerce"
    ).dt.date

    # Remove invalid rows
    df = df.dropna(
        subset=[
            "latitude",
            "longitude",
            "acq_date",
            "frp"
        ]
    )

    df = df[
        (df["latitude"] >= -90) &
        (df["latitude"] <= 90) &
        (df["longitude"] >= -180) &
        (df["longitude"] <= 180)
    ]

    df = df[df["frp"] >= 0]

    # --------------------------------------------------------
    # Create stable event hash
    # --------------------------------------------------------
    # The same FIRMS detection must receive the same hash
    # across repeated 3-hour polls so PostgreSQL can deduplicate
    # historical detections safely.

    import hashlib

    def make_event_hash(row):
        values = [
            row.get("latitude"),
            row.get("longitude"),
            row.get("acq_date"),
            row.get("acq_time"),
            row.get("satellite"),
            row.get("instrument")
        ]

        raw = "|".join(
            "" if pd.isna(v) else str(v)
            for v in values
        )

        return hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()

    if "event_hash" not in df.columns:
        df["event_hash"] = df.apply(
            make_event_hash,
            axis=1
        )

    # Remove duplicate FIRMS events
    df = df.drop_duplicates(
        subset=["event_hash"]
    )

    timestamp = pd.Timestamp.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_file = (
        OUTPUT_DIR /
        f"firms_clean_{timestamp}.csv"
    )

    df.to_csv(
        output_file,
        index=False
    )

    print(f"Clean detections: {len(df)}")
    print(f"Saved: {output_file}")
    print("=" * 70)

    return output_file


if __name__ == "__main__":
    run_cleaning()

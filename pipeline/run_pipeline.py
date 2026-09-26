import subprocess
import sys
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

STAGES = [
    (
        "FIRMS POLLER",
        BASE_DIR / "pipeline/live/firms_poller.py"
    ),
    (
        "FIRMS CLEANING",
        BASE_DIR / "pipeline/live/clean_firms.py"
    ),
    (
        "DBSCAN",
        BASE_DIR / "pipeline/live/dbscan_firms.py"
    ),
    (
        "PERSISTENCE + HISTORICAL HOTSPOTS",
        BASE_DIR / "pipeline/live/persistence_firms.py"
    ),
    (
        "WORLDCOVER",
        BASE_DIR / "pipeline/live/worldcover_firms.py"
    ),
    (
        "OSM",
        BASE_DIR / "pipeline/live/osm_firms.py"
    ),
    (
        "INDUSTRIAL PROXIMITY",
        BASE_DIR / "pipeline/live/industrial_proximity_firms.py"
    ),
    (
        "BUILD ML INPUT",
        BASE_DIR / "pipeline/live/build_live_ml_input.py"
    ),
    (
        "LOAD POSTGRESQL",
        BASE_DIR / "pipeline/live/load_processed_data.py"
    )
]


def run_stage(name, script):

    print()
    print("#" * 80)
    print(f"STARTING: {name}")
    print(f"SCRIPT:   {script}")
    print("#" * 80)

    subprocess.run(
        [
            PYTHON,
            str(script)
        ],
        cwd=BASE_DIR,
        check=True
    )

    print()
    print(f"COMPLETED: {name}")


def main():

    start = datetime.now()

    print("=" * 80)
    print("TEAM PYRON — LIVE FIRE PIPELINE")
    print("=" * 80)
    print(f"Started: {start}")
    print()

    try:

        for name, script in STAGES:

            if not script.exists():

                raise FileNotFoundError(
                    f"Missing pipeline script: {script}"
                )

            run_stage(
                name,
                script
            )

    except subprocess.CalledProcessError as exc:

        print()
        print("=" * 80)
        print("PIPELINE FAILED")
        print("=" * 80)
        print(
            f"Stage exited with code {exc.returncode}"
        )

        sys.exit(
            exc.returncode
        )

    end = datetime.now()

    print()
    print("=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)
    print(f"Started:  {start}")
    print(f"Finished: {end}")
    print(f"Duration: {end - start}")
    print("=" * 80)


if __name__ == "__main__":
    main()

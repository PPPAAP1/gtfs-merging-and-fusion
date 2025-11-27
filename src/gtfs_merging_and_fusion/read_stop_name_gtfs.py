import pandas as pd
from pathlib import Path
import yaml

def load_static_gtfs_stop(cfg: dict, stop_name: str) -> pd.DataFrame:
    static_dir = Path(cfg["paths"]["raw_static"])
    output_dir = Path(cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"🔹 Loading static GTFS data from: {static_dir}")

    # -------------------------
    trips_path = static_dir / "trips.txt"
    stop_times_path = static_dir / "stop_times.txt"
    stops_path = static_dir / "stops.txt"
    routes_path = static_dir / "routes.txt"

    for file in [trips_path, stop_times_path, stops_path, routes_path]:
        if not file.exists():
            raise FileNotFoundError(f"❌ Missing required GTFS file: {file}")

    # -------------------------
    # reading route trips stops
    # -------------------------
    routes = pd.read_csv(routes_path, dtype=str, low_memory=False)
    trips = pd.read_csv(trips_path, dtype=str, low_memory=False)
    stops = pd.read_csv(stops_path, dtype=str, low_memory=False)
    print(f"✅ Loaded routes({len(routes)}), trips({len(trips)}), stops({len(stops)})")

    # ------------------------- 
    # stop_times reading + filtering by stop_name
    # -------------------------
    print("📦 Reading stop_times.txt in chunks (filtering by stop_name)...")
    filtered_chunks = []
    total_rows = 0
    kept_rows = 0

    # Get target stop_id list
    matched_stops = stops[stops["stop_name"].str.contains(stop_name, case=False, na=False)]
    if matched_stops.empty:
        print(f"⚠️ No stops matched for '{stop_name}'")
        return pd.DataFrame()

    stop_ids = matched_stops["stop_id"].unique().tolist()
    print(f"🔹 Found {len(stop_ids)} stop_id(s) for '{stop_name}':")

    # Print all matched stop_name
    for sid, sname in zip(matched_stops["stop_id"], matched_stops["stop_name"]):
        print(f"   {sid} → {sname}")


    for chunk in pd.read_csv(stop_times_path, dtype=str, chunksize=500000):
        total_rows += len(chunk)
        chunk_filtered = chunk[chunk["stop_id"].isin(stop_ids)]
        kept_rows += len(chunk_filtered)
        filtered_chunks.append(chunk_filtered)
        print(f"  ⏩ Read {total_rows:,} rows, kept {kept_rows:,} so far")

    if kept_rows == 0:
        print("⚠️ No matching stop_times rows.")
        return pd.DataFrame()

    stop_times_filtered = pd.concat(filtered_chunks, ignore_index=True)
    stops_filtered = matched_stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]].copy()

    merged_df = (
        stop_times_filtered
        .merge(trips[["trip_id", "service_id"]], on="trip_id", how="left")
        .merge(stops_filtered, on="stop_id", how="left")
    )

    merged_df = merged_df[
        ["trip_id", "stop_id", "stop_name", "stop_lat", "stop_lon", "arrival_time", "departure_time", "service_id"]
    ].drop_duplicates().reset_index(drop=True)

    print(f"✅ Loaded {len(merged_df)} rows of static GTFS data.")

    safe_stop_name = stop_name.replace(" ", "_")
    output_file = output_dir / f"static_gtfs_{safe_stop_name}.csv"
    merged_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"✅ Saved merged static GTFS to {output_file}")

    return merged_df

# ------------------------- Standalone Run -------------------------
if __name__ == "__main__":
    # Load configuration file
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # User input stop_name:
    stop_name = input("Please enter stop name (e.g., Dresden Hbf): ").strip()
    if not stop_name:
        print("❌ No stop name entered, exiting")
        exit(0)

    df = load_static_gtfs_stop(cfg, stop_name)

    if not df.empty:
        # Output .CSV
        output_dir = Path(cfg["processed_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{stop_name.replace(' ', '_')}_static.csv"
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"📄 Saved filtered static GTFS to {output_file}")

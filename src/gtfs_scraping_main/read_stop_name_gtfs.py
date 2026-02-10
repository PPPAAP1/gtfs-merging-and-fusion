import pandas as pd
from pathlib import Path
import yaml
import matplotlib.pyplot as plt

"""
read_stop_name_gtfs.py

The script loads static GTFS data from the directory,
filters it by user-selected stop_name(s), and saves the filtered dataset to a new CSV file.

This will be useful if you have full GTFS Static data,
and you want to focus on specific destination stops (e.g., Dresden, or Dresden Hauptbahnhof, etc.) for your analysis.
"""

def load_static_gtfs_stop(cfg: dict, stop_name: str) -> pd.DataFrame:
    static_dir = Path(cfg["paths"]["raw_static"])
    output_dir = Path(cfg["processed_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    trips = pd.read_csv(static_dir / "trips.txt", dtype=str, low_memory=False)
    routes = pd.read_csv(static_dir / "routes.txt", dtype=str, low_memory=False)
    stops = pd.read_csv(static_dir / "stops.txt", dtype=str, low_memory=False)
    # route_type + trips
    trips = trips.merge(routes[["route_id","route_type"]], on="route_id", how="left")

    stop_times_path = static_dir / "stop_times.txt"

    matched_stops = stops[stops["stop_name"].str.contains(stop_name, case=False, na=False)]
    if matched_stops.empty:
        print(f"⚠️ No stops matched for '{stop_name}'")
        return pd.DataFrame(), []

    stop_ids = matched_stops["stop_id"].unique().tolist()
    print(f"Found {len(stop_ids)} stop_id(s) for '{stop_name}':")
    for sid, sname in zip(matched_stops["stop_id"], matched_stops["stop_name"]):
        print(f"   {sid} → {sname}")

    # -------------------------
    # stop_times reading + filtering by stop_ids in chunks
    # -------------------------
    print("📦 Reading stop_times.txt in chunks (filtering by stop_name)...")
    filtered_chunks = []
    total_rows = 0
    kept_rows = 0

    for chunk in pd.read_csv(stop_times_path, dtype=str, chunksize=500000):
        total_rows += len(chunk)
        chunk_filtered = chunk[chunk["stop_id"].isin(stop_ids)]
        kept_rows += len(chunk_filtered)
        filtered_chunks.append(chunk_filtered)
        print(f"  📦 Read {total_rows:,} rows, kept {kept_rows:,} so far")

    if kept_rows == 0:
        print("⚠️ No matching stop_times rows.")
        return pd.DataFrame(), []

    stop_times_filtered = pd.concat(filtered_chunks, ignore_index=True)

    merged_df = stop_times_filtered.merge(trips[["trip_id","service_id","route_type"]], on="trip_id", how="left")
    merged_df = merged_df.merge(matched_stops[["stop_id","stop_name","stop_lat","stop_lon"]], on="stop_id", how="left")
    merged_df = merged_df[["trip_id","stop_id","route_type","stop_name","stop_lat","stop_lon","arrival_time","departure_time","service_id"]]

    safe_name = stop_name.replace(" ","_")
    output_file = output_dir / f"static_gtfs_{safe_name}.csv"
    merged_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"✅ Saved static GTFS to {output_file}")

    return merged_df, stop_ids

def load_realtime_data(cfg: dict, stop_ids: list) -> pd.DataFrame:
    rt_dir = Path(cfg["paths"]["raw_rt"])
    all_files = sorted(list(rt_dir.glob("*")))  # output csv or json files
    total_files = len(all_files)
    all_records = []

    if total_files == 0:
        print("⚠️ No real-time files found in directory")
        return pd.DataFrame()
    
    for i, f in enumerate(all_files, 1):
        if f.suffix.lower() == ".csv":
            df = pd.read_csv(f, dtype=str)
        elif f.suffix.lower() == ".json":
            df = pd.read_json(f, dtype=str)
        else:
            print(f"⚠️ Skipping unsupported file type: {f.name}")
            continue

        df_filtered = df[df["stop_id"].isin(stop_ids)].copy()
        df_filtered["source_file"] = f.name
        all_records.append(df_filtered)

        print(f"Processed {f.name} ({i}/{total_files}), kept {len(df_filtered)} rows, {total_files - i} files to go")

    if not all_records:
        return pd.DataFrame()

    df_rt = pd.concat(all_records, ignore_index=True)
    print(f"✅ All files processed. Total real-time rows for this stop: {len(df_rt)}")
    return df_rt

def analyze_delay(static_df, realtime_df, stop_name, cfg):

    # Merge static + realtime
    df = pd.merge(
        realtime_df,
        static_df,
        on=["trip_id", "stop_id"],
        how="left",
        suffixes=("_rt", "_sched")
    )
    
    print("Static columns:", static_df.columns)
    print("Realtime columns:", realtime_df.columns)

    print("Merged columns:", df.columns)
    print(df.filter(regex="stop_name").head())

    # Convert arrival_delay (string/float) to numeric
    df["arrival_delay"] = pd.to_numeric(df["arrival_delay"], errors="coerce")

    # Compute delay in minutes
    df["delay_min"] = df["arrival_delay"] / 60.0

    # --- Compute departure delay ---
    if "departure_delay" in df.columns:
        df["departure_delay"] = pd.to_numeric(df["departure_delay"], errors="coerce")
        df["dep_delay_min"] = df["departure_delay"] / 60.0

    # Save CSV
    output_dir = Path(cfg["output_dir"])
    safe_name = stop_name.replace(" ", "_")
    delay_file = output_dir / f"delay_{safe_name}.csv"
    df.to_csv(delay_file, index=False, encoding="utf-8-sig")
    print(f"✅ Saved delay CSV to {delay_file}")


    
    # Plot trend: arrival_time_sched (static) vs delay_min
    # Convert scheduled arrival_time to datetime for plotting
    df["fetch_timestamp"] = pd.to_datetime(df["fetch_timestamp"], errors="coerce")

    plt.figure(figsize=(12, 6))
    plt.scatter(df["fetch_timestamp"], df["arrival_delay"], alpha=0.5)
    plt.xlabel("Fetch Timestamp")
    plt.ylabel("Delay (Seconds)")
    plt.title(f"Delay Trend - {stop_name}")
    plt.grid(True)
    plt.tight_layout()

    plot_file = output_dir / f"delay_trend_{safe_name}.png"
    plt.savefig(plot_file)
    print(f"✅ Saved delay trend plot to {plot_file}")
    plt.close()


if __name__ == "__main__":
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    stop_name = input("Please enter stop name (e.g., Dresden Hauptbahnhof): ").strip()
    if not stop_name:
        exit(0)

    static_df, stop_ids = load_static_gtfs_stop(cfg, stop_name)
    if static_df.empty:
        exit(0)

    realtime_df = load_realtime_data(cfg, stop_ids)
    if realtime_df.empty:
        print("⚠️ No real-time data for this stop")
        exit(0)

    analyze_delay(static_df, realtime_df, stop_name, cfg)



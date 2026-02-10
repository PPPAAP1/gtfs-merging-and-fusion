import pandas as pd
from pathlib import Path
import yaml

"""
read_route_type_gtfs.py

The script loads static GTFS data from the directory,
filters it by user-selected route_type(s), and saves the filtered dataset to a new CSV file.

This will be useful if you have full GTFS Static data,
and you want to focus on specific types of transportation (e.g., RBRE, ICE, etc.) for your analysis.
"""

# GTFS Route Type Reference
ROUTE_TYPE_NAMES = {
    "0": "Tram/Streetcar",
    "1": "Subway/Metro",
    "2": "Rail",
    "3": "Bus",
    "4": "Ferry",
    "5": "Cable car",
    "101": "High Speed Rail Service (ICE)",
    "102": "Long Distance Trains (InterCity：IC)",
    "103": "Inter Regional Rail Service InterRegio (DE)",
    "106": "Regional Train (Regionalzug：RB/RE)",
    "109": "Suburban Railway (S-Bahn (DE))",
    "110": "Replacement Rail Service (Ersatzverkehr Schiene)",
    "201": "International Coach Service (EuroLine, Touring)",
    "400": "Urban Railway Service",
    "700": "Bus Service",
    "704": "Local Bus Service",
    "715": "Demand and Response Bus Service",
    "900": "Tram Service",
    "1000": "Water Transport Service",
    "1501": "Communal Taxi Service",
}

def load_static_gtfs_route(cfg: dict) -> pd.DataFrame:
    static_dir = Path(cfg["paths"]["raw_static"])
    output_dir = Path(cfg["processed_dir"])
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
    # route_type filtering
    # -------------------------
    print("\n🔹 Available route_types in your data:")
    available_types = sorted(routes["route_type"].unique(), key=lambda x: int(x), reverse=True)
    for rt in available_types:
        count = len(routes[routes["route_type"] == rt])
        rt_name = ROUTE_TYPE_NAMES.get(rt, "Unknown")
        print(f"  - {rt:3s}: {rt_name:35s} ({count} routes)")

    route_type_filter = input("\nPlease enter route_type number, separated by commas (default: 106): ").strip()
    if not route_type_filter:
        route_type_list = ["106"]
    else:
        route_type_list = [x.strip() for x in route_type_filter.split(",")]

    route_ids = routes[routes["route_type"].isin(route_type_list)]["route_id"].unique().tolist()
    print(f"🔹 Found {len(route_ids)} route_ids for selected route_type(s): {route_type_list}")
    if len(route_ids) == 0:
        print("⚠️ no such route_id, please check route_type number input")
        print("⚠️ https://developers.google.com/transit/gtfs/reference/extended-route-types") 
        return pd.DataFrame()

    trips_filtered = trips[trips["route_id"].isin(route_ids)].copy()
    trip_ids = trips_filtered["trip_id"].unique().tolist()
    print(f"🔹 Found {len(trip_ids)} trip(s) under selected route_type(s)")

    if len(trip_ids) == 0:
        print("⚠️ no matching/existing trips found")
        return pd.DataFrame()


    # -------------------------
    # stop_times reading + filtering
    # -------------------------
    print("📦 Reading stop_times.txt in chunks...")
    filtered_chunks = []
    total_rows = 0
    kept_rows = 0

    for chunk in pd.read_csv(stop_times_path, dtype=str, chunksize=500000):
        total_rows += len(chunk)
        chunk_filtered = chunk[chunk["trip_id"].isin(trip_ids)]
        kept_rows += len(chunk_filtered)
        filtered_chunks.append(chunk_filtered)
        print(f"📦 Read {total_rows:,} rows, kept {kept_rows:,} so far")

    stop_times = pd.concat(filtered_chunks, ignore_index=True)
    stops = stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]].copy()

    # -------------------------
    # Filtering
    # -------------------------
    merged_df = (
        stop_times
        .merge(trips_filtered[["trip_id", "service_id"]], on="trip_id", how="left")
        .merge(stops, on="stop_id", how="left")
    )

    merged_df = merged_df[
        ["trip_id", "stop_id", "stop_name", "stop_lat", "stop_lon", "arrival_time", "departure_time", "service_id"]
    ].drop_duplicates().reset_index(drop=True)


    print(f"✅ Loaded {len(merged_df)} rows of static GTFS data.")

    route_suffix = "_".join(route_type_list)
    output_file = output_dir / f"static_gtfs_{route_suffix}.csv"
    merged_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Saved filtered static GTFS to {output_file}")
    return merged_df



if __name__ == "__main__":
    # 1️⃣ Load configuration file
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 2️⃣ Load static GTFS data
    df = load_static_gtfs_route(cfg)

    # 3️⃣ Display first few rows
    print(df.head())

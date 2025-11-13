"""
read_static_gtfs.py
-------------------
读取静态 GTFS 数据文件(txt 格式)，并整理成统一结构的 DataFrame
Columns: trip_id | stop_id | stop_name | arrival_time | departure_time | service_id
"""

import pandas as pd
from pathlib import Path

def load_static_gtfs(static_dir: Path) -> pd.DataFrame:
    print(f"🔹 Loading static GTFS data from: {static_dir}")

    # -------------------------
    # 1. 文件路径与存在性检查
    # -------------------------
    trips_path = static_dir / "trips.txt"
    stop_times_path = static_dir / "stop_times.txt"
    stops_path = static_dir / "stops.txt"
    routes_path = static_dir / "routes.txt"

    for file in [trips_path, stop_times_path, stops_path, routes_path]:
        if not file.exists():
            raise FileNotFoundError(f"❌ Missing required GTFS file: {file}")

    # -------------------------
    # 2. 读取主要文件
    # -------------------------
    routes = pd.read_csv(routes_path, dtype=str, low_memory=False)
    trips = pd.read_csv(trips_path, dtype=str, low_memory=False)
    stops = pd.read_csv(stops_path, dtype=str, low_memory=False)
    print(f"✅ Loaded routes({len(routes)}), trips({len(trips)}), stops({len(stops)})")

    # -------------------------
    # 3. route_type 诊断输出
    # -------------------------
    if "route_type" not in routes.columns:
        raise ValueError("❌ routes.txt 缺少 route_type 列")

    route_type_labels = {
        100: "Railway Service",
        101: "High Speed Rail Service (ICE)",
        102: "Long Distance (IC/EC)",
        103: "Inter Regional Rail",
        105: "Sleeper Rail Service",
        106: "Regional Rail (RB/RE)",
        108: "Rail Shuttle",
        109: "Suburban (S-Bahn)",
    }

    print("\n📊 当前数据中的 route_type 统计：")
    routes["route_type"] = routes["route_type"].str.strip()
    counts = routes["route_type"].value_counts().sort_index()
    for rt, cnt in counts.items():
        label = route_type_labels.get(int(rt)) if rt.isdigit() else "---UNKNOWN---"
        print(f"  {rt:<5} {cnt:>6} ({label})")

    # -------------------------
    # 4. 用户输入筛选条件
    # -------------------------
    route_type_filter = input("\n请输入要保留的 route_type 数字或范围, 用逗号分隔: ").strip()

    if not route_type_filter:
        route_type_list = ["106"]  # 默认德国区域铁路
    else:
        route_type_list = [x.strip() for x in route_type_filter.split(",")]

    route_ids = routes[routes["route_type"].isin(route_type_list)]["route_id"].unique().tolist()
    print(f"🔹 Found {len(route_ids)} route_ids for selected route_type(s): {route_type_list}")

    if len(route_ids) == 0:
        print("⚠️ 没有匹配的 route_id，请检查 route_type 是否正确。")
        return pd.DataFrame()

    # -------------------------
    # 5. 获取对应 trip_id
    # -------------------------
    if "route_id" not in trips.columns:
        raise ValueError("❌ trips.txt 缺少 route_id 列。")

    trips_filtered = trips[trips["route_id"].isin(route_ids)].copy()
    trip_ids = trips_filtered["trip_id"].unique().tolist()
    print(f"🔹 Found {len(trip_ids)} trip(s) under selected route_type(s)")

    if len(trip_ids) == 0:
        print("⚠️ 没有找到对应 trip，可能 route_id 没有匹配成功。")
        return pd.DataFrame()

    # -------------------------
    # 6. 分块读取 stop_times 并过滤
    # -------------------------
    print("📦 Reading stop_times.txt in chunks (filtering on the fly)...")
    filtered_chunks = []
    total_rows = 0
    kept_rows = 0

    for chunk in pd.read_csv(stop_times_path, dtype=str, chunksize=500000):
        total_rows += len(chunk)
        chunk_filtered = chunk[chunk["trip_id"].isin(trip_ids)]
        kept_rows += len(chunk_filtered)
        filtered_chunks.append(chunk_filtered)
        print(f"  ⏩ Read {total_rows:,} rows, kept {kept_rows:,} so far")

    if kept_rows == 0:
        print("⚠️ 没有匹配的 stop_times 行。")
        return pd.DataFrame()

    stop_times = pd.concat(filtered_chunks, ignore_index=True)
    print(f"✅ stop_times loaded with {len(stop_times):,} filtered rows.")

    # -------------------------
    # 7. 合并 + 精简列
    # -------------------------
    stops = stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]].copy()
    merged_df = (
        stop_times
        .merge(trips_filtered[["trip_id", "service_id"]], on="trip_id", how="left")
        .merge(stops, on="stop_id", how="left")
    )

    merged_df = merged_df[
        ["trip_id", "stop_id", "stop_name", "stop_lat", "stop_lon", "arrival_time", "departure_time", "service_id"]
    ].drop_duplicates().reset_index(drop=True)

    print(f"✅ Loaded {len(merged_df):,} rows of static GTFS data.")
    return merged_df


# -------------------------
# 独立测试
# -------------------------
if __name__ == "__main__":
    base_dir = Path(r"H:\The Coding Environment\Railway Operation\gtfs-data-mandf\gtfs-merging-and-fusion")
    static_dir = base_dir / "data_static"
    df = load_static_gtfs(static_dir)
    print(df.head())

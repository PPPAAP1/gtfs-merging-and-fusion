"""
read_static_gtfs.py
-------------------
读取静态 GTFS 数据文件(txt 格式)，并整理成统一结构的 DataFrame
Columns: trip_id | stop_id | stop_name | arrival_time | departure_time | service_id
"""

import pandas as pd
from pathlib import Path

def load_static_gtfs(static_dir: Path) -> pd.DataFrame:
    """
    读取 GTFS 静态数据目录下的必要文件，并返回整理后的 DataFrame。

    参数:
        static_dir (Path): 包含 GTFS 静态数据文件的目录路径

    返回:
        pandas.DataFrame: 整合后的静态 GTFS 数据表
    """
    print(f"🔹 Loading static GTFS data from: {static_dir}")

    # -------------------------
    # 1. 读取必要文件
    # -------------------------
    trips_path = static_dir / "trips.txt"
    stop_times_path = static_dir / "stop_times.txt"
    stops_path = static_dir / "stops.txt"
    routes_path = static_dir / "routes.txt"

    # 文件存在性检查
    for file in [trips_path, stop_times_path, stops_path, routes_path]:
        if not file.exists():
            raise FileNotFoundError(f"❌ Missing required GTFS file: {file}")

    trips = pd.read_csv(trips_path, low_memory=False, dtype=str)
    #### stop_times = pd.read_csv(stop_times_path, low_memory=False, dtype=str) # 必须分块读取。
    stops = pd.read_csv(stops_path, low_memory=False, dtype=str)
    routes = pd.read_csv(routes_path, low_memory=False, dtype=str)

    print("✅ Loaded trips.txt, stops.txt, routes.txt")

    # ===============================
    #   分块读取 stop_times.txt
    # ===============================
    print("📦 Reading stop_times.txt in chunks...")
    chunk_list = []
    for chunk in pd.read_csv(stop_times_path, dtype=str, chunksize=chunksize):
        chunk_list.append(chunk)
        print(f"  ⏩ Loaded {len(chunk)} rows (Total: {sum(len(c) for c in chunk_list)})")

    stop_times = pd.concat(chunk_list, ignore_index=True)
    print(f"✅ stop_times loaded with {len(stop_times)} rows.")

    # -------------------------
    # 2. route_type 筛选
    # -------------------------
    print("\n可选的交通类型（route_type）:") 
    
    # print(routes["route_type"].value_counts()) 我觉得可以加注释：

    # route_type 对照表（Needs to be Cross Validated!!）
    route_type_labels = {
        0: "Tram / Streetcar / Light rail",
        1: "Subway / Metro",
        2: "Rail / Train",
        3: "Bus",
        4: "Ferry",
        5: "Cable tram",
        6: "Aerial lift / Gondola",
        7: "Funicular",
        100: "Railway Service",
        101: "High-speed Rail",
        102: "Long-distance Rail",
        106: "Regional Rail",
        109: "Suburban Rail",
        200: "Bus Service",
        300: "Coach Service",
        400: "Urban Railway",
        700: "Regional Train (🇩🇪 DB Regio)",
        704: "Tram / Stadtbahn (🇩🇪)",
        715: "S-Bahn (🇩🇪)",
        900: "Water Transport",
        1000: "Air Service",
        1501: "Cableway / Seilbahn",
        201: "Express Bus",
    }

    # 显示带注释的 route_type 统计
    counts = routes["route_type"].value_counts().sort_index()
    for route_type, count in counts.items():
        label = route_type_labels.get(route_type, "Unknown Type")
        print(f"{route_type:<6} {count:>8}  ({label})")


    route_type_filter = input(
        "\n请输入要保留的 route_type 数字或范围: "
    ).strip()

    if route_type_filter == "":
        # 默认保留德国铁路（7开头）
        route_ids = routes[routes['route_type'].astype(str).str.startswith("7")]['route_id']
    else:
        # 用户输入逗号分隔多个类型
        route_type_list = [int(x.strip()) for x in route_type_filter.split(",")]
        route_ids = routes[routes['route_type'].isin(route_type_list)]['route_id']

    # 筛选 trips
    if 'route_id' not in trips.columns:
        raise ValueError("trips.txt 文件缺少 route_id 列，无法进行 route_type 筛选")
    trips = trips[trips['route_id'].isin(route_ids)]

    # -------------------------
    # 3. 保留必要列
    # -------------------------
    trips = trips[['trip_id', 'service_id']] if 'service_id' in trips.columns else trips[['trip_id']]
    stop_times = stop_times[['trip_id', 'stop_id', 'arrival_time', 'departure_time']]
    stops = stops[['stop_id', 'stop_name']]

    # -------------------------
    # 4. 合并 stop_times + trips + stops
    # -------------------------
    merged_df = (
        stop_times
        .merge(trips, on='trip_id', how='inner')
        .merge(stops, on='stop_id', how='left')
    )

    # -------------------------
    # 5. 排序 & 去重
    # -------------------------
    merged_df = merged_df[['trip_id', 'stop_id', 'stop_name', 'arrival_time', 'departure_time', 'service_id']]
    merged_df = merged_df.sort_values(by=['trip_id', 'stop_id']).drop_duplicates().reset_index(drop=True)

    print(f"✅ Loaded {len(merged_df)} rows of static GTFS data.")
    return merged_df


# -------------------------
# 独立测试
# -------------------------
if __name__ == "__main__":
    base_dir = Path(r"H:\The Coding Environment\Railway Operation\gtfs-data-mandf")
    static_dir = base_dir / "data_static"
    df = load_static_gtfs(static_dir)
    print(df.head())

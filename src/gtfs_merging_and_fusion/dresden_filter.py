import os
import pandas as pd

# -------------------------------
# 配置参数
# -------------------------------
# 清洗后的 GTFS-RT CSV
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
rt_file = os.path.join(base_dir, "gtfs_rt_cleaned.csv")

# 静态 GTFS 文件
trips_file = os.path.join(base_dir, "data_static/trips.txt")
routes_file = os.path.join(base_dir, "data_static/routes.txt")

# 输出 CSV
output_file = "gtfs_rt_dresden.csv"

# Dresden Hbf stop_id 列表，请自己填写
dresden_stop_ids = [
"de:14612:28:19:5",
"de:14612:28:2:6",
"de:14612:28",
"de:14612:28:2:3",
"de:14612:28:2:4",
"de:14612:28:2:1",
"de:14612:28:2:2",
"de:14612:32:1:1",
"de:14612:32:1:2",
"de:14612:28:20",

"de:14612:28:10:Gleis3",
"de:14612:28:11:Gleis1",
"de:14612:28:12:Gleis13",
"de:14612:28:12:Gleis14",
"de:14612:28:9:Gleis17",
"de:14612:28:8:Gleis18",
"de:14612:28:8:Gleis19",
"de:14612:28:11:Gleis2",
"de:14612:28:10:Gleis4",
"de:14612:28:14:Gleis6",
"de:14612:28:13:Gleis9",
"de:14612:28:13:Gleis10",
"de:14612:28:1:Gleis11",
"de:14612:28:1:Gleis12",

"de:14612:28:15",
"de:14612:28:17",
"de:14612:28:18",

"de:14612:28_G",
"de:14612:28_G_G",

"de:14612:28:16:93",

"000010002803",
"000010002804",
"000010002805",
"000010002806",
"000010002807",
"000010002808",
"000010002809",
"000010002829",
]

# 保留 route_type
valid_route_types = [101, 102, 103, 106, 109, 700, 704, 900, 901]

# -------------------------------
# 读取数据（确保 ID 列为字符串以避免合并时报错）
# -------------------------------
# 读取实时清洗结果，强制 trip_id 为字符串
df_rt = pd.read_csv(rt_file, dtype={"trip_id": str}, low_memory=False)

# 读取静态文件，强制 trip_id 和 route_id 为字符串以便合并
df_trips = pd.read_csv(trips_file, dtype={"trip_id": str, "route_id": str}, low_memory=False)
df_routes = pd.read_csv(routes_file, dtype={"route_id": str}, low_memory=False)

# 规范化 ID 字段（去除空白并统一为 str）
df_rt["trip_id"] = df_rt["trip_id"].astype(str).str.strip()
df_trips["trip_id"] = df_trips["trip_id"].astype(str).str.strip()
df_trips["route_id"] = df_trips["route_id"].astype(str).str.strip()
df_routes["route_id"] = df_routes["route_id"].astype(str).str.strip()

# route_type 转为整数（nullable Int64），便于后续比较和分类
df_routes["route_type"] = pd.to_numeric(df_routes.get("route_type"), errors="coerce").astype("Int64")

# -------------------------------
# 合并 route_type
# -------------------------------
# trip_id -> route_id
df_rt = df_rt.merge(df_trips[["trip_id", "route_id"]], on="trip_id", how="left")

# route_id -> route_type
df_rt = df_rt.merge(df_routes[["route_id", "route_type"]], on="route_id", how="left")

# 检查是否成功
print("Route type sample:")
print(df_rt[["trip_id","route_id","route_type"]].head())

# -------------------------------
# 筛选 Dresden Hbf stop_id
# -------------------------------
df_dresden = df_rt[df_rt["stop_id"].isin(dresden_stop_ids)]

# -------------------------------
# 筛选 route_type
# -------------------------------
df_dresden = df_dresden[df_dresden["route_type"].isin(valid_route_types)]

# -------------------------------
# 增加交通方式分类列
# -------------------------------
def classify_route(rt):
    if rt in [700, 704]:
        return "Bus"
    elif rt == 0:
        return "Tram"
    elif rt == 109:
        return "S-Bahn"
    elif rt in [101, 102, 103, 106]:
        return "ICE+IC"

df_dresden["transport_mode"] = df_dresden["route_type"].apply(classify_route)

# -------------------------------
# 输出结果
# -------------------------------
df_dresden.to_csv(output_file, index=False)

print(f"Filtered Dresden Hbf data saved to {output_file}")
print(f"Total events: {len(df_dresden)}")
print("Transport mode distribution:")
print(df_dresden["transport_mode"].value_counts())

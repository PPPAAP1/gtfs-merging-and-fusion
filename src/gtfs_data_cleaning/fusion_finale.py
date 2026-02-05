import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from statsmodels.nonparametric.smoothers_lowess import lowess


# Read Merged Static for single station
#YAML
merged_file = "H:\The Coding Environment\Railway Operation\gtfs-data-mandf\gtfs-merging-and-fusion\output\static_gtfs_Dresden_Hauptbahnhof.csv" #yaml
df = pd.read_csv(merged_file)

station_static_cols = ["trip_id","stop_id","stop_name","stop_lat","stop_lon","arrival_time","departure_time","service_id"]

for col in station_static_cols:
    if col not in df.columns:
        raise ValueError(f"Missing required column from static: {col}")
    

# Read merged Realtime for single station
#YAML
real_file = "H:\The Coding Environment\Railway Operation\gtfs-data-mandf\gtfs-merging-and-fusion\output\delay_Dresden_Hauptbahnhof.csv" #yaml
df_real = pd.read_csv(real_file)

station_realtime_cols = ["trip_id","stop_id","arrival_delay","departure_delay","fetch_timestamp","source_file","route_type","stop_name","stop_lat","stop_lon","arrival_time","departure_time","service_id","delay_min","dep_delay_min"]

for col in station_realtime_cols:
    if col not in df_real.columns:
        raise ValueError(f"Missing required column from real-time: {col}")
    

# somehow I need to format trip_id into strings
df["trip_id"] = df["trip_id"].astype(str)
df_real["trip_id"] = df_real["trip_id"].astype(str)

df["stop_id"] = df["stop_id"].astype(str)
df_real["stop_id"] = df_real["stop_id"].astype(str)

print("RT rows:", len(df_real))
print("Static rows:", len(df))

tmp = df_real.merge(df, on=["trip_id","stop_id"], how="left")
print(tmp.isna().sum())

# Merge static and realtime data on trip_id and stop_id
# merged_df = pd.merge(
#    df,
#    df_real,
#    on=["trip_id", "stop_id"],
#    how="left",
#    suffixes=("_scheduled", "_realtime")
#)

# Merge static and realtime data on  stop_id only
## merged_df = pd.merge(
#    df,
#    df_real,
#    on=["stop_id"],
#    how="left",
#    suffixes=("_scheduled", "_realtime")
#)

# Merge static and realtime data first,
merged_df = pd.merge(
        df,
        df_real,
        how="outer",
        on=["trip_id"],
        suffixes=("_scheduled", "_realtime")
        )

## I dont have the calendar date yet
if "scheduled_date" not in df.columns:
    df["scheduled_date"] = ""

final_columns = [
    "trip_id",
    "stop_id_scheduled",
    "stop_id_realtime",

    "scheduled_date",

    "route_type",

    "arrival_time_scheduled",
    "arrival_time_realtime",
    "departure_time_scheduled",
    "departure_time_realtime",
    "stop_name_scheduled",
    "stop_name_realtime",
    "stop_lat_scheduled",
    "stop_lat_realtime",
    "stop_lon_scheduled",
    "stop_lon_realtime",
    "service_id_scheduled",
    "service_id_realtime",

    "arrival_delay",
    "departure_delay",
    "delay_min",
    "dep_delay_min",
    "fetch_timestamp",
    "source_file"
]


    # Structrured from: A GTFS data acquisition and processing framework and its application to train delay prediction

# Cleaning

# 1. ALL DUPLICATES
merged_df = merged_df.drop_duplicates()

# 2. TRIP ID DUPLICATES
# merged_df = merged_df.drop_duplicates(subset=["trip_id", "arrival_delay", "departure_delay"])

# 2. Trip ID with same arrival and departure delay duplicates
merged_df = merged_df.drop_duplicates(subset=["trip_id", "arrival_delay", "departure_delay"])

# 2. STOP ID DUPLICATES
# merged_df = merged_df.drop_duplicates(subset=["stop_id", "arrival_delay", "departure_delay"])

# 3. Remove rows with no delay information at all
merged_df = merged_df.dropna(subset=["arrival_delay"], how="all")


final_columns = [c for c in final_columns if c in merged_df.columns]
df_final = merged_df[final_columns]
df_final.to_csv("final_merged_data_1204_test.csv", index=False)


print(f"Merged data saved to final_merged_data_1204_test.csv")
print(f"Total records in merged data: {len(df_final)}")

print("After cleaning:")
print("Rows:", len(merged_df))
print("Missing arrival_time_scheduled:", merged_df['arrival_time_scheduled'].isna().sum())
print("Missing delay info:", merged_df[['arrival_delay','departure_delay']].isna().all(axis=1).sum())

#DRAWING FIGURE

csv_file = "final_merged_data_1204_test.csv"
df_draw = pd.read_csv(csv_file)

y = df_draw["departure_delay"]
mean = y.mean()
std = y.std()

print(f"Mean departure delay: {mean}, STD: {std}")
plt.figure(figsize=(24, 6))
df_draw["fetch_timestamp"] = pd.to_datetime(df_draw["fetch_timestamp"], errors="coerce")
plt.scatter(df_draw["fetch_timestamp"], df_draw["departure_delay"], alpha=0.5, s=10)

color_map = {
    0: "lightgray", # tram, streetcar, light rail
    3: "green", # Bus
    106: "red", # RB and RE
    109: "blueviolet", #S-Bahn
    "unknown": "black"
}

df_draw["route_type_clean"] = df_draw["route_type"].apply(
    lambda v: v if v in [0, 3, 106, 109] else "unknown"
)

route_types = df_draw["route_type_clean"].unique()

for rt in route_types:
    subset = df_draw[df_draw["route_type_clean"] == rt]
    color = color_map.get(rt, "black")
    plt.scatter(
        subset["fetch_timestamp"],
        subset["departure_delay"],
        alpha=0.5,
        s=12,
        color=color,
        label=f"route_type={rt}")
    # --- LOESS 趋势线，仅对 0 和 3 ---
    if rt in [0, 3] and len(subset) > 5:
        # 转换时间为数值
        x = mdates.date2num(subset["fetch_timestamp"])
        y = subset["departure_delay"].values

        # frac 控制平滑程度，0.02~0.1 常用，可按数据量调
        loess_smoothed = lowess(y, x, frac=0.05, return_sorted=True)

        # 拆分 x/y
        x_smooth = mdates.num2date(loess_smoothed[:, 0])
        y_smooth = loess_smoothed[:, 1]

        # 绘制 LOESS 平滑趋势线
        plt.plot(
            x_smooth,
            y_smooth,
            color=color,
            linewidth=2.5,
            label=f"LOESS Trend (type {rt})"
        )

plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())

plt.xlabel("Fetch Timestamp")
plt.ylabel("departure Delay (seconds)")
plt.title("departure Delay Over Time")
plt.grid(True)

plt.axhline(mean, linestyle="--", label=f"Mean = {mean:.2f}")
plt.axhline(mean + std, color='grey', linestyle=":", label=f"Mean + STD = {mean+std:.2f}")
plt.axhline(mean - std, color='grey', linestyle=":", label=f"Mean - STD = {mean-std:.2f}")


plt.tight_layout()
plt.show()





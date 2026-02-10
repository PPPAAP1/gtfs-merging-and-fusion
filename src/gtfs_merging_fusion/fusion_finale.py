import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from statsmodels.nonparametric.smoothers_lowess import lowess
import yaml
from pathlib import Path


def merging_fusion():
    """
    Run merging and fusion on static and realtime GTFS data.
    Loads configuration from config.yaml and processes data accordingly.
    """
    # ================================
    # Load Configuration
    # ================================
    CONFIG_PATH = "config/config.yaml"

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"❌ Config file not found: {CONFIG_PATH}")
    except yaml.YAMLError as e:
        raise Exception(f"❌ YAML error in config: {e}")

    if "fusion" not in cfg:
        raise KeyError("❌ 'fusion' section not found in config.yaml")

    fusion_cfg = cfg["fusion"]

    # Read Merged Static for single station
    merged_file = fusion_cfg.get("static_gtfs_file")
    print(f"📂 Loading static GTFS from: {merged_file}")
    df = pd.read_csv(merged_file)

    station_static_cols = fusion_cfg.get("static_columns", [
        "trip_id", "stop_id", "stop_name", "stop_lat", "stop_lon",
        "arrival_time", "departure_time", "service_id"
    ])

    for col in station_static_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column from static: {col}")
        

    # Read merged Realtime for single station
    real_file = fusion_cfg.get("realtime_gtfs_file")
    print(f"📂 Loading realtime GTFS from: {real_file}")
    df_real = pd.read_csv(real_file)

    station_realtime_cols = fusion_cfg.get("realtime_columns", [
        "trip_id", "stop_id", "arrival_delay", "departure_delay", "fetch_timestamp",
        "source_file", "route_type", "stop_name", "stop_lat", "stop_lon",
        "arrival_time", "departure_time", "service_id", "delay_min", "dep_delay_min"
    ])

    for col in station_realtime_cols:
        if col not in df_real.columns:
            raise ValueError(f"Missing required column from real-time: {col}")
        

    # Format trip_id and stop_id into strings
    df["trip_id"] = df["trip_id"].astype(str)
    df_real["trip_id"] = df_real["trip_id"].astype(str)

    df["stop_id"] = df["stop_id"].astype(str)
    df_real["stop_id"] = df_real["stop_id"].astype(str)

    print("RT rows:", len(df_real))
    print("Static rows:", len(df))

    tmp = df_real.merge(df, on=["trip_id","stop_id"], how="left")
    print(tmp.isna().sum())

    # Merge static and realtime data on trip_id
    merged_df = pd.merge(
            df,
            df_real,
            how="outer",
            on=["trip_id"],
            suffixes=("_scheduled", "_realtime")
            )

    ## Add scheduled_date if missing
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

    # ================================
    # Data Cleaning
    # ================================
    # 1. Remove all duplicates
    merged_df = merged_df.drop_duplicates()

    # 2. Remove trip_id duplicates with same arrival/departure delays
    merged_df = merged_df.drop_duplicates(subset=["trip_id", "arrival_delay", "departure_delay"])

    # 3. Remove rows with no delay information
    merged_df = merged_df.dropna(subset=["arrival_delay"], how="all")

    # Select only available columns
    final_columns = [c for c in final_columns if c in merged_df.columns]
    df_final = merged_df[final_columns]
    
    # Save to CSV
    output_dir = Path(cfg.get("output_dir", "output/"))
    output_file = output_dir / "final_merged_data.csv"
    df_final.to_csv(output_file, index=False)
    print(f"✅ Merged data saved to {output_file}")
    print(f"📊 Total records in merged data: {len(df_final)}")

    print("\n📈 After cleaning:")
    print(f"Rows: {len(merged_df)}")
    print(f"Missing arrival_time_scheduled: {merged_df['arrival_time_scheduled'].isna().sum()}")
    print(f"Missing delay info: {merged_df[['arrival_delay','departure_delay']].isna().all(axis=1).sum()}")

    # ================================
    # Visualization: Departure Delay Trend
    # ================================
    print("\n📊 Generating departure delay trend visualization...")
    
    y = df_final["departure_delay"].dropna()
    mean = y.mean()
    std = y.std()

    print(f"Mean departure delay: {mean:.2f}s, STD: {std:.2f}s")

    plt.figure(figsize=(24, 6))
    df_final["fetch_timestamp"] = pd.to_datetime(df_final["fetch_timestamp"], errors="coerce")
    plt.scatter(df_final["fetch_timestamp"], df_final["departure_delay"], alpha=0.5, s=10)

    color_map = {
        0: "lightgray",    # tram, streetcar
        3: "green",        # Bus
        106: "red",        # RB and RE
        109: "blueviolet", # S-Bahn
        "unknown": "black"
    }

    df_final["route_type_clean"] = df_final["route_type"].apply(
        lambda v: v if v in [0, 3, 106, 109] else "unknown"
    )

    route_types = df_final["route_type_clean"].unique()

    for rt in route_types:
        subset = df_final[df_final["route_type_clean"] == rt]
        if subset.empty:
            continue
        color = color_map.get(rt, "black")
        plt.scatter(
            subset["fetch_timestamp"],
            subset["departure_delay"],
            alpha=0.5,
            s=12,
            color=color,
            label=f"route_type={rt}")
        
        # LOESS Trend Line
        if rt in [0, 3] and len(subset) > 5:
            x = mdates.date2num(subset["fetch_timestamp"])
            y_vals = subset["departure_delay"].values
            
            loess_smoothed = lowess(y_vals, x, frac=0.05, return_sorted=True)
            x_smooth = mdates.num2date(loess_smoothed[:, 0])
            y_smooth = loess_smoothed[:, 1]
            
            plt.plot(x_smooth, y_smooth, color=color, linewidth=2.5, 
                    label=f"LOESS Trend (type {rt})")

    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xlabel("Fetch Timestamp")
    plt.ylabel("Departure Delay (seconds)")
    plt.title("Departure Delay Over Time by Route Type")
    plt.grid(True)
    plt.axhline(mean, linestyle="--", label=f"Mean = {mean:.2f}s")
    plt.axhline(mean + std, color='grey', linestyle=":", label=f"Mean + STD = {mean+std:.2f}s")
    plt.axhline(mean - std, color='grey', linestyle=":", label=f"Mean - STD = {mean-std:.2f}s")
    plt.legend()
    plt.tight_layout()
    
    # Save plot
    plot_file = output_dir / "departure_delay_trend.png"
    plt.savefig(plot_file, dpi=150)
    print(f"✅ Saved trend plot to {plot_file}")
    plt.close()


if __name__ == "__main__":
    try:
        merging_fusion()
        print("\n✅ Merging and fusion completed successfully!")
    except Exception as e:
        print(f"\n❌ Error during merging: {e}")





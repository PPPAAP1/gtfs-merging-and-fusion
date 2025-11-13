import pandas as pd
from pathlib import Path
import glob
import subprocess
from read_static_gtfs import load_static_gtfs
from merge_gtfs import merge_data
from export_results import save_csv

# -------------------------
# 配置路径
# -------------------------
BASE_DIR = Path(r"H:\The Coding Environment\Railway Operation\gtfs-data-mandf\gtfs-merging-and-fusion")
STATIC_DIR = BASE_DIR / "data_static"
REALTIME_DIR = BASE_DIR / "data_realtime"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# -------------------------
# Step 1: Load Static GTFS, could it be done beforehand? 
# -------------------------
print("=== Step 1: Load Static GTFS ===")
static_df = load_static_gtfs(STATIC_DIR)
print(static_df.head())

# -------------------------
# Step 2: Load or Fetch Real-time GTFS CSV
# -------------------------
print("\n=== Step 2: Load Real-time GTFS CSV ===")
realtime_csv_files = sorted(glob.glob(str(REALTIME_DIR / "*.csv")))

if not realtime_csv_files:
    print("⚠️ 没有找到实时 CSV 文件，正在自动抓取...")
    subprocess.run(["python", str(BASE_DIR / "scripts" / "fetch_realtime_gtfs.py")], check=True)
    realtime_csv_files = sorted(glob.glob(str(REALTIME_DIR / "*.csv")))
    if not realtime_csv_files:
        raise FileNotFoundError("抓取失败，仍然没有 CSV 文件")

latest_csv = realtime_csv_files[-1]
rt_df = pd.read_csv(latest_csv, dtype=str)
print(f"Loaded real-time GTFS rows: {len(rt_df)} from {latest_csv}")

# -------------------------
# Step 3: Merge Static & Real-time
# -------------------------
print("\n=== Step 3: Merge Static & Real-time ===")
merged_df = merge_data(static_df, rt_df, chunk_size=1000000)
print(f"Merged DF rows: {len(merged_df)}")

# -------------------------
# Step 4: Export Results
# -------------------------
print("\n=== Step 4: Export Results ===")
# CSV 用 output_dir + filename
save_csv(merged_df, OUTPUT_DIR, "merged_gtfs.csv")
# save_xml(merged_df, OUTPUT_DIR, "merged_gtfs.xml")
# save_json(merged_df, OUTPUT_DIR, "merged_gtfs.json")

print("Alles fertig!")

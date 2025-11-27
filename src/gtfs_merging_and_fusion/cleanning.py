import pandas as pd
import glob
import os
import re

# -------------------------------
# 配置参数
# -------------------------------
# GTFS-RT CSV 文件夹路径：自动定位 `data_realtime` 下最近的 YYYY-MM-DD 子文件夹
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
realtime_dir = os.path.join(base_dir, "data_realtime")

csv_folder = None
if os.path.isdir(realtime_dir):
    # 列出所有子目录并筛选出符合日期格式的文件夹
    try:
        subdirs = [d for d in os.listdir(realtime_dir) if os.path.isdir(os.path.join(realtime_dir, d))]
    except Exception:
        subdirs = []

    date_dirs = sorted([d for d in subdirs if re.match(r"^\d{4}-\d{2}-\d{2}$", d)])
    if date_dirs:
        selected = date_dirs[-1]  # 选择最新的日期文件夹
        csv_folder = os.path.join(realtime_dir, selected)
    else:
        # 如果没有符合 YYYY-MM-DD 格式的子目录，尝试选择任意非隐藏子目录
        non_hidden = sorted([d for d in subdirs if not d.startswith('.')])
        if non_hidden:
            csv_folder = os.path.join(realtime_dir, non_hidden[-1])

if not csv_folder:
    # 回退到当前工作目录下的 `data_realtime`（如果存在）或者抛出错误
    fallback = os.path.join(os.getcwd(), "data_realtime")
    if os.path.isdir(fallback):
        csv_folder = fallback
    else:
        raise FileNotFoundError(f"Cannot locate data_realtime subfolder. Checked: {realtime_dir} and {fallback}")

# 输出文件路径
output_file = "gtfs_rt_cleaned.csv"

# 初步清洗参数
required_columns = ["trip_id", "stop_id", "arrival_delay", "fetch_timestamp"]
min_delay = -2    # 最小合理延迟（分钟）
max_delay = 240    # 最大合理延迟（分钟）

# 时间过滤：从所选文件夹名推断日期范围（如果文件夹名为 YYYY-MM-DD）
m = re.search(r"(\d{4}-\d{2}-\d{2})$", csv_folder)
if m:
    folder_date = m.group(1)
    start_date = pd.to_datetime(folder_date)
    end_date = pd.to_datetime(folder_date + " 23:59:59")
else:
    # 默认回退到今天的整天范围
    start_date = pd.to_datetime(pd.Timestamp.now().normalize())
    end_date = pd.to_datetime(pd.Timestamp.now().normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))

# 分块读取大小（文件数为单位，可根据内存调整）
chunk_size = 25  # 每次读取 25 个 CSV 文件

# -------------------------------
# 获取 CSV 文件列表
# -------------------------------
file_list = sorted(glob.glob(os.path.join(csv_folder, "*.csv")))

# -------------------------------
# 批量读取 + 分块处理
# -------------------------------
cleaned_chunks = []  # 保存每个分块清洗后的 DataFrame

for i in range(0, len(file_list), chunk_size):
    chunk_files = file_list[i:i+chunk_size]
    chunk_dfs = []
    
    for file in chunk_files:
        df_temp = pd.read_csv(file)
        
        # 只保留需要的列
        df_temp = df_temp[required_columns]
        
        # 删除缺失值
        df_temp = df_temp.dropna(subset=required_columns)
        
        # 删除异常 delay
        df_temp = df_temp[(df_temp["arrival_delay"] >= min_delay) & 
                          (df_temp["arrival_delay"] <= max_delay)]
        
        # 转换 fetch_timestamp 列为 datetime
        df_temp["fetch_timestamp"] = pd.to_datetime(df_temp["fetch_timestamp"])

        # 时间过滤
        df_temp = df_temp[(df_temp["fetch_timestamp"] >= start_date) & 
                  (df_temp["fetch_timestamp"] <= end_date)]
        
        chunk_dfs.append(df_temp)
    
    # 合并当前分块
    if chunk_dfs:
        chunk_combined = pd.concat(chunk_dfs, ignore_index=True)
        cleaned_chunks.append(chunk_combined)
        print(f"Processed files {i+1} ~ {i+len(chunk_files)}")
        
# -------------------------------
# 合并所有分块
# -------------------------------
if cleaned_chunks:
    df_all_cleaned = pd.concat(cleaned_chunks, ignore_index=True)
    
    # 去重（使用 fetch_timestamp）
    df_all_cleaned = df_all_cleaned.drop_duplicates(subset=["trip_id", "stop_id", "fetch_timestamp"])
    
    # 输出
    df_all_cleaned.to_csv(output_file, index=False)
    print(f"All cleaned data saved to {output_file}")
else:
    print("No valid data found in the selected files.")

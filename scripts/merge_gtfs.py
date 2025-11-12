import pandas as pd
from typing import Optional

def merge_data(static_df: pd.DataFrame, rt_df: pd.DataFrame, chunk_size: int = 1000000) -> pd.DataFrame:
    """
    分块 merge 静态 GTFS 与实时 GTFS 数据，减少内存占用。

    参数:
        static_df (pd.DataFrame): 静态 GTFS
        rt_df (pd.DataFrame): 实时 GTFS
        chunk_size (int): 每块处理行数，默认 1,000,000

    返回:
        pd.DataFrame: 合并后的结果
    """
     # 保留静态列
    static_df = static_df[['trip_id','stop_id','stop_name','arrival_time','departure_time','service_id']]
    
    # 保留实时列，但只取存在的列
    needed_cols = ['trip_id','stop_id','arrival_delay','departure_delay','status_arrival','status_departure','fetch_timestamp']
    existing_cols = [c for c in needed_cols if c in rt_df.columns]
    rt_df = rt_df[existing_cols]

    # 确保 key 为 str
    static_df['trip_id'] = static_df['trip_id'].astype(str)
    static_df['stop_id'] = static_df['stop_id'].astype(str)
    rt_df['trip_id'] = rt_df['trip_id'].astype(str)
    rt_df['stop_id'] = rt_df['stop_id'].astype(str)

    merged_chunks = []

    # 分块 merge
    for start in range(0, len(static_df), chunk_size):
        chunk = static_df.iloc[start:start+chunk_size]
        merged_chunk = chunk.merge(rt_df, on=['trip_id','stop_id'], how='left')
        merged_chunks.append(merged_chunk)

    # 合并所有块
    merged_df = pd.concat(merged_chunks, ignore_index=True)

    # 标记延迟
    merged_df['arrival_delay_flag'] = merged_df['arrival_delay'].apply(lambda x: 1 if pd.notnull(x) and x > 0 else 0)
    merged_df['departure_delay_flag'] = merged_df['departure_delay'].apply(lambda x: 1 if pd.notnull(x) and x > 0 else 0)

    return merged_df

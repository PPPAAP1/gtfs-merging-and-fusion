# chunked_import.py
import os
import pandas as pd
from sqlalchemy import create_engine

DB_USER = 'postgres'
DB_PASSWORD = 'Kamiljan0306'
DB_HOST = 'localhost'
DB_PORT = '5432'
DB_NAME = 'postgres'
GTFS_FOLDER = r'H:\The Coding Environment\Railway Operation\gtfs-data-mandf\gtfs-merging-and-fusion\data_static'
IF_EXISTS = 'append'  # 初次导入可先 'replace'，以后追加用 'append'
CHUNKSIZE = 200000    # 每次读入 200k 行，按内存调整

engine = create_engine(f'postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

gtfs_tables = {
    'stops.txt': 'stops',
    'routes.txt': 'routes',
    'trips.txt': 'trips',
    'stop_times.txt': 'stop_times',
    'calendar.txt': 'calendar',
    'calendar_dates.txt': 'calendar_dates',
    'shapes.txt': 'shapes',
    'feed_info.txt': 'feed_info',
    'agency.txt': 'agency'
}

for file_name, table_name in gtfs_tables.items():
    file_path = os.path.join(GTFS_FOLDER, file_name)
    if not os.path.exists(file_path):
        print(f"[跳过] {file_name} 不存在")
        continue
    print(f"[开始导入] {file_name} -> {table_name}")

    first_chunk = True
    for chunk in pd.read_csv(file_path, chunksize=CHUNKSIZE, dtype=str, low_memory=True, encoding='utf-8'):
        # 可在这里做列筛选或重命名，例如：
        # chunk = chunk[['stop_id','stop_name','stop_lat','stop_lon']]
        # chunk.columns = chunk.columns.str.lower()
        chunk.to_sql(table_name, engine, if_exists=IF_EXISTS if first_chunk else 'append', index=False, method='multi', chunksize=10000)
        first_chunk = False
        print(f"  写入一个 chunk, 行数={len(chunk)}")
    print(f"[完成] {file_name}")

print("全部导入完成 ✅")

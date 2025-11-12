"""
export_results.py
-----------------
统一管理 GTFS 数据导出：CSV、XML、JSON。
适合 merge_gtfs.py / fetch_realtime_gtfs.py 调用。
"""

from datetime import datetime
from pathlib import Path
import pandas as pd
from lxml import etree
import json

# ---------- CSV ----------
def save_csv(df: pd.DataFrame, output_dir: Path, filename: str):
    """
    保存 DataFrame 为 CSV，自动创建目录 + 时间戳防覆盖
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # 添加时间戳
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # 拆分文件名和扩展名
    stem, ext = filename.rsplit('.', 1)
    filename_with_time = f"{stem}_{timestamp}.{ext}"

    file_path = output_dir / filename_with_time
    df.to_csv(file_path, index=False, encoding='utf-8-sig')

    print(f"✅ Saved CSV: {file_path.name}")
    return file_path

# ---------- XML ----------
# def save_xml(df: pd.DataFrame, output_dir: Path, filename: str):
    """
    保存 DataFrame 为 XML，每个 trip 包含多个 stop 节点
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / filename

    root = etree.Element("GTFS_Merged")
    for trip_id, trip_group in df.groupby("trip_id"):
        trip_el = etree.SubElement(root, "trip", id=trip_id)
        for _, row in trip_group.iterrows():
            stop_el = etree.SubElement(trip_el, "stop", id=row['stop_id'])
            etree.SubElement(stop_el, "stop_name").text = str(row.get('stop_name', ''))
            etree.SubElement(stop_el, "scheduled_arrival").text = str(row.get('scheduled_arrival', ''))
            etree.SubElement(stop_el, "scheduled_departure").text = str(row.get('scheduled_departure', ''))
            etree.SubElement(stop_el, "arrival_delay").text = str(row.get('arrival_delay', ''))
            etree.SubElement(stop_el, "departure_delay").text = str(row.get('departure_delay', ''))
            etree.SubElement(stop_el, "status_arrival").text = str(row.get('status_arrival', ''))
            etree.SubElement(stop_el, "status_departure").text = str(row.get('status_departure', ''))
            etree.SubElement(stop_el, "fetch_timestamp").text = str(row.get('fetch_timestamp', ''))

    tree = etree.ElementTree(root)
    tree.write(str(file_path), pretty_print=True, encoding='utf-8', xml_declaration=True)
    print(f"✅ Saved XML: {file_path.name}")
    return file_path

# ---------- JSON ----------
# def save_json(data, output_dir: Path, filename: str):
    """
    保存任意数据为 JSON
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / filename
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved JSON: {file_path.name}")
    return file_path

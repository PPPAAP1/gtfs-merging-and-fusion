"""
analyze_routes.py
-----------------
分析 GTFS routes.txt + agency.txt，
自动推测线路所属交通系统类别（如 Regional Rail / Long-distance Rail / Bus / Tram 等），
并导出两个结果 CSV：
  1. routes_classified_all.csv  → 所有线路
  2. routes_classified_rail.csv → 仅保留铁路相关 (RB/RE & ICE/IC)
"""

import pandas as pd
import re
from pathlib import Path
from datetime import datetime


def infer_category(row):
    """通过关键词自动推测交通系统类别"""
    text = " ".join([
        str(row.get(c, "")).lower()
        for c in ["route_short_name", "route_long_name", "agency_name"]
    ])

    for pattern, label in classification_rules:
        if re.search(pattern.lower(), text):
            return label

    # 如果 route_id 明显含有 "bus" 等关键词，也补充判断
    route_id = str(row.get("route_id", "")).lower()
    if "bus" in route_id:
        return "Bus"

    return "Unknown"


# ---------- 分类规则 ----------
classification_rules = [
    (r"fernverkehr|ice|ic|flixtrain", "Long-distance Rail, ICE/IC"),
    (r"db regio|vias|abellio|metronom|erixx|brb|nordwestbahn|rb|re", "Regional Rail, RB/RE"),
    (r"s-bahn|s ?\d+", "Urban Rail (S-Bahn)"),
    (r"u-bahn|u ?\d+", "Metro"),
    (r"tram|straßenbahn|lokalbahn", "Tram / Light Rail"),
    (r"bus|expressbus", "Bus"),
]


def analyze_routes(gtfs_dir: Path, output_dir: Path):
    """核心分析函数"""
    routes_path = gtfs_dir / "routes.txt"
    agency_path = gtfs_dir / "agency.txt"

    if not routes_path.exists():
        raise FileNotFoundError(f"❌ Missing routes.txt at {routes_path}")
    if not agency_path.exists():
        raise FileNotFoundError(f"❌ Missing agency.txt at {agency_path}")

    print(f"🔹 Loading routes from: {routes_path}")
    routes = pd.read_csv(routes_path, dtype=str)
    agency = pd.read_csv(agency_path, dtype=str)

    # 合并 agency 信息（如果有 agency_id）
    if "agency_id" in routes.columns:
        routes = routes.merge(agency, on="agency_id", how="left")
    else:
        routes["agency_name"] = agency["agency_name"].iloc[0] if "agency_name" in agency.columns else "Unknown"

    # 推测系统类别
    print("🔍 Inferring transport system categories...")
    routes["system_category"] = routes.apply(infer_category, axis=1)

    # 输出结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_out = output_dir / f"routes_classified_all_{timestamp}.csv"
    rail_out = output_dir / f"routes_classified_rail_{timestamp}.csv"

    routes.to_csv(all_out, index=False, encoding="utf-8-sig")

    # 仅保留铁路类
    rail_df = routes[routes["system_category"].isin(["Long-distance Rail, ICE/IC", "Regional Rail, RB/RE"])]
    rail_df.to_csv(rail_out, index=False, encoding="utf-8-sig")

    print(f"✅ Saved all routes → {all_out.name} ({len(routes)} rows)")
    print(f"✅ Saved only rail  → {rail_out.name} ({len(rail_df)} rows)")

    # 简要统计
    print("\n📊 Category Summary:")
    print(routes["system_category"].value_counts())

    return routes, rail_df


# ---------- 独立测试 ----------
if __name__ == "__main__":
    base_dir = Path(r"H:\The Coding Environment\Railway Operation\gtfs-data-mandf")
    static_dir = base_dir / "data_static"
    output_dir = base_dir / "outputs"

    analyze_routes(static_dir, output_dir)

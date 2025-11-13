"""
fetch_realtime_gtfs.py
----------------------
每 12 分钟抓取一次 GTFS-RT TripUpdates feed，保存 .pb/.json/.csv。
自动记录时间轴，统计延迟记录总数。
每天结束时生成延迟趋势图。

输出：
- data_realtime/tripupdates_*.pb
- data_realtime/DELFI_GTFS_TripUpdates_*.csv
- data_realtime/timeline.csv
- data_realtime/delay_trend.png
"""

import os
import time
import json
import tempfile
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
from google.transit import gtfs_realtime_pb2
import matplotlib.pyplot as plt

# -------------------------
# 配置
# -------------------------
P12_FILE = r"H:\The Coding Environment\Railway Operation\gtfs-data-mandf\gtfs-merging-and-fusion\certificate.p12"
P12_PASSWORD = b"T34hM61D@WAh"
PULL_URL = "https://mobilithek.info:8443/mobilithek/api/v1.0/container/subscription?subscriptionID=912322615062511616"

OUTPUT_DIR = Path(r"H:\The Coding Environment\Railway Operation\gtfs-data-mandf\gtfs-merging-and-fusion\data_realtime")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TIMELINE_FILE = OUTPUT_DIR / "timeline.csv"

# 初始化时间轴
timeline_log = []

# -------------------------
# 抓取函数
# -------------------------
def fetch_gtfs_rt_once():
    """执行一次 GTFS-RT 抓取并保存"""
    print("=" * 60)
    print(f"🚀 Fetching GTFS-RT feed at {datetime.now().isoformat(timespec='seconds')}")

    # 1️⃣ 读取证书
    with open(P12_FILE, "rb") as f:
        p12_data = f.read()
    private_key, certificate, _ = pkcs12.load_key_and_certificates(
        p12_data, P12_PASSWORD, backend=default_backend()
    )
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )

    # 2️⃣ 写 PEM 临时文件
    with tempfile.NamedTemporaryFile(delete=False) as cert_file:
        cert_file.write(cert_pem)
        cert_path = cert_file.name
    with tempfile.NamedTemporaryFile(delete=False) as key_file:
        key_file.write(key_pem)
        key_path = key_file.name

    try:
        # 3️⃣ 下载 GTFS-RT 数据
        response = requests.get(PULL_URL, cert=(cert_path, key_path), timeout=30)
        if response.status_code != 200:
            print(f"❌ 下载失败: HTTP {response.status_code}")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pb_file_path = OUTPUT_DIR / f"tripupdates_{timestamp}.pb"
        pb_file_path.write_bytes(response.content)
        print(f"✅ Saved raw GTFS-RT feed to {pb_file_path.name}")

        # 4️⃣ 解析 protobuf
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        records = []
        fetch_time = datetime.now().isoformat(timespec='seconds')
        arrival_delays = 0
        departure_delays = 0

        for entity in feed.entity:
            if not entity.HasField('trip_update'):
                continue
            trip_id = entity.trip_update.trip.trip_id
            for stu in entity.trip_update.stop_time_update:
                stop_id = stu.stop_id
                arrival_delay = stu.arrival.delay if stu.HasField("arrival") and stu.arrival.HasField("delay") else None
                departure_delay = stu.departure.delay if stu.HasField("departure") and stu.departure.HasField("delay") else None

                if arrival_delay and arrival_delay > 0:
                    arrival_delays += 1
                if departure_delay and departure_delay > 0:
                    departure_delays += 1

                records.append({
                    "trip_id": trip_id,
                    "stop_id": stop_id,
                    "arrival_delay": arrival_delay,
                    "departure_delay": departure_delay,
                    "fetch_timestamp": fetch_time
                })

        # 5️⃣ 保存 JSON + CSV
        json_file_path = OUTPUT_DIR / f"DELFI_GTFS_TripUpdates_{timestamp}.json"
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        df = pd.DataFrame(records)
        csv_file_path = OUTPUT_DIR / f"DELFI_GTFS_TripUpdates_{timestamp}.csv"
        df.to_csv(csv_file_path, index=False, encoding="utf-8-sig")

        total_delays = arrival_delays + departure_delays
        print(f"📊 延迟记录统计: 到达延迟 {arrival_delays}, 出发延迟 {departure_delays}, 总计 {total_delays}")
        print(f"✅ Saved JSON/CSV ({len(records)} records)")

        # 6️⃣ 记录时间轴
        timeline_log.append({
            "timestamp": fetch_time,
            "records_total": len(records),
            "arrival_delays": arrival_delays,
            "departure_delays": departure_delays,
            "total_delay_records": total_delays
        })

        # 7️⃣ 追加保存 timeline.csv
        pd.DataFrame(timeline_log).to_csv(TIMELINE_FILE, index=False, encoding="utf-8-sig")

    except Exception as e:
        print(f"⚠️ Error during fetch: {e}")
    finally:
        os.remove(cert_path)
        os.remove(key_path)

# -------------------------
# 绘制趋势图
# -------------------------
def plot_delay_trend():
    """绘制延迟记录趋势图"""
    if not TIMELINE_FILE.exists():
        print("❌ 没有 timeline.csv，无法绘图。")
        return

    df = pd.read_csv(TIMELINE_FILE)
    if df.empty:
        print("❌ timeline.csv 是空的。")
        return

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    plt.figure(figsize=(12, 6))
    plt.plot(df['timestamp'], df['total_delay_records'], marker='o', linestyle='-')
    plt.title("GTFS-RT 延迟记录趋势（每12分钟）")
    plt.xlabel("时间")
    plt.ylabel("延迟记录总数")
    plt.grid(True)
    plt.tight_layout()

    plot_path = OUTPUT_DIR / "delay_trend.png"
    plt.savefig(plot_path, dpi=150)
    print(f"📈 延迟趋势图已保存到 {plot_path.name}")

# -------------------------
# 主循环
# -------------------------
if __name__ == "__main__":
    print("🚆 启动 GTFS-RT 抓取任务（每 12 分钟一次，按 Ctrl+C 终止）")
    try:
        while True:
            fetch_gtfs_rt_once()
            print("⏳ 等待 12 分钟...")
            time.sleep(12 * 60)
    except KeyboardInterrupt:
        print("\n🛑 手动中断抓取任务，正在绘制趋势图...")
        plot_delay_trend()
        print("✅ Alles fertig!")

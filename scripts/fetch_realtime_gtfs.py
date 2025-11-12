"""
fetch_realtime_gtfs.py
----------------------
抓取 GTFS-RT (TripUpdates) 数据流，打时间戳，保存原始文件 + CSV。
输出列：
    trip_id | stop_id | arrival_delay | departure_delay | fetch_timestamp
"""

import requests
import tempfile
import os
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
from google.transit import gtfs_realtime_pb2
import pandas as pd
from pathlib import Path
from datetime import datetime

# -------------------------
# 配置
# -------------------------
P12_FILE = r"H:\The Coding Environment\Railway Operation\gtfs-data-mandf\certificate.p12"
P12_PASSWORD = b"T34hM61D@WAh"
PULL_URL = "https://mobilithek.info:8443/mobilithek/api/v1.0/container/subscription?subscriptionID=912322615062511616"

# 输出目录
OUTPUT_DIR = Path(r"H:\The Coding Environment\Railway Operation\gtfs-data-mandf\data_realtime")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------
# 1. 从 p12 文件提取证书和私钥
# -------------------------
with open(P12_FILE, "rb") as f:
    p12_data = f.read()

private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
    p12_data, P12_PASSWORD, backend=default_backend()
)

cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
key_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption()
)

# -------------------------
# 2. 写临时 PEM 文件
# -------------------------
with tempfile.NamedTemporaryFile(delete=False) as cert_file:
    cert_file.write(cert_pem)
    cert_path = cert_file.name

with tempfile.NamedTemporaryFile(delete=False) as key_file:
    key_file.write(key_pem)
    key_path = key_file.name

# -------------------------
# 3. 请求数据
# -------------------------
response = requests.get(PULL_URL, cert=(cert_path, key_path))
if response.status_code != 200:
    raise Exception(f"下载失败: {response.status_code}")

# -------------------------
# 4. 保存原始 .pb 文件
# -------------------------
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
pb_file_path = OUTPUT_DIR / f"tripupdates_{timestamp}.pb"
pb_file_path.write_bytes(response.content)
print(f"✅ Saved raw GTFS-RT feed to {pb_file_path.name}")

# -------------------------
# 5. 解析数据
# -------------------------
try:
    parsed_data = response.json()
    DATA_TYPE = "json"
except Exception:
    try:
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        # Trip Updates Analysis
        records = []
        fetch_time = datetime.now().isoformat(timespec='seconds')

        for entity in feed.entity:
            if not entity.HasField('trip_update'):
                continue
            trip_id = entity.trip_update.trip.trip_id
            for stu in entity.trip_update.stop_time_update:
                stop_id = stu.stop_id
                arrival_delay = stu.arrival.delay if stu.HasField("arrival") and stu.arrival.HasField("delay") else None
                departure_delay = stu.departure.delay if stu.HasField("departure") and stu.departure.HasField("delay") else None
                records.append({
                    "trip_id": trip_id,
                    "stop_id": stop_id,
                    "arrival_delay": arrival_delay,
                    "departure_delay": departure_delay,
                    "fetch_timestamp": fetch_time
                })

        parsed_data = records
        DATA_TYPE = "pb"

    except Exception:
        parsed_data = response.text
        DATA_TYPE = "text"

print(f"Detected DATA_TYPE: {DATA_TYPE}")

# -------------------------
# 6. 保存 JSON
# -------------------------
json_file_path = OUTPUT_DIR / f"DELFI_GTFS_TripUpdates_{timestamp}.json"
with open(json_file_path, "w", encoding="utf-8") as f:
    json.dump(parsed_data, f, ensure_ascii=False, indent=2)
print(f"✅ Saved JSON to {json_file_path.name}")

# -------------------------
# 7. 保存 CSV（仅 Protobuf 类型）
# -------------------------
if DATA_TYPE == "pb":
    df = pd.DataFrame(parsed_data)
    csv_file_path = OUTPUT_DIR / f"DELFI_GTFS_TripUpdates_{timestamp}.csv"
    df.to_csv(csv_file_path, index=False, encoding="utf-8-sig")
    print(f"✅ Saved CSV to {csv_file_path.name}")
    print(df.head())

# -------------------------
# 8. 清理临时文件
# -------------------------
os.remove(cert_path)
os.remove(key_path)

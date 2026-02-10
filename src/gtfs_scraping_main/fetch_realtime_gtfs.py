import os
import time
import json
import tempfile
import requests
import pandas as pd
import yaml
from pathlib import Path
from datetime import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
from google.transit import gtfs_realtime_pb2
import matplotlib.pyplot as plt

"""
fetch_realtime_gtfs.py

The script fetches GTFS-RT trip updates using a .p12 certificate you get from your administrator,
and parses them into JSON and CSV formats.
It also maintains a timeline of delay records and generates a trend plot upon manual stop.

This will be useful if you don't have GTFS-RT Trip Update Data.
Please follow the instructions in README.md to set up your .p12 file and config.yaml correctly.
"""


# -------------------------
# Load Configuration
# -------------------------
CONFIG_PATH = "config/config.yaml"

try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
except FileNotFoundError:
    raise FileNotFoundError(f"❌ Check config file, config/config.yaml: {CONFIG_PATH}")
except yaml.YAMLError as e:
    raise Exception(f"❌ YAML error, check config/config.yaml: {e}")

if "realtime" not in cfg:
    raise KeyError("❌Check 'realtime', config/config.yaml")

rt_cfg = cfg["realtime"]

P12_FILE = rt_cfg.get("p12_file")
P12_PASSWORD = rt_cfg.get("p12_password", "").encode("utf-8")
PULL_URL = rt_cfg.get("pull_url")
OUTPUT_DIR = Path(rt_cfg.get("output_rt_dir", "data_realtime"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FETCH_INTERVAL_MINUTES = rt_cfg.get("fetch_interval_minutes", 12)
FETCH_INTERVAL_SECONDS = FETCH_INTERVAL_MINUTES * 60
PRINT_INTERVAL = 1  # Print countdown every second

TIMELINE_FILE = OUTPUT_DIR / "timeline.csv"
timeline_log = []

# --------------------------------------
# Fetching GTFS-RT
# --------------------------------------
def fetch_gtfs_rt_once():
    print("=" * 60)
    print(f"Fetching GTFS-RT feed at {datetime.now().isoformat(timespec='seconds')}")

    # Certificate and key extraction(GPT)
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

    # Write PEM temporary files
    with tempfile.NamedTemporaryFile(delete=False) as cert_file:
        cert_file.write(cert_pem)
        cert_path = cert_file.name

    with tempfile.NamedTemporaryFile(delete=False) as key_file:
        key_file.write(key_pem)
        key_path = key_file.name

    try:
        # Download GTFS-RT feed (GPT)
        response = requests.get(PULL_URL, cert=(cert_path, key_path), timeout=30)
        if response.status_code != 200:
            print(f"❌ Download Failed: HTTP {response.status_code}")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save raw .pb file
        pb_file_path = OUTPUT_DIR / f"tripupdates_{timestamp}.pb"
        pb_file_path.write_bytes(response.content)
        print(f"✅ Saved raw GTFS-RT feed to {pb_file_path.name}")

        # Parse protobuf
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

        # JSON
        json_file_path = OUTPUT_DIR / f"DELFI_GTFS_TripUpdates_{timestamp}.json"
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        # Save CSV
        csv_file_path = OUTPUT_DIR / f"DELFI_GTFS_TripUpdates_{timestamp}.csv"
        df = pd.DataFrame(records)
        df.to_csv(csv_file_path, index=False, encoding="utf-8-sig")  # Avoid Excel garbled text


        total_delays = arrival_delays + departure_delays
        print(f"📊 Delay minutes trend: Arrival {arrival_delays} minutes, Departure {departure_delays} minutes, Total {total_delays} minutes")
        print(f"✅ Saved JSON/CSV ({len(records)} records)")

        # Write to timeline.csv
        timeline_log.append({
            "timestamp": fetch_time,
            "records_total": len(records),
            "arrival_delays": arrival_delays,
            "departure_delays": departure_delays,
            "total_delay_records": total_delays
        })
        pd.DataFrame(timeline_log).to_csv(TIMELINE_FILE, index=False, encoding="utf-8-sig")

    except Exception as e:
        print(f"⚠️ Error during fetch: {e}")

    finally:
        os.remove(cert_path)
        os.remove(key_path)


# --------------------------------------
# Trend Plot
# --------------------------------------
def plot_delay_trend():
    if not TIMELINE_FILE.exists():
        print("❌ timeline.csv does not exist")
        return

    df = pd.read_csv(TIMELINE_FILE)
    if df.empty:
        print("❌ timeline.csv is empty")
        return

    df['timestamp'] = pd.to_datetime(df['timestamp'])

    plt.figure(figsize=(12, 6))
    plt.plot(df['timestamp'], df['total_delay_records'], marker='o')
    plt.title("GTFS-RT Delay Frequency Trend")
    plt.xlabel("Time")
    plt.ylabel("Number of Delay Records")
    plt.grid(True)
    plt.tight_layout()

    plot_path = OUTPUT_DIR / "delay_trend.png"
    plt.savefig(plot_path, dpi=150)
    print(f"📈 Saved trend plot: {plot_path.name}")

# --------------------------------------
# Main Program
# --------------------------------------
def start_fetch_loop():
    """Start the continuous GTFS-RT fetch loop"""
    print(f"🚆 GTFS-RT Fetch Task Started (Every {FETCH_INTERVAL_MINUTES} Minutes)")
    try:
        while True:
            fetch_gtfs_rt_once()
            remaining = FETCH_INTERVAL_SECONDS
            while remaining > 0:
                print(f"⏳ Next fetch countdown: {remaining} seconds", end="\r", flush=True)
                print(f"Press Ctrl+C to stop and generate trend plot...", end="\r", flush=True)
                sleep_time = min(PRINT_INTERVAL, remaining)
                time.sleep(sleep_time)
                remaining -= sleep_time
            print()
    except KeyboardInterrupt:
        print("\n🛑 Manual stop, generating trend plot...")
        plot_delay_trend()
        print("✅ Done!")

if __name__ == "__main__":
    start_fetch_loop()
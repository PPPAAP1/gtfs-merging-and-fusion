"""
gtfs_rt_fetch.py

Helpers for performing a single live GTFS-RT TripUpdates fetch using a
.p12 client certificate, as configured in config/config.yaml under the
'realtime' section. Used by pages/2_GTFS-RT_Live_Fetch.py.

This mirrors the fetch/parse logic in
src/gtfs_scraping_main/fetch_realtime_gtfs.py, but as importable functions
(no module-level config loading or infinite loop) so it can be called
on-demand from Streamlit.
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import yaml
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from google.transit import gtfs_realtime_pb2

RT_RECORD_COLUMNS = ["trip_id", "stop_id", "arrival_delay", "departure_delay", "fetch_timestamp"]


def load_realtime_config(config_path: str = "config/config.yaml") -> dict:
    """Load and return the 'realtime' section of config.yaml."""
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if "realtime" not in cfg:
        raise KeyError(f"'realtime' section not found in {config_path}")
    return cfg["realtime"]


def fetch_feed_bytes(p12_file: str, p12_password: str, pull_url: str, timeout: int = 30) -> bytes:
    """
    Download the raw GTFS-RT FeedMessage protobuf using a .p12 client certificate.
    Returns the raw response bytes. Raises FileNotFoundError / requests.HTTPError on failure.
    """
    with open(p12_file, "rb") as f:
        p12_data = f.read()

    private_key, certificate, _ = pkcs12.load_key_and_certificates(
        p12_data, p12_password.encode("utf-8"), backend=default_backend()
    )

    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    with tempfile.NamedTemporaryFile(delete=False) as cert_file:
        cert_file.write(cert_pem)
        cert_path = cert_file.name
    with tempfile.NamedTemporaryFile(delete=False) as key_file:
        key_file.write(key_pem)
        key_path = key_file.name

    try:
        response = requests.get(pull_url, cert=(cert_path, key_path), timeout=timeout)
        response.raise_for_status()
        return response.content
    finally:
        os.remove(cert_path)
        os.remove(key_path)


def parse_feed(raw_bytes: bytes, fetch_time: Optional[datetime] = None) -> pd.DataFrame:
    """
    Parse a GTFS-RT FeedMessage protobuf into a flat DataFrame with columns
    RT_RECORD_COLUMNS — one row per (trip_id, stop_id) stop_time_update.
    """
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(raw_bytes)

    fetch_time = fetch_time or datetime.now()
    fetch_time_str = fetch_time.isoformat(timespec="seconds")

    records = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        trip_id = entity.trip_update.trip.trip_id
        for stu in entity.trip_update.stop_time_update:
            arrival_delay = (
                stu.arrival.delay if stu.HasField("arrival") and stu.arrival.HasField("delay") else None
            )
            departure_delay = (
                stu.departure.delay if stu.HasField("departure") and stu.departure.HasField("delay") else None
            )
            records.append({
                "trip_id": trip_id,
                "stop_id": stu.stop_id,
                "arrival_delay": arrival_delay,
                "departure_delay": departure_delay,
                "fetch_timestamp": fetch_time_str,
            })

    return pd.DataFrame(records, columns=RT_RECORD_COLUMNS)


def save_fetch(raw_bytes: bytes, df: pd.DataFrame, output_dir: Path, fetch_time: datetime) -> dict:
    """
    Save a fetch in the same layout used by fetch_realtime_gtfs.py:
    output_dir/<YYYY-MM-DD>/{tripupdates_<ts>.pb, DELFI_GTFS_TripUpdates_<ts>.json/.csv}
    so the fetch is picked up by the GTFS-RT Explorer (Tab 1) like any
    background-loop fetch. Returns the written file paths.
    """
    date_dir = output_dir / fetch_time.strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    timestamp = fetch_time.strftime("%Y%m%d_%H%M%S")

    pb_path = date_dir / f"tripupdates_{timestamp}.pb"
    json_path = date_dir / f"DELFI_GTFS_TripUpdates_{timestamp}.json"
    csv_path = date_dir / f"DELFI_GTFS_TripUpdates_{timestamp}.csv"

    pb_path.write_bytes(raw_bytes)
    df.to_json(json_path, orient="records", indent=2, force_ascii=False)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    return {"pb": pb_path, "json": json_path, "csv": csv_path}

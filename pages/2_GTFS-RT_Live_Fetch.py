"""
GTFS-RT Live Fetch — Streamlit page
Run with:  streamlit run GTFS_Static_Explorer.py   (then open this page from the sidebar)
"""

import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from src.gtfs_rt_fetch import fetch_feed_bytes, load_realtime_config, parse_feed, save_fetch
from src.gtfs_rt_loader import join_with_static

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(page_title="GTFS-RT Live Fetch", page_icon="🛰️", layout="wide")

st.title("🛰️ GTFS-RT Live Fetch")
st.caption("Fetch the current GTFS-RT feed now and filter it down to the trips you care about")

st.markdown(
    """<style>
    .stDataFrame > div { overflow-x: auto !important; }
    </style>""",
    unsafe_allow_html=True,
)

# ─── Step 1: Static reference (defines what to keep) ──────────────────────────

st.header("Step 1 — Static reference (optional)")
st.caption(
    "Upload a CSV exported from the GTFS Explorer (Step 3), with original "
    "'trip_id' / 'stop_id' columns. The fetched feed will be filtered down to "
    "these IDs, and joined to add stop_name / route_type for display. "
    "If you skip this, the full live feed is shown unfiltered."
)

static_file = st.file_uploader("Static reference CSV", type=["csv"], key="live_static_upload")
static_df = None
trip_id_filter = None
stop_id_filter = None
join_on = ["trip_id", "stop_id"]

if static_file is not None:
    try:
        static_df = pd.read_csv(static_file)
        if "trip_id" not in static_df.columns or "stop_id" not in static_df.columns:
            st.error("Uploaded CSV must contain both 'trip_id' and 'stop_id' columns.")
            static_df = None
        else:
            trip_id_filter = set(static_df["trip_id"].astype(str))
            stop_id_filter = set(static_df["stop_id"].astype(str))

            match_mode = st.radio(
                "Match static reference by",
                ["trip_id + stop_id (exact)", "stop_id only"],
                horizontal=True,
                help=(
                    "Some GTFS-RT feeds use trip_id values (e.g. VDV 'Globaler Code' "
                    "composed identifiers) that don't match the static GTFS trip_id. "
                    "If 'trip_id + stop_id' gives no matches, switch to 'stop_id only' — "
                    "stop IDs (DHID) are usually stable across static and RT feeds."
                ),
            )
            if match_mode == "stop_id only":
                join_on = ["stop_id"]

            st.caption(
                f"{len(trip_id_filter):,} trip ID(s) and {len(stop_id_filter):,} stop ID(s) "
                "from the reference will be used to filter the live feed."
            )
    except Exception as exc:
        st.error(f"Could not read CSV: {exc}")

st.markdown("---")

# ─── Step 2: Connection status ────────────────────────────────────────────────

st.header("Step 2 — Connection")

try:
    rt_cfg = load_realtime_config()
    p12_file = rt_cfg.get("p12_file", "")
    p12_password = rt_cfg.get("p12_password", "")
    pull_url = rt_cfg.get("pull_url", "")
    output_rt_dir = Path(rt_cfg.get("output_rt_dir", "data/raw/rt/"))

    cert_ok = bool(p12_file) and Path(p12_file).is_file()
    config_ok = cert_ok and bool(p12_password) and bool(pull_url)

    col_a, col_b = st.columns(2)
    with col_a:
        st.write("Certificate file:", "✅ found" if cert_ok else "❌ not found")
        st.caption(p12_file or "(not set)")
    with col_b:
        st.write("Pull URL:", "✅ configured" if pull_url else "❌ not set")
        st.caption(pull_url or "(not set)")

    if not config_ok:
        st.error(
            "Realtime fetch is not fully configured — check the 'realtime' section "
            "in config/config.yaml (p12_file, p12_password, pull_url)."
        )
except (FileNotFoundError, KeyError) as exc:
    st.error(f"Could not load realtime config: {exc}")
    config_ok = False
    output_rt_dir = Path("data/raw/rt/")

st.markdown("---")

# ─── Step 3: Fetch now ────────────────────────────────────────────────────────

st.header("Step 3 — Fetch now")

save_result = st.checkbox(
    "Save each fetch to the RT data folder (so it shows up in the GTFS-RT Explorer)",
    value=True,
)


def _do_fetch(save: bool) -> dict:
    """
    Fetch the live feed once, apply the static-reference filter/join, and
    update session_state with the latest result. Returns a summary dict
    (also used for the continuous-fetch log).
    """
    fetch_time = datetime.now()
    try:
        raw_bytes = fetch_feed_bytes(p12_file, p12_password, pull_url)
        raw_df = parse_feed(raw_bytes, fetch_time=fetch_time)
    except Exception as exc:
        return {"time": fetch_time, "records": 0, "matched": 0, "error": str(exc), "csv_path": None}

    csv_path = None
    if save:
        paths = save_fetch(raw_bytes, raw_df, output_rt_dir, fetch_time)
        csv_path = paths["csv"]

    working_df = raw_df
    if static_df is not None:
        if join_on == ["stop_id"]:
            mask = working_df["stop_id"].astype(str).isin(stop_id_filter)
        else:
            mask = (
                working_df["trip_id"].astype(str).isin(trip_id_filter)
                & working_df["stop_id"].astype(str).isin(stop_id_filter)
            )
        working_df = working_df[mask]
        working_df = join_with_static(working_df, static_df, on=join_on)

    st.session_state["live_fetch_result"] = working_df
    st.session_state["live_fetch_time"] = fetch_time
    st.session_state["live_fetch_raw"] = raw_df
    st.session_state["live_fetch_trip_filter"] = trip_id_filter
    st.session_state["live_fetch_stop_filter"] = stop_id_filter

    return {
        "time": fetch_time,
        "records": len(raw_df),
        "matched": len(working_df),
        "error": None,
        "csv_path": csv_path,
    }


is_continuous = st.session_state.get("continuous_running", False)

if st.button("📡 Fetch live data now", disabled=not config_ok or is_continuous):
    with st.spinner("Connecting and downloading the live GTFS-RT feed..."):
        summary = _do_fetch(save_result)

    if summary["error"]:
        st.error(f"❌ Fetch failed: {summary['error']}")
    else:
        st.success(
            f"✅ Fetched {summary['records']:,} stop-time-update records at "
            f"{summary['time'].isoformat(timespec='seconds')}."
        )
        if summary["csv_path"]:
            st.caption(f"Saved to {summary['csv_path']}")

st.markdown("---")

# ─── Step 4: Continuous fetch ─────────────────────────────────────────────────

st.header("Step 4 — Continuous fetch")
st.caption(
    "Repeatedly fetch the live feed at a fixed interval until you click Stop. "
    "Keep this browser tab open while it runs."
)

if "continuous_log" not in st.session_state:
    st.session_state["continuous_log"] = []

default_interval = int(rt_cfg.get("FETCH_INTERVAL_MINUTES", 12) * 60) if config_ok else 720

col_int, col_start, col_stop = st.columns([2, 1, 1])
with col_int:
    interval_secs = st.number_input(
        "Fetch interval (seconds)",
        min_value=10, step=10, value=default_interval,
        key="continuous_interval",
        disabled=is_continuous,
    )
with col_start:
    st.write("")
    if st.button("▶ Start continuous fetch", disabled=not config_ok or is_continuous):
        st.session_state["continuous_running"] = True
        st.experimental_rerun()
with col_stop:
    st.write("")
    if st.button("⏹ Stop", disabled=not is_continuous):
        st.session_state["continuous_running"] = False
        st.experimental_rerun()

log_placeholder = st.empty()


def _render_log() -> None:
    log = st.session_state["continuous_log"]
    if log:
        log_df = pd.DataFrame(log[-20:]).iloc[::-1].reset_index(drop=True)
        log_placeholder.dataframe(log_df, height=250)


_render_log()

if is_continuous:
    status_placeholder = st.empty()

    with st.spinner("Fetching..."):
        summary = _do_fetch(save_result)

    st.session_state["continuous_log"].append({
        "time": summary["time"].strftime("%Y-%m-%d %H:%M:%S"),
        "records": summary["records"],
        "matched": summary["matched"],
        "error": summary["error"] or "",
    })
    st.session_state["continuous_log"] = st.session_state["continuous_log"][-100:]
    _render_log()

    if summary["error"]:
        status_placeholder.error(f"❌ Fetch failed: {summary['error']} — retrying in {interval_secs}s.")
    else:
        status_placeholder.success(
            f"✅ Fetched {summary['records']:,} records ({summary['matched']:,} matched) "
            f"at {summary['time'].strftime('%H:%M:%S')}."
        )

    countdown_placeholder = st.empty()
    for remaining in range(int(interval_secs), 0, -1):
        countdown_placeholder.caption(f"⏳ Next fetch in {remaining}s — click Stop to end.")
        time.sleep(1)

    st.experimental_rerun()

# ─── Results ───────────────────────────────────────────────────────────────────

result: pd.DataFrame = st.session_state.get("live_fetch_result")  # type: ignore[assignment]

if result is not None:
    st.markdown("---")
    st.header("Results")

    if result.empty:
        st.warning("No records matched your reference filter in this fetch.")

        raw_df: pd.DataFrame = st.session_state.get("live_fetch_raw")
        trip_filter = st.session_state.get("live_fetch_trip_filter")
        stop_filter = st.session_state.get("live_fetch_stop_filter")
        if raw_df is not None:
            with st.expander("Debug — compare trip / stop IDs"):
                st.write(f"Live feed: {len(raw_df):,} records, {raw_df['trip_id'].nunique():,} unique trip IDs.")
                live_trip_ids = set(raw_df["trip_id"].astype(str))
                live_stop_ids = set(raw_df["stop_id"].astype(str))
                st.write("Sample live trip IDs:", sorted(live_trip_ids)[:10])
                st.write("Sample live stop IDs:", sorted(live_stop_ids)[:10])
                if trip_filter is not None:
                    st.write(f"Static reference: {len(trip_filter):,} unique trip IDs, {len(stop_filter):,} unique stop IDs.")
                    st.write("Sample static trip IDs:", sorted(trip_filter)[:10])
                    st.write("Sample static stop IDs:", sorted(stop_filter)[:10])
                    st.write(f"Trip ID overlap: {len(live_trip_ids & trip_filter):,}")
                    st.write(f"Stop ID overlap: {len(live_stop_ids & stop_filter):,}")
    else:
        r1, r2, r3 = st.columns(3)
        r1.metric("Rows", f"{len(result):,}")
        r2.metric("Unique trips", f"{result['trip_id'].nunique():,}")
        r3.metric("Unique stops", f"{result['stop_id'].nunique():,}")

        delay_cols = [c for c in ("arrival_delay", "departure_delay") if c in result.columns]
        if delay_cols:
            delayed = result[result[delay_cols].abs().gt(0).any(axis=1)]
            st.caption(f"{len(delayed):,} / {len(result):,} rows report a non-zero delay.")

        st.subheader("Preview")
        st.dataframe(result.reset_index(drop=True), height=420)

        fetch_time: datetime = st.session_state["live_fetch_time"]
        csv_bytes = result.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="⬇️ Download CSV",
            data=csv_bytes,
            file_name=f"gtfs_rt_live_{fetch_time.strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

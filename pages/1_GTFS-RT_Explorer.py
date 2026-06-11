"""
GTFS-RT Explorer — Streamlit page
Run with:  streamlit run GTFS_Static_Explorer.py   (then open this page from the sidebar)
"""

from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from src.gtfs_rt_loader import (
    apply_rt_filters,
    join_with_static,
    list_available_dates,
    load_rt_data,
    plot_delay_trend,
)
from src.ui_utils import pick_folder

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(page_title="GTFS-RT Explorer", page_icon="📡", layout="wide")

st.title("📡 GTFS-RT Explorer")
st.caption("Browse already-fetched GTFS-RT (realtime) data and filter it")

st.markdown(
    """<style>
    .stDataFrame > div { overflow-x: auto !important; }
    </style>""",
    unsafe_allow_html=True,
)

# ─── Step 1: Load fetched RT data ─────────────────────────────────────────────

st.header("Step 1 — Load fetched RT data")

try:
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        _cfg = yaml.safe_load(f) or {}
except FileNotFoundError:
    _cfg = {}

_default_rt_dir = _cfg.get("realtime", {}).get("output_rt_dir", "data/raw/rt/")

if "rt_folder_path_input" not in st.session_state:
    st.session_state["rt_folder_path_input"] = _default_rt_dir

col_path, col_browse = st.columns([5, 1])

with col_browse:
    st.write("")  # vertical spacing to align with text input
    if st.button("📁 Browse"):
        picked = pick_folder()
        if picked:
            st.session_state["rt_folder_path_input"] = picked

with col_path:
    rt_folder_input = st.text_input(
        "GTFS-RT data folder",
        key="rt_folder_path_input",
        help="The folder containing per-date subfolders (YYYY-MM-DD) of fetched TripUpdates.",
    )

rt_dir = Path(rt_folder_input.strip()) if rt_folder_input.strip() else None
available_dates = list_available_dates(rt_dir) if rt_dir else []

if rt_dir is None:
    st.info("Enter a folder path to see available dates.")
elif not available_dates:
    st.warning(f"No date folders (YYYY-MM-DD) found under '{rt_dir}'.")
else:
    min_date, max_date = available_dates[0], available_dates[-1]
    st.caption(f"{len(available_dates)} date folder(s) available, from {min_date} to {max_date}.")

    col_from, col_to = st.columns(2)
    with col_from:
        date_from = st.date_input("From date", value=max_date, min_value=min_date, max_value=max_date)
    with col_to:
        date_to = st.date_input("To date", value=max_date, min_value=min_date, max_value=max_date)

    if date_to < date_from:
        st.error("'To date' must be on or after 'From date'.")
        selected_dates = []
    else:
        selected_dates = [d for d in available_dates if date_from <= d <= date_to]

    # ── Narrow scope before loading ─────────────────────────────────────────
    st.subheader("Narrow scope before loading")
    st.caption(
        "A single day of fetched data can contain tens of millions of rows. "
        "Provide a static reference CSV (exported from the GTFS Explorer's Step 3, "
        "with original 'trip_id' / 'stop_id' columns) and/or a list of trip IDs — "
        "only matching rows will be kept while loading. The same reference is also "
        "used to add stop_name / route_type for filtering in Step 2."
    )

    static_file = st.file_uploader("Static reference CSV (optional)", type=["csv"], key="rt_static_upload")
    static_df = None
    if static_file is not None:
        try:
            static_df = pd.read_csv(static_file)
            if "trip_id" not in static_df.columns or "stop_id" not in static_df.columns:
                st.error("Uploaded CSV must contain both 'trip_id' and 'stop_id' columns.")
                static_df = None
        except Exception as exc:
            st.error(f"Could not read CSV: {exc}")

    join_on = ["trip_id", "stop_id"]
    if static_df is not None:
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

    col_trip, col_stop = st.columns(2)
    with col_trip:
        trip_ids_text = st.text_area(
            "Trip IDs (optional, one per line)",
            placeholder="3037367106\n3038272783",
        )
    with col_stop:
        stop_ids_text = st.text_area(
            "Stop IDs (optional, one per line)",
            placeholder="de:14612:28:2:6",
        )
    manual_trip_ids = {t.strip() for t in trip_ids_text.splitlines() if t.strip()}
    manual_stop_ids = {s.strip() for s in stop_ids_text.splitlines() if s.strip()}

    trip_id_filter = set()
    stop_id_filter = set()
    if static_df is not None:
        trip_id_filter |= set(static_df["trip_id"].astype(str))
        stop_id_filter |= set(static_df["stop_id"].astype(str))
    trip_id_filter |= manual_trip_ids
    stop_id_filter |= manual_stop_ids

    if trip_id_filter or stop_id_filter:
        st.caption(
            f"{len(trip_id_filter):,} trip ID(s) and {len(stop_id_filter):,} stop ID(s) "
            "will be used to narrow the loaded data."
        )
        confirm_full_load = True
    else:
        st.warning(
            "⚠️ No trip ID / stop ID filter set. Loading without one can use several GB "
            "of memory and take a long time, especially for multi-day ranges."
        )
        confirm_full_load = st.checkbox("I understand — load without a filter anyway")

    if st.button("📂 Load RT data", disabled=not confirm_full_load or not selected_dates):
        progress_bar = st.progress(0.0)
        status_text = st.empty()

        def _on_file(file_idx: int, total_files: int, kept_rows: int) -> None:
            pct = file_idx / total_files if total_files else 1.0
            progress_bar.progress(pct)
            status_text.text(f"Reading file {file_idx:,} / {total_files:,} — {kept_rows:,} rows kept so far...")

        rt_df = load_rt_data(
            rt_dir, selected_dates,
            trip_ids=trip_id_filter or None,
            stop_ids=stop_id_filter or None,
            on_file=_on_file,
        )
        progress_bar.empty()
        status_text.empty()

        if rt_df.empty:
            st.warning("No GTFS-RT records found for the selected date range / filter.")
            st.session_state["rt_data"] = None
        else:
            st.session_state["rt_data"] = rt_df
            st.session_state["rt_static_ref"] = static_df
            st.session_state["rt_join_on"] = join_on
            st.session_state["rt_filtered"] = None
            st.success(f"✅ Loaded {len(rt_df):,} records from {len(selected_dates)} day(s).")

# ─── Overview + Step 2/3 (shown when data is loaded) ──────────────────────────

rt_df: pd.DataFrame = st.session_state.get("rt_data")  # type: ignore[assignment]

if rt_df is not None and not rt_df.empty:
    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total records", f"{len(rt_df):,}")
    col2.metric("Unique trips", f"{rt_df['trip_id'].nunique():,}")
    col3.metric("Unique stops", f"{rt_df['stop_id'].nunique():,}")
    st.caption(
        f"Fetch time range: {rt_df['fetch_timestamp'].min()} → {rt_df['fetch_timestamp'].max()}"
    )

    static_df = st.session_state.get("rt_static_ref")
    has_static = static_df is not None
    rt_join_on = st.session_state.get("rt_join_on", ["trip_id", "stop_id"])
    working_df = join_with_static(rt_df, static_df, on=rt_join_on) if has_static else rt_df
    if has_static:
        added_cols = [c for c in static_df.columns if c not in ("trip_id", "stop_id")]
        st.caption(
            f"Joined with static reference on {' + '.join(rt_join_on)} — "
            f"added columns: {', '.join(added_cols)}"
        )

    st.markdown("---")

    # ─── Step 2: Filters ────────────────────────────────────────────────────────

    st.header("Step 2 — Set Filters")
    st.caption("Tick the filters you want to apply, then click 'Apply filters'.")

    # ── Trip ID ───────────────────────────────────────────────────────────────
    use_trip = st.checkbox("Filter by trip ID")
    trip_ids = []
    if use_trip:
        filter_trip_ids_text = st.text_area(
            "Trip IDs to keep (one per line)",
            placeholder="3037367106\n3038272783",
            key="rt_filter_trip_ids",
        )
        trip_ids = [t.strip() for t in filter_trip_ids_text.splitlines() if t.strip()]
        if not trip_ids:
            st.warning("No trip IDs entered — this filter will be ignored.")

    # ── Stop name (requires static join) ───────────────────────────────────────
    use_stop = st.checkbox("Filter by stop name", disabled=not (has_static and "stop_name" in working_df.columns))
    selected_stop_names = []
    if use_stop:
        unique_names = sorted(working_df["stop_name"].dropna().unique().tolist())
        selected_stop_names = st.multiselect("Stop names", options=unique_names)
        if not selected_stop_names:
            st.warning("No stops selected — this filter will be ignored.")
    if not (has_static and "stop_name" in working_df.columns) and not use_stop:
        st.caption("↳ Stop name filter requires a static reference CSV with a 'stop_name' column.")

    # ── Route type (requires static join) ──────────────────────────────────────
    use_route_type = st.checkbox(
        "Filter by route type", disabled=not (has_static and "route_type" in working_df.columns)
    )
    selected_route_types = []
    if use_route_type:
        unique_types = sorted(working_df["route_type"].dropna().astype(str).unique().tolist())
        selected_route_types = st.multiselect("Route types", options=unique_types)
        if not selected_route_types:
            st.warning("No route types selected — this filter will be ignored.")

    # ── Time of day ──────────────────────────────────────────────────────────
    use_tod = st.checkbox("Filter by fetch time of day")
    tod_start = tod_end = None
    if use_tod:
        col_tod_a, col_tod_b = st.columns(2)
        with col_tod_a:
            tod_start = st.time_input("From time")
        with col_tod_b:
            tod_end = st.time_input("To time")

    # ── Delay threshold ──────────────────────────────────────────────────────
    use_delay = st.checkbox("Only show records with a minimum delay")
    min_delay_secs = None
    if use_delay:
        min_delay_secs = st.number_input(
            "Minimum |delay| in seconds (arrival or departure)",
            min_value=0, value=60, step=30,
        )

    no_active = not any([use_trip, use_stop, use_route_type, use_tod, use_delay])

    if st.button("🔍 Apply filters"):
        if no_active:
            st.session_state["rt_filtered"] = working_df
        else:
            st.session_state["rt_filtered"] = apply_rt_filters(
                working_df,
                trip_ids=trip_ids or None,
                stop_names=selected_stop_names or None,
                route_types=selected_route_types or None,
                time_of_day_start=tod_start,
                time_of_day_end=tod_end,
                min_delay_secs=min_delay_secs,
            )

    # ─── Step 3: Results ────────────────────────────────────────────────────────

    filtered: pd.DataFrame = st.session_state.get("rt_filtered")  # type: ignore[assignment]

    if filtered is not None:
        st.markdown("---")
        st.header("Step 3 — Results")

        if filtered.empty:
            st.warning("No data matched your filters. Try relaxing one or more conditions.")
        else:
            r1, r2, r3 = st.columns(3)
            r1.metric("Matched rows", f"{len(filtered):,}")
            r2.metric("Matched trips", f"{filtered['trip_id'].nunique():,}")
            r3.metric("Matched stops", f"{filtered['stop_id'].nunique():,}")

            st.subheader("Preview (first 1 000 rows)")
            st.dataframe(filtered.head(1_000).reset_index(drop=True), height=420)

            csv_bytes = filtered.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                label="⬇️ Download full CSV",
                data=csv_bytes,
                file_name="gtfs_rt_filtered.csv",
                mime="text/csv",
            )

            st.subheader("Delay trend")
            delay_options = [c for c in ("departure_delay", "arrival_delay") if c in filtered.columns]
            if delay_options:
                delay_col = st.selectbox("Delay column to plot", options=delay_options)
                fig = plot_delay_trend(filtered, delay_col=delay_col)
                st.pyplot(fig)
            else:
                st.caption("No delay columns available to plot.")

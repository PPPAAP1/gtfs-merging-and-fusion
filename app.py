"""
GTFS Explorer — Streamlit App
Run with:  streamlit run app.py
"""

import pandas as pd
import streamlit as st


def _pick_folder() -> str:
    """Open a native OS folder-picker dialog and return the selected path (or '')."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)   # bring dialog to front
        path = filedialog.askdirectory(title="Select GTFS folder")
        root.destroy()
        return path or ""
    except Exception:
        return ""

from src.gtfs_filter import apply_filters
from src.gtfs_loader import GTFSData, load_from_folder, load_from_zip

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="GTFS Explorer",
    page_icon="🚆",
    layout="wide",
)

st.title("🚆 GTFS Explorer")
st.caption("Extract the data you need from a static GTFS feed")

# Force horizontal scroll on dataframes (Streamlit 1.12 doesn't enable it by default)
st.markdown(
    "<style>.stDataFrame > div { overflow-x: auto !important; }</style>",
    unsafe_allow_html=True,
)

# ─── Step 1: Load ────────────────────────────────────────────────────────────

st.header("Step 1 — Load GTFS Data")

source = st.radio(
    "Data source",
    ["Upload ZIP file", "Use local folder path"],
    horizontal=True,
)

uploaded_file = None
folder_input = ""

if source == "Upload ZIP file":
    uploaded_file = st.file_uploader(
        "Select a GTFS ZIP file (must contain routes.txt / trips.txt / stops.txt / stop_times.txt)",
        type=["zip"],
    )
    st.caption("⚠️ Upload limit is 2 GB. For large feeds, recommended to use the **local folder path** option instead.")
else:
    if "folder_path_input" not in st.session_state:
        st.session_state["folder_path_input"] = ""

    col_path, col_browse = st.columns([5, 1])

    # Browse button must be processed BEFORE text_input is instantiated,
    # so that session_state["folder_path_input"] is set before the widget reads it.
    with col_browse:
        st.write("")   # vertical spacing to align with text input
        if st.button("📁 Browse"):
            picked = _pick_folder()
            if picked:
                st.session_state["folder_path_input"] = picked

    with col_path:
        folder_input = st.text_input(
            "GTFS folder path",
            key="folder_path_input",
            placeholder="e.g.  C:/gtfs/germany   or   data/raw/static",
        )

    st.caption("Point to the folder that contains the unpacked GTFS .txt files.")

if st.button("📂 Load data"):
    with st.spinner("Reading GTFS files..."):
        try:
            if source == "Upload ZIP file":
                if not uploaded_file:
                    st.error("Please select a ZIP file first.")
                    st.stop()
                raw = uploaded_file.read()
                gtfs: GTFSData = load_from_zip(raw)
                st.session_state.update(
                    {"gtfs": gtfs, "zip_bytes": raw, "folder_path": None, "result": None}
                )
            else:
                if not folder_input.strip():
                    st.error("Please enter a folder path.")
                    st.stop()
                gtfs = load_from_folder(folder_input.strip())
                st.session_state.update(
                    {"gtfs": gtfs, "zip_bytes": None, "folder_path": folder_input.strip(), "result": None}
                )
            st.success("✅ Data loaded successfully!")
        except FileNotFoundError as exc:
            st.error(f"❌ File not found: {exc}")
        except Exception as exc:
            st.error(f"❌ Load failed: {exc}")

# ─── Data overview (shown when data is loaded) ────────────────────────────────

gtfs: GTFSData = st.session_state.get("gtfs")  # type: ignore[assignment]

if gtfs and gtfs.is_loaded():
    overview = gtfs.get_overview()

    col1, col2, col3 = st.columns(3)
    col1.metric("Routes",     f"{overview['total_routes']:,}")
    col2.metric("Trips",      f"{overview['total_trips']:,}")
    col3.metric("Stops",      f"{overview['total_stops']:,}")

    with st.expander("View transport type breakdown"):
        df_stats: pd.DataFrame = overview["route_type_stats"].rename(
            columns={"route_type": "Type code", "label": "Transport type", "trip_count": "Trip count"}
        )
        st.dataframe(df_stats.reset_index(drop=True))

    st.markdown("---")

    # ─── Step 2: Filter ───────────────────────────────────────────────────────

    st.header("Step 2 — Set Filters")
    st.caption("Tick the filters you want to apply. At least one must be active.")

    def _valid_time(t: str) -> bool:
        if not t:
            return True
        parts = t.split(":")
        return len(parts) == 3 and all(p.isdigit() for p in parts)

    # ── Transport type ────────────────────────────────────────────────────────
    use_type = st.checkbox("Filter by transport type")
    if use_type:
        type_stats = overview["route_type_stats"]
        type_label_map = {
            str(row["route_type"]): f"{row['label']}  ({row['trip_count']:,} trips)"
            for _, row in type_stats.iterrows()
        }
        selected_types = st.multiselect(
            "Transport type",
            options=list(type_label_map.keys()),
            format_func=lambda x: type_label_map.get(x, x),
        )
    else:
        selected_types = None

    # ── Stop name ─────────────────────────────────────────────────────────────
    use_stop = st.checkbox("Filter by stop name")
    if use_stop:
        stop_query = st.text_input(
            "Stop name",
            placeholder="e.g.  Dresden Hauptbahnhof",
            help="Partial match, case-insensitive",
        )
        if stop_query.strip():
            q = stop_query.strip().lower()
            matched_stops = gtfs.stops[
                gtfs.stops["stop_name"].str.lower().str.contains(q, na=False, regex=False)
            ]
            if matched_stops.empty:
                st.warning(f"No stops found matching '{stop_query}'. Check your spelling.")
            else:
                unique_names = matched_stops["stop_name"].unique()
                preview = ", ".join(unique_names[:8])
                suffix = f", and {len(unique_names) - 8} more  ({len(unique_names)} total)" if len(unique_names) > 8 else f"  ({len(unique_names)} total)"
                st.success(f"Matched: {preview}{suffix}")
    else:
        stop_query = None

    # ── Service date ──────────────────────────────────────────────────────────
    use_date = st.checkbox(
        "Filter by service date",
        disabled=not overview["has_calendar"],
        help="Requires calendar.txt or calendar_dates.txt in the feed." if not overview["has_calendar"] else "",
    )
    if use_date and overview["has_calendar"]:
        target_date = st.date_input("Service date")
    else:
        target_date = None
        if use_date and not overview["has_calendar"]:
            st.warning("No calendar data found in this feed — date filter is unavailable.")

    # ── Departure time ────────────────────────────────────────────────────────
    use_dep = st.checkbox("Filter by departure time range")
    if use_dep:
        dep_start = st.text_input("Departure from", placeholder="06:00:00")
        dep_end   = st.text_input("Departure to",   placeholder="09:00:00")
    else:
        dep_start = dep_end = None

    # ── Arrival time ──────────────────────────────────────────────────────────
    use_arr = st.checkbox("Filter by arrival time range")
    if use_arr:
        arr_start = st.text_input("Arrival from", placeholder="06:00:00")
        arr_end   = st.text_input("Arrival to",   placeholder="09:00:00")
    else:
        arr_start = arr_end = None

    # ── Validate time fields ──────────────────────────────────────────────────
    time_fields = {
        "Departure from": dep_start or "",
        "Departure to":   dep_end   or "",
        "Arrival from":   arr_start or "",
        "Arrival to":     arr_end   or "",
    }
    bad_fields = [label for label, val in time_fields.items() if not _valid_time(val)]
    if bad_fields:
        st.error(f"Invalid time format in: {', '.join(bad_fields)} — use HH:MM:SS, e.g. 06:30:00")

    no_active = not any([use_type, use_stop, use_date, use_dep, use_arr])
    times_ok  = not bad_fields

    if times_ok and st.button("🔍 Apply filters"):
        if no_active:
            st.warning("⚠️ Please tick at least one filter.")
        else:
            progress_bar = st.progress(0.0)
            status_text  = st.empty()

            def _on_chunk(chunk_idx: int, kept: int) -> None:
                pct = min((chunk_idx + 1) / 150, 0.95)
                progress_bar.progress(pct)
                status_text.text(
                    f"Scanning stop_times.txt — chunk {chunk_idx + 1} processed, "
                    f"{kept:,} rows kept so far..."
                )

            try:
                result_df = apply_filters(
                    gtfs_data=gtfs,
                    zip_bytes=st.session_state.get("zip_bytes"),
                    route_types=selected_types or None,
                    stop_name_query=(stop_query or "").strip() or None,
                    target_date=target_date,
                    dep_time_start=(dep_start or "").strip() or None,
                    dep_time_end=(dep_end   or "").strip() or None,
                    arr_time_start=(arr_start or "").strip() or None,
                    arr_time_end=(arr_end   or "").strip() or None,
                    on_chunk=_on_chunk,
                )
                progress_bar.progress(1.0)
                status_text.empty()
                st.session_state["result"] = result_df
            except Exception as exc:
                progress_bar.empty()
                status_text.empty()
                st.error(f"Filter error: {exc}")

    # ─── Step 3: Results ──────────────────────────────────────────────────────

    result: pd.DataFrame = st.session_state.get("result")  # type: ignore[assignment]

    if result is not None:
        st.markdown("---")
        st.header("Step 3 — Review & Export")

        if result.empty:
            st.warning("No data matched your filters. Try relaxing one or more conditions.")
        else:
            r1, r2, r3 = st.columns(3)
            r1.metric("Matched trips",   f"{result['trip_id'].nunique():,}")
            r2.metric("Matched stops",   f"{result['stop_id'].nunique():,}")
            r3.metric("Total rows",      f"{len(result):,}")

            st.markdown("---")

            # ── Column selector ───────────────────────────────────────────────
            REQUIRED_COLS = ["trip_id", "stop_id", "stop_name", "arrival_time", "departure_time"]
            OPTIONAL_COLS = {
                "route_id":         "Route identifier",
                "route_type":       "Transport type code  (e.g. 106 = RB/RE)",
                "route_short_name": "Line name  (e.g. RE1, ICE 123)",
                "service_id":       "Service calendar ID",
                "stop_lat":         "Stop latitude",
                "stop_lon":         "Stop longitude",
                "stop_sequence":    "Stop position within the trip",
            }

            required_present = [c for c in REQUIRED_COLS if c in result.columns]
            optional_present  = [c for c in OPTIONAL_COLS  if c in result.columns]

            st.subheader("Output columns")
            st.caption(
                f"**Required** (always included): {', '.join(required_present)}"
            )

            opt_label_map = {c: f"{c}  —  {OPTIONAL_COLS[c]}" for c in optional_present}
            selected_optional = st.multiselect(
                "Optional columns",
                options=optional_present,
                default=optional_present,
                format_func=lambda c: opt_label_map.get(c, c),
            )

            # Preserve logical column order
            all_ordered = REQUIRED_COLS + list(OPTIONAL_COLS.keys())
            export_cols = [
                c for c in all_ordered
                if c in result.columns and (c in required_present or c in selected_optional)
            ]
            export_df = result[export_cols]

            # ── Preview ───────────────────────────────────────────────────────
            st.subheader("Preview (first 1 000 rows)")
            st.dataframe(export_df.head(1_000).reset_index(drop=True), height=420)

            # ── Download ──────────────────────────────────────────────────────
            csv_bytes = export_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                label="⬇️ Download full CSV",
                data=csv_bytes,
                file_name="gtfs_filtered.csv",
                mime="text/csv",
            )

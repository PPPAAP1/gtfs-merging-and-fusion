"""
GTFS Explorer — Streamlit App
Run with:  streamlit run app.py
"""

import numpy as np
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

def _stops_in_polygon(stops_df: pd.DataFrame, geojson_coords: list) -> pd.Series:
    """
    Vectorized ray-casting point-in-polygon test.
    geojson_coords: GeoJSON polygon coordinates — a list of rings, each ring a list
    of [lon, lat] pairs.  Only the exterior ring (index 0) is tested.
    Returns a boolean Series aligned to stops_df.index.
    """
    ring = np.array(geojson_coords[0])   # shape (N, 2): col 0 = lon, col 1 = lat
    px = stops_df["stop_lon"].values.astype(float)
    py = stops_df["stop_lat"].values.astype(float)
    inside = np.zeros(len(px), dtype=bool)
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i, 0], ring[i, 1]
        xj, yj = ring[j, 0], ring[j, 1]
        cond_y = (yi > py) != (yj > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            x_cross = (xj - xi) * (py - yi) / (yj - yi) + xi
        inside ^= cond_y & (px < x_cross)
        j = i
    return pd.Series(inside, index=stops_df.index)


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

st.markdown(
    """<style>
    /* Horizontal scroll on dataframes (Streamlit 1.12 default is hidden) */
    .stDataFrame > div { overflow-x: auto !important; }

    /* streamlit-folium 0.11.0: Leaflet fires Streamlit.setFrameHeight(0) after
       tile load, collapsing the iframe. Lock the minimum height via CSS so the
       !important rule wins over the JS-driven height reset. */
    iframe { min-height: 500px !important; }
    </style>""",
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
    selected_stop_names = []
    if use_stop:
        stop_mode = st.radio(
            "Selection method",
            ["Text search", "Draw on map"],
            horizontal=True,
        )

        # ── Text search ───────────────────────────────────────────────────────
        if stop_mode == "Text search":
            stop_search = st.text_input(
                "Search stop name",
                placeholder="e.g.  Dresden  or  Frankfurt",
                help="Type a keyword to search, then pick exact stops from the list below.",
            )
            if stop_search.strip():
                q = stop_search.strip().lower()
                matched_stops = gtfs.stops[
                    gtfs.stops["stop_name"].str.lower().str.contains(q, na=False, regex=False)
                ]
                unique_names = sorted(matched_stops["stop_name"].unique().tolist())

                if not unique_names:
                    st.warning(f"No stops found matching '{stop_search}'. Check your spelling.")
                else:
                    default_selection = unique_names if len(unique_names) <= 10 else []
                    if len(unique_names) > 10:
                        st.caption(
                            f"{len(unique_names)} stops found — please select which ones to include."
                        )
                    selected_stop_names = st.multiselect(
                        f"Select stops  ({len(unique_names)} found)",
                        options=unique_names,
                        default=default_selection,
                    )
                    if not selected_stop_names:
                        st.warning("No stops selected — this filter will be ignored.")

        # ── Draw on map ───────────────────────────────────────────────────────
        else:
            try:
                import folium
                from folium.plugins import Draw, FastMarkerCluster
                from streamlit_folium import st_folium
            except ImportError:
                st.error(
                    "Map selection requires extra packages. "
                    "Run:  pip install folium streamlit-folium"
                )
                st.stop()

            stops_geo = gtfs.stops.copy()
            for _col in ("stop_lat", "stop_lon"):
                if _col in stops_geo.columns:
                    stops_geo[_col] = pd.to_numeric(stops_geo[_col], errors="coerce")
            stops_geo = stops_geo.dropna(subset=["stop_lat", "stop_lon"])

            if stops_geo.empty:
                st.warning("No stops with coordinate data found in this feed.")
                selected_stop_names = []
            else:
                n_stops = len(stops_geo)

                _MAP_DISPLAY_LIMIT = 20_000
                display_stops = (
                    stops_geo.sample(_MAP_DISPLAY_LIMIT, random_state=42)
                    if n_stops > _MAP_DISPLAY_LIMIT
                    else stops_geo
                )

                # The folium Map object is consumed (Jinja2 state exhausted) after
                # st_folium renders it, so it must be rebuilt fresh on every rerun.
                # Only show the progress bar the first time; subsequent rebuilds are
                # silent and fast enough not to warrant a progress indicator.
                _first_build = "_stop_map_ready" not in st.session_state
                if _first_build:
                    _prog      = st.progress(0.0)
                    _prog_text = st.empty()
                    _prog_text.text("Computing map centre...")
                    _prog.progress(0.1)

                center_lat = float(stops_geo["stop_lat"].mean())
                center_lon = float(stops_geo["stop_lon"].mean())

                if _first_build:
                    _prog_text.text("Initializing base map...")
                    _prog.progress(0.3)

                _m = folium.Map(location=[center_lat, center_lon], zoom_start=6)

                if _first_build:
                    _prog_text.text(
                        f"Adding {len(display_stops):,} stop markers (clustered)..."
                    )
                    _prog.progress(0.6)

                locations = display_stops[["stop_lat", "stop_lon"]].values.tolist()
                FastMarkerCluster(data=locations, name="Stops").add_to(_m)

                if _first_build:
                    _prog_text.text("Adding draw controls...")
                    _prog.progress(0.9)

                Draw(
                    export=False,
                    draw_options={
                        "polyline": False,
                        "circle": False,
                        "circlemarker": False,
                        "marker": False,
                        "rectangle": True,
                        "polygon": True,
                    },
                ).add_to(_m)

                if _first_build:
                    st.session_state["_stop_map_ready"] = True
                    _prog.progress(1.0)
                    _prog.empty()
                    _prog_text.empty()

                if n_stops > _MAP_DISPLAY_LIMIT:
                    st.info(
                        f"Map displays a random sample of {_MAP_DISPLAY_LIMIT:,} / {n_stops:,} stops. "
                        "Your drawn shape will still match **all** stops inside it."
                    )
                else:
                    st.caption(
                        f"Showing all {n_stops:,} stops (clustered). "
                        "Zoom in, then use the toolbar on the **left edge** to draw a "
                        "rectangle or polygon."
                    )

                map_out = st_folium(_m, width=700, height=500, key="stop_map_selector")

                drawn_geom = None
                if map_out and map_out.get("last_active_drawing"):
                    drawn_geom = map_out["last_active_drawing"].get("geometry")

                selected_stop_names = []
                if drawn_geom and drawn_geom.get("type") == "Polygon":
                    coords = drawn_geom["coordinates"]
                    mask   = _stops_in_polygon(stops_geo, coords)
                    inside_df = stops_geo[mask]

                    if inside_df.empty:
                        st.warning("No stops inside the drawn shape — try a larger area.")
                    else:
                        matched_names = sorted(
                            inside_df["stop_name"].dropna().unique().tolist()
                        )
                        st.success(
                            f"{len(inside_df):,} stop entries / "
                            f"{len(matched_names):,} unique names inside your selection."
                        )
                        st.caption(
                            f"{len(matched_names)} stop names pre-selected — "
                            "deselect any you don't need."
                        )
                        selected_stop_names = st.multiselect(
                            f"Stops in selection  ({len(matched_names)} names)",
                            options=matched_names,
                            default=matched_names,
                        )
                        if not selected_stop_names:
                            st.warning("No stops selected — this filter will be ignored.")

    # ── Service date range ────────────────────────────────────────────────────
    use_date = st.checkbox(
        "Filter by service date range",
        disabled=not overview["has_calendar"],
        help="Requires calendar.txt or calendar_dates.txt in the feed." if not overview["has_calendar"] else "",
    )
    if use_date and overview["has_calendar"]:
        date_start = st.date_input("From date")
        date_end   = st.date_input("To date", value=date_start)
        if date_end < date_start:
            st.error("'To date' must be on or after 'From date'.")
            use_date = False   # block Apply until fixed
        else:
            delta_days = (date_end - date_start).days + 1
            if delta_days == 1:
                st.caption("Single day selected.")
            elif delta_days > 90:
                st.warning(f"Large range: {delta_days} days — filtering may take a moment.")
            else:
                st.caption(f"Range: {delta_days} days.")
    else:
        date_start = date_end = None
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
                    stop_names=selected_stop_names or None,
                    date_start=date_start,
                    date_end=date_end,
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

            # ── Field name mapping ────────────────────────────────────────────
            rename_map: dict = {}
            with st.expander("Field name mapping  (optional)"):
                st.caption(
                    "Rename GTFS columns to match your own database or system schema. "
                    "Edit the field below each column — leave unchanged to keep the original name."
                )
                for _col in export_cols:
                    new_name = st.text_input(
                        _col,
                        value=_col,
                        key=f"rename_{_col}",
                    )
                    stripped = (new_name or "").strip()
                    if stripped and stripped != _col:
                        rename_map[_col] = stripped

                if rename_map:
                    effective_names = [rename_map.get(c, c) for c in export_cols]
                    if len(effective_names) != len(set(effective_names)):
                        st.error(
                            "Duplicate output names detected — each column must have a unique name."
                        )
                        rename_map = {}   # suppress rename until conflict is resolved
                    else:
                        st.success(
                            f"Renaming: "
                            + ",  ".join(f"{k} → {v}" for k, v in rename_map.items())
                        )

            if rename_map:
                export_df = export_df.rename(columns=rename_map)

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

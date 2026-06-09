import io
import zipfile
from datetime import date as date_cls
from pathlib import Path
from typing import Callable, List, Optional

import pandas as pd

from src.gtfs_loader import CHUNK_SIZE, GTFSData


def _time_to_secs(t: str) -> int:
    """Convert 'H:MM:SS' or 'HH:MM:SS' to integer seconds. Works for times > 24:00."""
    h, m, s = t.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def _series_to_secs(series: pd.Series) -> pd.Series:
    """Vectorized conversion of a time column (HH:MM:SS) to integer seconds.
    Non-zero-padded hours (e.g. '6:30:00') and NaN values are handled safely.
    NaN / unparseable → -1 (will never satisfy a positive time filter).
    """
    parts = series.str.strip().str.split(":", n=2, expand=True)
    secs = (
        pd.to_numeric(parts[0], errors="coerce") * 3600
        + pd.to_numeric(parts[1], errors="coerce") * 60
        + pd.to_numeric(parts[2], errors="coerce")
    )
    return secs.fillna(-1).astype(int)


def apply_filters(
    gtfs_data: GTFSData,
    zip_bytes: Optional[bytes] = None,
    route_types: Optional[List[str]] = None,
    stop_names: Optional[List[str]] = None,
    date_start: Optional[date_cls] = None,
    date_end: Optional[date_cls] = None,
    dep_time_start: Optional[str] = None,
    dep_time_end: Optional[str] = None,
    arr_time_start: Optional[str] = None,
    arr_time_end: Optional[str] = None,
    on_chunk: Optional[Callable[[int, int], None]] = None,
) -> pd.DataFrame:
    """
    Filter static GTFS stop_times by any combination of:
      - route_types     : list of route_type strings, e.g. ["106", "109"]
      - stop_name_query : partial stop name, case-insensitive
      - target_date     : only trips running on this date (requires calendar data)
      - dep_time_start/end : departure time window, "HH:MM:SS"
      - arr_time_start/end : arrival time window,   "HH:MM:SS"

    stop_times.txt is streamed in chunks for memory efficiency.
    on_chunk(chunk_index, kept_rows_so_far) is called after every chunk.
    """
    routes = gtfs_data.routes.copy()
    trips  = gtfs_data.trips.copy()
    stops  = gtfs_data.stops.copy()

    # ── 1. Narrow routes by type ──────────────────────────────────────────────
    if route_types:
        routes = routes[routes["route_type"].isin([str(rt) for rt in route_types])]

    valid_trip_ids = set(
        trips.loc[trips["route_id"].isin(routes["route_id"]), "trip_id"]
    )
    if not valid_trip_ids:
        return pd.DataFrame()

    # ── 2. Narrow trips by date range ────────────────────────────────────────
    if date_start is not None or date_end is not None:
        effective_start = date_start or date_end
        effective_end   = date_end   or date_start
        active_sids = gtfs_data.get_active_service_ids_in_range(effective_start, effective_end)
        if active_sids is not None:
            valid_trip_ids &= set(
                trips.loc[trips["service_id"].isin(active_sids), "trip_id"]
            )
            if not valid_trip_ids:
                return pd.DataFrame()

    # ── 3. Narrow stops by explicitly selected names ──────────────────────────
    valid_stop_ids: Optional[set] = None
    if stop_names:
        matched = stops[stops["stop_name"].isin(stop_names)]
        if matched.empty:
            return pd.DataFrame()
        valid_stop_ids = set(matched["stop_id"])

    # ── 4. Pre-compute time thresholds (seconds) ──────────────────────────────
    dep_start_s = _time_to_secs(dep_time_start) if dep_time_start else None
    dep_end_s   = _time_to_secs(dep_time_end)   if dep_time_end   else None
    arr_start_s = _time_to_secs(arr_time_start) if arr_time_start else None
    arr_end_s   = _time_to_secs(arr_time_end)   if arr_time_end   else None

    # ── 5. Stream stop_times, apply all filters in one pass ──────────────────
    def _process(chunk: pd.DataFrame) -> pd.DataFrame:
        chunk = chunk[chunk["trip_id"].isin(valid_trip_ids)]
        if chunk.empty:
            return chunk

        if valid_stop_ids is not None:
            chunk = chunk[chunk["stop_id"].isin(valid_stop_ids)]
            if chunk.empty:
                return chunk

        if dep_start_s is not None or dep_end_s is not None:
            dep = _series_to_secs(chunk["departure_time"])
            mask = pd.Series(True, index=chunk.index)
            if dep_start_s is not None:
                mask &= dep >= dep_start_s
            if dep_end_s is not None:
                mask &= (dep >= 0) & (dep <= dep_end_s)
            chunk = chunk[mask]
            if chunk.empty:
                return chunk

        if arr_start_s is not None or arr_end_s is not None:
            arr = _series_to_secs(chunk["arrival_time"])
            mask = pd.Series(True, index=chunk.index)
            if arr_start_s is not None:
                mask &= arr >= arr_start_s
            if arr_end_s is not None:
                mask &= (arr >= 0) & (arr <= arr_end_s)
            chunk = chunk[mask]

        return chunk

    result_chunks: list = []
    kept_rows = 0
    for chunk_idx, chunk in enumerate(_iter_stop_times(gtfs_data, zip_bytes)):
        filtered = _process(chunk)
        if not filtered.empty:
            result_chunks.append(filtered)
            kept_rows += len(filtered)
        if on_chunk:
            on_chunk(chunk_idx, kept_rows)

    if not result_chunks:
        return pd.DataFrame()

    result = pd.concat(result_chunks, ignore_index=True)

    # ── 6. Enrich with route_type / route_short_name ──────────────────────────
    route_cols = ["route_id", "route_type"]
    if "route_short_name" in routes.columns:
        route_cols.append("route_short_name")

    trips_enriched = trips[trips["route_id"].isin(routes["route_id"])].copy()
    trips_enriched = trips_enriched.merge(routes[route_cols], on="route_id", how="left")

    trip_cols = ["trip_id", "route_id", "route_type", "service_id"]
    if "route_short_name" in trips_enriched.columns:
        trip_cols.append("route_short_name")

    result = result.merge(trips_enriched[trip_cols], on="trip_id", how="left")

    # ── 7. Enrich with stop name / coordinates ────────────────────────────────
    stop_cols = ["stop_id", "stop_name"]
    for c in ("stop_lat", "stop_lon"):
        if c in stops.columns:
            stop_cols.append(c)

    result = result.merge(stops[stop_cols], on="stop_id", how="left")

    # ── 8. Return columns in a sensible order ─────────────────────────────────
    ordered = [
        "trip_id", "route_id", "route_type", "route_short_name", "service_id",
        "stop_id", "stop_name", "stop_lat", "stop_lon",
        "arrival_time", "departure_time", "stop_sequence",
    ]
    final_cols = [c for c in ordered if c in result.columns]
    return result[final_cols].reset_index(drop=True)


# ─── internal: stop_times iterator ───────────────────────────────────────────

def _iter_stop_times(gtfs_data: GTFSData, zip_bytes: Optional[bytes]):
    """Yield stop_times.txt DataFrame chunks from either a ZIP or a folder."""
    if gtfs_data.source_type == "zip":
        if not zip_bytes:
            raise ValueError("zip_bytes must be provided when source_type is 'zip'")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            names = z.namelist()
            matches = [n for n in names if n == "stop_times.txt" or n.endswith("/stop_times.txt")]
            if not matches:
                raise FileNotFoundError("'stop_times.txt' not found in ZIP.")
            with z.open(matches[0]) as f:
                yield from pd.read_csv(f, dtype=str, chunksize=CHUNK_SIZE, low_memory=False)
    else:
        path = Path(gtfs_data.source_path) / "stop_times.txt"
        if not path.exists():
            raise FileNotFoundError(f"'stop_times.txt' not found in folder '{gtfs_data.source_path}'.")
        yield from pd.read_csv(path, dtype=str, chunksize=CHUNK_SIZE, low_memory=False)

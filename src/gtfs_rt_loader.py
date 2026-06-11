"""
gtfs_rt_loader.py

Helpers for browsing, loading and filtering already-fetched GTFS-RT
TripUpdates data, as written by
src/gtfs_scraping_main/fetch_realtime_gtfs.py into
data/raw/rt/<YYYY-MM-DD>/DELFI_GTFS_TripUpdates_<timestamp>.csv (+ .json)
"""

from datetime import date as date_cls, datetime, time as time_cls
from pathlib import Path
from typing import Callable, List, Optional, Set

import pandas as pd

RT_COLUMNS = ["trip_id", "stop_id", "arrival_delay", "departure_delay", "fetch_timestamp", "source_file"]


def list_available_dates(rt_dir: Path) -> List[date_cls]:
    """Return sorted dates that have a fetched-data subfolder (YYYY-MM-DD) under rt_dir."""
    if not rt_dir.is_dir():
        return []
    dates = []
    for entry in rt_dir.iterdir():
        if not entry.is_dir():
            continue
        try:
            dates.append(datetime.strptime(entry.name, "%Y-%m-%d").date())
        except ValueError:
            continue
    return sorted(dates)


def load_rt_data(
    rt_dir: Path,
    dates: List[date_cls],
    trip_ids: Optional[Set[str]] = None,
    stop_ids: Optional[Set[str]] = None,
    on_file: Optional[Callable[[int, int, int], None]] = None,
) -> pd.DataFrame:
    """
    Load and concatenate GTFS-RT TripUpdate files for the given dates.
    Prefers the .csv file for a given fetch; falls back to .json if no
    matching .csv exists. Returns RT_COLUMNS (fetch_timestamp parsed as
    datetime); empty DataFrame with those columns if nothing is found.

    A single day of fetched data can contain tens of millions of rows, so:
      - trip_ids / stop_ids: if either is given, each file's rows are kept
        when trip_id is in trip_ids OR stop_id is in stop_ids, immediately
        after reading and before concatenation. Some GTFS-RT feeds use
        trip_id values (e.g. VDV "Globaler Code" composed identifiers) that
        do not match the static GTFS trip_id namespace — stop_id (DHID) is
        usually stable across static and RT feeds and is the more reliable
        narrowing key in that case.
      - on_file(file_index, total_files, kept_rows_so_far): optional progress
        callback, called once per file (1-based file_index).
    """
    all_files: List[Path] = []
    for d in dates:
        folder = rt_dir / d.strftime("%Y-%m-%d")
        if not folder.is_dir():
            continue

        files = {f.stem: f for f in folder.glob("DELFI_GTFS_TripUpdates_*.json")}
        files.update({f.stem: f for f in folder.glob("DELFI_GTFS_TripUpdates_*.csv")})

        all_files.extend(files[stem] for stem in sorted(files))

    frames = []
    kept_rows = 0
    for i, f in enumerate(all_files):
        try:
            if f.suffix == ".csv":
                df = pd.read_csv(f, dtype={"trip_id": str, "stop_id": str})
            else:
                df = pd.read_json(f, dtype={"trip_id": str, "stop_id": str})
        except Exception:
            df = None

        if df is not None:
            if trip_ids is not None or stop_ids is not None:
                mask = pd.Series(False, index=df.index)
                if trip_ids is not None:
                    mask |= df["trip_id"].isin(trip_ids)
                if stop_ids is not None:
                    mask |= df["stop_id"].isin(stop_ids)
                df = df[mask]
            if not df.empty:
                df["source_file"] = f.name
                frames.append(df)
                kept_rows += len(df)

        if on_file is not None:
            on_file(i + 1, len(all_files), kept_rows)

    if not frames:
        return pd.DataFrame(columns=RT_COLUMNS)

    out = pd.concat(frames, ignore_index=True, sort=False)
    out["fetch_timestamp"] = pd.to_datetime(out["fetch_timestamp"], errors="coerce")
    return out


def join_with_static(
    rt_df: pd.DataFrame,
    static_df: pd.DataFrame,
    on: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Left-join RT records onto a static-GTFS reference table (e.g. an export
    from the GTFS Explorer's Step 3), bringing in stop_name / route_type /
    etc. for filtering and display.

    on: join key(s), defaults to ["trip_id", "stop_id"]. Pass ["stop_id"]
    when the RT feed's trip_id namespace doesn't match the static GTFS
    trip_id (common with VDV "Globaler Code" composed identifiers) — stop_id
    (DHID) is usually stable across static and RT feeds. In that mode,
    static_df is de-duplicated by stop_id (first match kept) to avoid
    multiplying RT rows by every route serving a stop.
    Both inputs' join columns are coerced to string before the merge.
    """
    on = on or ["trip_id", "stop_id"]
    static_df = static_df.copy()
    rt_df = rt_df.copy()
    for df in (static_df, rt_df):
        for col in ("trip_id", "stop_id"):
            if col in df.columns:
                df[col] = df[col].astype(str)

    if on == ["stop_id"]:
        static_df = static_df.drop_duplicates(subset=["stop_id"])

    return rt_df.merge(static_df, on=on, how="left", suffixes=("", "_static"))


def apply_rt_filters(
    df: pd.DataFrame,
    trip_ids: Optional[List[str]] = None,
    stop_names: Optional[List[str]] = None,
    route_types: Optional[List[str]] = None,
    fetch_start: Optional[datetime] = None,
    fetch_end: Optional[datetime] = None,
    time_of_day_start: Optional[time_cls] = None,
    time_of_day_end: Optional[time_cls] = None,
    min_delay_secs: Optional[int] = None,
) -> pd.DataFrame:
    """
    Filter a (possibly static-joined) GTFS-RT DataFrame by any combination of:
      - trip_ids        : exact trip_id matches
      - stop_names      : exact stop_name matches (requires a static join)
      - route_types     : route_type matches, compared as strings (requires a static join)
      - fetch_start/end : inclusive fetch_timestamp range (full datetime)
      - time_of_day_start/end : inclusive time-of-day window applied to fetch_timestamp,
                                e.g. only keep records fetched between 06:00 and 09:00
      - min_delay_secs  : keep rows where |arrival_delay| or |departure_delay| >= this value
    """
    out = df

    if trip_ids:
        out = out[out["trip_id"].astype(str).isin(trip_ids)]

    if stop_names and "stop_name" in out.columns:
        out = out[out["stop_name"].isin(stop_names)]

    if route_types and "route_type" in out.columns:
        out = out[out["route_type"].astype(str).isin(route_types)]

    if fetch_start is not None:
        out = out[out["fetch_timestamp"] >= fetch_start]

    if fetch_end is not None:
        out = out[out["fetch_timestamp"] <= fetch_end]

    if time_of_day_start is not None and time_of_day_end is not None:
        tod = out["fetch_timestamp"].dt.time
        if time_of_day_start <= time_of_day_end:
            out = out[(tod >= time_of_day_start) & (tod <= time_of_day_end)]
        else:
            # Window wraps past midnight, e.g. 22:00 -> 02:00
            out = out[(tod >= time_of_day_start) | (tod <= time_of_day_end)]

    if min_delay_secs is not None:
        delay_cols = [c for c in ("arrival_delay", "departure_delay") if c in out.columns]
        if delay_cols:
            mask = pd.Series(False, index=out.index)
            for c in delay_cols:
                mask = mask | (out[c].abs() >= min_delay_secs)
            out = out[mask.fillna(False)]

    return out


_PLOT_POINT_LIMIT = 20_000
_LOESS_POINT_LIMIT = 5_000


def plot_delay_trend(df: pd.DataFrame, delay_col: str = "departure_delay"):
    """
    Build a scatter plot of `delay_col` (seconds) over fetch_timestamp.
    If a 'route_type' column is present (from a static join), points are
    colour-coded by route type and groups with enough points get a LOESS
    trend line. Returns a matplotlib Figure — caller is responsible for
    displaying/closing it.

    Large inputs are randomly downsampled to _PLOT_POINT_LIMIT points (and
    LOESS is skipped for groups over _LOESS_POINT_LIMIT) to keep rendering
    fast regardless of how much data was loaded.
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    plot_df = df.dropna(subset=[delay_col, "fetch_timestamp"])
    fig, ax = plt.subplots(figsize=(12, 5))

    if plot_df.empty:
        ax.set_title(f"No {delay_col} data to plot")
        return fig

    title_suffix = ""
    if len(plot_df) > _PLOT_POINT_LIMIT:
        plot_df = plot_df.sample(_PLOT_POINT_LIMIT, random_state=42)
        title_suffix = f" (random sample of {_PLOT_POINT_LIMIT:,} / {len(df):,} rows)"

    if "route_type" in plot_df.columns:
        for rt_value, subset in plot_df.groupby("route_type"):
            ax.scatter(
                subset["fetch_timestamp"], subset[delay_col],
                alpha=0.5, s=10, label=f"route_type={rt_value}",
            )
            if 5 < len(subset) <= _LOESS_POINT_LIMIT:
                try:
                    from statsmodels.nonparametric.smoothers_lowess import lowess
                    x = mdates.date2num(subset["fetch_timestamp"])
                    y = subset[delay_col].values
                    smoothed = lowess(y, x, frac=0.2, return_sorted=True)
                    ax.plot(mdates.num2date(smoothed[:, 0]), smoothed[:, 1], linewidth=2)
                except Exception:
                    pass
        ax.legend(fontsize=8)
    else:
        ax.scatter(plot_df["fetch_timestamp"], plot_df[delay_col], alpha=0.5, s=10)

    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.set_xlabel("Fetch timestamp")
    ax.set_ylabel(f"{delay_col} (seconds)")
    ax.set_title(f"{delay_col.replace('_', ' ').title()} over time{title_suffix}")
    ax.grid(True)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig

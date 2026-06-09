import io
import zipfile
from datetime import date as date_cls
from pathlib import Path
from typing import Optional

import pandas as pd

ROUTE_TYPE_NAMES: dict[str, str] = {
    "0":    "Tram / Straßenbahn",
    "1":    "U-Bahn / Metro",
    "2":    "Fernbahn (Rail)",
    "3":    "Bus",
    "4":    "Fähre (Ferry)",
    "5":    "Seilbahn",
    "101":  "Hochgeschwindigkeit (ICE)",
    "102":  "Fernverkehr (IC/EC)",
    "103":  "Interregio (DE)",
    "106":  "Regionalbahn (RB/RE)",
    "109":  "S-Bahn",
    "110":  "Schienenersatzverkehr",
    "201":  "Fernbus (international)",
    "400":  "Stadtbahn",
    "700":  "Busverkehr",
    "704":  "Stadtbus",
    "715":  "Rufbus",
    "900":  "Straßenbahn",
    "1000": "Fährverbindung",
    "1501": "Gemeinschaftstaxi",
}

CHUNK_SIZE = 500_000


class GTFSData:
    """
    Holds small GTFS tables that fit in memory.
    stop_times.txt is streamed on demand by gtfs_filter.py.
    """

    def __init__(self) -> None:
        self.routes:         Optional[pd.DataFrame] = None
        self.trips:          Optional[pd.DataFrame] = None
        self.stops:          Optional[pd.DataFrame] = None
        self.calendar:       Optional[pd.DataFrame] = None  # optional
        self.calendar_dates: Optional[pd.DataFrame] = None  # optional
        self.source_type: str = ""   # "zip" or "folder"
        self.source_path: str = ""   # absolute folder path when source_type == "folder"

    def is_loaded(self) -> bool:
        return all(df is not None for df in (self.routes, self.trips, self.stops))

    @property
    def has_calendar(self) -> bool:
        return self.calendar is not None or self.calendar_dates is not None

    def get_overview(self) -> dict:
        trips_typed = self.trips.merge(
            self.routes[["route_id", "route_type"]], on="route_id", how="left"
        )
        stats = (
            trips_typed.groupby("route_type", dropna=False)
            .size()
            .reset_index(name="trip_count")
            .sort_values("trip_count", ascending=False)
        )
        stats["route_type"] = stats["route_type"].astype(str)
        stats["label"] = stats["route_type"].map(ROUTE_TYPE_NAMES).fillna("Sonstige")
        return {
            "total_routes": len(self.routes),
            "total_trips":  len(self.trips),
            "total_stops":  len(self.stops),
            "has_calendar": self.has_calendar,
            "route_type_stats": stats,
        }

    def get_active_service_ids_in_range(self, start_date, end_date) -> Optional[set]:
        """
        Return service_ids active on at least one day within [start_date, end_date].
        Both args accept datetime.date or 'YYYYMMDD' strings.
        Returns None if no calendar data was loaded.

        Uses a single vectorised pass over calendar.txt regardless of range length,
        plus one pass over calendar_dates.txt for exception additions.
        """
        if not self.has_calendar:
            return None

        from datetime import timedelta

        def _to_date_and_str(d):
            if isinstance(d, date_cls):
                return d, d.strftime("%Y%m%d")
            s = str(d)
            return pd.Timestamp(s).date(), s

        start_date, start_str = _to_date_and_str(start_date)
        end_date,   end_str   = _to_date_and_str(end_date)

        active: set = set()

        # ── Regular schedule (calendar.txt) ───────────────────────────────────
        if self.calendar is not None and not self.calendar.empty:
            # Services whose validity period overlaps the requested range
            overlap = self.calendar[
                (self.calendar["start_date"].astype(str) <= end_str)
                & (self.calendar["end_date"].astype(str) >= start_str)
            ]
            if not overlap.empty:
                # Which day-of-week names actually appear in the requested range?
                all_weekdays = [
                    "monday", "tuesday", "wednesday", "thursday",
                    "friday", "saturday", "sunday",
                ]
                days_in_range: set = set()
                cur = start_date
                while cur <= end_date:
                    days_in_range.add(cur.strftime("%A").lower())
                    cur += timedelta(days=1)

                active_day_cols = [
                    d for d in all_weekdays
                    if d in days_in_range and d in overlap.columns
                ]
                if active_day_cols:
                    runs_on_range_day = overlap[active_day_cols].isin(["1"]).any(axis=1)
                    active.update(overlap.loc[runs_on_range_day, "service_id"])

        # ── Exception additions (calendar_dates.txt) ──────────────────────────
        if self.calendar_dates is not None and not self.calendar_dates.empty:
            in_range = self.calendar_dates[
                (self.calendar_dates["date"].astype(str) >= start_str)
                & (self.calendar_dates["date"].astype(str) <= end_str)
            ]
            added = in_range.loc[
                in_range["exception_type"].astype(str) == "1", "service_id"
            ]
            active.update(added)
            # Note: we deliberately do NOT subtract exception_type=2 removals here.
            # A service removed on one day may still run on other days in the range.

        return active

    def get_active_service_ids(self, date) -> Optional[set]:
        """
        Return service_ids active on the given date.
        date: datetime.date or 'YYYYMMDD' string.
        Returns None if no calendar data was loaded.
        """
        if not self.has_calendar:
            return None

        if isinstance(date, date_cls):
            date_str = date.strftime("%Y%m%d")
            day_name = date.strftime("%A").lower()
        else:
            date_str = str(date)
            ts = pd.Timestamp(date_str)
            day_name = ts.day_name().lower()

        active: set = set()

        # Regular weekly schedule
        if self.calendar is not None and not self.calendar.empty:
            in_range = self.calendar[
                (self.calendar["start_date"].astype(str) <= date_str)
                & (self.calendar["end_date"].astype(str) >= date_str)
            ]
            if day_name in in_range.columns:
                active.update(
                    in_range.loc[in_range[day_name].astype(str) == "1", "service_id"]
                )

        # Exception overrides
        if self.calendar_dates is not None and not self.calendar_dates.empty:
            day_rows = self.calendar_dates[
                self.calendar_dates["date"].astype(str) == date_str
            ]
            added   = day_rows.loc[day_rows["exception_type"].astype(str) == "1", "service_id"]
            removed = day_rows.loc[day_rows["exception_type"].astype(str) == "2", "service_id"]
            active.update(added)
            active -= set(removed)

        return active


# ─── public API ──────────────────────────────────────────────────────────────

def load_from_zip(zip_bytes: bytes) -> "GTFSData":
    """Load GTFS tables from an in-memory ZIP blob."""
    data = GTFSData()
    data.source_type = "zip"
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        data.routes = _read_zip_file(z, "routes.txt")
        data.trips  = _read_zip_file(z, "trips.txt")
        data.stops  = _read_zip_file(z, "stops.txt")
        data.calendar       = _try_read_zip_file(z, "calendar.txt")
        data.calendar_dates = _try_read_zip_file(z, "calendar_dates.txt")
    return data


def load_from_folder(folder_path: str) -> "GTFSData":
    """Load GTFS tables from a local folder."""
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: '{folder_path}'")
    data = GTFSData()
    data.source_type = "folder"
    data.source_path = str(folder.resolve())
    data.routes = _read_folder_file(folder, "routes.txt")
    data.trips  = _read_folder_file(folder, "trips.txt")
    data.stops  = _read_folder_file(folder, "stops.txt")
    data.calendar       = _try_read_folder_file(folder, "calendar.txt")
    data.calendar_dates = _try_read_folder_file(folder, "calendar_dates.txt")
    return data


# ─── helpers ─────────────────────────────────────────────────────────────────

def _read_zip_file(z: zipfile.ZipFile, fname: str) -> pd.DataFrame:
    names = z.namelist()
    matches = [n for n in names if n == fname or n.endswith("/" + fname)]
    if not matches:
        raise FileNotFoundError(f"'{fname}' not found in ZIP. Please confirm this is a complete GTFS feed.")
    with z.open(matches[0]) as f:
        return pd.read_csv(f, dtype=str, low_memory=False)


def _try_read_zip_file(z: zipfile.ZipFile, fname: str) -> Optional[pd.DataFrame]:
    """Like _read_zip_file but returns None instead of raising if file is absent."""
    try:
        return _read_zip_file(z, fname)
    except FileNotFoundError:
        return None


def _read_folder_file(folder: Path, fname: str) -> pd.DataFrame:
    path = folder / fname
    if not path.exists():
        raise FileNotFoundError(
            f"'{fname}' not found in folder '{folder}'. "
            "Please verify the path contains a complete GTFS feed."
        )
    return pd.read_csv(path, dtype=str, low_memory=False)


def _try_read_folder_file(folder: Path, fname: str) -> Optional[pd.DataFrame]:
    """Like _read_folder_file but returns None instead of raising if file is absent."""
    try:
        return _read_folder_file(folder, fname)
    except FileNotFoundError:
        return None

# GTFS Explorer Dashboard

A local Streamlit dashboard for exploring, filtering, collecting, and combining
German public-transport data in GTFS Static and GTFS Realtime formats.

## Overview

This project provides three connected workflows in one browser-based app:

1. **GTFS Static Explorer**: Load a GTFS ZIP file or folder, filter routes,
   stops, trips, and service data, preview the result, and export it as CSV.
2. **GTFS-RT Explorer**: Open previously collected realtime data, restrict the
   time and geographic scope, inspect delays, and export filtered records.
3. **GTFS-RT Live Fetch**: Retrieve current TripUpdates from Mobilithek using a
   client certificate, optionally filter them with a static reference, and run
   repeated collection at a configurable interval.

The project is intended as a practical starting point for researchers and
students studying the difference between planned schedules and observed public-
transport operations.

## Features

- Load GTFS Static feeds from ZIP files or extracted folders.
- Filter by transport mode, route, stop, location, and service attributes.
- Select stops geographically on an interactive map.
- Browse large collections of previously fetched GTFS-RT records.
- Fetch nationwide German GTFS-RT TripUpdates from Mobilithek.
- Merge static schedules with realtime delay observations.
- Preview results and export analysis-ready CSV files.

## Project layout

```text
gtfs-merging-and-fusion/
├── GTFS_Static_Explorer.py       # Streamlit entry point
├── Start Dashboard.bat           # Windows double-click launcher
├── pages/
│   ├── 1_GTFS-RT_Explorer.py     # Browse collected realtime data
│   └── 2_GTFS-RT_Live_Fetch.py   # Fetch live TripUpdates
├── src/                           # Loading, filtering, fetching, and fusion
├── config/
│   ├── config.yaml                # Paths and realtime connection settings
│   ├── config.example.yaml        # Safe configuration template
│   └── configREADME.md            # Configuration reference
├── data/                          # Local input and collected data
└── output/                        # Generated exports and figures
```

## Requirements

- Windows with Python 3.9 or newer.
- A modern web browser.
- GTFS Static data for the static explorer.
- For live GTFS-RT collection: a Mobilithek account, organization access, and
  the `.p12` client certificate issued for that subscription.

See `ISG_DataSubscription.pdf` for the Mobilithek subscription procedure.

## Installation

No command-line installation is required on Windows. The launcher creates an
isolated environment and installs the packages from `requirements.txt` on its
first run.

For a manual installation:

```bash
git clone https://github.com/PPPAAP1/gtfs-merging-and-fusion.git
cd gtfs-merging-and-fusion
python -m pip install -r requirements.txt
```

## Usage

### Windows: start by double-clicking

Double-click `Start Dashboard.bat` in the project folder. On the first start,
the launcher creates a local `.dashboard-venv` environment and installs the
required packages. Later starts open the dashboard directly.

Keep the launcher window open while using the dashboard. Closing it stops the
dashboard. The older `run_app.bat` filename remains available and opens the same
launcher.

### Command line

```bash
python -m streamlit run GTFS_Static_Explorer.py
```

Streamlit opens the dashboard in the default browser. Use the sidebar to move
between the Static Explorer, GTFS-RT Explorer, and GTFS-RT Live Fetch pages.

## Configuration

Realtime acquisition is configured in `config/config.yaml`. Before fetching,
set the following values under `realtime`:

- `p12_file`: path to the Mobilithek client certificate.
- `p12_password`: password for that certificate.
- `pull_url`: TripUpdates subscription endpoint.
- `FETCH_INTERVAL_MINUTES`: interval for continuous collection.
- `output_rt_dir`: directory used for saved realtime data.

Paths, filters, fusion inputs, and output columns are documented in
`config/configREADME.md`. Use forward slashes in YAML paths on Windows.

Do not commit real certificate files or passwords to a public repository.
Both `config/config.yaml` and `*.p12` are intentionally ignored by Git. The
launcher creates `config/config.yaml` from `config/config.example.yaml` when it
is missing.

### Certificate safety

Treat the `.p12` file and its password like an account password:

- Keep the certificate only on machines that perform the realtime fetch.
- Store it outside the repository when practical and reference its local path.
- Never commit the certificate, password, or private subscription URL.
- If any of these values have previously been committed, revoke or replace the
  credential; deleting it in a later commit does not remove it from Git history.

## Data notes

- GTFS ZIP uploads are limited by Streamlit's upload configuration; use the
  local-folder option for very large feeds.
- Realtime feeds can generate large datasets. At a 12-minute interval, storage
  use can approach approximately 1 GiB per day.
- Continuous fetching runs only while the Dashboard and launcher window remain
  open.

## License

Licensed under the Apache License 2.0. See `LICENSE` for details.

## Reference

- [GTFS documentation](https://gtfs.org/documentation/overview/)

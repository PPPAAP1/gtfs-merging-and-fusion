# GTFS Explorer Dashboard

A local Streamlit application for working with German GTFS Static and GTFS
Realtime data. It supports timetable filtering, realtime collection, delay
inspection, and CSV export from one browser interface.

## Start on Windows

Double-click `Start Dashboard.bat`.

On its first run, the launcher creates a local `.dashboard-venv` environment
and installs the required packages. Later starts open the Dashboard directly.
Keep the launcher window open while using the app; closing it stops the server.

To start manually instead:

```bash
python -m pip install -r requirements.txt
python -m streamlit run GTFS_Static_Explorer.py
```

## Dashboard pages

### GTFS Static Explorer

Load a GTFS ZIP file or extracted folder, then filter by transport type, stop,
map selection, service date, or arrival/departure time. Results can be previewed,
renamed, and exported as CSV.

### GTFS-RT Explorer

Open previously collected realtime records, narrow them by date and time, inspect
delay trends, and export filtered results.

### GTFS-RT Live Fetch

Fetch current Mobilithek TripUpdates once or continuously. A static GTFS result
can optionally be used to restrict the collected trips and stops.

## Realtime configuration

The launcher creates `config/config.yaml` from the safe example when the file is
missing. Before using live fetching, set these local values under `realtime`:

- `p12_file`: path to the Mobilithek client certificate;
- `p12_password`: certificate password;
- `pull_url`: TripUpdates subscription endpoint;
- `FETCH_INTERVAL_MINUTES`: continuous-fetch interval;
- `output_rt_dir`: directory for collected realtime files.

See `config/configREADME.md` and `ISG_DataSubscription.pdf` for additional setup
information. Use forward slashes in YAML paths on Windows.

`config/config.yaml` and all `.p12` files are ignored by Git. Keep the certificate
and its password local; the repository contains only `config/config.example.yaml`.

## Project layout

```text
gtfs-merging-and-fusion/
├── GTFS_Static_Explorer.py       # Main Streamlit page
├── Start Dashboard.bat           # Windows launcher
├── pages/                         # Realtime Explorer and Live Fetch pages
├── src/                           # Loading, filtering, fetching, and fusion code
├── config/                        # Safe template and local configuration
├── data/                          # Local GTFS input and collected data
└── output/                        # Generated exports and figures
```

## Requirements

- Windows with Python 3.9 or newer;
- a modern web browser;
- GTFS Static data for timetable exploration;
- Mobilithek organization access and a `.p12` certificate for live collection.

## Data notes

- For very large GTFS feeds, use the local-folder option instead of browser upload.
- Realtime collection can approach roughly 1 GiB per day at a 12-minute interval.
- Continuous fetching stops when the Dashboard process is closed.

## License

Apache License 2.0. See `LICENSE` for details.

GTFS format documentation: [gtfs.org](https://gtfs.org/documentation/overview/).

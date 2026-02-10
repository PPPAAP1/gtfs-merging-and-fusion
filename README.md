## GTFS-RT Web Crawling Blueprint for Public Transportation data in Germany

This project provides a beginner-friendly blueprint for collecting, processing GTFS Data for German Public Transport operation.
It is desinged as a demonstration for researchers, and students who wants to work with real-time, real-world transit data.

---

## Motivation
GTFS data is widely used in transportation research and applications, the relationship between **static timetables** and **real-time operational data** is often interested in studying delay-trend, periodic operation, impact in disruptions and live-event analysis.

This project serves as a *Tutorial 101* for:
- Understanding the structure of GTFS-Static and GTFS-Realtime data
- Fetching real-time trip updates and service alerts from official German data sources (DELFI via Mobilithek)
- Demonstration of processing flow by merging and fusing static and real-time data in a simple way.

The initial research motivation is to **analyze the gap between planned schedules (GTFS-Static) and realized railway operations (GTFS-RT)**, which is a common interest, but often documented in a less "analyse-friendly" way.

---

## Features
- Filter and sort GTFS-Static data based on custom preferences (e.g. vehicle type, location)
- Fetch nationwide GTFS-Realtime trip updates and service alerts for Germany
- Merge real-time data with static schedules to obtain an overall view of system operations

## Prerequisites
- Python 3.8+
- Required dependencies listed in `requirements.txt`
- A registered account on `mobilithek.info`
- Access to a Mobilithek organization (contact your organization administrator)
- For further steps, please see XXXX

## Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/PPPAAP1/strecken-info-export
cd gtfs-merging-and-fusion
pip install -r requirements.txt
```

## Project Structure

```
├── config/                     # Configuration files (paths, parameters)
├── data/                       # Raw GTFS-Static and GTFS-Realtime data
├── output/                     # Generated CSVs and plots
├── src/                        # Source code
│   ├── gtfs_merging_fusion/                # GTFS static processing
│   │   └── fusion_finale.py                
│   └── gtfs_scraping_main/                 # GTFS realtime processing
│       └── fetch_realtime_gtfs.py          
│       └── read_route_type_gtfs.py         
│       └── read_stop_name_gtfs.py          

```

## Configuration
All of the configurations are paired with a `config.yaml`file under the folder `config`. See `ConfigREADME.MD` for more.

## License
Apache-2.0 license

## References
- [GTFS Specification Reference](https://developers.google.com/transit/gtfs/reference/extended-route-types)
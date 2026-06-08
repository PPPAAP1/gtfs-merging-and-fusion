## Configuration Overview

This `config.yaml` file sets up the GTFS and GTFS-RT data pipeline for railway operation analysis.

### Core Sections

**Project**: Defines project metadata and version information.

**Paths**: Specifies directories for static GTFS data and real-time data organized by date (YYYY-MM-DD format).

**Default Route Type**: Sets the transit modes to analyze (e.g., "106" for regional trains).

**Realtime**: Configures real-time data fetching with:
- SSL certificate authentication (p12 file and password)
- API subscription endpoint
- Fetch interval (12 minutes)
- Output directories for raw and processed RT data

**Processed/Output Directories**: Defines where cleaned data and visualizations are stored.

**Filters**: 
- Valid route types for analysis (ICE, IC, regional trains, buses, trams, S-Bahn)
- Category mapping to group similar transit modes

**Settings**: Logging configuration.

### Usage Notes

- Use forward slashes (/) in all file paths
- Stop the real-time fetcher manually with Ctrl+C
- Organize real-time data in `data/raw/rt/YYYY-MM-DD/` directories

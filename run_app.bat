@echo off
cd /d "%~dp0"
set PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
python -m streamlit run GTFS_Static_Explorer.py
pause

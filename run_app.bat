@echo off
cd /d "%~dp0"
set PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
echo Loading GTFS Explorer, please wait...
python -m pip install -r requirements.txt --quiet
python -m streamlit run GTFS_Static_Explorer.py
pause

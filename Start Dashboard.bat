@echo off
setlocal
cd /d "%~dp0"
title GTFS Explorer Dashboard

echo ========================================
echo   GTFS Explorer Dashboard
echo ========================================
echo.

set "VENV_DIR=%~dp0.dashboard-venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python"

if not exist "%~dp0config\config.yaml" (
    copy /Y "%~dp0config\config.example.yaml" "%~dp0config\config.yaml" >nul
    echo Created local config\config.yaml from the safe example.
    echo Add your Mobilithek certificate details there before live fetching.
    echo.
)

if exist "%VENV_PYTHON%" goto check_dependencies

echo First start: preparing the local Python environment...
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv "%VENV_DIR%"
)

rem Some Windows installations contain py.exe but have no Python registered
rem with it. Fall back to python.exe if the launcher did not create the venv.
if exist "%VENV_PYTHON%" goto check_dependencies
where python >nul 2>nul
if errorlevel 1 goto python_missing
python -m venv "%VENV_DIR%"

if not exist "%VENV_PYTHON%" goto environment_failed

:check_dependencies
"%VENV_PYTHON%" -c "import streamlit, pandas, numpy, yaml, folium, google.transit.gtfs_realtime_pb2" >nul 2>nul
if not errorlevel 1 goto start_dashboard

echo Installing required packages. This can take a few minutes...
"%VENV_PYTHON%" -m pip install --disable-pip-version-check -r "%~dp0requirements.txt"
if errorlevel 1 goto install_failed

:start_dashboard
echo.
echo Starting Dashboard...
echo The page will open automatically in your web browser.
echo Keep this window open while using the Dashboard.
echo Press Ctrl+C here to stop it.
echo.
"%VENV_PYTHON%" -m streamlit run "%~dp0GTFS_Static_Explorer.py"

echo.
echo The Dashboard has stopped.
pause
exit /b 0

:python_missing
echo.
echo ERROR: Python 3 is not installed or could not be found.
echo Install Python from https://www.python.org/downloads/
echo During installation, select "Add Python to PATH", then try again.
pause
exit /b 1

:environment_failed
echo.
echo ERROR: The local Python environment could not be created.
pause
exit /b 1

:install_failed
echo.
echo ERROR: Required packages could not be installed.
echo Check your internet connection and try again.
pause
exit /b 1

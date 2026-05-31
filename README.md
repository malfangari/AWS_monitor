# SMA-AWS Monitor

A real‑time weather station monitor for Vaisala AWS330 ( for now 31 MAY 2026, then other stations would be added IN SHAA ALLAH).

## Features
- Register/edit/delete stations via web UI or API
- Ingest weather data over TCP ports
- Automatic time drift detection and data quarantine
- SQLite database for reporting
- Live dashboard with station status

## Setup
1. Install dependencies: `pip install fastapi uvicorn requests`
2. Run `python main.py`
3. Run `python bridge.py` (in a separate terminal)
4. Open `http://localhost:8000`

## Configuration
- Port range: 50000–50100 (can be changed in `main.py`)
- Stations stored in SQLite (`weather.db`)
- CSV logs in `data/ingest_log.csv`

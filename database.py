import csv
import os
import sqlite3
import json
from datetime import datetime

# ---------- Generic CSV logging (parser‑agnostic) ----------
CSV_FILE = "data/ingest_log.csv"   # new file name to avoid confusion with old format
CSV_HEADERS = ["station_id", "received_at", "observed_at", "drift_seconds", "status", "all_parameters"]

def save_to_csv(station_id, received_at, observed_at, all_parameters, drift_seconds, status):
    """
    Saves a log entry with all parameters as a JSON string.
    No hardcoded tags – works with any parser.
    """
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode='a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "station_id": station_id,
            "received_at": received_at,
            "observed_at": observed_at,
            "drift_seconds": drift_seconds,
            "status": status,
            "all_parameters": json.dumps(all_parameters)
        })

# ---------- SQLite database for reporting ----------
DB_PATH = "weather.db"

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def init_database():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                port INTEGER UNIQUE NOT NULL,
                parser_type TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                last_seen TEXT,
                status TEXT DEFAULT 'offline'
            )
        ''')
        # Add updated_at column if missing (for existing databases)
        cursor.execute("PRAGMA table_info(stations)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'updated_at' not in columns:
            cursor.execute("ALTER TABLE stations ADD COLUMN updated_at TEXT")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weather_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                received_at TEXT NOT NULL,
                drift_seconds REAL,
                all_parameters TEXT NOT NULL,
                FOREIGN KEY (station_id) REFERENCES stations(station_id)
            )
        ''')
        # Add 'locked' column if missing
        cursor.execute("PRAGMA table_info(stations)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'locked' not in columns:
            cursor.execute("ALTER TABLE stations ADD COLUMN locked INTEGER DEFAULT 0")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ingestion_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id TEXT NOT NULL,
                received_at TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT,
                storage_location TEXT,
                raw_message_preview TEXT,
                drift_seconds REAL
            )
        ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS raw_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_id TEXT NOT NULL,
        received_at TEXT NOT NULL,
        raw_text TEXT NOT NULL,
        FOREIGN KEY (station_id) REFERENCES stations(station_id)
            )
        ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_raw_station ON raw_messages(station_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_raw_received ON raw_messages(received_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_weather_station ON weather_data(station_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_weather_observed ON weather_data(observed_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_station ON ingestion_log(station_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_received ON ingestion_log(received_at)')
    conn.commit()
print("✅ SQLite database initialized")
    
# --- Station CRUD ---
def get_all_stations():
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stations ORDER BY station_id")
        return [dict(row) for row in cursor.fetchall()]

def get_station_by_port(port):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stations WHERE port = ?", (port,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_station_by_id(station_id):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stations WHERE station_id = ?", (station_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def register_station_db(station_id, name, port, parser_type):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO stations (station_id, name, port, parser_type, registered_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (station_id, name, port, parser_type, datetime.now().isoformat(), 'offline'))
        conn.commit()

def update_station_db(station_id, name=None, port=None, parser_type=None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if name is not None:
            cursor.execute("UPDATE stations SET name = ? WHERE station_id = ?", (name, station_id))
        if port is not None:
            cursor.execute("UPDATE stations SET port = ? WHERE station_id = ?", (port, station_id))
        if parser_type is not None:
            cursor.execute("UPDATE stations SET parser_type = ? WHERE station_id = ?", (parser_type, station_id))
        cursor.execute("UPDATE stations SET updated_at = ? WHERE station_id = ?", (datetime.now().isoformat(), station_id))
        conn.commit()

def delete_station_db(station_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM weather_data WHERE station_id = ?", (station_id,))
        cursor.execute("DELETE FROM ingestion_log WHERE station_id = ?", (station_id,))
        cursor.execute("DELETE FROM stations WHERE station_id = ?", (station_id,))
        conn.commit()

def update_station_last_seen(station_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE stations SET last_seen = ?, status = 'online' WHERE station_id = ?",
                       (datetime.now().isoformat(), station_id))
        conn.commit()

# --- Weather data and logging ---
def save_weather_data(station_id, observed_at, received_at, drift_seconds, all_parameters_json):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO weather_data (station_id, observed_at, received_at, drift_seconds, all_parameters)
            VALUES (?, ?, ?, ?, ?)
        ''', (station_id, observed_at, received_at, drift_seconds, all_parameters_json))
        conn.commit()

def log_ingestion(station_id, status, reason, storage_location, raw_message_preview, drift_seconds):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ingestion_log (
                station_id, received_at, status, reason, storage_location,
                raw_message_preview, drift_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            station_id, datetime.now().isoformat(), status, reason,
            storage_location, raw_message_preview, drift_seconds
        ))
        conn.commit()

# --- Dashboard status helper ---
def get_station_status_for_dashboard():
    stations = get_all_stations()
    result = {}
    for station in stations:
        sid = station['station_id']
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Get latest weather data (any status)
            cursor.execute('''
                SELECT all_parameters, observed_at, drift_seconds
                FROM weather_data
                WHERE station_id = ?
                ORDER BY observed_at DESC LIMIT 1
            ''', (sid,))
            latest = cursor.fetchone()
            # Get last successful or warning ingestion (ignore FAILED)
            cursor.execute('''
                SELECT received_at, status FROM ingestion_log
                WHERE station_id = ? AND status != 'FAILED'
                ORDER BY received_at DESC LIMIT 1
            ''', (sid,))
            last_success = cursor.fetchone()

        if last_success:
            last_received_iso = last_success['received_at']
            last_received = last_received_iso[:19]
            last_time = datetime.fromisoformat(last_received_iso)
            seconds_ago = (datetime.now() - last_time).total_seconds()
            if seconds_ago <= 300:
                status = 'warning' if last_success['status'] == 'WARNING' else 'online'
            elif seconds_ago <= 600:
                status = 'warning'
            else:
                status = 'offline'
        else:
            last_received = 'Never'
            last_received_iso = None
            status = 'offline'

        if latest:
            data = json.loads(latest['all_parameters'])
        else:
            data = {}

        result[sid] = {
            "name": station['name'],
            "last_received": last_received,
            "last_received_iso": last_received_iso,
            "status": status,
            "data": data,
            "drift_seconds": latest['drift_seconds'] if latest else None,
            "port": station['port'],
            "parser_type": station['parser_type']
        }
    return result
# --- Optional migration from old stations.json ---
def migrate_stations_from_json():
    if not os.path.exists("stations.json"):
        return
    with open("stations.json", "r") as f:
        stations_json = json.load(f)
    for sid, cfg in stations_json.items():
        if not get_station_by_id(sid):
            register_station_db(
                station_id=sid,
                name=cfg.get("name", sid),
                port=cfg.get("port", 0),
                parser_type=cfg.get("parser", "Vaisala")
            )
            print(f"Migrated station {sid}")
    print("Migration from stations.json complete")

# ---------- Raw messages for Port Monitor ----------
def save_raw_message(station_id, raw_text):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO raw_messages (station_id, received_at, raw_text)
            VALUES (?, ?, ?)
        ''', (station_id, datetime.now().isoformat(), raw_text))
        conn.commit()

def get_recent_raw_messages(station_id, limit=50):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT received_at, raw_text FROM raw_messages
            WHERE station_id = ?
            ORDER BY received_at DESC LIMIT ?
        ''', (station_id, limit))
        return [dict(row) for row in cursor.fetchall()]

def set_station_lock(station_id, locked=True):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Ensure the 'locked' column exists (create if missing)
        cursor.execute("PRAGMA table_info(stations)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'locked' not in columns:
            cursor.execute("ALTER TABLE stations ADD COLUMN locked INTEGER DEFAULT 0")
        cursor.execute("UPDATE stations SET locked = ? WHERE station_id = ?", (1 if locked else 0, station_id))
        conn.commit()

def is_station_locked(station_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT locked FROM stations WHERE station_id = ?", (station_id,))
        row = cursor.fetchone()
        return row and row[0] == 1
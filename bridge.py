import socket
import threading
import requests
import time
import sqlite3
import os

API_URL = "http://127.0.0.1:8000/ingest"
DB_PATH = "weather.db"

def load_stations_from_db():
    """Load stations directly from SQLite database."""
    if not os.path.exists(DB_PATH):
        print(f"⚠️ Database {DB_PATH} not found. Start main.py first.")
        return {}
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT station_id, port FROM stations")
        rows = cursor.fetchall()
        conn.close()
        # Return {port: station_id}
        return {row['port']: row['station_id'] for row in rows}
    except Exception as e:
        print(f"❌ Error reading database: {e}")
        return {}

def handle_station(port, station_name):
    """Listen on a single port and forward data."""
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('0.0.0.0', port))
                s.listen(5)
                print(f"📡 Bridge listening for '{station_name}' on port {port}")
                while True:
                    conn, addr = s.accept()
                    with conn:
                        data = conn.recv(4096).decode('utf-8', errors='ignore')
                        if data:
                            print(f"📩 Data from {station_name} ({addr}): {data[:100]}...")
                            try:
                                resp = requests.post(
                                    f"{API_URL}/{port}",
                                    data=data,
                                    headers={"Content-Type": "text/plain"},
                                    timeout=5
                                )
                                if resp.status_code == 200:
                                    print(f"✅ Forwarded")
                                else:
                                    print(f"❌ API error {resp.status_code}: {resp.text[:100]}")
                            except Exception as e:
                                print(f"⚠️ Forward error: {e}")
        except OSError as e:
            print(f"⚠️ Port {port} in use or unavailable: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"⚠️ Listener on port {port} crashed: {e}")
            time.sleep(5)

def start_bridge():
    print("=" * 50)
    print("SMA-AWS Bridge (SQLite version)")
    print("=" * 50)
    print(f"Forwarding to: {API_URL}")
    print("Monitoring database for stations...\n")

    active_ports = set()
    threads = {}

    while True:
        stations = load_stations_from_db()   # {port: station_id}
        current_ports = set(stations.keys())

        # Stop threads for ports that no longer exist
        for port in list(active_ports):
            if port not in current_ports:
                print(f"🛑 Removing listener on port {port}")
                # Thread cannot be forcibly stopped; it will exit on its own.
                # We simply stop tracking it.
                if port in threads:
                    del threads[port]
                active_ports.remove(port)

        # Start threads for new ports
        for port in current_ports:
            if port not in active_ports:
                station_name = stations[port]
                t = threading.Thread(target=handle_station, args=(port, station_name), daemon=True)
                t.start()
                threads[port] = t
                active_ports.add(port)
                print(f"🚀 Started listener for {station_name} on port {port}")

        time.sleep(10)   # check every 10 seconds

if __name__ == "__main__":
    try:
        start_bridge()
    except KeyboardInterrupt:
        print("\n🛑 Bridge stopped.")
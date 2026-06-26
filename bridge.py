import socket
import threading
import requests
import time
import sqlite3
import os
from database import get_station_mode

API_URL = "http://127.0.0.1:8000/ingest"
DB_PATH = "weather.db"

# Global dict to hold listener sockets and their threads
listeners = {}  # port -> {'socket': sock, 'thread': thread, 'running': bool}

def load_stations():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT station_id, port, mode FROM stations")
    rows = cursor.fetchall()
    conn.close()
    return {row['port']: {'station_id': row['station_id'], 'mode': row['mode']} for row in rows}

def handle_connection(port, station_id, conn_sock, addr):
    """Handle a single connection from the station."""
    try:
        data = conn_sock.recv(4096).decode('utf-8', errors='ignore')
        if not data:
            return
        # Check mode at the moment of data receipt
        mode = get_station_mode(station_id)  # function to query DB
        if mode == 'terminal':
            # Do not forward; the station expects terminal, not data
            return
        # Forward to API
        response = requests.post(f"{API_URL}/{port}", data=data, headers={"Content-Type": "text/plain"}, timeout=5)
        if response.status_code == 200:
            print(f"✅ Forwarded data from {station_id}")
        else:
            print(f"❌ API error {response.status_code} for {station_id}")
    except Exception as e:
        print(f"⚠️ Error handling connection on port {port}: {e}")

def listener_thread(port, station_id):
    """Main listener loop for a port. Re‑creates the socket if mode changes."""
    while True:
        # Check mode
        mode = get_station_mode(station_id)
        if mode == 'terminal':
            # If terminal mode, release the port and wait
            if port in listeners and listeners[port].get('socket'):
                try:
                    listeners[port]['socket'].close()
                except:
                    pass
                listeners[port]['socket'] = None
                print(f"🔌 Port {port} released for terminal mode ({station_id})")
            time.sleep(2)
            continue

        # Data mode: ensure socket is open
        if port not in listeners or listeners[port].get('socket') is None:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('0.0.0.0', port))
                sock.listen(5)
                listeners[port] = {'socket': sock, 'running': True}
                print(f"📡 Data listener started on port {port} ({station_id})")
            except Exception as e:
                print(f"❌ Failed to bind port {port}: {e}")
                time.sleep(5)
                continue

        # Accept connections
        try:
            sock = listeners[port]['socket']
            sock.settimeout(2)  # so we can check mode periodically
            conn, addr = sock.accept()
            # Handle connection in a separate thread
            t = threading.Thread(target=handle_connection, args=(port, station_id, conn, addr), daemon=True)
            t.start()
        except socket.timeout:
            continue
        except Exception as e:
            print(f"⚠️ Error on port {port}: {e}")
            time.sleep(1)

def start_bridge():
    print("="*50)
    print("SMA-AWS Bridge (NM10‑style dynamic mode)")
    print("="*50)
    stations = load_stations()
    for port, info in stations.items():
        t = threading.Thread(target=listener_thread, args=(port, info['station_id']), daemon=True)
        t.start()
        print(f"🚀 Listener for {info['station_id']} on port {port} (mode: {info['mode']})")

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Bridge stopped.")

if __name__ == "__main__":
    try:
        start_bridge()
    except KeyboardInterrupt:
        print("\n🛑 Bridge stopped.")
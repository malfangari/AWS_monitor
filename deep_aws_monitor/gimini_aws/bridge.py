import socket
import threading
import requests

# CONFIGURATION: Add your station ports here
STATIONS = {
    5001: "Station_Alpha",
    5002: "Station_Bravo",
    5003: "Station_Charlie",
    5004: "rrrr"

}

API_URL = "http://127.0.0.1:8000/ingest"

def handle_station(port, station_name):
    """Listens to a specific TCP port for Vaisala data"""
    # Create a TCP/IP socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Allow the port to be reused immediately after restart
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', port))
        s.listen()
        print(f"📡 Bridge listening for {station_name} on port {port}...")

        while True:
            conn, addr = s.accept()
            with conn:
                try:
                    # Receive the data (Vaisala messages are usually < 4096  bytes 4KB)
                    raw_data = conn.recv(4096).decode('utf-8', errors='ignore')
                    if raw_data:
                        print(f"📩 Data received from {addr} on port {port}")
                        
                        # Forward the raw string to the SMA-AWS Monitor API
                        response = requests.post(API_URL, data=raw_data)
                        
                        if response.status_code == 200:
                            print(f"✅ Successfully forwarded to API")
                        else:
                            print(f"❌ API Error: {response.status_code}")
                except Exception as e:
                    print(f"⚠️ Error on port {port}: {e}")

def start_bridge():
    threads = []
    for port, name in STATIONS.items():
        # Start a new thread for every port in our list
        t = threading.Thread(target=handle_station, args=(port, name), daemon=True)
        t.start()
        threads.append(t)
    
    # Keep the main thread alive
    for t in threads:
        t.join()

if __name__ == "__main__":
    try:
        start_bridge()
    except KeyboardInterrupt:
        print("\n🛑 Bridge shutting down.")
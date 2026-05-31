import socket
import threading
import requests
import time

# CONFIGURATION: This will be overridden by stations.json
# But keep as fallback or for first run
STATIONS = {
    # Example: 5001: "Station_Alpha"
}

API_URL = "http://127.0.0.1:8000/ingest"

def load_stations_from_api():
    """Try to load stations from the main app's registry"""
    try:
        # We can't read stations.json directly from bridge without path,
        # so we'll rely on the API telling us which ports to listen on
        # For now, use manual config or environment variables
        return STATIONS
    except:
        return STATIONS

def handle_station(port, station_name):
    """Listens to a specific TCP port for Vaisala data"""
    try:
        # Create a TCP/IP socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Allow the port to be reused immediately after restart
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('0.0.0.0', port))
            s.listen(5)
            print(f"📡 Bridge listening for {station_name} on port {port}...")
            
            while True:
                try:
                    conn, addr = s.accept()
                    with conn:
                        # Receive the data
                        raw_data = conn.recv(4096).decode('utf-8', errors='ignore')
                        if raw_data:
                            print(f"📩 Data received from {addr} on port {port}")
                            print(f"   Raw: {raw_data[:100]}...")  # First 100 chars
                            
                            # Forward to API - important: use params, not data
                            # The endpoint expects port as path parameter
                            response = requests.post(
                                f"{API_URL}/{port}",  # Port in URL path
                                data=raw_data,  # Send as raw text
                                headers={"Content-Type": "text/plain"},
                                timeout=5
                            )
                            
                            if response.status_code == 200:
                                print(f"✅ Successfully forwarded to API")
                            else:
                                print(f"❌ API Error: {response.status_code} - {response.text}")
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"⚠️ Connection error on port {port}: {e}")
                    time.sleep(1)  # Prevent tight loop on error
    except Exception as e:
        print(f"❌ Failed to bind to port {port}: {e}")

def start_bridge():
    """Start bridge with stations from config"""
    stations = load_stations_from_api()
    
    if not stations:
        print("⚠️ No stations configured. Using example configuration.")
        print("   Add stations via web admin at http://localhost:8000/admin")
        print("   Then update bridge.py with the port numbers")
        stations = {
            5001: "Example_Station_1",
            5002: "Example_Station_2",
        }
    
    threads = []
    for port, name in stations.items():
        # Start a new thread for every port
        t = threading.Thread(target=handle_station, args=(port, name), daemon=True)
        t.start()
        threads.append(t)
        print(f"🚀 Started thread for {name} on port {port}")
    
    # Keep the main thread alive
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\n🛑 Bridge shutting down.")

if __name__ == "__main__":
    print("=" * 50)
    print("SMA-AWS Data Bridge")
    print("=" * 50)
    print(f"Forwarding to: {API_URL}")
    print("Press Ctrl+C to stop\n")
    
    try:
        start_bridge()
    except KeyboardInterrupt:
        print("\n🛑 Bridge stopped.")
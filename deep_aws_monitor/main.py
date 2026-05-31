from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import json
import os
import sys

from parser import PARSER_MAP, get_friendly_name
from database import save_to_csv

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# File Paths
STATIONS_FILE = "stations.json"
QUARANTINE_ROOT = "data_issues"
DRIFT_LOG = "drift_log.json"

# Create directories if they don't exist
os.makedirs(QUARANTINE_ROOT, exist_ok=True)
os.makedirs("data", exist_ok=True)  # Ensure data directory exists for CSV

# Global Status for the Dashboard
latest_status = {}

def get_registry():
    if os.path.exists(STATIONS_FILE):
        with open(STATIONS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_registry(registry):
    with open(STATIONS_FILE, "w") as f:
        json.dump(registry, f, indent=4)

def save_raw_quarantine(station_id, raw_msg, reason):
    """Save problematic messages to quarantine"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filename = f"{QUARANTINE_ROOT}/{station_id}_{timestamp}.txt"
    with open(filename, "w") as f:
        f.write(f"Reason: {reason}\n")
        f.write(f"Received: {datetime.now().isoformat()}\n")
        f.write(f"Raw Message:\n{raw_msg}\n")

def calculate_time_drift(reported_timestamp):
    """Calculate drift between reported time and server time"""
    if not reported_timestamp:
        return None
    
    try:
        # Parse the reported timestamp
        reported_time = datetime.fromisoformat(reported_timestamp)
        current_time = datetime.now()
        drift = (current_time - reported_time).total_seconds()
        return drift
    except:
        return None

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html", context={}
    )

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="admin.html", context={}
    )

@app.post("/admin/register")
async def register_station(
    station_id: str = Form(...),
    name: str = Form(...),
    port: int = Form(...),
    parser_type: str = Form(...)
):
    registry = get_registry()
    
    registry[station_id] = {
        "name": name,
        "port": port,
        "parser": parser_type,
        "registered_at": datetime.now().isoformat()
    }
    
    save_registry(registry)
    
    # Initialize status for this station
    latest_status[station_id] = {
        "name": name,
        "last_received": "Never",
        "last_received_iso": None,
        "status": "unknown",
        "data": {},
        "labels": {}
    }
    
    return RedirectResponse(url="/", status_code=303)

@app.get("/monitor")
async def get_monitor_data():
    """Returns the latest status of all stations for the UI"""
    return latest_status

@app.post("/ingest/{port}")
async def ingest(port: int, request: Request):
    """Receives live weather data, parses it, and updates the dashboard"""
    raw_payload = await request.body()
    raw_msg = raw_payload.decode('utf-8', errors='ignore').strip()
    
    if not raw_msg:
        return {"error": "Empty payload"}
    
    registry = get_registry()
    
    # Identify the station by the port it arrived on
    target_id = None
    for sid, cfg in registry.items():
        if cfg['port'] == port:
            target_id = sid
            break
    
    if not target_id:
        save_raw_quarantine("unknown", raw_msg, f"Port {port} not registered")
        return {"error": f"Port {port} not registered"}
    
    station_config = registry[target_id]
    parser_name = station_config['parser']
    
    # Check if parser exists
    if parser_name not in PARSER_MAP or PARSER_MAP[parser_name] is None:
        save_raw_quarantine(target_id, raw_msg, f"Parser '{parser_name}' not implemented")
        return {"error": f"Parser '{parser_name}' not available"}
    
    # Parse the message
    try:
        parsed_result = PARSER_MAP[parser_name](raw_msg)
        
        if parsed_result is None:
            save_raw_quarantine(target_id, raw_msg, "Parser returned None (invalid format)")
            return {"error": "Invalid message format"}
        
        # Extract data
        station_id = parsed_result.get("station_id", target_id)
        timestamp = parsed_result.get("timestamp")
        data = parsed_result.get("data", {})
        
        # Calculate time drift if timestamp exists
        drift = None
        status = "online"
        
        if timestamp:
            drift = calculate_time_drift(timestamp)
            # Flag as warning if drift > 5 minutes (300 seconds)
            if drift and abs(drift) > 300:
                status = "warning"
        
        # Save to CSV using database.py
        try:
            # Add metadata to data dict for CSV export
            data_with_meta = data.copy()
            data_with_meta["S"] = station_id
            if parsed_result.get("raw_date"):
                data_with_meta["D"] = parsed_result.get("raw_date")
            if parsed_result.get("raw_time"):
                data_with_meta["T"] = parsed_result.get("raw_time")
            
            save_to_csv(data_with_meta)
            print(f"✅ Saved to CSV: {station_id}")
        except Exception as e:
            print(f"⚠️ CSV save error: {e}")
        
        # Update global status for dashboard
        friendly_labels = {}
        for key in data.keys():
            friendly_labels[key] = get_friendly_name(key)
        
        latest_status[station_id] = {
            "name": station_config.get("name", station_id),
            "last_received": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_received_iso": datetime.now().isoformat(),
            "status": status,
            "data": data,
            "labels": friendly_labels,
            "drift_seconds": drift
        }
        
        return {"status": "ok", "station": station_id}
        
    except Exception as e:
        save_raw_quarantine(target_id, raw_msg, f"Unexpected error: {str(e)}")
        return {"error": f"Processing error: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
from fastapi import Request, Form # type: ignore
from fastapi.responses import RedirectResponse # type: ignore
from parser import PARSER_MAP, get_friendly_name
from fastapi import FastAPI, Request, Form # type: ignore
from fastapi.responses import HTMLResponse, RedirectResponse # type: ignore
from fastapi.templating import Jinja2Templates # type: ignore
import json, os, re, datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# File Paths
STATIONS_FILE = "stations.json"
QUARANTINE_ROOT = "data_issues"
CLEAN_ROOT = "data_records"

# Global Status for the Dashboard
latest_status = {}

def get_registry():
    if os.path.exists(STATIONS_FILE):
        with open(STATIONS_FILE, "r") as f:
            return json.load(f)
    return {}

import json

def save_registry(registry):
    with open("stations.json", "w") as f:
        json.dump(registry, f, indent=4)
        
# --- PARSER FACTORY ---
def parse_vaisala(raw_msg):
    data = {}
    # Simple regex to catch key=value pairs
    tags = re.findall(r'([A-Za-z]+)=([-+]?\d*\.\d+|\d+)', raw_msg)
    for tag, val in tags:
        data[tag] = float(val)
    
    s_match = re.search(r'S=([^,]+)', raw_msg)
    t_match = re.search(r'T=([^, \r\n]+)', raw_msg)
    
    return {
        "station_id": s_match.group(1) if s_match else "Unknown",
        "time_str": t_match.group(1) if t_match else None,
        "parameters": data
    }

PARSERS = {"Vaisala": parse_vaisala}

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Ensure "request" is inside the context dictionary
    return templates.TemplateResponse(
        request=request, name="index.html", context={}
    )

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="admin.html", context={}
    )
# --- ROUTE 1: THE ADMIN (For You) ---
@app.post("/admin/register")
async def register_station(
    station_id: str = Form(...),
    name: str = Form(...),
    port: int = Form(...),
    parser_type: str = Form(...)  # This matches your HTML <select name="parser_type">
):
    registry = get_registry()
    
    # Save to stations.json
    registry[station_id] = {
        "name": name,
        "port": port,
        "parser": parser_type
    }
    
    save_registry(registry)
    
    # After registering, redirect back to the dashboard
    return RedirectResponse(url="/", status_code=303) 
@app.get("/monitor")
async def get_monitor_data():
    """Returns the latest status of all stations for the UI"""
    return latest_status

# --- ROUTE 2: THE INGEST (For the AWS Stations) ---
@app.post("/ingest/{port}")
async def ingest(port: int, request: Request):
    """Receives live weather data, parses it, and updates the dashboard"""
    raw_payload = await request.body()
    raw_msg = raw_payload.decode('utf-8')
    registry = get_registry()
    
    # Identify the station by the port it arrived on
    target_id = next((sid for sid, cfg in registry.items() if cfg['port'] == port), None)
    
    if not target_id:
        return {"error": "Port not registered"}

    # Get the parser name from registry (e.g., 'Vaisala')
    parser_name = registry[target_id]['parser']
    
    # Use the PARSER_MAP from your parsers.py file
    parsed = PARSER_MAP[parser_name](raw_msg)
    
    # ... (Rest of your drift calculation and storage logic) ...
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn # type: ignore
    # Start the server on all local IPs at port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
from fastapi import FastAPI, Request, Form, HTTPException # type: ignore
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse # type: ignore
from fastapi.templating import Jinja2Templates # type: ignore
from datetime import datetime
from datetime import timedelta
import json
import os
import sqlite3
from parser import PARSER_MAP, get_friendly_name
from parser import FRIENDLY_NAMES

from database import (
    init_database,
    get_all_stations,
    get_station_by_port,
    get_station_by_id,
    register_station_db,
    update_station_db,
    delete_station_db,
    update_station_last_seen,
    save_weather_data,
    log_ingestion,
    get_station_status_for_dashboard,
    save_raw_message,
    get_recent_raw_messages,
    set_station_lock,
    is_station_locked,
    save_to_csv, # keep existing CSV function
    get_db_connection 
)

app = FastAPI()
templates_env = Jinja2Templates(directory="templates")

def is_ajax_request(request: Request) -> bool:
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

# Directories
QUARANTINE_ROOT = "data_issues"
os.makedirs(QUARANTINE_ROOT, exist_ok=True)
os.makedirs("data", exist_ok=True)

# Port range validation
MIN_PORT = 50000
MAX_PORT = 50100

def is_valid_port(port: int) -> bool:
    return MIN_PORT <= port <= MAX_PORT

def save_raw_quarantine(station_id, raw_msg, reason):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filename = f"{QUARANTINE_ROOT}/{station_id}_{timestamp}.txt"
    with open(filename, "w") as f:
        f.write(f"Reason: {reason}\n")
        f.write(f"Received: {datetime.now().isoformat()}\n")
        f.write(f"Raw Message:\n{raw_msg}\n")

def calculate_time_drift(reported_timestamp):
    if not reported_timestamp:
        return None
    try:
        reported_time = datetime.fromisoformat(reported_timestamp)
        current_time = datetime.now()
        return (current_time - reported_time).total_seconds()
    except:
        return None

# ---------- Routes ----------

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    parsers = [name for name, func in PARSER_MAP.items() if func is not None]
    return templates_env.TemplateResponse(
        request=request,
        name="index.html",
        context={"parsers": parsers}
    )
"""@app.get("/", response_class=HTMLResponse)
async def admin_page(request: Request, error: str = None):
    return templates_env.TemplateResponse(request=request, name="admin.html", context={"error": error})"""

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, error: str = None):
    # Get all implemented parsers from PARSER_MAP
    parsers = [name for name, func in PARSER_MAP.items() if func is not None]
    return templates_env.TemplateResponse(
        request=request,
        name="admin.html",
        context={"error": error, "parsers": parsers}
    )
@app.post("/admin/register")
async def register_station(
    request: Request,
    station_id: str = Form(...),
    name: str = Form(...),
    port: int = Form(...),
    parser_type: str = Form(...)
):
    # Validate port range
    if not is_valid_port(port):
        error_msg = f"Port must be between {MIN_PORT} and {MAX_PORT}"
        if is_ajax_request(request):
            return JSONResponse(status_code=400, content={"error": error_msg})
        return RedirectResponse(url=f"/admin?error={error_msg}", status_code=303)

    # Check if station_id already exists
    if get_station_by_id(station_id):
        error_msg = f"Station ID '{station_id}' is already registered"
        if is_ajax_request(request):
            return JSONResponse(status_code=409, content={"error": error_msg})
        return RedirectResponse(url=f"/admin?error={error_msg}", status_code=303)

    # Check if port already used by another station
    existing = get_station_by_port(port)
    if existing and existing['station_id'] != station_id:
        error_msg = f"Port {port} is already used by station {existing['station_id']}"
        if is_ajax_request(request):
            return JSONResponse(status_code=409, content={"error": error_msg})
        return RedirectResponse(url=f"/admin?error={error_msg}", status_code=303)

    # Register in database
    register_station_db(station_id, name, port, parser_type)
    return RedirectResponse(url="/", status_code=303)

@app.delete("/admin/delete/{station_id}")
async def delete_station(station_id: str):
    if not get_station_by_id(station_id):
        raise HTTPException(status_code=404, detail="Station not found")
    delete_station_db(station_id)
    return {"status": "success"}

@app.put("/admin/edit/{station_id}")
async def edit_station(
    request: Request,
    station_id: str,
    name: str = Form(...),
    port: int = Form(...),
    parser_type: str = Form(...)
):
    if not is_valid_port(port):
        error_msg = f"Port must be between {MIN_PORT} and {MAX_PORT}"
        if is_ajax_request(request):
            return JSONResponse(status_code=400, content={"error": error_msg})
        return RedirectResponse(url=f"/?error={error_msg}", status_code=303)

    # Check port conflict with a DIFFERENT station
    existing = get_station_by_port(port)
    if existing and existing['station_id'] != station_id:
        error_msg = f"Port {port} already used by station {existing['station_id']}"
        if is_ajax_request(request):
            return JSONResponse(status_code=409, content={"error": error_msg})
        return RedirectResponse(url=f"/?error={error_msg}", status_code=303)

    # Update station
    update_station_db(station_id, name=name, port=port, parser_type=parser_type)
    return RedirectResponse(url="/", status_code=303)

@app.get("/monitor")
async def get_monitor_data():
    """Returns the latest status from database (replaces in‑memory latest_status)"""
    status_data = get_station_status_for_dashboard()
    # Add friendly labels
    for sid, station in status_data.items():
        labels = {}
        for key in station.get('data', {}).keys():
            labels[key] = get_friendly_name(key)
        station['labels'] = labels
    return status_data
from jinja2 import Environment, FileSystemLoader
from fastapi.responses import HTMLResponse # type: ignore

@app.get("/report")
async def report_form(request: Request):
    # Compute default date range: last 30 days
    now = datetime.now()
    default_end = now.strftime("%Y-%m-%dT%H:%M")
    default_start = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M")

    # Create a fresh Jinja2 environment for this request only
    jinja_env = Environment(loader=FileSystemLoader("templates"))
    template = jinja_env.get_template("report.html")
    
    stations = get_all_stations()
    elements = {k: v for k, v in FRIENDLY_NAMES.items() if k not in ['S','D','T']}
    
    html_content = template.render(
        request=request,
        stations=stations,
        elements=elements,
        selected_stations=[],
        selected_elements=[],
        start_time=default_start,
        end_time=default_end,
        rows=None
    )
    return HTMLResponse(content=html_content)

from fastapi.responses import HTMLResponse # type: ignore
from jinja2 import Environment, FileSystemLoader

@app.post("/report")
async def generate_report(
    request: Request,
    stations: list[str] = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    elements: list[str] = Form(...)
):
    stations_list = stations
    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)
    selected_elements = elements

    # Build SQL query
    select_clauses = ["station_id", "observed_at"]
    for elem in selected_elements:
        select_clauses.append(f"json_extract(all_parameters, '$.{elem}') as {elem}")
    select_str = ", ".join(select_clauses)

    placeholders = ','.join(['?' for _ in stations_list])
    query = f"""
        SELECT {select_str}
        FROM weather_data
        WHERE station_id IN ({placeholders})
          AND observed_at BETWEEN ? AND ?
        ORDER BY observed_at ASC
    """
    params = stations_list + [start_dt.isoformat(), end_dt.isoformat()]

    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]

    # Add station names
    station_names = {s['station_id']: s['name'] for s in get_all_stations()}
    for row in rows:
        row['station_name'] = station_names.get(row['station_id'], row['station_id'])

    # Determine which elements actually have any non‑null data in the result set
    visible_elements = []
    for elem in selected_elements:
        if any(row.get(elem) is not None for row in rows):
            visible_elements.append(elem)

    stations_all = get_all_stations()
    from parser import FRIENDLY_NAMES
    elements_all = {k: v for k, v in FRIENDLY_NAMES.items() if k not in ['S', 'D', 'T']}

    # Create a fresh Jinja2 environment for rendering
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("report.html")
    html_content = template.render(
        request=request,
        stations=stations_all,
        elements=elements_all,
        selected_stations=stations_list,
        selected_elements=selected_elements,
        visible_elements=visible_elements,   # ← new variable
        start_time=start_time,
        end_time=end_time,
        rows=rows
    )
    return HTMLResponse(content=html_content)

@app.post("/ingest/{port}")
async def ingest(port: int, request: Request):
    raw_payload = await request.body()
    raw_msg = raw_payload.decode('utf-8', errors='ignore').strip()
    raw_preview = raw_msg[:100] + "..." if len(raw_msg) > 100 else raw_msg

    if not raw_msg:
        return {"error": "Empty payload"}

    # Find station by port
    station = get_station_by_port(port)
    if not station:
        save_raw_quarantine("unknown", raw_msg, f"Port {port} not registered")
        return {"error": f"Port {port} not registered"}
    station_id = station['station_id']
    parser_name = station['parser_type']

    # Save raw message for later retrieval (Port Monitor)
    save_raw_message(station_id, raw_msg)
    
    #check if station is locked (remote access active)
    if is_station_locked(station_id):
         return {"status": "locked", "message": "Remote access active, data not processed"}
    
    print(f"DEBUG: Using parser '{parser_name}' for station {station_id}")
    if parser_name not in PARSER_MAP or PARSER_MAP[parser_name] is None:
        save_raw_quarantine(station_id, raw_msg, f"Parser '{parser_name}' not implemented")
        return {"error": f"Parser '{parser_name}' not available"}

    try:
        parsed_result = PARSER_MAP[parser_name](raw_msg)
        if parsed_result is None:
            save_raw_quarantine(station_id, raw_msg, "Parser returned None (invalid format)")
            return {"error": "Invalid message format"}

        message_station_id = parsed_result.get("station_id", station_id)
        timestamp = parsed_result.get("timestamp")
        data = parsed_result.get("data", {})

        # Validate station ID from message matches registered station
        if message_station_id != station_id:
            reason = f"Station ID mismatch: message says '{message_station_id}', port {port} registered for '{station_id}'"
            log_ingestion(station_id, "FAILED", reason, QUARANTINE_ROOT, raw_preview, None)
            save_raw_quarantine(station_id, raw_msg, reason)
            return JSONResponse(status_code=400, content={"error": reason})

        # Calculate drift
        drift = None
        status = "online"
        if timestamp:
            drift = calculate_time_drift(timestamp)
            if drift and abs(drift) > 300:
                status = "warning"

        # --- Database logging (new) ---
        received_at = datetime.now().isoformat()
        observed_at = timestamp if timestamp else received_at
        all_params_json = json.dumps(data)

        # Log ingestion attempt
        log_ingestion(
            station_id=station_id,
            status="SUCCESS" if status == "online" else "WARNING",
            reason=f"Drift: {drift:.1f}s" if drift and abs(drift) > 300 else None,
            storage_location="data_records",
            raw_message_preview=raw_preview,
            drift_seconds=drift
        )

        """if message_station_id != station_id:
            reason = f"Station ID mismatch: message says '{message_station_id}', port {port} registered for '{station_id}'"
            print(f"❌ {reason}")
            log_ingestion(station_id, "FAILED", reason, QUARANTINE_ROOT, raw_preview, None)
            save_raw_quarantine(station_id, raw_msg, reason)
            return JSONResponse(status_code=400, content={"error": reason})""" 
        
        print(f"🔍 VERIFY: Registered station on port {port} = '{station_id}'")
        print(f"🔍 VERIFY: Parsed station ID from message = '{message_station_id}'")
        print(f"🔍 VERIFY: Match? {message_station_id == station_id}")

        # Save weather data (only if not a drift warning? We save both, but for reporting we save all)
        # We'll always save to weather_data; reporting can filter by drift later.
        save_weather_data(
            station_id=station_id,
            observed_at=observed_at,
            received_at=received_at,
            drift_seconds=drift,
            all_parameters_json=all_params_json
        )

        # Update last_seen in stations table
        update_station_last_seen(station_id)

        # --- CSV logging (unchanged) ---
        try:
            save_to_csv(
                station_id=station_id,
                received_at=received_at,
                observed_at=observed_at,
                all_parameters=data,
                drift_seconds=drift,
                status=status
            )
            print(f"✅ Saved to generic CSV: {station_id}")
        except Exception as e:
            print(f"⚠️ CSV save error: {e}")

        # (No need for in‑memory latest_status – dashboard reads from DB)
        return {"status": "ok", "station": station_id, "drift": drift}

    except Exception as e:
        save_raw_quarantine(station_id, raw_msg, f"Unexpected error: {str(e)}")
        return {"error": f"Processing error: {str(e)}"}
@app.get("/api/raw_data/{station_id}")
async def get_raw_data(station_id: str, limit: int = 50):
    station = get_station_by_id(station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    messages = get_recent_raw_messages(station_id, limit)
    return {"station_id": station_id, "messages": messages}

# ---------- Initialize database on startup ----------
init_database()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
import re
from datetime import datetime

def parse_vaisala_aws330(raw_msg: str):
    """
    Decodes a Vaisala AWS330 message.
    Extracts S (ID), D (Date), T (Time) and all meteorological parameters.
    Prepares a clean dictionary for main.py.
    """
    # 1. Clean the message: Remove newlines and extra spaces
    clean_msg = raw_msg.replace('\n', '').replace('\r', '').strip()
    
    # 2. Extract content inside parentheses
    match = re.search(r'\((.*?)\)', clean_msg, re.DOTALL)
    if not match:
        # Try without parentheses (some formats)
        content = clean_msg
    else:
        content = match.group(1)
    
    parts = [p for p in content.split(';') if p]
    
    parsed_parameters = {}
    station_id = "Unknown"
    obs_timestamp = None
    raw_date = None
    raw_time = None

    for entry in parts:
        if ':' in entry:
            raw_tag, val = entry.split(':', 1)
            
            # Clean the tag (Remove leading numbers/spaces)
            tag = re.sub(r'^\s*\d+\s+', '', raw_tag).strip()
            val = val.strip()

            # Handle Null values
            if val.startswith('/'):
                final_val = None
            else:
                try:
                    # Try float first, then int
                    if '.' in val:
                        final_val = float(val)
                    else:
                        final_val = int(val)
                except ValueError:
                    final_val = val

            # --- SPECIAL HANDLING FOR SMA PROTOCOL TAGS ---
            if tag == 'S':
                station_id = str(val)
            elif tag == 'D':
                raw_date = str(val)  # Expects DDMMYY
            elif tag == 'T':
                raw_time = str(val)  # Expects HHMMSS
            else:
                # Add all other met parameters to the data dictionary
                parsed_parameters[tag] = final_val
                    
    # 3. Create a Python Datetime object from D and T
    if raw_date and raw_time:
        try:
            # Vaisala Format: D:DDMMYY;T:HHMMSS
            dt_obj = datetime.strptime(f"{raw_date}{raw_time}", "%d%m%y%H%M%S")
            obs_timestamp = dt_obj.isoformat()
        except ValueError as e:
            print(f"Timestamp parse error: {e} - D:{raw_date} T:{raw_time}")
            obs_timestamp = None

    # 4. Final Output structured for main.py
    return {
        "station_id": station_id,
        "timestamp": obs_timestamp,  # ISO string for main.py to calculate drift
        "raw_date": raw_date,        # Keep raw for CSV
        "raw_time": raw_time,        # Keep raw for CSV
        "data": parsed_parameters,   # The actual measurements
        "raw_msg": raw_msg           # Kept for the quarantine file
    }

# --- THE SWITCHBOARD FOR MAIN.PY ---
PARSER_MAP = {
    "Vaisala": parse_vaisala_aws330,
    "Thies": None  # Ready for future expansion
}

# --- FRIENDLY NAME LOGIC ---
FRIENDLY_NAMES = {
    # Metadata & Time
    "S": "Station ID",
    "D": "Date (DDMMYY)",
    "T": "Time (HHMMSS)",

    # Temperature & Humidity
    "TAAVG1M": "Air Temp (1m Avg)",
    "TAAVG1H": "Air Temp (1h Avg)",
    "TAAVG1D": "Air Temp (Daily Avg)",
    "TAMIN1D": "Min Temp (Daily)",
    "TAMAX1D": "Max Temp (Daily)",
    "RHAVG1M": "Humidity (1m Avg)",
    "RHAVG1H": "Humidity (1h Avg)",
    "DPAVG1M": "Dewpoint (1m Avg)",
    "DPAVG1H": "Dewpoint (1h Avg)",
    "TBAVG1M": "Brightness Temp (1m)",
    "TBAVG1H": "Brightness Temp (1h)",
    "HIAVG1M": "Heat Index (1m)",
    "WCHAVG1M": "Wind Chill (1m)",

    # Pressure
    "QFEAVG1M": "QFE Pressure (1m)",
    "QFEAVG1H": "QFE Pressure (1h)",
    "QFEMIN1H": "QFE Min (1h)",
    "QFEMAX1H": "QFE Max (1h)",
    "QFEAVG1D": "QFE Avg (Daily)",
    "QFEMIN1D": "QFE Min (Daily)",
    "QFEMAX1D": "QFE Max (Daily)",
    "QFFAVG1M": "QFF MSL Pressure (1m)",
    "QFFAVG1H": "QFF MSL Pressure (1h)",
    "QFFMIN1H": "QFF Min (1h)",
    "QFFMAX1H": "QFF Max (1h)",
    "QFFMIN1D": "QFF Min (Daily)",
    "QFFAVG1D": "QFF Avg (Daily)",
    "QFFMAX1D": "QFF Max (Daily)",
    "QNHAVG1M": "QNH Altimeter (1m)",
    "QNHAVG1H": "QNH Altimeter (1h)",
    "QNHMIN1H": "QNH Min (1h)",
    "QNHMAX1H": "QNH Max (1h)",
    "QNHAVG1D": "QNH Avg (Daily)",
    "QNHMIN1D": "QNH Min (Daily)",
    "QNHMAX1D": "QNH Max (Daily)",
    "PAAVG1M": "Station Pressure (1m)",  # Added for database.py
    "PTREND3H": "Pressure Trend (3h)",
    "PTEND3H": "Pressure Tendency (3h)",
    "VPAVG1H": "Vapor Pressure (1h)",

    # Wind Data
    "WS": "Wind Speed (Instant)",
    "WD": "Wind Direction (Instant)",
    "WDAVG2M": "Wind Direction (2m Avg)",
    "WDMIN2M": "Wind Direction (2m Min)",
    "WDMAX2M": "Wind Direction (2m Max)",
    "WSAVG2M": "Wind Speed (2m Avg)",
    "WSMIN2M": "Wind Speed (2m Min)",
    "WSMAX2M": "Wind Speed (2m Max)",
    "WDAVG10M": "Wind Direction (10m Avg)",
    "WDMIN10M": "Wind Direction (10m Min)",
    "WDMAX10M": "Wind Direction (10m Max)",
    "WSAVG10M": "Wind Speed (10m Avg)",
    "WSMIN10M": "Wind Speed (10m Min)",
    "WSMAX10M": "Wind Speed (10m Max)",
    "WDWSMAX10M": "Max Wind Gust Dir (10m)",

    # Precipitation
    "PRSUM1M": "Precipitation (1m Sum)",
    "PRSUM10M": "Precipitation (10m Sum)",
    "PRSUM30M": "Precipitation (30m Sum)",
    "PRSUM1H": "Precipitation (1h Sum)",
    "PRSUM3H": "Precipitation (3h Sum)",
    "PRSUM6H": "Precipitation (6h Sum)",
    "PRSUM12H": "Precipitation (12h Sum)",
    "PRSUM1D": "Precipitation (Daily Sum)",
    "PRFSUM1H": "Precipitation Frequency (1h)",
    "SNAVG1H": "Snow Depth (1h)",

    # Soil Temperatures
    "TS1AVG10M": "Soil Temp 1 (10m Avg)",
    "TS1AVG1H": "Soil Temp 1 (1h Avg)",
    "TS1MIN1H": "Soil Temp 1 Min (1h)",
    "TS1MAX1H": "Soil Temp 1 Max (1h)",
    "TS1AVG1D": "Soil Temp 1 Avg (Daily)",
    "TS1MIN1D": "Soil Temp 1 Min (Daily)",
    "TS1MAX1D": "Soil Temp 1 Max (Daily)",
    "TS2AVG10M": "Soil Temp 2 (10m Avg)",
    "TS2AVG1H": "Soil Temp 2 (1h Avg)",
    "TS2MIN1H": "Soil Temp 2 Min (1h)",
    "TS2MAX1H": "Soil Temp 2 Max (1h)",
    "TS2AVG1D": "Soil Temp 2 Avg (Daily)",
    "TS2MIN1D": "Soil Temp 2 Min (Daily)",
    "TS2MAX1D": "Soil Temp 2 Max (Daily)",

    # Radiation
    "GIRRAVG1M": "Global Radiation (1m)",
    "GIRRAVG1H": "Global Radiation (1h)",
    "GIRRAVG1D": "Global Radiation (Daily)",
    "SDUR1D": "Sunshine Duration (Daily)",
    "EVAP1D": "Evaporation (Daily)",

    # Diagnostics & Visibility
    "UPTIME": "System Uptime (sec)",
    "STATUS": "System Status Code",
    "EXTDC": "External DC Power (V)",
    "VIS": "Visibility",
    "BATTERY": "Battery Voltage"
}

def get_friendly_name(tag):
    return FRIENDLY_NAMES.get(tag, tag)
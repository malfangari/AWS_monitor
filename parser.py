import re
from datetime import datetime

# ---------- Existing Vaisala AWS330 parser (tagged, simple colon format) ----------
def parse_vaisala_aws330(raw_msg: str):
    """
    Decodes a Vaisala AWS330 message.
    Extracts S (ID), D (Date), T (Time) and all meteorological parameters.
    """
    clean_msg = raw_msg.replace('\n', '').replace('\r', '').strip()
    match = re.search(r'\((.*?)\)', clean_msg, re.DOTALL)
    content = match.group(1) if match else clean_msg
    parts = [p for p in content.split(';') if p]
    
    parsed_parameters = {}
    station_id = "Unknown"
    obs_timestamp = None
    raw_date = None
    raw_time = None

    for entry in parts:
        if ':' in entry:
            raw_tag, val = entry.split(':', 1)
            tag = re.sub(r'^\s*\d+\s+', '', raw_tag).strip()
            val = val.strip()
            if val.startswith('/'):
                final_val = None
            else:
                try:
                    final_val = float(val) if '.' in val else int(val)
                except ValueError:
                    final_val = val
            if tag == 'S':
                station_id = str(val)
            elif tag == 'D':
                raw_date = str(val)
            elif tag == 'T':
                raw_time = str(val)
            else:
                parsed_parameters[tag] = final_val
    print(f"DEBUG: Stored keys for {station_id}: {list(parsed_parameters.keys())}")
    if raw_date and raw_time:
        try:
            dt_obj = datetime.strptime(f"{raw_date}{raw_time}", "%y%m%d%H%M%S")
            obs_timestamp = dt_obj.isoformat()
        except ValueError:
            pass

    return {
        "station_id": station_id,
        "timestamp": obs_timestamp,
        "raw_date": raw_date,
        "raw_time": raw_time,
        "data": parsed_parameters,
        "raw_msg": raw_msg
    }

# ---------- New parser for SMSAWS (Vaisala without header / pipe format) ----------
def parse_vaisala_smsaws(raw_msg: str):
    """
    Decodes a Vaisala SMSAWS message (the pipe‑separated format used by AWS810 etc.)
    Returns a dictionary with the same CSV tag keys as the (csv normal format) parser.
    """
    # Remove control characters and newlines
    clean_msg = raw_msg.replace('\n', '').replace('\r', '').replace('<SOH>', '').replace('<STX>', '').replace('<ETX>', '').strip()
    
    # Extract content inside parentheses
    match = re.search(r'\((.*?)\)', clean_msg, re.DOTALL)
    if not match:
        content = clean_msg
    else:
        content = match.group(1)
    
    parts = [p for p in content.split(';') if p]
    
    parsed_parameters = {}
    station_id = "Unknown"
    obs_timestamp = None
    raw_date = None
    raw_time = None
    
    # Mapping from (measurement, statistic, period, sensor) -> CSV tag
    # Based on AWS810 documentation (Tables 15–17)
    # We'll build a dynamic mapping using patterns
    
    # First, handle the simple S, D, T tags
    for entry in parts:
        if ':' in entry and entry.startswith(('S:', 'D:', 'T:')):
            tag, val = entry.split(':', 1)
            if tag == 'S':
                station_id = val.strip()
            elif tag == 'D':
                raw_date = val.strip()
            elif tag == 'T':
                raw_time = val.strip()
    
    # Now parse all other entries that have pipe syntax
    for entry in parts:
        if ':' not in entry:
            continue
        # Split at first colon
        left, right = entry.split(':', 1)
        left = left.strip()
        right = right.strip()
        
        # Extract components: e.g., "TA|AVG|PT1M| |degC"
        parts_left = left.split('|')
        if len(parts_left) < 2:
            continue
        
        base_tag = parts_left[0]        # e.g., TA, RH, WS, WD, QFE, etc.
        statistic = parts_left[1] if len(parts_left) > 1 else None   # AVG, MIN, MAX, SUM, VALUE
        period = parts_left[2] if len(parts_left) > 2 else None       # PT1M, PT1H, PT24H, etc.
        sensor = None 
        for part in parts_left:
          if part in ('1', '2'):
             sensor = part        
        # Determine the CSV tag based on the mapping rules
        csv_tag = None
        
        # Temperature (TA)
        if base_tag == 'TA':
            if statistic == 'AVG' and period == 'PT1M':
                csv_tag = 'TAAVG1M'
            elif statistic == 'AVG' and period == 'PT1H':
                csv_tag = 'TAAVG1H'
            elif statistic == 'AVG' and period == 'PT24H':
                csv_tag = 'TAAVG1D'
            elif statistic == 'MIN' and period == 'PT24H':
                csv_tag = 'TAMIN1D'
            elif statistic == 'MAX' and period == 'PT24H':
                csv_tag = 'TAMAX1D'
        # Relative humidity (RH)
        elif base_tag == 'RH':
            if statistic == 'AVG' and period == 'PT1M':
                csv_tag = 'RHAVG1M'
            elif statistic == 'AVG' and period == 'PT1H':
                csv_tag = 'RHAVG1H'
            elif statistic == 'MIN' and period == 'PT24H':
                csv_tag = 'RH1MIN1D'   # not in original but can be added
            elif statistic == 'MAX' and period == 'PT24H':
                csv_tag = 'RH1MAX1D'
        # Dew point (TD)
        elif base_tag == 'TD':
            if statistic == 'AVG' and period == 'PT1M':
                csv_tag = 'TDAVG1M'
        # Pressure QFE, QFF, QNH
        elif base_tag == 'QFE':
            if statistic == 'AVG' and period == 'PT1M':
                csv_tag = 'QFEAVG1M'
            elif statistic == 'AVG' and period == 'PT1H':
                csv_tag = 'QFEAVG1H'
            elif statistic == 'MIN' and period == 'PT1H':
                csv_tag = 'QFEMIN1H'
            elif statistic == 'MAX' and period == 'PT1H':
                csv_tag = 'QFEMAX1H'
            elif statistic == 'AVG' and period == 'PT24H':
                csv_tag = 'QFEAVG1D'
        elif base_tag == 'QFF':
            if statistic == 'AVG' and period == 'PT1M':
                csv_tag = 'QFFAVG1M'
            elif statistic == 'AVG' and period == 'PT1H':
                csv_tag = 'QFFAVG1H'
            elif statistic == 'MIN' and period == 'PT1H':
                csv_tag = 'QFFMIN1H'
            elif statistic == 'MAX' and period == 'PT1H':
                csv_tag = 'QFFMAX1H'
            elif statistic == 'AVG' and period == 'PT24H':
                csv_tag = 'QFFAVG1D'
        elif base_tag == 'QNH':
            if statistic == 'AVG' and period == 'PT1M':
                csv_tag = 'QNHAVG1M'
            elif statistic == 'AVG' and period == 'PT1H':
                csv_tag = 'QNHAVG1H'
            elif statistic == 'MIN' and period == 'PT1H':
                csv_tag = 'QNHMIN1H'
            elif statistic == 'MAX' and period == 'PT1H':
                csv_tag = 'QNHMAX1H'
            elif statistic == 'AVG' and period == 'PT24H':
                csv_tag = 'QNHAVG1D'
        # Wind speed (WS)
        elif base_tag == 'WS':
            if statistic == 'AVG' and period == 'PT3S' and sensor == '1':
                csv_tag = 'WS'          # instantaneous? document shows WS|AVG|PT3S|1|mps -> WS
            elif statistic == 'AVG' and period == 'PT2M' and sensor == '1':
                csv_tag = 'WSAVG2M'
            elif statistic == 'MIN' and period == 'PT2M' and sensor == '1':
                csv_tag = 'WSMIN2M'
            elif statistic == 'MAX' and period == 'PT2M' and sensor == '1':
                csv_tag = 'WSMAX2M'
            elif statistic == 'AVG' and period == 'PT10M' and sensor == '1':
                csv_tag = 'WSAVG10M'
            elif statistic == 'MIN' and period == 'PT10M' and sensor == '1':
                csv_tag = 'WSMIN10M'
            elif statistic == 'MAX' and period == 'PT10M' and sensor == '1':
                csv_tag = 'WSMAX10M'
            # Secondary sensor (sensor '2')
            elif statistic == 'AVG' and period == 'PT2M' and sensor == '2':
                csv_tag = 'WS2AVG2M'
            elif statistic == 'AVG' and period == 'PT10M' and sensor == '2':
                csv_tag = 'WS2AVG10M'
        # Wind direction (WD)
        elif base_tag == 'WD':
            if statistic == 'AVG' and period == 'PT3S' and sensor == '1':
                csv_tag = 'WD'
            elif statistic == 'AVG' and period == 'PT2M' and sensor == '1':
                csv_tag = 'WDAVG2M'
            elif statistic == 'MIN' and period == 'PT2M' and sensor == '1':
                csv_tag = 'WDMIN2M'
            elif statistic == 'MAX' and period == 'PT2M' and sensor == '1':
                csv_tag = 'WDMAX2M'
            elif statistic == 'AVG' and period == 'PT10M' and sensor == '1':
                csv_tag = 'WDAVG10M'
            elif statistic == 'MIN' and period == 'PT10M' and sensor == '1':
                csv_tag = 'WDMIN10M'
            elif statistic == 'MAX' and period == 'PT10M' and sensor == '1':
                csv_tag = 'WDMAX10M'
            # Secondary sensor
            elif statistic == 'AVG' and period == 'PT2M' and sensor == '2':
                csv_tag = 'WD2AVG2M'
            elif statistic == 'AVG' and period == 'PT10M' and sensor == '2':
                csv_tag = 'WD2AVG10M'
        # Precipitation (PR)
        elif base_tag == 'PR':
            if statistic == 'SUM' and period == 'PT1M':
                csv_tag = 'PRSUM1M'
            elif statistic == 'SUM' and period == 'PT1H':
                csv_tag = 'PRSUM1H'
            elif statistic == 'SUM' and period == 'PT24H':
                csv_tag = 'PRSUM1D'
        # Pressure trend (PATR)
        elif base_tag == 'PATR':
            if statistic == 'VALUE' and period == 'PT3H':
                csv_tag = 'PTREND3H'
        # Pressure tendency (PATE)
        elif base_tag == 'PATE':
            if statistic == 'VALUE' and period == 'PT3H':
                csv_tag = 'PTEND3H'
        # Vapor pressure (VPA)
        elif base_tag == 'VPA':
            if statistic == 'AVG' and period == 'PT1H':
                csv_tag = 'VPAVG1H'
        # Wind gust direction (WGD)
        elif base_tag == 'WGD':
            if statistic == 'VALUE' and period == 'PT10M' and sensor == '1':
                csv_tag = 'WDWSMAX10M'   # direction of max gust
        # Solar radiation (SR)
        elif base_tag == 'SR':
            if statistic == 'AVG' and period == 'PT1M':
                csv_tag = 'GIRRAVG1M'    # global radiation
            elif statistic == 'AVG' and period == 'PT1H':
                csv_tag = 'GIRRAVG1H'
        # Sunshine duration (SDUR)
        elif base_tag == 'SDUR':
            if statistic == 'SUM' and period == 'PT24H':
                csv_tag = 'SDUR1D'
        # Snow depth (SNH)
        elif base_tag == 'SNH':
            if statistic == 'VALUE' and period == 'PT1M':
                csv_tag = 'SNAVG1H'      # or a separate key
        # Soil temperature (TS)
        elif base_tag == 'TS':
            if statistic == 'AVG' and period == 'PT10M':
                csv_tag = 'TS1AVG10M'
            elif statistic == 'AVG' and period == 'PT1H':
                csv_tag = 'TS1AVG1H'
            elif statistic == 'MAX' and period == 'PT24H':
                csv_tag = 'TS1MAX1D'
        # Battery voltage
        elif base_tag == 'BATTERYV':
            if statistic == 'VALUE' and period == 'PT1M':
                csv_tag = 'BATTERY'
        # External DC voltage
        elif base_tag == 'EXTDC':
            if statistic == 'VALUE' and period == 'PT1M':
                csv_tag = 'EXTDC'
        # Uptime
        elif base_tag == 'UPTIME':
            if statistic == 'VALUE' and period == 'PT1H':
                csv_tag = 'UPTIME'
        # Status
        elif base_tag == 'STATUS':
            if statistic == 'VALUE':
                csv_tag = 'STATUS'
        # Add more mappings as needed (evapotranspiration, cloud, visibility, etc.)
        
        if csv_tag:
            # Parse the value (right part)
            try:
                value = float(right) if '.' in right else int(right)
            except ValueError:
                value = right
            parsed_parameters[csv_tag] = value
    
    # Create timestamp from D and T (if available)
    if raw_date and raw_time:
        try:
            # raw_date is expected as YYMMDD, raw_time as HHMMSS
            dt_obj = datetime.strptime(f"{raw_date}{raw_time}", "%y%m%d%H%M%S")
            obs_timestamp = dt_obj.isoformat()
        except ValueError:
            pass
    print(f"DEBUG: Stored keys for station {station_id}: {list(parsed_parameters.keys())}")
    print("DEBUG parsed_parameters keys:", list(parsed_parameters.keys()))
    return {
        "station_id": station_id,
        "timestamp": obs_timestamp,
        "raw_date": raw_date,
        "raw_time": raw_time,
        "data": parsed_parameters,
        "raw_msg": raw_msg
    }

# ---------- Parser registry (switchboard) ----------
PARSER_MAP = {
    "Vaisala": parse_vaisala_aws330,
    "Vaisala Without Header": parse_vaisala_smsaws,
    "Thies": None
}

# ---------- Friendly name mappings (extend with new tags) ----------
FRIENDLY_NAMES = {
    # Metadata & Time
    "S": "Station ID",
    "D": "Date (YYMMDD)",
    "T": "Time (HHMMSS)",

    # Temperature & Humidity (Vaisala AWS330)
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

    # Pressure (Vaisala AWS330)
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
    "PAAVG1M": "Station Pressure (1m)",
    "PTREND3H": "Pressure Trend (3h)",
    "PTEND3H": "Pressure Tendency (3h)",
    "VPAVG1H": "Vapor Pressure (1h)",

    # Wind Data (Vaisala AWS330)
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

    # Precipitation (Vaisala AWS330)
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

    # Soil Temperatures (Vaisala AWS330)
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

    # Radiation (Vaisala AWS330)
    "GIRRAVG1M": "Global Radiation (1m)",
    "GIRRAVG1H": "Global Radiation (1h)",
    "GIRRAVG1D": "Global Radiation (Daily)",
    "SDUR1D": "Sunshine Duration (Daily)",
    "EVAP1D": "Evaporation (Daily)",

    # Diagnostics & Visibility (Vaisala AWS330)
    "UPTIME": "System Uptime (sec)",
    "STATUS": "System Status Code",
    "EXTDC": "External DC Power (V)",
    "VIS": "Visibility",
    "BATTERY": "Battery Voltage",

    # ---------- New tags for "Vaisala Without Header" (SMS 50041 / NM10) ----------
    "TA": "Air Temperature (degC)",
    "RH": "Relative Humidity (%)",
    "TD": "Dewpoint (degC)",
    "TAB": "Brightness Temp (degC)",
    "HTIDX": "Heat Index (degC)",
    "PA": "Station Pressure (hPa)",
    "QFE": "QFE Pressure (hPa)",
    "QFF": "QFF Pressure (hPa)",
    "QNH": "QNH Altimeter (hPa)",
    "VPA": "Vapor Pressure (hPa)",
    "PATR": "Pressure Trend (3h)",
    "PATE": "Pressure Tendency (3h)",
    "PR": "Precipitation (mm)",
    "PRF": "Precipitation Frequency (mmph)",
    "SNS": "Snow Depth (mm)",
    "SNH": "Snow Height (cm)",
    "WGD": "Wind Gust Direction (deg)",
    "WCH": "Wind Chill (degC)",
    "SR": "Solar Radiation (W/m²)",
    "SDUR": "Sunshine Duration (min)",
    "PW": "Precipitable Water (WMO code)",
    "CB1": "Cloud Base 1 (m)",
    "CL1": "Cloud Cover 1 (octa)",
    "CA1": "Cloud Amount 1 (octa)",
    "VV": "Vertical Visibility (m)",
    "TS": "Soil Temperature (degC)",
    "ETO": "Evapotranspiration (mm)",
    "BATTERYV": "Battery Voltage (V)",
    "WL": "Water Level (m)",
    "TW": "Water Temperature (degC)"
}
FRIENDLY_NAMES.update({
    "RH1MIN1D": "Min Relative Humidity (Daily)",
    "TDAVG1M": "Dewpoint (1m Avg)",
    "RH1MAX1D": "Max Relative Humidity (Daily)",   # in case it appears later
})
def get_friendly_name(tag):
    return FRIENDLY_NAMES.get(tag, tag)
import csv
import os
import json
from datetime import datetime

# Define where to save the data
DATA_DIR = "data_records"
CSV_FILE = os.path.join(DATA_DIR, "weather_log.csv")

# Metadata headers for the CSV file
HEADERS = [
    "Station_ID", "Station_Name", "Received_At", "Obs_Date", "Obs_Time",
    "Air_Temp_C", "Relative_Humidity_pct", "Dewpoint_C", 
    "Station_Pressure_hPa", "QFE_hPa", "QFF_hPa", "QNH_hPa", 
    "Wind_Speed_ms", "Wind_Dir_deg", "Wind_Gust_ms",
    "Precipitation_mm", "Visibility_km", "Battery_Voltage_V", 
    "System_Status", "Time_Drift_Seconds"
]

def ensure_data_dir():
    """Ensure the data directory exists"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def map_vaisala_to_csv(data):
    """
    Maps Vaisala tags to CSV column names.
    data: dict with Vaisala tags like "S", "D", "T", "TAAVG1M", etc.
    """
    # Extract date and time from parsed timestamp if available
    obs_date = ""
    obs_time = ""
    if data.get("timestamp"):
        try:
            dt = datetime.fromisoformat(data["timestamp"])
            obs_date = dt.strftime("%Y-%m-%d")
            obs_time = dt.strftime("%H:%M:%S")
        except:
            pass
    # Fallback to D and T tags if timestamp not available
    elif data.get("D") and data.get("T"):
        obs_date = f"20{data['D'][4:6]}-{data['D'][2:4]}-{data['D'][0:2]}" if len(data['D']) == 6 else data['D']
        obs_time = f"{data['T'][0:2]}:{data['T'][2:4]}:{data['T'][4:6]}" if len(data['T']) == 6 else data['T']
    
    return {
        "Station_ID": data.get("S") or data.get("station_id", "Unknown"),
        "Station_Name": data.get("station_name", ""),
        "Received_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Obs_Date": obs_date,
        "Obs_Time": obs_time,
        "Air_Temp_C": data.get("TAAVG1M") or data.get("TA"),
        "Relative_Humidity_pct": data.get("RHAVG1M") or data.get("RH"),
        "Dewpoint_C": data.get("DPAVG1M") or data.get("TD"),
        "Station_Pressure_hPa": data.get("PAAVG1M") or data.get("PA"),
        "QFE_hPa": data.get("QFEAVG1M"),
        "QFF_hPa": data.get("QFFAVG1M"),
        "QNH_hPa": data.get("QNHAVG1M"),
        "Wind_Speed_ms": data.get("WSAVG2M") or data.get("WS"),
        "Wind_Dir_deg": data.get("WDAVG2M") or data.get("WD"),
        "Wind_Gust_ms": data.get("WSMAX2M") or data.get("WSMAX10M"),
        "Precipitation_mm": data.get("PRSUM1H"),
        "Visibility_km": data.get("VIS"),
        "Battery_Voltage_V": data.get("BATTERY") or data.get("EXTDC"),
        "System_Status": data.get("STATUS"),
        "Time_Drift_Seconds": data.get("drift_seconds", 0)
    }

def save_to_csv(data, station_name=""):
    """
    Saves parsed weather data into a CSV file.
    Creates the file and headers if they don't exist.
    
    Args:
        data: Dictionary containing parsed Vaisala data
        station_name: Optional friendly name for the station
    """
    ensure_data_dir()
    
    file_exists = os.path.isfile(CSV_FILE)
    
    # Add station name to data if provided
    if station_name:
        data["station_name"] = station_name
    
    # Map the data to CSV format
    row_to_save = map_vaisala_to_csv(data)
    
    try:
        with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            
            # If the file is new, write the descriptive headers
            if not file_exists:
                writer.writeheader()
                
            writer.writerow(row_to_save)
            print(f"✅ CSV entry added for station {row_to_save['Station_ID']}")
            
    except Exception as e:
        print(f"❌ Error writing to CSV: {e}")

def save_to_json(data, station_id):
    """Save individual records as JSON files (complementary to CSV)"""
    ensure_data_dir()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filename = f"{station_id}_{timestamp}.json"
    filepath = os.path.join(DATA_DIR, filename)
    
    record = {
        "station_id": station_id,
        "received_at": datetime.now().isoformat(),
        "parsed_data": data,
        "csv_headers": HEADERS
    }
    
    with open(filepath, "w") as f:
        json.dump(record, f, indent=2)

def query_csv(station_id=None, start_date=None, end_date=None):
    """
    Query the CSV file for specific data.
    
    Args:
        station_id: Filter by station ID
        start_date: Filter start date (YYYY-MM-DD)
        end_date: Filter end date (YYYY-MM-DD)
    
    Returns:
        List of dictionaries matching the query
    """
    if not os.path.exists(CSV_FILE):
        return []
    
    results = []
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Apply filters
            if station_id and row['Station_ID'] != station_id:
                continue
            if start_date and row['Obs_Date'] < start_date:
                continue
            if end_date and row['Obs_Date'] > end_date:
                continue
            results.append(row)
    
    return results

def get_latest_reading(station_id):
    """Get the latest reading for a specific station"""
    if not os.path.exists(CSV_FILE):
        return None
    
    latest = None
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Station_ID'] == station_id:
                latest = row  # Last one in file is the latest
    
    return latest

# Optional: Create a separate file for daily summaries
def generate_daily_summary(date=None):
    """Generate a daily summary CSV for all stations"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    summary_file = os.path.join(DATA_DIR, f"summary_{date}.csv")
    summary_headers = [
        "Station_ID", "Station_Name", "Date", "Avg_Temp", "Max_Temp", "Min_Temp",
        "Avg_Humidity", "Total_Rainfall", "Avg_Wind_Speed", "Max_Wind_Gust"
    ]
    
    # Query all data for the date
    records = query_csv(start_date=date, end_date=date)
    
    if not records:
        print(f"No records found for {date}")
        return
    
    # Group by station and calculate aggregates
    station_stats = {}
    for record in records:
        sid = record['Station_ID']
        if sid not in station_stats:
            station_stats[sid] = {
                'temps': [], 'humidities': [], 'rainfall': 0, 
                'wind_speeds': [], 'wind_gusts': [], 'name': record['Station_Name']
            }
        
        # Collect values (convert to float where possible)
        try:
            if record['Air_Temp_C']:
                station_stats[sid]['temps'].append(float(record['Air_Temp_C']))
            if record['Relative_Humidity_pct']:
                station_stats[sid]['humidities'].append(float(record['Relative_Humidity_pct']))
            if record['Wind_Speed_ms']:
                station_stats[sid]['wind_speeds'].append(float(record['Wind_Speed_ms']))
            if record['Wind_Gust_ms']:
                station_stats[sid]['wind_gusts'].append(float(record['Wind_Gust_ms']))
            if record['Precipitation_mm']:
                station_stats[sid]['rainfall'] += float(record['Precipitation_mm'])
        except ValueError:
            pass
    
    # Write summary
    with open(summary_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=summary_headers)
        writer.writeheader()
        
        for sid, stats in station_stats.items():
            writer.writerow({
                "Station_ID": sid,
                "Station_Name": stats['name'],
                "Date": date,
                "Avg_Temp": sum(stats['temps'])/len(stats['temps']) if stats['temps'] else None,
                "Max_Temp": max(stats['temps']) if stats['temps'] else None,
                "Min_Temp": min(stats['temps']) if stats['temps'] else None,
                "Avg_Humidity": sum(stats['humidities'])/len(stats['humidities']) if stats['humidities'] else None,
                "Total_Rainfall": stats['rainfall'],
                "Avg_Wind_Speed": sum(stats['wind_speeds'])/len(stats['wind_speeds']) if stats['wind_speeds'] else None,
                "Max_Wind_Gust": max(stats['wind_gusts']) if stats['wind_gusts'] else None
            })
    
    print(f"✅ Daily summary saved to {summary_file}")
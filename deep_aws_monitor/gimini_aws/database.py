import csv
import os

# Define where to save the data
CSV_FILE = "data/weather_log.csv"
# Metadata headers for the CSV file
HEADERS = [
    "Station_ID", "Date", "Time", "Air_Temp", "Relative_Humidity", 
    "Dewpoint", "Station_Pressure", "QFE", "QFF", "QNH_Altimeter", 
    "Wind_Speed", "Wind_Dir", "Visibility", "Battery_Voltage", "Status"
]
def save_to_csv(data):
    """
    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    Saves the dictionary of parsed weather data into a CSV file.
    Creates the file and headers if they don't exist.
    """

    file_exists = os.path.isfile(CSV_FILE)
    
    # We map the Vaisala tags to our specific Header names
    # This ensures the CSV is always organized in the same order
    row_to_save = {
        "Station_ID": data.get("S"),
        "Date": data.get("D"),
        "Time": data.get("T"),
        "Air_Temp": data.get("TAAVG1M"),
        "Relative_Humidity": data.get("RHAVG1M"),
        "Dewpoint": data.get("DPAVG1M"),
        "Station_Pressure": data.get("PAAVG1M"),
        "QFE": data.get("QFEAVG1M"),
        "QFF": data.get("QFFAVG1M"),
        "QNH_Altimeter": data.get("QNHAVG1M"),
        "Wind_Speed": data.get("WS"),
        "Wind_Dir": data.get("WD"),
        "Visibility": data.get("VIS"),
        "Battery_Voltage": data.get("BATTERY"),
        "Status": data.get("STATUS")
    }

    with open(CSV_FILE, mode='a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        
        # If the file is new, write the descriptive headers
        if not file_exists:
            writer.writeheader()
            
        writer.writerow(row_to_save)

# Parse the message
try:
    parsed_result = PARSER_MAP[parser_name](raw_msg)
    
    if parsed_result is None:
        reason = "Invalid message format - parser returned None"
        log_ingestion(registered_station_id, "FAILED", reason, QUARANTINE_ROOT, raw_preview)
        save_quarantine_backup(registered_station_id, raw_msg, reason)
        log_data_issue(registered_station_id, "PARSE_ERROR", raw_msg, reason)
        return {"error": reason}
    
    # Extract data
    message_station_id = parsed_result.get("station_id", "Unknown")
    timestamp = parsed_result.get("timestamp")
    data = parsed_result.get("data", {})
    
    # ============================================================
    # >>> ADD THIS ID & PORT VERIFICATION LOGIC RIGHT HERE <<<
    # ============================================================
    if message_station_id != registered_station_id:
        reason = f"Station ID mismatch: Message says '{message_station_id}' but port {port} is registered for '{registered_station_id}'"
        print(f"❌ {reason}")
        
        # Log the rejection
        log_ingestion(registered_station_id, "FAILED", reason, QUARANTINE_ROOT, raw_preview)
        save_quarantine_backup(registered_station_id, raw_msg, reason)
        log_data_issue(registered_station_id, "STATION_MISMATCH", raw_msg, reason)
        
        return {
            "error": reason, 
            "expected_station": registered_station_id, 
            "received_station": message_station_id,
            "port": port
        }
    # ============================================================
    # Continue with existing code (drift calculation, etc.)
    # ============================================================
    
    # Calculate time drift
    drift = None
    status = "SUCCESS"
    reason = None
    # ... rest of your existing code ...
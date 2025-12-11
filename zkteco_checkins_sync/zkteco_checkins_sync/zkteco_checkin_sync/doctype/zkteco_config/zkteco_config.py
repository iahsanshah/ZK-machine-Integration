# Copyright (c) 2025, osama.ahmed@deliverydevs.com
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
import requests
from frappe.utils import today, now_datetime, get_datetime, flt, cint
from datetime import datetime, timedelta
import json
import socket
try:
    from zk import ZK
except Exception:
    ZK = None


class ZKTecoConfig(Document):
    pass


def build_api_url(server_ip, server_port, endpoint="", use_https=None):
    """
    Build API URL with proper protocol (HTTP/HTTPS)

    Args:
        server_ip: Server IP address
        server_port: Server port
        endpoint: API endpoint path
        use_https: Force HTTPS (True), HTTP (False), or auto-detect (None)

    Returns:
        Full URL string
    """
    # Auto-detect protocol based on port if not specified
    if use_https is None:
        # Common HTTPS ports: 443, 8443
        # Common HTTP ports: 80, 8080, 4370
        port_int = int(str(server_port).strip())
        use_https = port_int in [443, 8443]

    protocol = "https" if use_https else "http"
    base_url = f"{protocol}://{server_ip}:{server_port}"

    if endpoint:
        # Ensure endpoint starts with /
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        return base_url + endpoint

    return base_url


def detect_log_type(transaction):
    """
    Intelligently detect if transaction is IN or OUT
    Checks multiple possible fields from ZKTeco
    """
    # Log the raw transaction for debugging
    frappe.logger().info("===== DETECT_LOG_TYPE START =====")
    frappe.logger().info(f"Transaction data: {json.dumps(transaction, default=str, ensure_ascii=False, indent=2)}")
    
    # First, check for any field that might contain 'IN' or 'OUT' directly
    for key, value in transaction.items():
        if not value and value not in [0, False]:
            continue
            
        value_str = str(value).upper().strip()
        
        # Check for OUT indicators
        out_indicators = ['OUT', 'CHECK OUT', 'CHECKOUT', 'CHK OUT', 'CHKOUT', 'OUTGOING', 'EXIT']
        if any(x in value_str for x in out_indicators):
            frappe.logger().info(f"✅ Found OUT indicator in field '{key}': {value}")
            return "OUT"
            
        # Check for IN indicators
        in_indicators = ['IN', 'CHECK IN', 'CHECKIN', 'CHK IN', 'CHKIN', 'ENTRY']
        if any(x in value_str for x in in_indicators):
            frappe.logger().info(f"✅ Found IN indicator in field '{key}': {value}")
            return "IN"
    
    # Try specific known fields with standard processing
    field_checks = [
        # (field_name, is_numeric, out_value, in_value)
        ('log_type', False, 'OUT', 'IN'),
        ('punch_state', True, 1, 0),
        ('punch', True, 1, 0),
        ('punchtype', True, 1, 0),
        ('type', False, 'OUT', 'IN'),
        ('direction', False, 'OUT', 'IN'),
        ('status', False, 'OUT', 'IN'),
        ('verify_type', True, 1, 0),
    ]
    
    frappe.logger().info("Checking standard fields...")
    for field, is_numeric, out_val, in_val in field_checks:
        if field not in transaction or transaction[field] is None:
            frappe.logger().debug(f"Field '{field}' not found in transaction")
            continue
            
        try:
            if is_numeric:
                # Handle numeric fields
                val = int(transaction[field])
                if val == out_val:
                    frappe.logger().info(f"✅ Using numeric field '{field}': {val} -> OUT")
                    return "OUT"
                elif val == in_val:
                    frappe.logger().info(f"✅ Using numeric field '{field}': {val} -> IN")
                    return "IN"
                else:
                    frappe.logger().debug(f"Numeric field '{field}' value {val} doesn't match OUT ({out_val}) or IN ({in_val})")
            else:
                # Handle string fields
                val = str(transaction[field]).upper().strip()
                out_val_upper = str(out_val).upper()
                in_val_upper = str(in_val).upper()
                
                if val == out_val_upper:
                    frappe.logger().info(f"✅ Using string field '{field}': {val} -> OUT")
                    return "OUT"
                elif val == in_val_upper:
                    frappe.logger().info(f"✅ Using string field '{field}': {val} -> IN")
                    return "IN"
                else:
                    frappe.logger().debug(f"String field '{field}' value '{val}' doesn't match OUT ('{out_val_upper}') or IN ('{in_val_upper}')")
        except (ValueError, TypeError) as e:
            frappe.logger().warning(f"Error processing field '{field}': {str(e)}")
    
    # Check for punch_state_display (text) - common in ZKTeco
    punch_state_display = str(transaction.get('punch_state_display', '')).lower().strip()
    if punch_state_display:
        frappe.logger().info(f"Checking punch_state_display: '{punch_state_display}'")
        out_indicators = ['out', 'check out', 'checkout', 'چیک آؤٹ']
        in_indicators = ['in', 'check in', 'checkin', 'چیک ان']
        
        if any(x in punch_state_display for x in out_indicators):
            frappe.logger().info(f"✅ Using punch_state_display (OUT): {punch_state_display}")
            return "OUT"
        elif any(x in punch_state_display for x in in_indicators):
            frappe.logger().info(f"✅ Using punch_state_display (IN): {punch_state_display}")
            return "IN"
    
    # Check for any field that might contain 'punch' or 'state'
    frappe.logger().info("Checking all fields for punch/state indicators...")
    for key, value in transaction.items():
        if not value and value not in [0, False]:
            continue
            
        key_lower = key.lower()
        if 'punch' in key_lower or 'state' in key_lower or 'type' in key_lower:
            value_str = str(value).lower()
            out_indicators = ['out', 'check out', 'checkout', 'چیک آؤٹ']
            in_indicators = ['in', 'check in', 'checkin', 'چیک ان']
            
            if any(x in value_str for x in out_indicators):
                frappe.logger().info(f"✅ Using field '{key}' (OUT): {value}")
                return "OUT"
            elif any(x in value_str for x in in_indicators):
                frappe.logger().info(f"✅ Using field '{key}' (IN): {value}")
                return "IN"
            else:
                frappe.logger().debug(f"Field '{key}' with value '{value}' didn't match any indicators")
    
    # Log all keys for debugging
    frappe.logger().info("All transaction keys and values:")
    for key, value in transaction.items():
        frappe.logger().info(f"  {key}: {value} (type: {type(value).__name__})")
    
    # Default to IN if we can't determine (more common to have check-ins than check-outs)
    frappe.logger().warning("❌ Could not determine log type for transaction, defaulting to IN")
    frappe.logger().info("===== DETECT_LOG_TYPE END =====")
    return "IN"


@frappe.whitelist()
def check_device_status(server_ip=None, server_port=None):
    """
    Simple socket connection check to device
    Returns device status without needing token
    """
    server_ip = server_ip or frappe.db.get_single_value("ZKTeco Config", "server_ip")
    server_port = server_port or frappe.db.get_single_value("ZKTeco Config", "server_port")
    
    if not server_ip or not server_port:
        return {"connected": False, "error": "Server IP or Port not configured"}
    
    try:
        import socket
        import time
        
        start_time = time.time()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        
        result = s.connect_ex((server_ip, int(server_port)))
        response_time = (time.time() - start_time) * 1000  # Convert to ms
        s.close()
        
        if result == 0:
            return {
                "connected": True,
                "ip": server_ip,
                "port": server_port,
                "response_time": round(response_time, 2),
                "message": "Device is online"
            }
        else:
            return {
                "connected": False,
                "ip": server_ip,
                "port": server_port,
                "error": "Connection refused or timeout"
            }
    
    except Exception as e:
        return {
            "connected": False,
            "ip": server_ip,
            "port": server_port,
            "error": str(e)
        }


@frappe.whitelist()
def register_api_token(server_ip: str | None = None, server_port: str | int | None = None, username: str | None = None, password: str | None = None):
    """
    Calls the remote API to obtain a token and returns it to the client.
    """
    # Prefer values provided by the form; fallback to saved Single DocType values
    server_ip = server_ip or frappe.db.get_single_value("ZKTeco Config", "server_ip")
    server_port = server_port or frappe.db.get_single_value("ZKTeco Config", "server_port")
    username = username or frappe.db.get_single_value("ZKTeco Config", "username")
    password = password or frappe.db.get_single_value("ZKTeco Config", "password")

    if str(server_port).strip() == "4370":
        return {"success": True, "device_mode": True, "message": _("Token not required for device on port 4370.")}
    if not all([server_ip, server_port, username, password]):
        frappe.throw(_("Please configure server IP, port, username, and password in ZKTeco Config."))

    # Build URL with proper protocol
    url = build_api_url(server_ip, server_port, "/api-token-auth/")

    payload = {
        "username": username,
        "password": password
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()

        data = resp.json()
        token = data.get("token")
        if not token:
            frappe.throw(_("Token not found in API response."))

        return {"success": True, "token": token}

    except requests.exceptions.RequestException as e:
        frappe.throw(_("Connection error: {0}").format(str(e)))


@frappe.whitelist()
def test_connection():
    """
    Enhanced test connection that shows latest transactions with detailed info
    """
    # Get token from the singleton config
    cfg = frappe.get_single("ZKTeco Config")
    token = (cfg.token or "").strip()
    server_ip = frappe.db.get_single_value("ZKTeco Config", "server_ip")
    server_port = frappe.db.get_single_value("ZKTeco Config", "server_port")
    
    if str(server_port).strip() == "4370":
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((server_ip, int(server_port)))
            s.close()
            return {
                "ok": True,
                "status_code": 200,
                "url": f"{server_ip}:{server_port}",
                "total_transactions": 0,
                "transactions_preview": [],
                "message": _("Connected to device on port 4370. Token is not required."),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    if not token:
        return {"ok": False, "error": _("Token not set in ZKTeco Config. Please register/save a token first.")}

    base_url = build_api_url(server_ip, server_port, "/iclock/api/transactions/")
    day = today()
    start_time = f"{day} 00:00:00"
    end_time = f"{day} 23:59:59"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    params = {
        "start_time": start_time,
        "end_time": end_time,
    }

    try:
        resp = requests.get(base_url, headers=headers, params=params, timeout=15)
        
        if resp.ok:
            try:
                data = resp.json()
                
                # Process and format transaction data for display
                formatted_transactions = []
                transaction_count = 0
                
                # Handle ZKTeco API response structure
                if isinstance(data, dict) and 'data' in data:
                    transactions = data['data']
                    transaction_count = data.get('count', len(transactions))
                elif isinstance(data, dict) and 'results' in data:
                    transactions = data['results']
                    transaction_count = len(transactions)
                elif isinstance(data, list):
                    transactions = data
                    transaction_count = len(transactions)
                else:
                    transactions = []
                
                # Format latest 5 transactions for preview
                for transaction in transactions[:5]:
                    try:
                        # Map ZKTeco transaction fields based on actual API response
                        emp_code = transaction.get('emp_code')
                        punch_time = transaction.get('punch_time')
                        punch_state = transaction.get('punch_state')
                        punch_state_display = transaction.get('punch_state_display')
                        device_id = transaction.get('terminal_alias') or transaction.get('terminal_sn')
                        first_name = transaction.get('first_name', '')
                        last_name = transaction.get('last_name', '') or ''
                        verify_type_display = transaction.get('verify_type_display')
                        
                        # Combine first and last name
                        zkteco_name = f"{first_name} {last_name}".strip()
                        
                        # Try to find employee name from ERPNext
                        employee_name = zkteco_name
                        erpnext_employee = None
                        if emp_code:
                            # Try to find employee by employee_id or user_id
                            employee = frappe.db.get_value("Employee", 
                                                         {"employee": emp_code}, 
                                                         ["name", "employee_name"])
                            if not employee:
                                employee = frappe.db.get_value("Employee", 
                                                             {"user_id": emp_code}, 
                                                             ["name", "employee_name"])
                            if employee:
                                erpnext_employee = employee[0] if isinstance(employee, tuple) else employee
                                employee_name = f"{employee[1]} (ERPNext)" if isinstance(employee, tuple) else f"{employee} (ERPNext)"
                        
                        # Determine log type based on punch_state
                        log_type = detect_log_type(transaction)
                        
                        formatted_transactions.append({
                            "id": transaction.get('id'),
                            "employee_code": emp_code,
                            "employee_name": employee_name,
                            "erpnext_employee": erpnext_employee,
                            "punch_time": punch_time,
                            "log_type": log_type,
                            "punch_state_display": punch_state_display,
                            "device_id": device_id,
                            "verify_method": verify_type_display,
                            "zkteco_name": zkteco_name,
                            "department": transaction.get('department'),
                            "raw_data": transaction
                        })
                    except Exception as e:
                        frappe.log_error(f"Error processing transaction: {e}", "ZKTeco Transaction Processing")
                        continue
                
                return {
                    "ok": True,
                    "status_code": resp.status_code,
                    "url": resp.url,
                    "total_transactions": transaction_count,
                    "transactions_preview": formatted_transactions,
                    "raw_sample": transactions[:2] if transactions else [],
                    "message": f"Found {transaction_count} transactions for {day}"
                }
                
            except json.JSONDecodeError as e:
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": f"Invalid JSON response: {str(e)}",
                    "raw_response": resp.text[:500]
                }
        else:
            return {
                "ok": False,
                "status_code": resp.status_code,
                "url": resp.url,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}"
            }
            
    except requests.RequestException as e:
        return {
            "ok": False,
            "error": f"Connection error: {str(e)}"
        }


def sync_zkteco_transactions():
    """
    Main function to sync ZKTeco transactions with ERPNext Employee Checkin records
    """
    # Implement lock mechanism to prevent concurrent execution
    lock_key = "zkteco_sync_lock"
    if frappe.cache().get_value(lock_key):
        frappe.logger().info("ZKTeco sync already running, skipping this execution")
        return

    try:
        # Acquire lock with 5 minute timeout
        frappe.cache().set_value(lock_key, "locked", expires_in_sec=300)

        # Check if sync is enabled
        cfg = frappe.get_single("ZKTeco Config")
        if str(cfg.server_port).strip() == "4370":
            frappe.logger().info("ZKTeco Sync skipped: Device mode (port 4370) does not support API-based sync.")
            return

        if not cfg.enable_sync:
            frappe.log_error("ZKTeco sync is disabled", "ZKTeco Sync")
            return

        if not cfg.token:
            frappe.log_error("ZKTeco token not configured", "ZKTeco Sync")
            return
        # Get transactions from last sync or last hour (timezone-aware)
        last_sync = frappe.db.get_single_value("ZKTeco Config", "last_sync")
        if last_sync:
            last_sync = get_datetime(last_sync)
        else:
            last_sync = now_datetime() - timedelta(hours=1)

        current_time = now_datetime()

        transactions = fetch_zkteco_transactions(cfg, last_sync, current_time)

        transactions = adjust_checkin_sequence(transactions)

        processed_count = 0
        error_count = 0

        if transactions:
            for transaction in transactions:
                try:
                    if create_employee_checkin(transaction):
                        processed_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    error_count += 1
                    frappe.log_error(f"Error creating checkin for transaction {transaction}: {str(e)}", "ZKTeco Sync Error")

        # Always update last sync time, even if no transactions found
        total_synced = frappe.db.get_single_value("ZKTeco Config", "total_synced_records") or 0
        frappe.db.set_single_value("ZKTeco Config", "last_sync", current_time)
        frappe.db.set_single_value("ZKTeco Config", "total_synced_records", total_synced + processed_count)
        frappe.db.commit()

        if transactions:
            frappe.logger().info(f"ZKTeco Sync completed: {processed_count} processed, {error_count} errors")
        else:
            frappe.logger().info("ZKTeco Sync completed: No new transactions found")

    except Exception as e:
        frappe.log_error(f"ZKTeco sync failed: {str(e)}", "ZKTeco Sync Fatal Error")
    finally:
        # Always release lock when done
        frappe.cache().delete_value(lock_key)


def fetch_zkteco_transactions(cfg, start_time, end_time):
    """
    Fetch transactions from ZKTeco device with pagination support
    """
    server_ip = cfg.server_ip
    server_port = cfg.server_port
    token = cfg.token

    base_url = build_api_url(server_ip, server_port, "/iclock/api/transactions/")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    params = {
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    all_transactions = []
    current_url = base_url
    max_pages = 100  # Prevent infinite loops

    try:
        for page_num in range(max_pages):
            # First page uses params, subsequent pages use full URL from 'next'
            if page_num == 0:
                resp = requests.get(current_url, headers=headers, params=params, timeout=30)
            else:
                resp = requests.get(current_url, headers=headers, timeout=30)

            resp.raise_for_status()
            data = resp.json()

            # Extract transactions from response
            transactions = []
            next_url = None

            if isinstance(data, dict):
                # Check for pagination
                next_url = data.get('next')

                # Extract transactions
                if 'data' in data:
                    transactions = data['data']
                elif 'results' in data:
                    transactions = data['results']
                elif 'transactions' in data:
                    transactions = data['transactions']
            elif isinstance(data, list):
                transactions = data

            # Add transactions to the list
            if transactions:
                all_transactions.extend(transactions)

            # Check if there are more pages
            if not next_url:
                break

            current_url = next_url

            # Log pagination progress
            if page_num > 0:
                frappe.logger().info(f"ZKTeco pagination: Fetched page {page_num + 1}, total transactions so far: {len(all_transactions)}")

        if len(all_transactions) > 0:
            frappe.logger().info(f"ZKTeco fetch completed: {len(all_transactions)} transactions from {page_num + 1} page(s)")

        return all_transactions

    except Exception as e:
        frappe.log_error(f"Failed to fetch ZKTeco transactions: {str(e)}", "ZKTeco API Error")
        return all_transactions if all_transactions else []


def adjust_checkin_sequence(transactions):
    from collections import defaultdict
    
    if not transactions:
        return transactions

    frappe.logger().info("===== ADJUST_CHECKIN_SEQUENCE START =====")
    frappe.logger().info(f"Processing {len(transactions)} transactions")
    
    grouped = defaultdict(list)

    # First, log the initial state of all transactions
    for idx, t in enumerate(transactions):
        frappe.logger().info(f"Transaction {idx + 1} initial state - log_type: {t.get('log_type')}, time: {t.get('punch_time') or t.get('punchTime') or t.get('time')}")

    # Group punches per employee per date
    for t in transactions:
        emp = t.get("emp_code") or t.get("employee_code")
        raw_time = (
            t.get('punch_time') or t.get('punchTime') or
            t.get('punchtime') or t.get('timestamp') or
            t.get('time')
        )
        if not emp or not raw_time:
            frappe.logger().warning(f"Skipping transaction with missing emp_code or time: {t}")
            continue

        try:
            dt = get_datetime(raw_time)
            date_key = dt.strftime("%Y-%m-%d")
            grouped[(emp, date_key)].append((dt, t))
        except Exception as e:
            frappe.logger().warning(f"Error parsing time {raw_time}: {str(e)}")
            continue

    # Process each employee's daily check-ins
    for (emp, date), punches in grouped.items():
        frappe.logger().info(f"\nProcessing employee {emp} on {date} - {len(punches)} punches")
        
        # Sort by time
        punches.sort(key=lambda x: x[0])
        
        # Log the sorted punches
        for i, (dt, t) in enumerate(punches):
            frappe.logger().info(f"  Punch {i + 1}: {dt.time()} - Current log_type: {t.get('log_type')}")

        # If only one punch, set as IN by default
        if len(punches) == 1:
            punch = punches[0][1]
            if 'log_type' not in punch or punch['log_type'] not in ['IN', 'OUT']:
                punch["log_type"] = "IN"
                punch["_sequence_adjusted"] = True
                frappe.logger().info("  Single punch - Set as IN")
            continue

        # First punch = IN (if not already set)
        first = punches[0][1]
        if 'log_type' not in first or first['log_type'] not in ['IN', 'OUT']:
            first["log_type"] = "IN"
            first["_sequence_adjusted"] = True
            frappe.logger().info("  First punch - Set as IN")

        # Last punch = OUT (if not already set)
        last = punches[-1][1]
        if 'log_type' not in last or last['log_type'] not in ['IN', 'OUT']:
            last["log_type"] = "OUT"
            last["_sequence_adjusted"] = True
            frappe.logger().info("  Last punch - Set as OUT")

        # For exactly two punches, we're done
        if len(punches) == 2:
            frappe.logger().info("  Two punches - First is IN, Last is OUT")
            continue

        # For more than two punches, alternate the middle ones
        prev_type = "IN"  # Start with IN for the first punch
        for i in range(1, len(punches) - 1):
            current = punches[i][1]
            
            # Skip if already has a valid log type
            if 'log_type' in current and current['log_type'] in ['IN', 'OUT']:
                prev_type = current['log_type']
                frappe.logger().info(f"  Middle punch {i} - Using existing log_type: {prev_type}")
                continue
                
            # Alternate the log type
            current["log_type"] = "OUT" if prev_type == "IN" else "IN"
            current["_sequence_adjusted"] = True
            frappe.logger().info(f"  Middle punch {i} - Set as {current['log_type']} (prev: {prev_type})")
            prev_type = current["log_type"]

    frappe.logger().info("===== ADJUST_CHECKIN_SEQUENCE END =====")
    return transactions

    return transactions



def create_employee_checkin(transaction):
    """
    Create Employee Checkin record from ZKTeco transaction
    """
    try:
        # Log raw transaction for debugging
        frappe.logger().info(f"Raw transaction data: {json.dumps(transaction, default=str, ensure_ascii=False)}")
        
        # Log the incoming transaction for debugging
        frappe.logger().debug(f"Processing transaction: {json.dumps(transaction, default=str, ensure_ascii=False)}")
        
        # Extract transaction data based on ZKTeco API response structure
        try:
            # Extract employee code with multiple possible field names
            emp_code = (
                transaction.get('emp_code') or 
                transaction.get('employee_code') or
                transaction.get('employee_no') or
                str(transaction.get('id', '')).split('_')[0]  # Fallback for IDs like 'EMP001_123'
            )
            
            # Define all possible time fields to check
            time_fields = [
                'punch_time', 'punchTime', 'punchtime', 'time', 
                'timestamp', 'punchTimeStr', 'checktime', 'record_time'
            ]
            
            # Define all possible datetime formats to try
            time_formats = [
                '%Y-%m-%d %H:%M:%S',    # 2023-12-08 14:30:45
                '%Y-%m-%dT%H:%M:%S',    # 2023-12-08T14:30:45
                '%Y-%m-%d %H:%M',       # 2023-12-08 14:30
                '%Y-%m-%d',             # 2023-12-08
                '%Y/%m/%d %H:%M:%S',    # 2023/12/08 14:30:45
                '%d-%m-%Y %H:%M:%S',    # 08-12-2023 14:30:45
                '%d/%m/%Y %H:%M:%S',    # 08/12/2023 14:30:45
                '%Y%m%d%H%M%S',         # 20231208143045
                '%Y%m%d',               # 20231208
                '%d.%m.%Y %H:%M:%S',    # 08.12.2023 14:30:45
                '%b %d %Y %H:%M:%S',    # Dec 08 2023 14:30:45
                '%b %d %Y %H:%M:%S.%f', # Dec 08 2023 14:30:45.123456
                '%Y-%m-%d %H:%M:%S.%f', # 2023-12-08 14:30:45.123456
                '%Y-%m-%d %H:%M:%S%z',  # 2023-12-08 14:30:45+0500
                '%Y-%m-%dT%H:%M:%S%z',  # 2023-12-08T14:30:45+0500
            ]
            
            punch_time = None
            used_field = None
            
            # Try each time field
            for field in time_fields:
                if field not in transaction or not transaction[field]:
                    continue
                    
                value = transaction[field]
                used_field = field
                
                # Handle None or empty values
                if value is None or (isinstance(value, str) and not value.strip()):
                    continue
                    
                # Handle string timestamps
                if isinstance(value, str):
                    value = value.strip()
                    for fmt in time_formats:
                        try:
                            punch_time = datetime.strptime(value, fmt)
                            frappe.logger().debug(f"Parsed {field} as {fmt}: {punch_time}")
                            break
                        except ValueError:
                            continue
                # Handle numeric timestamps (UNIX timestamp in seconds or milliseconds)
                elif isinstance(value, (int, float)):
                    try:
                        ts = float(value)
                        # If timestamp is in milliseconds, convert to seconds
                        if ts > 1e12:  # Roughly year 2001 in milliseconds
                            ts = ts / 1000.0
                        punch_time = datetime.fromtimestamp(ts)
                        frappe.logger().debug(f"Converted {field} from timestamp: {punch_time}")
                    except (ValueError, TypeError, OSError) as e:
                        frappe.logger().debug(f"Failed to parse timestamp {value} from {field}: {str(e)}")
                        continue
                # Handle datetime objects directly
                elif hasattr(value, 'strftime'):  # Already a datetime object
                    punch_time = value
                    frappe.logger().debug(f"Using direct datetime object from {field}: {punch_time}")
                    break
                
                if punch_time is not None:
                    break
            
            if punch_time is None:
                frappe.logger().warning(f"Could not parse punch time from transaction: {json.dumps(transaction, default=str)}")
                return False
                
            # Log which field was used for debugging
            if used_field:
                frappe.logger().debug(f"Using time from field: {used_field} = {punch_time}")
            
            # Ensure punch_time is timezone-naive (remove timezone info if present)
            if hasattr(punch_time, 'tzinfo') and punch_time.tzinfo is not None:
                punch_time = punch_time.replace(tzinfo=None)
            
            # Get device information
            device_id = (
                transaction.get('terminal_alias') or 
                transaction.get('terminal_sn') or 
                transaction.get('device_alias') or
                transaction.get('device_id') or
                f"{transaction.get('ip_address', '')}:{transaction.get('port', '')}" or
                'Unknown'
            )
            
            transaction_id = transaction.get('id') or transaction.get('transaction_id') or transaction.get('uid') or 'unknown'
            
            # Additional logging for debugging
            frappe.logger().debug(f"Extracted data - Emp: {emp_code}, Time: {punch_time} (type: {type(punch_time)}), Device: {device_id}, ID: {transaction_id}")
            
            if not emp_code:
                frappe.logger().warning(f"Missing employee code in transaction: {json.dumps(transaction, default=str)}")
                return False
                
            # Validate punch time is within a reasonable range
            now = now_datetime()
            if not isinstance(punch_time, datetime):
                frappe.logger().warning(f"Invalid punch_time type: {type(punch_time)} for transaction {transaction_id}")
                return False
                
            if punch_time > now + timedelta(days=1):  # Future date check (allow 1 day in future for timezone differences)
                frappe.logger().warning(f"Future date in transaction {transaction_id}: {punch_time} (current time: {now})")
                return False
                
            if (now - punch_time) > timedelta(days=90):
                frappe.logger().warning(f"Skipping old transaction: {transaction_id} from {punch_time}")
                return False
                
        except Exception as e:
            frappe.log_error(f"Error processing transaction data: {str(e)}\nTransaction: {json.dumps(transaction, default=str)}", "ZKTeco Data Processing Error")
            return False
        
        # Find employee
        employee = find_employee_by_code(emp_code)
        if not employee:
            frappe.log_error(f"Employee not found for code: {emp_code}", "ZKTeco Employee Mapping")
            return False
        
        # Convert punch_time to datetime
        try:
            if isinstance(punch_time, str):
                punch_datetime = get_datetime(punch_time)
            else:
                punch_datetime = punch_time
                
            # If we still don't have a valid datetime, try parsing from timestamp
            if not punch_datetime and 'timestamp' in transaction:
                try:
                    punch_datetime = get_datetime(transaction['timestamp']/1000)  # Convert from milliseconds
                except:
                    pass
                    
            if not punch_datetime:
                frappe.log_error(f"Could not parse punch time: {punch_time}", "ZKTeco Time Parse Error")
                return False
                
        except Exception as e:
            frappe.log_error(f"Error parsing time {punch_time}: {str(e)}", "ZKTeco Time Parse Error")
            return False

        # Validate timestamp is reasonable
        current_time = now_datetime()
        max_past_days = 90  # Don't sync records older than 90 days

        # Check if timestamp is in the future (with 5-minute buffer for clock differences)
        if punch_datetime > current_time + timedelta(minutes=5):
            frappe.log_error(
                f"Transaction timestamp is in the future: {punch_datetime} (current: {current_time})\nTransaction: {json.dumps(transaction, default=str, ensure_ascii=False)}",
                "ZKTeco Invalid Timestamp"
            )
            return False

        # Check if timestamp is too old
        if punch_datetime < current_time - timedelta(days=max_past_days):
            frappe.logger().debug(
                f"Skipping old transaction: {punch_datetime} (older than {max_past_days} days)"
            )
            return False

        # Check if log_type was already set by adjust_checkin_sequence
        if transaction.get('_sequence_adjusted') is not None and transaction.get('log_type'):
            log_type = transaction['log_type']
            frappe.logger().info(f"Using sequence-adjusted log type: {log_type}")
        else:
            # Log before detecting log type
            frappe.logger().info("Detecting log type for transaction")
            log_type = detect_log_type(transaction)
            
            # Log the detected log type
            if log_type:
                frappe.logger().info(f"Detected log type: {log_type}")
            else:
                log_type = "IN"  # Default to "IN" if detection fails
                frappe.logger().warning("Could not determine log type, defaulting to IN")
                
            # Log the final log type being used
            frappe.logger().info(f"Final log type being used: {log_type}")
            
            # Also log transaction keys for debugging
            frappe.logger().info(f"Transaction keys: {list(transaction.keys())}")
            if 'punch_state_display' in transaction:
                frappe.logger().info(f"punch_state_display: {transaction['punch_state_display']}")
            if 'punch_state' in transaction:
                frappe.logger().info(f"punch_state: {transaction['punch_state']}")
            if 'punch' in transaction:
                frappe.logger().info(f"punch: {transaction['punch']}")

        # Build unique device_id with transaction ID to prevent duplicates
        unique_device_id = f"{device_id} (ZKTeco-{transaction_id})" if (device_id and transaction_id) else (device_id or f"ZKTeco-{transaction_id}" if transaction_id else "ZKTeco Device")
        
        # Clean up device ID if it's too long (Frappe has a limit of 140 chars)
        unique_device_id = (unique_device_id[:135] + '...') if len(unique_device_id) > 140 else unique_device_id

        # Create a more precise timestamp for the checkin (including seconds)
        checkin_time = punch_datetime.strftime('%Y-%m-%d %H:%M:%S')
        
        # Check if checkin already exists - include log_type to allow both IN and OUT for same employee/time
        existing_checkin = frappe.db.get_value("Employee Checkin", {
            "employee": employee,
            "time": ["=", checkin_time],
            "log_type": log_type,
            "device_id": ["like", f"%{device_id}%" if device_id else "%ZKTeco%"]
        }, ['name', 'device_id', 'log_type'], as_dict=1)

        if existing_checkin:
            frappe.logger().debug(f"Skipping duplicate checkin: {employee} at {checkin_time} ({log_type}) - {existing_checkin}")
            return True  # Already processed
        
        # Create Employee Checkin
        checkin_data = {
            "doctype": "Employee Checkin",
            "employee": employee,
            "time": checkin_time,
            "log_type": log_type,
            "device_id": unique_device_id,
            "skip_auto_attendance": 0
        }
        
        # Add additional metadata if available
        for field in ['device_name', 'terminal_sn', 'terminal_alias', 'verify_type', 'verify_type_display']:
            if field in transaction and transaction[field]:
                checkin_data[f'zkteco_{field}'] = str(transaction[field])
        
        # Log the checkin data for debugging
        frappe.logger().debug(f"Creating checkin: {json.dumps(checkin_data, default=str)}")
        
        checkin = frappe.get_doc(checkin_data)
        checkin.insert(ignore_permissions=True, ignore_if_duplicate=True)
        frappe.db.commit()
        
        frappe.logger().info(f"Created {log_type} checkin for employee {employee} at {checkin_time}")
        return True
        
    except frappe.DuplicateEntryError:
        frappe.logger().debug(f"Duplicate checkin detected and skipped: {str(e)}")
        frappe.db.rollback()
        return True
    except Exception as e:
        error_msg = f"Error creating Employee Checkin: {str(e)}\nTransaction: {json.dumps(transaction, default=str, ensure_ascii=False)}"
        frappe.log_error(error_msg, "ZKTeco Checkin Creation Error")
        frappe.db.rollback()
        return False
        return False


@frappe.whitelist()
def test_transaction_parsing(transaction_json):
    """
    Test how a transaction will be parsed
    """
    import json
    from frappe.utils import now_datetime
    
    try:
        if isinstance(transaction_json, str):
            transaction = json.loads(transaction_json)
        else:
            transaction = transaction_json
            
        log_type = detect_log_type(transaction)
        
        # Extract relevant fields for display
        emp_code = transaction.get('emp_code')
        punch_time = transaction.get('punch_time') or transaction.get('punchTime')
        device_id = transaction.get('terminal_alias') or transaction.get('terminal_sn') or transaction.get('device_alias')
        transaction_id = transaction.get('id') or transaction.get('transaction_id')
        
        # Try to find employee
        employee = find_employee_by_code(emp_code) if emp_code else None
        
        # Format the time if available
        formatted_time = None
        if punch_time:
            try:
                if isinstance(punch_time, str):
                    dt = get_datetime(punch_time)
                else:
                    dt = punch_time
                formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                formatted_time = str(punch_time)
        
        return {
            "success": True,
            "log_type": log_type,
            "employee": {
                "code": emp_code,
                "found": bool(employee),
                "id": employee
            },
            "time": {
                "raw": punch_time,
                "formatted": formatted_time
            },
            "device": {
                "id": device_id,
                "terminal_alias": transaction.get('terminal_alias'),
                "terminal_sn": transaction.get('terminal_sn')
            },
            "transaction_id": transaction_id,
            "parsed_fields": {
                k: v for k, v in transaction.items() 
                if k in ['punch_state', 'punch_state_display', 'log_type', 'type', 'punchtype', 'direction']
            },
            "raw_transaction": transaction
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "transaction": transaction_json if not isinstance(transaction_json, str) else transaction_json[:1000]
        }


def find_employee_by_code(emp_code):
    """
    Find employee by various ID fields
    """
    # Try employee field first
    employee = frappe.db.get_value("Employee", {"employee": emp_code}, "name")
    if employee:
        return employee
    
    # Try user_id field
    employee = frappe.db.get_value("Employee", {"user_id": emp_code}, "name")
    if employee:
        return employee
    
    # Try attendance_device_id if it exists
    if frappe.db.has_column("Employee", "attendance_device_id"):
        employee = frappe.db.get_value("Employee", {"attendance_device_id": emp_code}, "name")
        if employee:
            return employee
    
    return None


@frappe.whitelist()
@frappe.whitelist()
def test_sync_with_sample_data():
    """
    Test the sync process with sample data
    """
    sample_data = [
        {
            "id": "test-001",
            "emp_code": "EMP-0001",  # Replace with a valid employee code
            "punch_time": now_datetime().strftime('%Y-%m-%d %H:%M:%S'),
            "punch_state": 0,  # 0 for IN, 1 for OUT
            "terminal_alias": "Test Device",
            "punch_state_display": "Check In"
        },
        {
            "id": "test-002",
            "emp_code": "EMP-0001",  # Same employee as above
            "punch_time": (now_datetime() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S'),
            "punch_state": 1,  # 1 for OUT
            "terminal_alias": "Test Device",
            "punch_state_display": "Check Out"
        }
    ]
    
    results = []
    for transaction in sample_data:
        try:
            # First test parsing
            parse_result = test_transaction_parsing(transaction)
            
            # Then test creating the checkin
            create_result = create_employee_checkin(transaction)
            
            results.append({
                "transaction_id": transaction.get('id'),
                "parse_result": parse_result,
                "create_success": create_result
            })
        except Exception as e:
            results.append({
                "transaction_id": transaction.get('id'),
                "error": str(e),
                "transaction": transaction
            })
    
    return {
        "success": True,
        "results": results,
        "message": f"Processed {len(results)} sample transactions"
    }


def manual_sync():
    """
    Manual sync trigger for testing
    """
    try:
        cfg = frappe.get_single("ZKTeco Config")
        if str(cfg.server_port).strip() == "4370":
            return device_mode_sync()
        sync_zkteco_transactions()
        return {"success": True, "message": "Sync completed successfully"}
    except Exception as e:
        frappe.log_error(f"Manual sync failed: {str(e)}", "ZKTeco Manual Sync")
        return {"success": False, "message": f"Sync failed: {str(e)}"}


def scheduled_sync():
    """
    Scheduled sync function that respects the frequency setting
    """
    try:
        cfg = frappe.get_single("ZKTeco Config")
        if not cfg.enable_sync:
            return

        # For frequent syncs (less than 60 seconds), check if we should actually run
        sync_seconds = int(cfg.seconds or 300)
        if sync_seconds < 60:
            last_run = frappe.cache().get_value("zkteco_last_sync_run")
            current_time = now_datetime()

            if last_run:
                time_diff = (current_time - get_datetime(last_run)).total_seconds()
                if time_diff < sync_seconds:
                    return  # Not yet time for next sync

            # Update last run time
            frappe.cache().set_value("zkteco_last_sync_run", current_time)

        # Check if using multiple devices
        if cfg.use_multiple_devices and cfg.devices:
            sync_multiple_devices(cfg)
        elif str(cfg.server_port).strip() == "4370":
            device_mode_sync()
        else:
            sync_zkteco_transactions()

    except Exception as e:
        frappe.log_error(f"Scheduled ZKTeco sync failed: {str(e)}", "ZKTeco Scheduled Sync Error")


def cleanup_scheduler_check():
    """
    Cleanup function to ensure scheduler is working properly
    """
    try:
        cfg = frappe.get_single("ZKTeco Config")
        if cfg.enable_sync:
            # Log that the scheduler is active
            frappe.logger().info("ZKTeco scheduler check: Active")
    except Exception as e:
        frappe.log_error(f"ZKTeco scheduler check failed: {str(e)}", "ZKTeco Scheduler Check")


@frappe.whitelist()
def get_sync_status():
    """
    Get current sync status and statistics
    """
    try:
        cfg = frappe.get_single("ZKTeco Config")
        
        # Get last sync time
        last_sync = frappe.db.get_single_value("ZKTeco Config", "last_sync")
        
        # Count recent employee checkins from ZKTeco
        recent_checkins = frappe.db.count("Employee Checkin", {
            "device_id": ["like", "%ZKTeco%"],
            "creation": [">=", frappe.utils.add_days(today(), -1)]
        })
        
        # Count IN and OUT separately
        checkins_in = frappe.db.count("Employee Checkin", {
            "device_id": ["like", "%ZKTeco%"],
            "log_type": "IN",
            "creation": [">=", frappe.utils.add_days(today(), -1)]
        })
        
        checkins_out = frappe.db.count("Employee Checkin", {
            "device_id": ["like", "%ZKTeco%"],
            "log_type": "OUT",
            "creation": [">=", frappe.utils.add_days(today(), -1)]
        })
        
        return {
            "enabled": cfg.enable_sync,
            "sync_frequency": cfg.seconds,
            "last_sync": last_sync,
            "recent_checkins_24h": recent_checkins,
            "checkins_in_24h": checkins_in,
            "checkins_out_24h": checkins_out,
            "server_configured": bool(cfg.server_ip and cfg.server_port),
            "token_configured": bool(cfg.token)
        }
        
    except Exception as e:
        return {"error": str(e)}


@frappe.whitelist()
def set_config(server_ip: str, server_port: str | int, enable_sync: int = 1, seconds: int | None = None):
    cfg = frappe.get_single("ZKTeco Config")
    cfg.server_ip = server_ip
    cfg.server_port = str(server_port)
    cfg.enable_sync = cint(enable_sync)
    if seconds is not None:
        cfg.seconds = str(seconds)
    cfg.save(ignore_permissions=True)
    frappe.db.commit()
    return {
        "ok": True,
        "server_ip": cfg.server_ip,
        "server_port": cfg.server_port,
        "enable_sync": cfg.enable_sync,
        "seconds": cfg.seconds,
    }


@frappe.whitelist()
def device_mode_sync():
    # Implement lock mechanism to prevent concurrent execution
    lock_key = "zkteco_device_sync_lock"
    if frappe.cache().get_value(lock_key):
        return {"success": False, "message": "Device sync already running"}

    try:
        # Acquire lock with 5 minute timeout
        frappe.cache().set_value(lock_key, "locked", expires_in_sec=300)

        cfg = frappe.get_single("ZKTeco Config")
        ip = cfg.server_ip
        port = int(str(cfg.server_port or "4370").strip())
        if port != 4370:
            return {"success": False, "message": "Device mode only supports port 4370"}
        if not ZK:
            return {"success": False, "message": "Device library not available"}

        zk = ZK(ip, port=port, timeout=10, ommit_ping=True)
        conn = zk.connect()
        records = conn.get_attendance()

        # Convert attendance records to transaction format
        transactions = []
        for att in records or []:
            emp_code = str(getattr(att, "user_id", "") or "").strip()
            punch_datetime = getattr(att, "timestamp", None)
            punch_val = int(getattr(att, "punch", 0))

            if emp_code and punch_datetime:
                transactions.append({
                    "emp_code": emp_code,
                    "punch_time": punch_datetime,
                    "punch": punch_val,
                    "timestamp": punch_datetime,
                    "_device_mode": True
                })

        conn.disconnect()

        # Apply sequence adjustment to ensure proper IN/OUT alternation
        frappe.logger().info(f"Device mode: Got {len(transactions)} transactions, applying sequence adjustment")
        transactions = adjust_checkin_sequence(transactions)

        # Create checkins with adjusted log types
        created = 0
        for transaction in transactions:
            if create_checkin_from_attendance_v2(transaction, f"{ip}:{port}"):
                created += 1

        frappe.db.set_single_value("ZKTeco Config", "last_sync", now_datetime())
        total_synced = frappe.db.get_single_value("ZKTeco Config", "total_synced_records") or 0
        frappe.db.set_single_value("ZKTeco Config", "total_synced_records", total_synced + created)
        frappe.db.commit()

        frappe.logger().info(f"Device mode sync completed: {created} records created")
        return {"success": True, "created": created}
    except Exception as e:
        frappe.log_error(f"Device mode sync failed: {str(e)}", "ZKTeco Device Sync Error")
        return {"success": False, "message": str(e)}
    finally:
        # Always release lock when done
        frappe.cache().delete_value(lock_key)


def create_checkin_from_attendance(att, device_id):
    try:
        emp_code = str(getattr(att, "user_id", "") or "").strip()
        if not emp_code:
            return False
        employee = find_employee_by_code(emp_code)
        if not employee:
            return False
        punch_datetime = getattr(att, "timestamp", None)
        if not punch_datetime:
            return False

        # Validate timestamp is reasonable
        current_time = now_datetime()
        max_past_days = 90

        # Check if timestamp is in the future
        if punch_datetime > current_time + timedelta(minutes=5):
            return False

        # Check if timestamp is too old
        if punch_datetime < current_time - timedelta(days=max_past_days):
            return False

        log_type = "IN"
        try:
            punch_val = int(getattr(att, "punch", 0))
            log_type = "OUT" if punch_val == 1 else "IN"
        except Exception:
            log_type = "IN"
        # Fixed: Include log_type in duplicate check to allow both IN and OUT
        existing = frappe.db.exists("Employee Checkin", {
            "employee": employee,
            "time": punch_datetime,
            "device_id": device_id,
            "log_type": log_type
        })
        if existing:
            return True
        checkin = frappe.get_doc({
            "doctype": "Employee Checkin",
            "employee": employee,
            "time": punch_datetime,
            "log_type": log_type,
            "device_id": device_id,
            "skip_auto_attendance": 0
        })
        checkin.insert(ignore_permissions=True)
        frappe.db.commit()
        return True
    except Exception:
        return False


def create_checkin_from_attendance_v2(transaction, device_id):
    """
    Create checkin from transaction dict (used after sequence adjustment)
    """
    try:
        emp_code = transaction.get("emp_code")
        if not emp_code:
            return False

        employee = find_employee_by_code(emp_code)
        if not employee:
            frappe.logger().debug(f"Employee not found for code: {emp_code}")
            return False

        punch_datetime = transaction.get("punch_time") or transaction.get("timestamp")
        if not punch_datetime:
            return False

        # Validate timestamp is reasonable
        current_time = now_datetime()
        max_past_days = 90

        # Check if timestamp is in the future
        if punch_datetime > current_time + timedelta(minutes=5):
            return False

        # Check if timestamp is too old
        if punch_datetime < current_time - timedelta(days=max_past_days):
            return False

        # Use log_type from adjusted sequence (this is the key fix!)
        log_type = transaction.get("log_type", "IN")

        # Log the action for debugging
        frappe.logger().debug(f"Creating {log_type} checkin for {employee} at {punch_datetime}")

        # Check for existing record with same time and log_type
        existing = frappe.db.exists("Employee Checkin", {
            "employee": employee,
            "time": punch_datetime,
            "device_id": device_id,
            "log_type": log_type
        })

        if existing:
            frappe.logger().debug(f"Duplicate found, skipping: {employee} at {punch_datetime} ({log_type})")
            return True

        # Create the checkin
        checkin = frappe.get_doc({
            "doctype": "Employee Checkin",
            "employee": employee,
            "time": punch_datetime,
            "log_type": log_type,
            "device_id": device_id,
            "skip_auto_attendance": 0
        })
        checkin.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.logger().info(f"✅ Created {log_type} checkin for {employee} at {punch_datetime}")
        return True

    except Exception as e:
        frappe.logger().error(f"Error creating checkin: {str(e)}")
        frappe.db.rollback()
        return False


@frappe.whitelist()
def fix_existing_checkins():
    """
    One-click fix for existing checkin records with wrong IN/OUT log types
    """
    try:
        from collections import defaultdict

        # Get all ZKTeco checkin records
        checkins = frappe.get_all("Employee Checkin",
            filters={"device_id": ["like", "%:4370%"]},
            fields=["name", "employee", "employee_name", "time", "log_type"],
            order_by="employee asc, time asc"
        )

        if not checkins:
            return {"success": True, "message": "No records found to fix"}

        # Group by employee and date
        grouped = defaultdict(list)
        for checkin in checkins:
            emp = checkin.employee
            dt = get_datetime(checkin.time)
            date_key = dt.strftime("%Y-%m-%d")
            grouped[(emp, date_key)].append({
                "name": checkin.name,
                "time": dt,
                "current_log_type": checkin.log_type
            })

        updates = []
        for (emp, date), daily_checkins in grouped.items():
            daily_checkins.sort(key=lambda x: x["time"])

            for idx, checkin in enumerate(daily_checkins):
                if idx == 0:
                    correct = "IN"
                elif idx == len(daily_checkins) - 1:
                    correct = "OUT"
                else:
                    prev = daily_checkins[idx - 1].get("correct_log_type", daily_checkins[idx - 1]["current_log_type"])
                    correct = "OUT" if prev == "IN" else "IN"

                checkin["correct_log_type"] = correct

                if checkin["current_log_type"] != correct:
                    updates.append((checkin["name"], correct))

        # Apply updates
        for name, log_type in updates:
            frappe.db.set_value("Employee Checkin", name, "log_type", log_type, update_modified=True)

        frappe.db.commit()

        return {
            "success": True,
            "message": f"Successfully fixed {len(updates)} records",
            "updated_count": len(updates)
        }

    except Exception as e:
        frappe.log_error(f"Error fixing checkins: {str(e)}", "ZKTeco Fix Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def remove_duplicate_checkins():
    """
    Remove duplicate Employee Checkin records (same employee + time + log_type)
    """
    try:
        checkins = frappe.get_all("Employee Checkin",
            filters={"device_id": ["like", "%:4370%"]},
            fields=["name", "employee", "time", "log_type", "creation"],
            order_by="employee asc, time asc, creation asc"
        )

        seen = {}
        to_delete = []

        for checkin in checkins:
            key = (checkin.employee, str(checkin.time), checkin.log_type)

            if key in seen:
                to_delete.append(checkin.name)
            else:
                seen[key] = checkin.name

        # Delete duplicates
        for name in to_delete:
            frappe.delete_doc("Employee Checkin", name, ignore_permissions=True, force=True)

        frappe.db.commit()

        return {
            "success": True,
            "message": f"Successfully removed {len(to_delete)} duplicate records",
            "deleted_count": len(to_delete)
        }

    except Exception as e:
        frappe.log_error(f"Error removing duplicates: {str(e)}", "ZKTeco Duplicate Removal Error")
        return {"success": False, "message": str(e)}


def sync_multiple_devices(cfg):
    """
    Sync from multiple ZKTeco devices configured in child table
    """
    try:
        if not cfg.devices:
            frappe.logger().warning("No devices configured for multi-device sync")
            return

        total_created = 0
        total_devices = 0
        failed_devices = []

        for device in cfg.devices:
            if not device.enabled:
                frappe.logger().info(f"Skipping disabled device: {device.device_name}")
                continue

            try:
                frappe.logger().info(f"Syncing device: {device.device_name} ({device.server_ip}:{device.server_port})")

                # Check if device mode (port 4370) or API mode
                port = str(device.server_port).strip()
                if port == "4370":
                    result = sync_single_device_mode(device)
                else:
                    result = sync_single_api_mode(device)

                if result.get("success"):
                    total_created += result.get("created", 0)
                    total_devices += 1

                    # Update device sync stats
                    frappe.db.set_value("ZKTeco Device", device.name, {
                        "last_sync": now_datetime(),
                        "total_synced": (device.total_synced or 0) + result.get("created", 0)
                    })
                else:
                    failed_devices.append(f"{device.device_name}: {result.get('message', 'Unknown error')}")

            except Exception as e:
                error_msg = f"Device {device.device_name} sync failed: {str(e)}"
                frappe.logger().error(error_msg)
                failed_devices.append(f"{device.device_name}: {str(e)}")

        # Update global sync stats
        frappe.db.set_single_value("ZKTeco Config", "last_sync", now_datetime())
        current_total = frappe.db.get_single_value("ZKTeco Config", "total_synced_records") or 0
        frappe.db.set_single_value("ZKTeco Config", "total_synced_records", current_total + total_created)
        frappe.db.commit()

        summary = f"Synced {total_devices} device(s), created {total_created} records"
        if failed_devices:
            summary += f"\n\nFailed devices:\n" + "\n".join(failed_devices)

        frappe.logger().info(summary)
        return {"success": True, "message": summary, "created": total_created}

    except Exception as e:
        frappe.log_error(f"Multi-device sync failed: {str(e)}", "ZKTeco Multi-Device Sync Error")
        return {"success": False, "message": str(e)}


def sync_single_device_mode(device):
    """
    Sync single device in Device Mode (Port 4370)
    """
    try:
        if not ZK:
            return {"success": False, "message": "Device library not available"}

        ip = device.server_ip
        port = int(device.server_port)

        zk = ZK(ip, port=port, timeout=10, ommit_ping=True)
        conn = zk.connect()
        records = conn.get_attendance()

        # Convert attendance records to transaction format
        transactions = []
        for att in records or []:
            emp_code = str(getattr(att, "user_id", "") or "").strip()
            punch_datetime = getattr(att, "timestamp", None)
            punch_val = int(getattr(att, "punch", 0))

            if emp_code and punch_datetime:
                transactions.append({
                    "emp_code": emp_code,
                    "punch_time": punch_datetime,
                    "punch": punch_val,
                    "timestamp": punch_datetime,
                    "_device_mode": True
                })

        conn.disconnect()

        # Apply sequence adjustment
        frappe.logger().info(f"Device {device.device_name}: Got {len(transactions)} transactions")
        transactions = adjust_checkin_sequence(transactions)

        # Create checkins
        created = 0
        device_id = f"{ip}:{port}"
        for transaction in transactions:
            if create_checkin_from_attendance_v2(transaction, device_id):
                created += 1

        frappe.logger().info(f"Device {device.device_name}: Created {created} records")
        return {"success": True, "created": created}

    except Exception as e:
        return {"success": False, "message": str(e)}


def sync_single_api_mode(device):
    """
    Sync single device in API Mode (Port 80/443)
    """
    try:
        ip = device.server_ip
        port = device.server_port
        token = device.token

        if not token:
            return {"success": False, "message": "API token not configured"}

        # Fetch transactions using the API
        base_url = f"http://{ip}:{port}"
        headers = {"Authorization": f"Bearer {token}"}

        # Get transactions (simplified - you may need to adjust based on your API)
        response = requests.get(f"{base_url}/iclock/api/transactions/", headers=headers, timeout=30)

        if response.status_code != 200:
            return {"success": False, "message": f"API error: {response.status_code}"}

        transactions = response.json()
        if not transactions:
            return {"success": True, "created": 0}

        # Apply sequence adjustment
        transactions = adjust_checkin_sequence(transactions)

        # Create checkins
        created = 0
        device_id = f"{ip}:{port}"
        for transaction in transactions:
            if create_checkin_from_attendance_v2(transaction, device_id):
                created += 1

        return {"success": True, "created": created}

    except Exception as e:
        return {"success": False, "message": str(e)}

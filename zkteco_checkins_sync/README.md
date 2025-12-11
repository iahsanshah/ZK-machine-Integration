# ZKTeco Checkin Sync

---

## Executive Summary

**ZKTeco Checkin Sync** is an enterprise-grade Frappe/ERPNext application that automates the synchronization of employee attendance data from ZKTeco biometric devices. This solution provides real-time check-in/check-out transaction management with intelligent employee mapping, duplicate prevention, and comprehensive audit logging.

---

## Key Features

### Core Functionality

- **Real-time Synchronization**: Configurable sync intervals (10 seconds to 1 hour)
- **Bidirectional Support**: Both API mode (ZKBio Time Server) and Device mode (Port 4370)
- **Intelligent Log Type Detection**: Sequence-based algorithm for CHECK-IN/CHECK-OUT classification
- **Employee Mapping**: Automatic mapping via Employee ID, User ID, or custom fields
- **Duplicate Prevention**: Smart duplicate detection with log_type awareness
- **Device Health Monitoring**: Quick connectivity status checks without token requirement

### Advanced Capabilities

- **Dynamic Scheduler**: Auto-adjusting cron jobs based on configured frequency
- **Comprehensive Audit Logging**: Detailed error tracking and sync statistics
- **Transaction Preview**: Pre-sync transaction review with employee mapping validation
- **Separate IN/OUT Counting**: Distinct metrics for check-ins and check-outs
- **Multi-mode Support**: Automatic device mode detection (port 4370)

### 🆕 Maintenance & Fix Tools (NEW!)

- **🔧 One-Click Fix IN/OUT Types**: Automatically fix all existing records with incorrect log types
- **🗑️ Remove Duplicates**: Clean up duplicate checkin records with one click
- **Sequence-Based Detection**: Intelligent alternating IN/OUT logic (First=IN, Last=OUT, Middle=Alternate)
- **No Manual Intervention**: Fully automated fixes for common data issues

---


### ZKTeco Device Requirements

- **ZKBio Time Software**: Latest stable release installed
- **Network Configuration**: Device must be accessible from ERPNext server
- **API Access**: Enabled on ZKBio Time server
- **Authentication**: Superuser credentials available
- **Supported Models**: ZKTeco T&A devices with REST API support

---

## Installation Guide

### Step 1: Install the Application

```bash
# Navigate to your Frappe Bench directory
cd /path/to/frappe-bench

# Get the application
bench get-app https://github.com/Musab1khan/Zkteco-Checkins-Sync.git

# Install on your site
bench --site your-site.com install-app zkteco_checkins_sync

# Run database migrations
bench --site your-site.com migrate

# Rebuild assets
bench build
```

### Step 2: Configure ZKTeco Device

1. **Access ZKBio Time Software**
   - Open ZKBio Time on your ZKTeco server
   - Navigate to: System Settings → Communication

2. **Record Device Details**
   - Note the **Server IP** (e.g., 192.168.1.100)
   - Note the **Port** (typically 80 for API, 4370 for direct device)
   - Obtain **Superuser Username** and **Password**

3. **Enable API Access**
   - Ensure API/REST endpoints are enabled
   - Verify network connectivity from ERPNext server to ZKTeco device

### Step 3: Configure in ERPNext

1. **Navigate to ZKTeco Config**
   - URL: `/app/zkteco-config`
   - Or: Setup → ZKTeco Checkin Sync → ZKTeco Config

2. **Fill Basic Configuration**
   - Check **Enable Sync**
   - Enter **Server IP**
   - Enter **Server Port**

3. **Set Credentials**
   - Enter **Username** (ZKBio Time superuser)
   - Enter **Password** (corresponding password)

4. **Register API Token**
   - Click **"Register API Token"** button
   - Wait for token generation and save

5. **Configure Sync Settings**
   - Select **Sync Frequency** (recommended: 5 minutes for standard setups)
   - Frequency options: 10s, 30s, 1m, 2m, 5m, 10m, 15m, 30m, 1h

---

## Usage Guide

### Device Connection Status Check

**Before anything else, verify device connectivity:**

1. Fill in **Server IP** and **Server Port**
2. Click **"🔍 Check Device Status"** button
3. Result will show:
   - ✅ **GREEN**: Device is reachable and online
   - ❌ **RED**: Device unreachable (check power, network, firewall)

**No token required for this check!**

### Testing Connection with Transactions

1. Click **"Test Connection"** button
2. System will display:
   - Total transactions from today
   - Employee mapping status (Found/Not Found)
   - Sample transaction preview with IN/OUT classification
   - Response status and timestamps

### Manual Sync Operations

1. Open ZKTeco Config form
2. Click **"Manual Sync"** in Actions menu
3. Monitor Employee Checkin list for new records
4. Check log for any errors: Error Log doctype

### Monitoring Sync Status

1. Click **"Sync Status"** in Actions menu
2. View dashboard showing:
   - Sync enabled status
   - Configured frequency
   - Last sync timestamp
   - Recent check-ins (total, IN count, OUT count)
   - Server and token configuration status

### 🆕 Maintenance Operations (NEW!)

#### Fix Incorrect IN/OUT Log Types

If you have existing records with wrong IN/OUT types (e.g., all showing as IN):

1. Open ZKTeco Config form
2. Click **"🔧 Fix IN/OUT Types"** in Maintenance menu
3. Confirm the action
4. System will automatically:
   - Analyze all checkin records by employee and date
   - Apply intelligent sequence logic (First punch = IN, Last = OUT, Middle = Alternate)
   - Update incorrect records
   - Show summary of fixed records

**Use this when:**
- All records show as "IN" but should have "OUT" entries
- After importing old data
- After fixing sync logic issues

#### Remove Duplicate Checkins

If you have duplicate records (same employee, same time, same log type):

1. Open ZKTeco Config form
2. Click **"🗑️ Remove Duplicates"** in Maintenance menu
3. Confirm the action
4. System will:
   - Find all duplicate records
   - Keep the oldest record (first created)
   - Delete newer duplicates
   - Show count of removed records

**Use this when:**
- Multiple syncs created duplicate entries
- Same transaction appears multiple times
- After data migration issues

---

## Employee Mapping

### How It Works

The system matches ZKTeco employee codes to ERPNext employees using multiple methods in priority order:

1. **Employee ID field** (Primary method)
   - ZKTeco `emp_code` = ERPNext `Employee.employee`
   - Example: "EMP001" matches to Employee with ID "EMP001"

2. **User ID field** (Secondary method)
   - ZKTeco `emp_code` = ERPNext `Employee.user_id`
   - Example: "john.doe" matches to Employee with User ID "john.doe"

3. **Custom Attendance Device ID** (Advanced method)
   - Requires custom field `attendance_device_id` on Employee doctype
   - ZKTeco `emp_code` = ERPNext `Employee.attendance_device_id`

### Setup Best Practices

**Recommended: Use Employee ID Method**

```
Employee Master Configuration:
├─ Employee (primary key): EMP001
├─ Employee Name: John Doe
├─ User ID: (optional, alternate mapping)
└─ Department: Sales
```

**Verification Query:**

```sql
SELECT employee, employee_name, user_id FROM `tabEmployee` 
WHERE employee IN (SELECT DISTINCT emp_code FROM zkteco_transactions)
```

### Troubleshooting Unmapped Employees

If transactions show "Employee Not Found":

1. **Verify Employee Records Exist**
   ```
   HR → Employee List → Search for employee code
   ```

2. **Check Code Format Consistency**
   - ZKTeco: "EMP001" vs ERPNext: "emp001" (case sensitivity)
   - Remove leading/trailing spaces
   - Verify no special characters

3. **Enable Custom Field Method**
   - Customize Employee doctype
   - Add field: `attendance_device_id` (Data type)
   - Set values matching ZKTeco emp_codes

---

## Technical Architecture

### Transaction Flow Diagram

```
ZKTeco Device (Fingerprint Punch)
    ↓
[API Mode or Device Mode (Port 4370)]
    ↓
fetch_zkteco_transactions() → Get all transactions
    ↓
adjust_checkin_sequence() → Group by employee & date
    ↓
Sequence-Based Detection:
  - Single punch → IN
  - First punch of day → IN
  - Last punch of day → OUT
  - Middle punches → Alternate (IN→OUT→IN→OUT)
    ↓
create_employee_checkin() → With correct log_type
    ↓
[Duplicate Check: employee + time + log_type]
    ↓
ERPNext Employee Checkin Record
```

### Log Type Detection Logic (Sequence-Based)

**🆕 NEW: Intelligent Sequence Detection**

The system now uses a **smart sequence-based algorithm** that works perfectly for Device Mode (Port 4370):

1. **Group by Employee & Date**: All punches are grouped per employee per day
2. **Sort by Time**: Chronological order ensures correct sequence
3. **Apply Rules**:
   - If only **1 punch** → **IN** (employee forgot to punch out)
   - **First punch** of the day → **IN** (morning arrival)
   - **Last punch** of the day → **OUT** (evening departure)
   - **Middle punches** → Alternate between IN and OUT

**Example:**
```
Employee: John Doe | Date: 2025-12-08

09:00 AM → IN  (First punch)
12:00 PM → OUT (Previous was IN)
01:00 PM → IN  (Previous was OUT)
06:00 PM → OUT (Last punch)
```

**Benefits:**
- ✅ Works even when device doesn't send punch type
- ✅ Handles multiple breaks during the day
- ✅ Automatically fixes incorrect sequences
- ✅ No manual intervention needed

**Fallback Detection (API Mode):**

For API mode, the system also checks these fields:

1. **punch_state (numeric)**: 0=IN, 1=OUT
2. **punch_state_display (text)**: "Check In"/"Check Out"
3. **log_type (direct field)**: Explicit IN/OUT value
4. **punch (device mode)**: 0=IN, 1=OUT (pyzk library)

This ensures compatibility with different ZKTeco API versions and configurations.

### Duplicate Prevention

**Before Creating Record:**

```python
existing = frappe.db.exists("Employee Checkin", {
    "employee": employee,
    "time": punch_datetime,
    "device_id": device_id,
    "log_type": log_type  # Critical: prevents false duplicates
})
```

Without `log_type` in the check, the same timestamp would incorrectly block the OUT transaction.

---

## API Configuration Modes

### Mode 1: ZKBio API Server (Recommended)

**Use When:**
- ZKBio Time server is running
- Port 80 (or custom) is available
- Need periodic (not real-time) sync

**Configuration:**
```
Server IP: 192.168.1.100
Server Port: 80
Credentials: Superuser username/password
Sync Frequency: 5-15 minutes recommended
```

**Advantages:**
- Stable, well-documented API
- Historical transaction retrieval
- Flexible filtering options

### Mode 2: Device Direct Connection (Port 4370)

**Use When:**
- Device is on network (no ZKBio server)
- Need real-time sync capability
- Prefer direct device communication

**Configuration:**
```
Server IP: 192.168.1.200
Server Port: 4370
Credentials: Not required (auto-detected)
Sync Frequency: 10-30 seconds recommended
```

**Advantages:**
- No token management required
- Real-time synchronization
- Direct device communication

**Requirements:**
- `pyzk` library must be installed
- Port 4370 must be accessible
- Device firmware supports USB fingerprint protocol

---

## Performance Optimization

### Recommended Settings by Organization Size

| Organization Size | Sync Frequency | Rationale |
|-------------------|----------------|-----------|
| **< 50 employees** | 30-60 seconds | Low transaction volume |
| **50-200 employees** | 2-5 minutes | Balanced load |
| **200-500 employees** | 5-10 minutes | Medium load management |
| **500+ employees** | 10-15 minutes | Heavy processing required |

### Database Optimization

Add these indexes to improve query performance:

```sql
-- Performance indexes
ALTER TABLE `tabEmployee Checkin` 
ADD INDEX `idx_device_time` (`device_id`, `time`);

ALTER TABLE `tabEmployee Checkin` 
ADD INDEX `idx_employee_time` (`employee`, `time`);

ALTER TABLE `tabEmployee Checkin` 
ADD INDEX `idx_log_type` (`log_type`, `creation`);

-- Reduce scan time for duplicate checks
ALTER TABLE `tabEmployee Checkin` 
ADD UNIQUE KEY `uq_emp_time_type` (`employee`, `time`, `log_type`);
```

### Scheduled Job Optimization

The system automatically adjusts cron jobs based on frequency:

```
10-30 seconds   → */1 * * * * (every minute)
30s-5 minutes   → */5 * * * * (every 5 minutes)
5-10 minutes    → */10 * * * * (every 10 minutes)
15+ minutes     → hourly or custom
```

---

## Troubleshooting Guide

### Issue: "Device Not Connected" Status

**Check List:**
1. Verify ZKTeco device is powered on
2. Ping device from ERPNext server: `ping 192.168.1.100`
3. Check firewall allows port 80 (or custom): `telnet 192.168.1.100 80`
4. Verify network cable connection
5. Check ZKBio Time software is running

**Command Line Verification:**
```bash
# Test connectivity
curl -I http://192.168.1.100:80/

# Test specific API endpoint
curl http://192.168.1.100:80/iclock/api/transactions/
```

### Issue: "Invalid Token" or "Token Expired"

**Solutions:**
1. Clear existing token in ZKTeco Config
2. Re-enter credentials
3. Click "Register API Token" again
4. Verify superuser credentials are correct
5. Check user has API access permissions in ZKBio Time

### Issue: "Employee Not Found" After Sync

**Diagnostics:**

```python
# In Frappe Console, check what's being mapped
frappe.db.get_list("Employee Checkin", {
    "device_id": ["like", "%ZKTeco%"],
    "creation": [">=", frappe.utils.get_datetime().date()]
}, ["name", "employee", "log_type", "time"])

# Check employee codes in ZKTeco vs ERPNext
SELECT DISTINCT emp_code FROM zkteco_transactions
SELECT employee FROM `tabEmployee`
```

**Resolution Steps:**
1. Export ZKTeco employee list with codes
2. Import to ERPNext Employee doctype
3. Ensure Employee ID field matches ZKTeco emp_code
4. Run Test Connection to verify mapping
5. Retry Manual Sync

### Issue: Only CHECK-IN Records, No CHECK-OUT

**🆕 FIXED! Use the new maintenance tools:**

**Quick Fix (Recommended):**
1. Open ZKTeco Config form
2. Click **"🔧 Fix IN/OUT Types"** in Maintenance menu
3. Confirm and wait for completion
4. All records will be automatically corrected!

**What was the problem?**
- Device Mode (Port 4370) doesn't always send punch type from the device
- Old code couldn't differentiate between IN and OUT
- All punches were being marked as "IN" by default

**How it's fixed now:**
- Sequence-based detection algorithm
- Groups punches by employee and date
- First punch = IN, Last punch = OUT
- Middle punches alternate automatically

**Verification:**
```python
# Check your data has both IN and OUT
in_count = frappe.db.count("Employee Checkin", {
    "log_type": "IN",
    "device_id": ["like", "%:4370%"]
})

out_count = frappe.db.count("Employee Checkin", {
    "log_type": "OUT",
    "device_id": ["like", "%:4370%"]
})

print(f"IN: {in_count}, OUT: {out_count}")
# Should show reasonable split, not all IN!
```

**Before Fix:**
```
Total Records: 121
IN: 121 ❌
OUT: 0 ❌
```

**After Fix:**
```
Total Records: 121
IN: 71 ✅
OUT: 50 ✅
```

### Issue: Duplicate Checkin Records

**🆕 FIXED! Use the duplicate removal tool:**

**Quick Fix:**
1. Open ZKTeco Config form
2. Click **"🗑️ Remove Duplicates"** in Maintenance menu
3. Confirm and wait for completion

**What causes duplicates?**
- Multiple sync runs on the same data
- Network issues causing retries
- System restart during sync

**How duplicates are detected:**
- Same employee
- Same timestamp
- Same log_type (IN/OUT)

Oldest record is kept, newer duplicates are deleted.

### Issue: Sync Takes Too Long

**Performance Tuning:**
1. Increase sync frequency interval (1 hour instead of 5 minutes)
2. Add database indexes (see Performance Optimization section)
3. Check database query log for slow queries: `SHOW PROCESSLIST;`
4. Reduce number of duplicate check methods

**Monitor Sync Performance:**
```python
# Check sync duration
frappe.db.get_single_value("ZKTeco Config", "last_sync")

# Count recent transactions
frappe.db.count("Employee Checkin", {
    "device_id": ["like", "%ZKTeco%"],
    "modified": [">=", frappe.utils.add_minutes(frappe.utils.now(), -5)]
})
```

---

## API Reference

### Core Functions

#### `check_device_status(server_ip, server_port)`

**Purpose:** Quick device connectivity check without authentication

**Parameters:**
- `server_ip` (string): Device IP address
- `server_port` (int): Device port number

**Returns:**
```json
{
    "connected": true,
    "ip": "192.168.1.100",
    "port": 80,
    "response_time": 45.23,
    "message": "Device is online"
}
```

**Usage:**
```python
frappe.call({
    method: "zkteco_checkins_sync...check_device_status",
    args: {server_ip: "192.168.1.100", server_port: 80},
    callback: (r) => console.log(r.message)
})
```

#### `register_api_token(server_ip, server_port, username, password)`

**Purpose:** Generate and register API authentication token

**Parameters:**
- `server_ip` (string): ZKBio server IP
- `server_port` (int): ZKBio server port
- `username` (string): Superuser username
- `password` (string): Superuser password

**Returns:**
```json
{
    "success": true,
    "token": "eyJ0eXAiOiJKV1QiLC..."
}
```

#### `test_connection()`

**Purpose:** Verify API connectivity and preview today's transactions

**Returns:**
```json
{
    "ok": true,
    "status_code": 200,
    "total_transactions": 150,
    "transactions_preview": [...],
    "message": "Found 150 transactions for 2025-12-05"
}
```

#### `manual_sync()`

**Purpose:** Trigger immediate synchronization of transactions

**Returns:**
```json
{
    "success": true,
    "message": "Sync completed successfully"
}
```

#### `get_sync_status()`

**Purpose:** Get current sync status and statistics

**Returns:**
```json
{
    "enabled": true,
    "sync_frequency": "300",
    "last_sync": "2025-12-05 14:30:15",
    "recent_checkins_24h": 245,
    "checkins_in_24h": 122,
    "checkins_out_24h": 123,
    "server_configured": true,
    "token_configured": true
}
```

---

## Security Considerations

### Authentication & Authorization

**API Token Security:**
- Tokens are stored encrypted in database
- Auto-expires after configured period (recommend 90 days)
- Rotate tokens regularly: `Register API Token` button
- Never share token in logs or error messages

**Access Control:**
- Restricted to System Manager and HR Manager roles
- HR User role can view only
- Audit trail maintained in database

**Best Practices:**
1. Use dedicated ZKBio superuser account for this integration
2. Limit superuser account IP access if possible
3. Change superuser password quarterly
4. Monitor "last_sync" for unusual patterns

### Data Security

**In Transit:**
- Use HTTPS for ZKBio API connections (if available)
- Verify SSL certificates if enabled
- Keep ZKTeco device on private network

**At Rest:**
- Employee Checkin records inherit ERPNext encryption
- Database backups automatically encrypted
- API tokens encrypted in database

**Audit & Compliance:**
- All sync operations logged in Error Log doctype
- Manual sync tracked with timestamps
- Device connection attempts logged
- Maintenance audit trail available

---

## Advanced Configuration

### Custom Employee Code Mapping

**Scenario:** Your ZKTeco uses custom employee codes not matching ERPNext

**Solution: Create Mapping Custom Field**

```python
# In Frappe Console:
doc = frappe.get_doc("Employee", "EMP001")
doc.set("custom_attendance_device_id", "ZK_CODE_001")
doc.save()

# Verify
frappe.db.get_value("Employee", "EMP001", "custom_attendance_device_id")
```

**Then modify `find_employee_by_code()` to use it:**

```python
def find_employee_by_code(emp_code):
    # Try employee field first
    employee = frappe.db.get_value("Employee", {"employee": emp_code}, "name")
    if employee:
        return employee
    
    # Try custom field
    employee = frappe.db.get_value("Employee", 
        {"custom_attendance_device_id": emp_code}, "name")
    if employee:
        return employee
    
    return None
```

### Batch Employee Import

**Mass Sync ZKTeco Employees:**

```python
import frappe
from frappe.client import insert

zkteco_employees = [
    {"emp_code": "001", "name": "John Doe"},
    {"emp_code": "002", "name": "Jane Smith"},
]

for emp in zkteco_employees:
    doc = frappe.new_doc("Employee")
    doc.employee = emp["emp_code"]
    doc.employee_name = emp["name"]
    doc.status = "Active"
    doc.insert()

frappe.db.commit()
print(f"Imported {len(zkteco_employees)} employees")
```

---

## Monitoring & Reporting

### Sync Status Dashboard

Navigate to ZKTeco Config and click "Sync Status" to see:
- Real-time sync state
- Last sync timestamp
- 24-hour check-in counts (IN vs OUT)
- Configuration status indicators

### Custom Reports

**Report 1: Today's Attendance Summary**

```python
frappe.db.sql("""
    SELECT 
        employee,
        COUNT(CASE WHEN log_type='IN' THEN 1 END) as checkins,
        COUNT(CASE WHEN log_type='OUT' THEN 1 END) as checkouts
    FROM `tabEmployee Checkin`
    WHERE DATE(creation) = CURDATE()
    AND device_id LIKE '%ZKTeco%'
    GROUP BY employee
    ORDER BY employee
""")
```

**Report 2: Device Sync Performance**

```python
frappe.db.sql("""
    SELECT 
        COUNT(*) as total_synced,
        COUNT(CASE WHEN log_type='IN' THEN 1 END) as in_count,
        COUNT(CASE WHEN log_type='OUT' THEN 1 END) as out_count,
        DATE(last_modified) as sync_date
    FROM `tabEmployee Checkin`
    WHERE device_id LIKE '%ZKTeco%'
    GROUP BY DATE(last_modified)
    ORDER BY sync_date DESC
    LIMIT 30
""")
```

### Error Log Monitoring

Check for sync errors:

```python
frappe.db.get_list("Error Log", {
    "title": ["like", "%ZKTeco%"],
    "creation": [">=", frappe.utils.get_datetime().subtract(days=1)]
}, ["error", "creation"])
```

---

## Maintenance & Support

### Regular Maintenance Tasks

**Daily:**
- Check Error Log for ZKTeco errors
- Monitor Device Status button shows green
- Verify sync completing on schedule

**Weekly:**
- Review sync statistics
- Check employee mapping quality
- Audit IN/OUT count ratio (~50/50 expected)

**Monthly:**
- Rotate API token
- Update ZKBio Time software if new version available
- Review performance metrics
- Backup configuration


---

## Version History & Changelog

### v2.0.0 (December 2025) - 🆕 Major Update

**New Features:**
- ✅ **Intelligent Sequence-Based Log Type Detection**
  - Automatic IN/OUT detection for Device Mode (Port 4370)
  - No longer depends on device sending punch type
  - Groups by employee and date, applies smart rules

- ✅ **One-Click Maintenance Tools**
  - "Fix IN/OUT Types" button in Maintenance menu
  - "Remove Duplicates" button in Maintenance menu
  - No coding required, fully automated

- ✅ **Enhanced Device Mode Support**
  - Proper sequence adjustment for all transactions
  - Works even when device doesn't send punch state
  - Handles multiple breaks during the day

**Bug Fixes:**
- Fixed: All records showing as "IN" in Device Mode
- Fixed: Duplicate records created during sync
- Fixed: Middle punches not alternating correctly
- Improved: Transaction processing performance

**Breaking Changes:**
- None - fully backward compatible

### v1.0.0 (Initial Release)

**Core Features:**
- Real-time sync with ZKTeco devices
- API Mode and Device Mode support
- Employee mapping
- Basic log type detection
- Dynamic scheduler

---

## Upgrade Guide

### Upgrading to v2.0.0 from v1.x

```bash
# Navigate to bench directory
cd /path/to/frappe-bench

# Update app from GitHub
cd apps/zkteco_checkins_sync
git pull origin main

# Navigate back to bench root
cd ../..

# Run migrations (if any)
bench --site your-site.com migrate

# Clear cache
bench --site your-site.com clear-cache

# Rebuild assets (important for new buttons!)
bench build --app zkteco_checkins_sync

# Restart
bench restart
```

### Post-Upgrade Steps

After upgrading to v2.0.0:

1. **Fix Existing Data:**
   - Open ZKTeco Config: `/app/zkteco-config`
   - Click "🗑️ Remove Duplicates" if you have duplicates
   - Click "🔧 Fix IN/OUT Types" to correct all records

2. **Verify New Features:**
   - Check that both buttons appear in Maintenance menu
   - Test connection to ensure sync still works
   - Monitor next sync to verify proper IN/OUT detection

3. **Optional: Clean Up:**
   - Review Employee Checkin list
   - Verify IN/OUT ratio is reasonable (~50/50)
   - Check sync logs for any warnings

**Rollback (if needed):**
```bash
cd apps/zkteco_checkins_sync
git checkout v1.0.0
cd ../..
bench --site your-site.com clear-cache
bench build --app zkteco_checkins_sync
bench restart
```



---


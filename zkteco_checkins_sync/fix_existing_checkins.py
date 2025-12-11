#!/usr/bin/env python3
"""
Script to fix existing Employee Checkin records that have incorrect IN/OUT log types.
This script will:
1. Find all Employee Checkin records from ZKTeco device (port 4370)
2. Group by employee and date
3. Reapply sequence-based IN/OUT detection
4. Update records with correct log_type

Usage:
    bench --site erp.cosmopharmaint.com execute zkteco_checkins_sync.fix_existing_checkins.fix_all_checkins
"""

import frappe
from frappe.utils import get_datetime
from collections import defaultdict
from datetime import datetime


def fix_all_checkins(dry_run=True):
    """
    Fix all existing checkin records with incorrect log types

    Args:
        dry_run (bool): If True, only show what would be changed without actually updating
    """
    frappe.logger().info("="*80)
    frappe.logger().info("STARTING EMPLOYEE CHECKIN FIX")
    frappe.logger().info("="*80)

    # Get all ZKTeco checkin records (device mode)
    checkins = frappe.get_all("Employee Checkin",
        filters={
            "device_id": ["like", "%111.88.28.220:4370%"],
            "time": [">=", "2025-09-01"]  # Only fix recent records
        },
        fields=["name", "employee", "employee_name", "time", "log_type", "device_id"],
        order_by="employee asc, time asc"
    )

    frappe.logger().info(f"Found {len(checkins)} checkin records to analyze")

    if not checkins:
        frappe.logger().info("No records found to fix")
        return {"success": True, "message": "No records found", "updated": 0}

    # Group by employee and date
    grouped = defaultdict(list)

    for checkin in checkins:
        emp = checkin.employee
        dt = get_datetime(checkin.time)
        date_key = dt.strftime("%Y-%m-%d")
        grouped[(emp, date_key)].append({
            "name": checkin.name,
            "employee": checkin.employee,
            "employee_name": checkin.employee_name,
            "time": dt,
            "current_log_type": checkin.log_type,
            "device_id": checkin.device_id
        })

    frappe.logger().info(f"Grouped into {len(grouped)} employee-date combinations")

    # Track changes
    updates_needed = []
    no_change_needed = 0

    # Process each employee's daily checkins
    for (emp, date), daily_checkins in grouped.items():
        # Sort by time
        daily_checkins.sort(key=lambda x: x["time"])

        frappe.logger().info(f"\n{'='*60}")
        frappe.logger().info(f"Employee: {daily_checkins[0]['employee_name']} ({emp})")
        frappe.logger().info(f"Date: {date}")
        frappe.logger().info(f"Total punches: {len(daily_checkins)}")

        # Apply sequence logic
        if len(daily_checkins) == 1:
            # Single punch = IN
            correct_log_type = "IN"
            current = daily_checkins[0]["current_log_type"]

            if current != correct_log_type:
                frappe.logger().info(f"  Single punch - Should be IN (currently: {current})")
                updates_needed.append({
                    "name": daily_checkins[0]["name"],
                    "employee_name": daily_checkins[0]["employee_name"],
                    "time": daily_checkins[0]["time"],
                    "current": current,
                    "correct": correct_log_type
                })
            else:
                no_change_needed += 1
                frappe.logger().info(f"  ✓ Single punch - Already correct (IN)")

        else:
            # Multiple punches - alternate IN/OUT
            for idx, checkin in enumerate(daily_checkins):
                # First punch = IN, then alternate
                if idx == 0:
                    correct_log_type = "IN"
                elif idx == len(daily_checkins) - 1:
                    # Last punch should be OUT (if more than 1 punch)
                    correct_log_type = "OUT"
                else:
                    # Middle punches alternate
                    prev_type = daily_checkins[idx - 1].get("correct_log_type") or daily_checkins[idx - 1]["current_log_type"]
                    correct_log_type = "OUT" if prev_type == "IN" else "IN"

                # Store correct type for next iteration
                checkin["correct_log_type"] = correct_log_type

                current = checkin["current_log_type"]
                time_str = checkin["time"].strftime("%H:%M:%S")

                if current != correct_log_type:
                    frappe.logger().info(f"  {idx+1}. {time_str} - Should be {correct_log_type} (currently: {current}) ❌")
                    updates_needed.append({
                        "name": checkin["name"],
                        "employee_name": checkin["employee_name"],
                        "time": checkin["time"],
                        "current": current,
                        "correct": correct_log_type
                    })
                else:
                    no_change_needed += 1
                    frappe.logger().info(f"  {idx+1}. {time_str} - Already correct ({correct_log_type}) ✓")

    # Summary
    frappe.logger().info("\n" + "="*80)
    frappe.logger().info("SUMMARY")
    frappe.logger().info("="*80)
    frappe.logger().info(f"Total records analyzed: {len(checkins)}")
    frappe.logger().info(f"Records needing update: {len(updates_needed)}")
    frappe.logger().info(f"Records already correct: {no_change_needed}")

    if not updates_needed:
        frappe.logger().info("\n✅ All records are already correct!")
        return {"success": True, "message": "All records already correct", "updated": 0}

    # Show what will be updated
    frappe.logger().info("\n" + "="*80)
    frappe.logger().info("UPDATES TO BE MADE:")
    frappe.logger().info("="*80)

    for update in updates_needed[:20]:  # Show first 20
        frappe.logger().info(f"{update['employee_name']} | {update['time'].strftime('%Y-%m-%d %H:%M')} | {update['current']} → {update['correct']}")

    if len(updates_needed) > 20:
        frappe.logger().info(f"... and {len(updates_needed) - 20} more")

    # Apply updates if not dry run
    if dry_run:
        frappe.logger().info("\n" + "="*80)
        frappe.logger().info("🔍 DRY RUN MODE - No changes made")
        frappe.logger().info("To apply changes, run:")
        frappe.logger().info("  bench --site erp.cosmopharmaint.com execute 'zkteco_checkins_sync.fix_existing_checkins.fix_all_checkins' --kwargs '{\"dry_run\": False}'")
        frappe.logger().info("="*80)

        return {
            "success": True,
            "dry_run": True,
            "updates_needed": len(updates_needed),
            "no_change_needed": no_change_needed
        }

    else:
        frappe.logger().info("\n" + "="*80)
        frappe.logger().info("⚙️  APPLYING UPDATES...")
        frappe.logger().info("="*80)

        updated_count = 0
        error_count = 0

        for update in updates_needed:
            try:
                frappe.db.set_value("Employee Checkin",
                    update["name"],
                    "log_type",
                    update["correct"],
                    update_modified=True
                )
                updated_count += 1

                if updated_count % 10 == 0:
                    frappe.logger().info(f"  Updated {updated_count}/{len(updates_needed)} records...")
                    frappe.db.commit()

            except Exception as e:
                error_count += 1
                frappe.logger().error(f"Error updating {update['name']}: {str(e)}")

        # Final commit
        frappe.db.commit()

        frappe.logger().info("\n" + "="*80)
        frappe.logger().info("✅ UPDATE COMPLETE")
        frappe.logger().info("="*80)
        frappe.logger().info(f"Successfully updated: {updated_count}")
        frappe.logger().info(f"Errors: {error_count}")
        frappe.logger().info("="*80)

        return {
            "success": True,
            "dry_run": False,
            "updated": updated_count,
            "errors": error_count,
            "no_change_needed": no_change_needed
        }


if __name__ == "__main__":
    print("This script must be run through Frappe bench console")
    print("Usage: bench --site erp.cosmopharmaint.com execute zkteco_checkins_sync.fix_existing_checkins.fix_all_checkins")

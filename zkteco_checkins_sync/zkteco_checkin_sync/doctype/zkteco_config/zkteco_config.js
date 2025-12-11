// Copyright (c) 2025, osama.ahmed@deliverydevs.com and contributors
// For license information, please see license.txt

frappe.ui.form.on("ZKTeco Config", {
    refresh(frm) {
        // Add custom buttons
        if (frm.doc.enable_sync && (frm.doc.token || (frm.doc.server_port || '').toString() === '4370')) {
            frm.add_custom_button(__('Manual Sync'), function() {
                manual_sync(frm);
            }, __('Actions'));

            frm.add_custom_button(__('Sync Status'), function() {
                show_sync_status(frm);
            }, __('Actions'));
        }

        // Add maintenance buttons
        frm.add_custom_button(__('🔧 Fix IN/OUT Types'), function() {
            fix_checkin_types(frm);
        }, __('Maintenance'));

        frm.add_custom_button(__('🗑️ Remove Duplicates'), function() {
            remove_duplicates(frm);
        }, __('Maintenance'));

        // Show sync status indicator
        if (frm.doc.enable_sync) {
            show_sync_indicator(frm);
        }
    },

    enable_sync(frm) {
        if (frm.doc.enable_sync) {
            frappe.show_alert({
                message: __('ZKTeco sync enabled. Configure server settings and test connection.'),
                indicator: 'blue'
            });
        }
    },

    check_device_status(frm) {
        frappe.call({
            method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.check_device_status",
            args: {
                server_ip: frm.doc.server_ip,
                server_port: frm.doc.server_port,
            },
            freeze: true,
            freeze_message: __("Checking device connection...")
        }).then((r) => {
            const result = r.message || {};
            
            if (result.connected) {
                frappe.msgprint({
                    title: __("✅ Device Connected"),
                    message: `
                        <div style="padding: 15px; background-color: #d4edda; border-radius: 5px;">
                            <h5 style="color: #155724; margin-top: 0;">🟢 Device is Reachable!</h5>
                            <p><strong>IP:</strong> ${result.ip}</p>
                            <p><strong>Port:</strong> ${result.port}</p>
                            <p><strong>Response Time:</strong> ${result.response_time || 'N/A'} ms</p>
                            <p style="margin-bottom: 0;"><strong>Status:</strong> Device is online and responding</p>
                        </div>
                    `,
                    indicator: "green"
                });
            } else {
                frappe.msgprint({
                    title: __("❌ Device Not Connected"),
                    message: `
                        <div style="padding: 15px; background-color: #f8d7da; border-radius: 5px;">
                            <h5 style="color: #721c24; margin-top: 0;">🔴 Device is Unreachable!</h5>
                            <p><strong>IP:</strong> ${result.ip}</p>
                            <p><strong>Port:</strong> ${result.port}</p>
                            <p><strong>Error:</strong> ${result.error || 'Connection timeout'}</p>
                            <hr>
                            <p style="margin-bottom: 0;"><strong>Troubleshooting:</strong></p>
                            <ul>
                                <li>Check if ZKTeco device is powered on</li>
                                <li>Verify IP address is correct</li>
                                <li>Check network connectivity</li>
                                <li>Ensure firewall allows connection on this port</li>
                            </ul>
                        </div>
                    `,
                    indicator: "red"
                });
            }
        }).catch((e) => {
            frappe.msgprint({
                title: __("Error"),
                message: `<pre style="white-space:pre-wrap; color: red;">${frappe.utils.escape_html(e.message || e)}</pre>`,
                indicator: "red"
            });
        });
    },

    test_connection(frm) {
        frappe.call({
            method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.test_connection",
            freeze: true,
            freeze_message: __("Testing connection...")
        }).then((r) => {
            const msg = r.message || {};
            if (msg.ok) {
                frappe.show_alert({
                    message: __(`✅ Connected successfully! Found ${msg.total_transactions || 0} transactions today.`),
                    indicator: "green"
                });
                
                // Show detailed transaction preview
                if (msg.transactions_preview && msg.transactions_preview.length > 0) {
                    show_transaction_preview(msg.transactions_preview, msg.total_transactions);
                } else {
                    frappe.msgprint({
                        title: __("Connection Successful"),
                        message: __(`✅ Connection successful!<br>
                                   📊 Total transactions today: ${msg.total_transactions || 0}<br>
                                   🔗 URL: ${msg.url}<br>
                                   📡 Status: ${msg.status_code}<br>
                                   ${msg.message || ''}`),
                        indicator: "green"
                    });
                }
            } else {
                frappe.show_alert({
                    message: __(`❌ Connection failed. Status: ${msg.status_code || "N/A"}`),
                    indicator: "red"
                });
                if (msg.error) {
                    frappe.msgprint({
                        title: __("Connection Error"),
                        message: `<pre style="white-space:pre-wrap; color: red;">${frappe.utils.escape_html(msg.error)}</pre>`,
                        indicator: "red"
                    });
                }
            }
        }).catch((e) => {
            frappe.msgprint({
                title: __("Error"),
                message: `<pre style="white-space:pre-wrap; color: red;">${frappe.utils.escape_html(e.message || e)}</pre>`,
                indicator: "red"
            });
        });
    },

    register_api_token(frm) {
        frappe.call({
            method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.register_api_token",
            args: {
                server_ip: frm.doc.server_ip,
                server_port: frm.doc.server_port,
                username: frm.doc.username,
                password: frm.doc.password,
            },
            freeze: true,
            freeze_message: __("Registering token...")
        }).then((r) => {
            if (r.message && r.message.token) {
                frm.set_value("token", r.message.token);
                frm.save().then(() => {
                    frappe.show_alert({ 
                        message: __("✅ API token registered and saved successfully!"), 
                        indicator: "green" 
                    });
                });
            } else if (r.message && r.message.device_mode) {
                frappe.show_alert({
                    message: __("✅ Device mode detected on port 4370 – token not required."),
                    indicator: "green"
                });
            }
        }).catch((e) => {
            frappe.msgprint({
                title: __("Token Registration Failed"),
                message: frappe.utils.escape_html(e.message || e),
                indicator: "red"
            });
        });
    }
});

function show_transaction_preview(transactions, total_count) {
    let html = `<div style="margin-bottom: 15px;">
                    <strong>📊 Found ${total_count} transactions today</strong><br>
                    <small>Showing latest ${transactions.length} transactions:</small>
                </div>`;
    
    html += `<div style="max-height: 400px; overflow-y: auto;">
             <table class="table table-bordered table-striped" style="font-size: 12px;">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th>ID</th>
                        <th>Employee</th>
                        <th>Time</th>
                        <th>Type</th>
                        <th>Device</th>
                        <th>ERPNext Status</th>
                    </tr>
                </thead>
                <tbody>`;
    
    transactions.forEach(txn => {
        const statusBadge = txn.erpnext_employee ? 
            '<span style="color: green;">✅ Mapped</span>' : 
            '<span style="color: orange;">⚠️ Not Found</span>';
        
        const logTypeColor = txn.log_type === 'IN' ? 'blue' : 'red';
        
        html += `<tr>
                    <td>${txn.id || 'N/A'}</td>
                    <td>
                        <strong>${txn.employee_code}</strong><br>
                        <small>${txn.zkteco_name || 'Unknown'}</small>
                    </td>
                    <td>${txn.punch_time}</td>
                    <td><span style="color: ${logTypeColor}; font-weight: bold;">${txn.log_type}</span></td>
                    <td>${txn.device_id || 'Unknown'}</td>
                    <td>${statusBadge}</td>
                </tr>`;
    });
    
    html += `</tbody></table></div>`;
    
    html += `<div style="margin-top: 15px; padding: 10px; background-color: #e7f3ff; border-radius: 4px;">
                <small><strong>💡 Tips:</strong><br>
                • Make sure employee codes in ERPNext match the emp_code from ZKTeco<br>
                • Employees with "Not Found" status won't be synced to ERPNext<br>
                • Enable sync and set frequency to automatically import these transactions</small>
             </div>`;
    
    const d = new frappe.ui.Dialog({
        title: __('ZKTeco Transactions Preview'),
        fields: [{
            fieldtype: 'HTML',
            fieldname: 'transaction_preview',
            options: html
        }],
        size: 'large'
    });
    
    d.show();
}

function manual_sync(frm) {
    frappe.call({
        method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.manual_sync",
        freeze: true,
        freeze_message: __("Syncing transactions...")
    }).then((r) => {
        if (r.message && r.message.success) {
            frappe.show_alert({
                message: __('✅ Manual sync completed successfully!'),
                indicator: 'green'
            });
        } else {
            frappe.show_alert({
                message: __(`❌ Sync failed: ${r.message.message || 'Unknown error'}`),
                indicator: 'red'
            });
        }
    });
}

function show_sync_status(frm) {
    frappe.call({
        method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.get_sync_status"
    }).then((r) => {
        const status = r.message || {};
        
        let html = '<div style="padding: 10px;">';
        
        if (status.error) {
            html += `<div style="color: red;">❌ Error: ${status.error}</div>`;
        } else {
            html += `<table class="table table-bordered">
                        <tr><td><strong>Sync Enabled:</strong></td><td>${status.enabled ? '✅ Yes' : '❌ No'}</td></tr>
                        <tr><td><strong>Sync Frequency:</strong></td><td>Every ${status.sync_frequency || 'N/A'} seconds</td></tr>
                        <tr><td><strong>Last Sync:</strong></td><td>${status.last_sync || 'Never'}</td></tr>
                        <tr><td><strong>Recent Check-ins (24h):</strong></td><td>${status.recent_checkins_24h || 0}</td></tr>
                        <tr><td><strong>Check-ins IN (24h):</strong></td><td>${status.checkins_in_24h || 0}</td></tr>
                        <tr><td><strong>Check-ins OUT (24h):</strong></td><td>${status.checkins_out_24h || 0}</td></tr>
                        <tr><td><strong>Server Configured:</strong></td><td>${status.server_configured ? '✅ Yes' : '❌ No'}</td></tr>
                        <tr><td><strong>Token Configured:</strong></td><td>${status.token_configured ? '✅ Yes' : '❌ No'}</td></tr>
                     </table>`;
        }
        
        html += '</div>';
        
        frappe.msgprint({
            title: __('ZKTeco Sync Status'),
            message: html,
            indicator: status.enabled ? 'green' : 'orange'
        });
    });
}

function show_sync_indicator(frm) {
    const sync_frequency = frm.doc.seconds;
    const token_configured = frm.doc.token ? true : false;
    const device_mode = (frm.doc.server_port || '').toString() === '4370';

    let indicator_color = 'red';
    let indicator_text = 'Sync Disabled';

    if (frm.doc.enable_sync && (token_configured || device_mode)) {
        indicator_color = 'green';
        indicator_text = device_mode ? 'Device Mode (4370)' : `Sync Active (${sync_frequency}s)`;
    } else if (frm.doc.enable_sync) {
        indicator_color = 'orange';
        indicator_text = 'Sync Enabled (Token Missing)';
    }

    frm.dashboard.add_indicator(indicator_text, indicator_color);
}

function fix_checkin_types() {
    frappe.confirm(
        __('This will fix all existing Employee Checkin records with incorrect IN/OUT log types. Continue?'),
        function() {
            frappe.call({
                method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.fix_existing_checkins",
                freeze: true,
                freeze_message: __("Fixing checkin records...")
            }).then((r) => {
                if (r.message && r.message.success) {
                    frappe.msgprint({
                        title: __('✅ Fix Complete'),
                        message: `<div style="padding: 15px;">
                                    <p><strong>${r.message.message}</strong></p>
                                    <p>Updated ${r.message.updated_count || 0} records</p>
                                 </div>`,
                        indicator: 'green'
                    });
                } else {
                    frappe.msgprint({
                        title: __('Error'),
                        message: r.message.message || 'Unknown error',
                        indicator: 'red'
                    });
                }
            });
        }
    );
}

function remove_duplicates() {
    frappe.confirm(
        __('This will remove duplicate Employee Checkin records (same employee, time, and log type). Continue?'),
        function() {
            frappe.call({
                method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.remove_duplicate_checkins",
                freeze: true,
                freeze_message: __("Removing duplicate records...")
            }).then((r) => {
                if (r.message && r.message.success) {
                    frappe.msgprint({
                        title: __('✅ Cleanup Complete'),
                        message: `<div style="padding: 15px;">
                                    <p><strong>${r.message.message}</strong></p>
                                    <p>Removed ${r.message.deleted_count || 0} duplicate records</p>
                                 </div>`,
                        indicator: 'green'
                    });
                } else {
                    frappe.msgprint({
                        title: __('Error'),
                        message: r.message.message || 'Unknown error',
                        indicator: 'red'
                    });
                }
            });
        }
    );
}

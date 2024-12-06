import frappe
Extra_idle_time_logs = frappe.db.sql("""
SELECT idle_log.name, idle_log.employee
FROM `tabEmployee Idle Time` as idle_log
LEFT JOIN `tabApplication Usage log` as application_usage_log
ON idle_log.employee = application_usage_log.employee
AND application_usage_log.from_time < idle_log.start_time
AND application_usage_log.to_time > idle_log.end_time
WHERE application_usage_log.employee = 'HR-EMP-00019' and application_usage_log.date = "2024-07-01"
""",as_dict=True)


Extra_idle_time_logs = frappe.db.sql("""
SELECT idle_log.name, idle_log.employee
FROM `tabEmployee Idle Time` as idle_log
LEFT JOIN `tabApplication Usage log` as application_usage_log
ON idle_log.employee = application_usage_log.employee
AND application_usage_log.from_time < idle_log.end_time
AND application_usage_log.to_time > idle_log.start_time
WHERE application_usage_log.name IS NULL
""", as_dict=True)

import frappe

import frappe

# Fetch all from_time and to_time intervals from Application Usage log
application_logs = frappe.db.sql("""
SELECT from_time, to_time
FROM `tabApplication Usage log`
WHERE employee = 'HR-EMP-00019'
""", as_dict=True)

# Fetch all Employee Idle Time logs
idle_time_logs = frappe.db.sql("""
SELECT name, employee, start_time, end_time
FROM `tabEmployee Idle Time`
WHERE employee = 'HR-EMP-00019'
""", as_dict=True)

# Function to check if there is any overlap between two time intervals
def is_overlap(idle_start, idle_end, app_start, app_end):
    return not (idle_end <= app_start or idle_start >= app_end)

# Filter Employee Idle Time logs that do not overlap with any Application Usage log intervals
filtered_idle_time_logs = []
for idle_log in idle_time_logs:
    overlap_found = False
    for app_log in application_logs:
        if is_overlap(idle_log['start_time'], idle_log['end_time'], app_log['from_time'], app_log['to_time']):
            overlap_found = True
            break
    if not overlap_found:
        filtered_idle_time_logs.append(idle_log)

# Output the filtered Employee Idle Time logs
for log in filtered_idle_time_logs:
    print(f"Name: {log['name']}, Employee: {log['employee']}, Start Time: {log['start_time']}, End Time: {log['end_time']}")


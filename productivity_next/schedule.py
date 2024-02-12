import frappe
from frappe.utils import nowdate, get_datetime
from datetime import timedelta
from .api import set_application_checkin_checkout


def get_all_employee_status():
    all_logs = frappe.db.get_list("Application Checkin Checkout", filters={"time": ["Between", [nowdate(), nowdate()]]}, fields=["employee", "status", "time"], order_by = "creation asc")

    employe_map = {}

    for row in all_logs:
        employe_map[row.employee] = row
    
    return [row for row in employe_map.values() if row.status == "In"]

def get_last_activity_time_of_user(employee, time):
    screen_shot_log_time = frappe.db.get_all("Screen Screenshot Log", filters={"datetime": [">=", time], "employee": employee}, fields=["max(datetime) as time"], order_by = "creation desc", limit=1)
    application_usage_log_time = frappe.db.get_all("Application Usage log", filters={"date": nowdate(), "employee": employee, "to_time": [">=", time]}, fields=["to_time as time"], order_by = "creation desc", limit=1)

    times = [time]
    if screen_shot_log_time and screen_shot_log_time[0]['time']:
        times.append(screen_shot_log_time[0]['time'])
    
    if application_usage_log_time and application_usage_log_time[0]['time']:
        times.append(application_usage_log_time[0]['time'])

    return max(times)

def get_time_difference(current_time):
    data = get_all_employee_status()

    for row in data:
        row['last_activity_time'] = get_datetime(get_last_activity_time_of_user(row.employee, row.time))
        row['time_difference'] = current_time - row['last_activity_time']
    
    return data

def checkout_inactive_users():
    current_time = get_datetime().replace(microsecond=0)
    data = get_time_difference(current_time)

    for row in data:
        if row.time_difference > timedelta(minutes=10):
            print(row)
            set_application_checkin_checkout(row.employee, "Out", current_time, True)
            if user := frappe.db.get_value("Employee", row.employee, "user_id"):
                for obt in frappe.db.get_all("OAuth Bearer Token", {"user": user, "purpose": "productivity_desktop"}):
                    frappe.delete_doc("OAuth Bearer Token", obt.name, ignore_permissions=True)
            


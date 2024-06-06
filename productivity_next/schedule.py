import frappe
from frappe.utils import nowdate, get_datetime
from datetime import timedelta
from .api import set_application_checkin_checkout,set_application_idletime_checkin_checkout


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
            if user := frappe.db.get_value("Employee", row.employee, "user_id"):                
                set_application_checkin_checkout(row.employee, "Out", current_time, 1, user)
                set_application_idletime_checkin_checkout(row.employee, "end", current_time, 1, user)
                for obt in frappe.db.get_all("OAuth Bearer Token", {"user": user, "purpose": "productivity_desktop"}):
                    frappe.delete_doc("OAuth Bearer Token", obt.name, ignore_permissions=True)

def delete_older_screenshots():
    delete_files_before = frappe.db.get_single_value("Application Log Settings", "delete_files_before_days") or 15
    current_date = get_datetime().replace(microsecond=0, hour=0, minute=0, second=0)
    to_datetime = current_date - timedelta(days=delete_files_before)

    screenshot_logs = frappe.db.get_all("Screen Screenshot Log", filters={"creation": ["<", to_datetime]}, pluck='name')

    for row in screenshot_logs:
        frappe.delete_doc("Screen Screenshot Log", row)

def bg_employee_log_generation():
    call_logs = frappe.db.get_all(
        "Fincall Log", {"employee_fincall_generated": 0, "ignore_contact": 0}
    )
    if call_logs:
        frappe.enqueue(
            enqueue_logs,
            call_logs=call_logs,
            queue="long",
            job_name="Employee Log Generation",
        )
        frappe.msgprint("Log generation has started in Background")

def enqueue_logs(call_logs):
    for row in call_logs:
        if not frappe.db.exists("Employee Fincall", {"fincall_log_ref": row.name}):
            call_doc = frappe.get_doc("Fincall Log", row.name)
            create_employee_log(call_doc)
        elif frappe.db.exists("Employee Fincall", {"fincall_log_ref": row.name}):
            frappe.db.set_value(
                "Fincall Log", row.name, "employee_fincall_generated", 1
            )

def create_employee_log(fincall_log):
        # Retrieve employee details
    employee_details = frappe.db.get_value(
        "Employee",
        fincall_log.employee,
        ["name", "employee_name"],
        as_dict=True,
    )

    if employee_details:
        # Calculate the date 15 days ago
        fifteen_days_ago = fincall_log.call_datetime - timedelta(days=30)

        # Check if an Employee Fincall document with the same data exists in the last 15 days
        existing_fincall = frappe.db.sql("""
            SELECT name 
            FROM `tabEmployee Fincall` 
            WHERE employee = %(employee)s
            AND customer_no = %(customer_no)s
            AND calltype = %(calltype)s
            AND call_datetime BETWEEN %(fifteen_days_ago)s AND %(call_datetime)s
            and call_datetime = %(call_datetime)s
        """, {
            "employee": employee_details['name'],
            "customer_no": fincall_log.customer_no,
            "calltype": fincall_log.calltype,
            "fifteen_days_ago": fifteen_days_ago,
            "call_datetime": fincall_log.call_datetime,
        })

        if fincall_log.customer_no[0] == "0":
            fincall_log.customer_no = "+91" + fincall_log.customer_no[1:]
        elif fincall_log.customer_no[0] != "+" and fincall_log.customer_no[0] != "0":
            fincall_log.customer_no = "+91" + fincall_log.customer_no

        if not existing_fincall:
            # Create new Employee Fincall document
            ec_doc = frappe.new_doc("Employee Fincall")
            ec_doc.employee = employee_details['name']
            ec_doc.employee_name = employee_details['employee_name']
            ec_doc.employee_mobile = fincall_log.employee_mobile
            ec_doc.client = fincall_log.client
            ec_doc.customer_no = fincall_log.customer_no
            ec_doc.call_datetime = fincall_log.call_datetime
            ec_doc.duration = fincall_log.duration
            ec_doc.date = get_datetime(fincall_log.call_datetime).date()
            ec_doc.calltype = fincall_log.calltype
            ec_doc.fincall_log_ref = fincall_log.name

            # Try to get contact details
            contact_query = """
                SELECT c.name, dl.link_doctype, dl.link_name 
                FROM `tabContact` AS c 
                JOIN `tabContact Phone` AS cp ON cp.parent = c.name 
                JOIN `tabDynamic Link` AS dl ON dl.parent = c.name 
                WHERE cp.phone LIKE %s
                LIMIT 1
            """
            contact_details = frappe.db.sql(contact_query, ("%{}%".format(fincall_log.customer_no),), as_dict=True)

            if contact_details:
                contact = contact_details[0]
                ec_doc.link_to = contact.get('link_doctype', '')
                ec_doc.contact = contact.get('name', '')
                ec_doc.link_name = contact.get('link_name', '')

            ec_doc.flags.ignore_permissions = True
            ec_doc.save()

            # Update flag indicating that employee fincall is generated
            fincall_log.db_set("employee_fincall_generated", 1)



        

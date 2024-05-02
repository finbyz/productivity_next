import frappe
from frappe.auth import LoginManager
from frappe.core.doctype.user.user import User
from productivity_next.utils.auth import get_bearer_token
from frappe.utils import nowdate
from frappe.utils import nowdate, get_datetime

@frappe.whitelist(allow_guest=True)
def login(username, password, purpose):
    login_manager = LoginManager()
    login_manager.authenticate(username, password)
    frappe.session.user = username

    token = get_bearer_token(username, expires_in_days=1, purpose=purpose)

    return {"status": True, "access_token": token['access_token'], "expiration_time": token["expiration_time"]}

@frappe.whitelist()
def set_application_checkin_checkout(employee, status, time, system_genereted = 0, user = None):
    last_status = None
    all_logs = frappe.db.get_list("Application Checkin Checkout", filters={"employee": employee, "time": ["Between", [nowdate(), nowdate()]]}, fields=["status", "time"], order_by="creation desc", limit=1)

    if all_logs:
        last_status = all_logs[0]['status']

    if status == "In":
        if last_status == "In":
            doc = frappe.new_doc("Application Checkin Checkout")
            doc.employee = employee
            doc.status = "Out"
            doc.time = time
            doc.system_generated = system_genereted
            doc.save()
            if system_genereted:
                user_last_time = frappe.db.get_list("Application Usage log", {"employee": employee}, fields=["date","to_time"], order_by="creation desc", limit=1)
                if user_last_time:
                    doc.db_set("time", user_last_time[0].to_time)
                doc.db_set("owner", user)

        doc = frappe.new_doc("Application Checkin Checkout")
        doc.employee = employee
        doc.status = status
        doc.time = time
        doc.system_generated = system_genereted
        doc.save()
        if system_genereted:
            user_last_time = frappe.db.get_list("Application Usage log", {"employee": employee}, fields=["date","to_time"], order_by="creation desc", limit=1)
            if user_last_time:
                doc.db_set("time", user_last_time[0].to_time)
            doc.db_set("owner", user)

    elif status == "Out":
        if last_status == "In":
            doc = frappe.new_doc("Application Checkin Checkout")
            doc.employee = employee
            doc.status = status
            doc.time = time
            doc.system_generated = system_genereted
            doc.save()
            if system_genereted:
                user_last_time = frappe.db.get_list("Application Usage log", {"employee": employee}, fields=["date","to_time"], order_by="creation desc", limit=1)
                if user_last_time:
                    doc.db_set("time", user_last_time[0].to_time)
                doc.db_set("owner", user)

    return {"status": last_status}

@frappe.whitelist()
def set_application_idletime_checkin_checkout(employee, status, time, system_genereted = 0, user = None):
    last_status = None
    all_logs = frappe.db.get_list("Idle Time Log", filters={"employee": employee, "time": ["Between", [nowdate(), nowdate()]]}, fields=["status", "time"], order_by="creation desc", limit=1)

    if all_logs:
        last_status = all_logs[0]['status']

    if status == "start":
        if last_status == "start":
            doc = frappe.new_doc("Idle Time Log")
            doc.employee = employee
            doc.status = "end"
            doc.time = time
            doc.system_generated = system_genereted
            doc.save()
            if system_genereted:
                doc.db_set("owner", user)

        doc = frappe.new_doc("Idle Time Log")
        doc.employee = employee
        doc.status = status
        doc.time = time
        doc.system_generated = system_genereted
        doc.save()
        if system_genereted:
            doc.db_set("owner", user)

    elif status == "end":
        if last_status == "start":
            doc = frappe.new_doc("Idle Time Log")
            doc.employee = employee
            doc.status = status
            doc.time = time
            doc.system_generated = system_genereted
            doc.save()
            if system_genereted:
                doc.db_set("owner", user)

    return {"status": last_status}


@frappe.whitelist()
def get_usage_time(employee):
    all_logs = frappe.db.get_all("Application Checkin Checkout", filters={"employee": employee, "time": ["Between", [nowdate(), nowdate()]]}, fields=["status", "time"], order_by="creation asc")

    usage_time = 0
    last_status = None
    
    for row in all_logs:
        if row.status == "In" and last_status != "In":
            start_time = row.time
        elif row.status == "Out" and last_status == "In":
            end_time = row.time
            usage_time += (end_time - start_time).total_seconds()

        last_status = row.status

    return usage_time

@frappe.whitelist()
def update_user_auth_token(employee, purpose, date):
    if data := frappe.get_list("Employee", filters={"name": employee}, fields=["user_id"], limit=1, pluck="user_id"):
        username = data[0]
        token = get_bearer_token(username, expires_in_days=1, purpose=purpose, date=date)
        return {"status": True, "access_token": token['access_token'], "expiration_time": token["expiration_time"]}

    return {"status": False, "access_token": None, "expiration_time": None}

@frappe.whitelist()
def set_user_idel_time(*args, **kwargs):
    employee=kwargs.get("employee")
    idle_time=kwargs.get("idle_time")
    status=kwargs.get("status")

    doc = frappe.new_doc("Idle Time Log")
    doc.employee = employee
    doc.time =idle_time
    doc.status = status
    doc.save(ignore_permissions=True)

    return {"status": True}

@frappe.whitelist()
def get_user_idel_time(employee=None):
    if not employee:
        return 0
    all_logs = frappe.db.get_all("Idle Time Log", filters={"employee": employee, "time": ["Between", [nowdate(), nowdate()]]}, fields=["status", "time"], order_by="creation asc")

    idle_time = 0
    last_status = None
    
    for row in all_logs:
        if row.status == "start" and last_status != "start":
            start_time = row.time
        elif row.status == "end" and last_status == "start":
            end_time = row.time
            idle_time += (end_time - start_time).total_seconds()

        last_status = row.status

    return idle_time

@frappe.whitelist()
def get_user_last_check_in_and_out(emp_id):
    try:
        emp_data=frappe.db.get_all("Application Checkin Checkout", filters={"time": ["Between", [nowdate(), nowdate()]],"employee":emp_id}, fields=["employee", "status", "time","system_generated"], order_by = "creation desc",limit=1)
        if emp_data and emp_data[0].status=="Out" and emp_data[0].system_generated==1:
            user_id=frappe.get_all("Employee", filters={"name": emp_id}, fields=["user_id"], limit=1, pluck="user_id")[0]
            doc = frappe.new_doc("Application Checkin Checkout")
            doc.employee = emp_id
            doc.status = "In"
            doc.time = get_datetime().replace(microsecond=0)
            doc.system_generated = 1
            doc.save(ignore_permissions=True)
            doc.db_set("owner",user_id)
    except Exception as e:
        return {"status": False, "message": str(e)}
    return {"status": True, "message": emp_data}

@frappe.whitelist(allow_guest=True)
def user_error_log(employee, error_message):
    try:
        doc = frappe.new_doc("User Error Log")
        doc.employee = employee
        doc.error_details = error_message
        doc.time = get_datetime().replace(microsecond=0)
        doc.flags.ignore_permissions = True
        doc.save()
        return 200
    except:
        return 500
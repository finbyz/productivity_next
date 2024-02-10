import frappe
from frappe.auth import LoginManager
from frappe.core.doctype.user.user import User
from productivity_next.utils.auth import get_bearer_token
from frappe.utils import nowdate

@frappe.whitelist(allow_guest=True)
def login(username, password, purpose):
    login_manager = LoginManager()
    login_manager.authenticate(username, password)
    frappe.session.user = username

    token = get_bearer_token(username, expires_in_days=1, purpose=purpose)

    return {"status": True, "access_token": token['access_token'], "expiration_time": token["expiration_time"]}


@frappe.whitelist()
def set_application_checkin_checkout(employee, status, time):
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
            doc.save()

        doc = frappe.new_doc("Application Checkin Checkout")
        doc.employee = employee
        doc.status = status
        doc.time = time
        doc.save()

    elif status == "Out":
        if last_status == "In":
            doc = frappe.new_doc("Application Checkin Checkout")
            doc.employee = employee
            doc.status = status
            doc.time = time
            doc.save()

    return {"status": last_status}


@frappe.whitelist()
def get_usage_time(employee):
    all_logs = frappe.db.get_list("Application Checkin Checkout", filters={"employee": employee, "time": ["Between", [nowdate(), nowdate()]]}, fields=["status", "time"], order_by="creation asc")

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

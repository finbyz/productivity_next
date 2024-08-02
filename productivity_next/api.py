import json
import frappe
from frappe.auth import LoginManager
from productivity_next.utils.auth import get_bearer_token
from frappe.utils import nowdate
from frappe.utils import nowdate, get_datetime
from frappe.utils import time_diff_in_seconds
from frappe.utils import flt
import requests
from werkzeug import Response
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import (
    cint,
    getdate,
    get_fullname,
    get_url_to_form,
    now_datetime,
    validate_email_address,
)


@frappe.whitelist(allow_guest=True)
def login(username, password, purpose):
    login_manager = LoginManager()
    login_manager.authenticate(username, password)
    frappe.session.user = username

    token = get_bearer_token(username, expires_in_days=1, purpose=purpose)

    return {
        "status": True,
        "access_token": token["access_token"],
        "expiration_time": token["expiration_time"],
    }


@frappe.whitelist()
def set_application_checkin_checkout(
    employee, status, time, system_genereted=0, user=None
):
    last_status = None
    all_logs = frappe.db.get_list(
        "Application Checkin Checkout",
        filters={"employee": employee, "time": ["Between", [nowdate(), nowdate()]]},
        fields=["status", "time"],
        order_by="time desc",
        limit=1,
    )

    if all_logs:
        last_status = all_logs[0]["status"]

    doc = frappe.new_doc("Application Checkin Checkout")
    doc.employee = employee
    doc.status = status
    doc.time = time
    doc.system_generated = system_genereted
    doc.save()
    if system_genereted:
        doc.db_set("owner", user)

    return {"status": last_status}


@frappe.whitelist()
def set_application_idletime_checkin_checkout(
    employee, status, time, system_genereted=0, user=None
):
    last_status = None
    all_logs = frappe.db.get_list(
        "Idle Time Log",
        filters={"employee": employee, "time": ["Between", [nowdate(), nowdate()]]},
        fields=["status", "time"],
        order_by="creation desc",
        limit=1,
    )

    if all_logs:
        last_status = all_logs[0]["status"]

    if status == "start":
        if last_status == "start":
            doc = frappe.new_doc("Idle Time Log")
            doc.employee = employee
            doc.status = "end"
            doc.time = time
            doc.system_generated = system_genereted
            doc.save()
            if system_genereted:
                # user_last_time = frappe.db.get_list("Application Usage log", {"employee": employee,"date":["Between", [nowdate(), nowdate()]]}, fields=["date","to_time"], order_by="creation desc", limit=1)
                # if user_last_time:
                #     doc.db_set("time", user_last_time[0].to_time)
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
    # #set value for safty purpose in incaase user checkout not done
    # emp_data=frappe.db.get_all("Application Checkin Checkout", filters={"time": ["Between", [nowdate(), nowdate()]],"employee":employee}, fields=["employee", "status", "time","system_generated"], order_by = "creation desc",limit=1)
    # if emp_data and emp_data[0].status=="In":
    #     user_id=frappe.get_all("Employee", filters={"name": employee}, fields=["user_id"], limit=1, pluck="user_id")[0]
    #     doc = frappe.new_doc("Application Checkin Checkout")
    #     doc.employee = employee
    #     doc.status = "Out"
    #     doc.time = get_datetime().replace(microsecond=0)
    #     doc.system_generated = 1
    #     doc.save(ignore_permissions=True)
    #     doc.db_set("owner",user_id)

    all_logs = frappe.db.get_all(
        "Application Checkin Checkout",
        filters={"employee": employee, "time": ["Between", [nowdate(), nowdate()]]},
        fields=["status", "time"],
        order_by="time asc",
    )

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
    if data := frappe.get_list(
        "Employee",
        filters={"name": employee},
        fields=["user_id"],
        limit=1,
        pluck="user_id",
    ):
        username = data[0]
        token = get_bearer_token(
            username, expires_in_days=1, purpose=purpose, date=date
        )
        return {
            "status": True,
            "access_token": token["access_token"],
            "expiration_time": token["expiration_time"],
        }

    return {"status": False, "access_token": None, "expiration_time": None}


@frappe.whitelist()
def set_user_idel_time(*args, **kwargs):
    employee = kwargs.get("employee")
    from_time = kwargs.get("from_time")
    to_time = kwargs.get("to_time")

    doc = frappe.new_doc("Employee Idle Time")
    doc.employee = employee
    doc.from_time = from_time
    doc.to_time = to_time
    doc.duration = time_diff_in_seconds(to_time, from_time)
    doc.save(ignore_permissions=True)

    return {"status": True}


@frappe.whitelist()
def get_user_idel_time(employee=None):
    if not employee:
        return 0

    all_logs = frappe.db.get_all(
        "Employee Idle Time",
        filters={"employee": employee, "end_time": ["Between", [nowdate(), nowdate()]]},
        fields=["duration", "employee"],
        order_by="creation ",
    )

    idle_time = 0

    for row in all_logs:
        idle_time += row.duration

    return idle_time


@frappe.whitelist(methods=["GET", "POST"])
def get_employee_time(employee=None):
    if not employee:
        return 0

    total_application_time = frappe.db.get_all(
        "Application Usage log",
        filters={"employee": employee, "date": nowdate()},
        fields=["sum(duration) as duration"],
    )

    idle_application_time = frappe.db.get_all(
        "Employee Idle Time",
        filters={"employee": employee, "date": nowdate()},
        fields=["sum(duration) as duration"],
    )

    if total_application_time:
        total_application_time = flt(total_application_time[0].duration)
    else:
        total_application_time = 0

    if idle_application_time:
        idle_application_time = flt(idle_application_time[0].duration)
    else:
        idle_application_time = 0

    return {
        "total_time": total_application_time,
        "active_time": max(total_application_time - idle_application_time, 0),
        "idle_time": idle_application_time,
    }


@frappe.whitelist()
def get_user_last_check_in_and_out(emp_id):
    try:
        emp_data = frappe.db.get_all(
            "Application Checkin Checkout",
            filters={"time": ["Between", [nowdate(), nowdate()]], "employee": emp_id},
            fields=["employee", "status", "time", "system_generated"],
            order_by="creation desc",
            limit=1,
        )
        if (
            emp_data
            and emp_data[0].status == "Out"
            and emp_data[0].system_generated == 1
        ):
            user_id = frappe.get_all(
                "Employee",
                filters={"name": emp_id},
                fields=["user_id"],
                limit=1,
                pluck="user_id",
            )[0]
            doc = frappe.new_doc("Application Checkin Checkout")
            doc.employee = emp_id
            doc.status = "In"
            doc.time = get_datetime().replace(microsecond=0)
            doc.system_generated = 1
            doc.save(ignore_permissions=True)
            doc.db_set("owner", user_id)
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


@frappe.whitelist()
def get_app_usage_time(employee):
    if not employee:
        return 0
    all_logs = frappe.db.get_all(
        "Application Usage log",
        filters={"employee": employee, "date": ["Between", [nowdate(), nowdate()]]},
        fields=["duration", "employee"],
        order_by="creation ",
    )

    idle_time = 0

    for row in all_logs:
        idle_time += row.duration

    return idle_time


@frappe.whitelist()
def add_meeting(
    meeting_from,
    meeting_to,
    meeting_arranged_by,
    internal_meeting,
    purpose,
    industry,
    party_type,
    party,
    discussion,
    meeting_company_representative,
    meeting_party_representative
):
    meeting_company_representative = json.loads(meeting_company_representative)
    if meeting_party_representative:
        meeting_party_representative = json.loads(meeting_party_representative) 
    else:
        meeting_party_representative = []
    meeting = frappe.new_doc("Meeting")
    meeting.meeting_from = meeting_from
    meeting.meeting_to = meeting_to
    meeting.meeting_arranged_by = meeting_arranged_by
    meeting.internal_meeting = internal_meeting
    meeting.purpose = purpose
    meeting.industry = industry if industry else None
    meeting.party_type = party_type if party_type else None
    meeting.party = party if party else None
    meeting.discussion = discussion
    for row in meeting_company_representative:
        meeting.append(
            "meeting_company_representative",
            {
                "employee": row.get("employee"),
                "employee_name": row.get("employee_name"),
            },
        )
    for row in meeting_party_representative:
        meeting.append(
            "meeting_party_representative",
            {
                "contact": row.get("contact"),
            },
        )
    meeting.save()
    meeting.submit()

    return {"message": "Meeting added successfully"}


@frappe.whitelist()
def make_meetings(source_name, doctype, ref_doctype, target_doc=None):
    def set_missing_values(source, target):
        target.party_type = doctype
        now = now_datetime()
        if ref_doctype == "Meeting Schedule":
            target.scheduled_from = target.scheduled_to = now
        else:
            target.meeting_from = target.meeting_to = now
            if doctype == "Lead":
                target.organization = source.company_name

    def update_contact(source, target, source_parent):
        if doctype == "Lead":
            if not source.organization_lead:
                target.contact = source.lead_name

    doclist = get_mapped_doc(
        doctype,
        source_name,
        {
            doctype: {
                "doctype": ref_doctype,
                "field_map": {
                    "company_name": "organization",
                    "customer_name": "organization",
                    "contact_email": "email_id",
                    "contact_mobile": "mobile_no",
                },
                "field_no_map": ["naming_series", "lead", "customer", "opportunity"],
                "postprocess": update_contact,
            }
        },
        target_doc,
        set_missing_values,
    )

    return doclist

@frappe.whitelist(allow_guest=True, methods=["POST"])
def organization_signup(
    domain,
    organization_name,
    contact_person,
    email,
    mobile_no,
    subscription_plan="",
):
    """
    API_PATH: /api/method/productivity_next.api.organization_signup
    """
    user_details = frappe.get_doc("User", frappe.session.user)
    api_secret = frappe.generate_hash(length=15)
    if not user_details.api_key:
        api_key = frappe.generate_hash(length=15)
        user_details.api_key = api_key
    user_details.api_secret = api_secret
    user_details.flags.ignore_permissions = True
    user_details.save()

    productify_subscription = frappe.get_doc({
        "doctype": "Productify Subscription",
        "organization_name": organization_name,
        "email": email,
        "mobile_no": mobile_no,
        "erpnext_url": domain,
    })
    productify_subscription.insert()
    frappe.msgprint(_(f"Organization signed up successfully,{productify_subscription.name}"))

    url = "https://productivity.finbyz.tech/api/method/productivity_backend.api.organization_signup"

    payload = json.dumps(
        {
            "domain": domain,
            "organization_name": organization_name,
            "contact_person": contact_person,
            "email": email,
            "mobile_no": mobile_no,
            "subscription_plan": subscription_plan,
            "api_key": user_details.api_key,
            "api_secret": api_secret,
        }
    )
    headers = {
        "Content-Type": "application/json",
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    return Response(
        response=response.text,
        status=response.status_code,
        content_type="application/json",
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def send_user_list(user_list):
    url = "https://productivity.finbyz.tech/api/method/productivity_backend.api.receive_user_list"
    organization_name = frappe.db.get_single_value("Productify Subscription", "organization_name")
    
    if not organization_name:
        return {"message": "Organization name is not set in Productify Subscription"}
    productify_subscription = frappe.get_doc("Productify Subscription", organization_name)
    
    payload = json.dumps({
        "users": user_list,
        "organization_id": organization_name
    })
    users = json.loads(user_list)
    productify_subscription.list_of_users = []
    for user in users:
        productify_subscription.append(
            "list_of_users",
            {
                'employee': user.get("name"),
                'fincall':user.get("fincall"),
                'application_usage':user.get("application_usage"),
                'sales_person':user.get("sales_person"),
            },
        )
    productify_subscription.save(ignore_permissions=True)
    
    headers = {
        "Content-Type": "application/json",
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    return Response(
        response=response.text,
        status=response.status_code,
        content_type="application/json",
    )
    
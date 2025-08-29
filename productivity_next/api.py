import json
import frappe
from frappe.auth import LoginManager
from frappe.boot import DocType
from frappe.desk.form.assign_to import get
from frappe.share import notify_assignment
import frappe.utils
from productivity_next.utils.auth import get_bearer_token, update_expiry_time
from frappe.utils import nowdate, today
from frappe.utils import nowdate, get_datetime
from frappe.utils import time_diff_in_seconds
from frappe.utils import flt
from datetime import datetime,date
import requests
from werkzeug import Response
import pytz
from frappe import _
import logging
from frappe.model.mapper import get_mapped_doc
from frappe.utils import (
    cint,
    getdate,
    get_fullname,
    get_url_to_form,
    now_datetime,
    validate_email_address,
)
from frappe.query_builder import Order

from frappe.utils import get_datetime, convert_utc_to_system_timezone, getdate
from geopy.distance import geodesic
from frappe.query_builder import Order


@frappe.whitelist(allow_guest=True)
def login(username, password, purpose):
    login_manager = LoginManager()
    login_manager.authenticate(username, password)
    frappe.session.user = username

    token = get_bearer_token(username, expires_in_days=7, purpose=purpose)
    productify_subscription = frappe.get_doc(
        "Productify Subscription"
    )
    
    return {
        "status": True,
        "access_token": token["access_token"],
        "refresh_token": token["refresh_token"],
        "expiration_time": token["expiration_time"],
        "employee": frappe.db.get_value(
            "Employee", {"user_id": frappe.session.user}, "name"
        ),
        "full_name": frappe.db.get_value(
            "Employee", {"user_id": frappe.session.user}, "employee_name"
        ),
        "enable_blurred_screenshot": productify_subscription.get("enable_blurred_screenshot",False),
    }

@frappe.whitelist(allow_guest=True)
def login_with_challenge(username, password, purpose):
    login_manager = LoginManager()
    login_manager.authenticate(username, password)
    frappe.session.user = username

    token = get_bearer_token(username, expires_in_days=7, purpose=purpose)
    productify_subscription = frappe.get_doc(
        "Productify Subscription"
    )
    return {
        "status": True,
        "access_token": token["access_token"],
        "refresh_token": token["refresh_token"],
        "access_token_expiry": token["expiration_time"],
        "employee": frappe.db.get_value(
            "Employee", {"user_id": frappe.session.user}, "name"
        ),
        "full_name": frappe.db.get_value(
            "Employee", {"user_id": frappe.session.user}, "employee_name"
        ),
        "token": productify_subscription.token,
        "email": frappe.session.user,
        'erpnext_url': frappe.utils.get_url(),
    }

@frappe.whitelist(methods=["GET"])
def get_token():
    productify_subscription = frappe.get_doc(
        "Productify Subscription"
    )
    challenge = productify_subscription.get("token","")
    return challenge

@frappe.whitelist(allow_guest=True)
def update_token(refresh_token, purpose):
    access_token = update_expiry_time(
        frappe.session.user, refresh_token, expires_in_days=7, purpose=purpose
    )

    return {
        "status": True,
        "access_token": access_token,
        "refresh_token": frappe.db.get_value(
            "OAuth Bearer Token", access_token, "refresh_token"
        ),
        "expiration_time": frappe.db.get_value(
            "OAuth Bearer Token", access_token, "expiration_time"
        ),
        "employee": frappe.db.get_value(
            "Employee", {"user_id": frappe.session.user}, "name"
        ),
        "full_name": frappe.db.get_value(
            "Employee", {"user_id": frappe.session.user}, "employee_name"
        ),
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


@frappe.whitelist(allow_guest=False)
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
    # industry,
    party_type,
    party,
    discussion,
    meeting_company_representative,
    meeting_party_representative,
    project=None,
    task=None,
    latitude=None,
    longitude=None
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
    if project:
        meeting.project = project
    if task:
        meeting.task = task
    # meeting.industry = industry if industry else None
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
    if latitude and longitude:
        meeting.latitude = latitude
        meeting.longitude = longitude
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


@frappe.whitelist(allow_guest=False, methods=["POST"])
def organization_signup(
    domain,
    organization_name,
    contact_person,
    email,
    mobile_no,
    fincall=False,
    application_usage=False,
    sales_person=False,
    project=False,
    issue=False,
):
    """
    API_PATH: /api/method/productivity_next.api.organization_signup
    """

    url = "https://productivity.finbyz.tech/api/method/productivity_backend.api.organization_signup"

    payload = json.dumps(
        {
            "domain": domain,
            "organization_name": organization_name,
            "contact_person": contact_person,
            "email": email,
            "mobile_no": mobile_no,
            "fincall": fincall,
            "application_usage": application_usage,
            "sales_person": sales_person,
            "project": project,
            "issue": issue,
        }
    )
    headers = {
        "Content-Type": "application/json",
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    if response.status_code != 200:
        return Response(
            response=response.text,
            status=response.status_code,
            content_type="application/json",
        )
    resp_data = response.json()
    productify_subscription = frappe.get_doc(
        {
            "doctype": "Productify Subscription",
            "organization_name": organization_name,
            "email": email,
            "mobile_no": mobile_no,
            "erpnext_url": domain,
            "api_key": resp_data.get("api_key"),
            "api_secret": resp_data.get("api_secret"),
            "name1": contact_person,
            "application_organization_name": resp_data.get("application_organization_name"),
            "call_organization_name": resp_data.get("call_organization_name"),
        }
    )
    productify_subscription.insert()
    frappe.msgprint(
        _(f"Organization signed up successfully,{productify_subscription.name}")
    )

    return Response(
        response=response.text,
        status=response.status_code,
        content_type="application/json",
    )

@frappe.whitelist(allow_guest=False, methods=["POST"])
def send_user_list(user_list):
    url = "https://productivity.finbyz.tech/api/method/productivity_backend.api.receive_user_list"
    organization_name = frappe.db.get_single_value(
        "Productify Subscription", "organization_name"
    )

    if not organization_name:
        return {"message": "Organization name is not set in Productify Subscription"}
    productify_subscription = frappe.get_doc("Productify Subscription", organization_name)
    payload = json.dumps({"users": user_list, "erpnext_url": frappe.utils.get_url()})
    users = json.loads(user_list)
    productify_subscription.list_of_users = []
    for user in users:
        productify_subscription.append(
            "list_of_users",
            {
                "employee": user.get("name"),
                "fincall": user.get("fincall"),
                "application_usage": user.get("application_usage"),
                "sales_person": user.get("sales_person"),
                "disable_stop_button": 1,
            },
        )
    productify_subscription.save(ignore_permissions=True)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"token {productify_subscription.api_key}:{productify_subscription.get_password('api_secret')}",
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    return Response(
        response=response.text,
        status=response.status_code,
        content_type="application/json",
    )


@frappe.whitelist(methods=["GET"])
def get_active_projects():
    """
    API_PATH: /api/method/productivity_next.api.get_active_projects
    """
    subcription = frappe.get_doc("Productify Subscription")
    if subcription.project_tracking and subcription.issue_tracking:
        projects = frappe.get_all(
            "Project", filters={"status": "Open"}, fields=["name", "project_name"]
        )
        return projects
    return []


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_employee_last_callTime(employee=None):
    if not employee:
        return {"message": "Something went wrong"}

    last_call_data = frappe.db.sql(
        f"""
    select employee,employee_name,call_datetime
    from `tabEmployee Fincall`
    where employee = '{employee}'
    order by call_datetime desc
    limit 1
    """,
        as_dict=True,
    )
    if not last_call_data:
        return {}
    return {
        "employee": last_call_data[0].employee,
        "employee_name": last_call_data[0].employee_name,
        "call_datetime": last_call_data[0].call_datetime,
    }


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_employee_fincall(employee, employee_mobile, customer_no, date, call_datetime):
    if (
        not employee
        or not employee_mobile
        or not customer_no
        or not date
        or not call_datetime
    ):
        return "Something went wrong"

    employee_fincall = frappe.db.sql(
        f"""
    SELECT name, link_to, contact, link_name, calltype, fincall_log_ref, spoke_about
    FROM `tabEmployee Fincall`
    WHERE date = '{date}' AND employee = '{employee}' AND employee_mobile = '{employee_mobile}' AND customer_no = '{customer_no}' AND call_datetime = '{call_datetime}'
    """,
        as_dict=True,
    )

    if not employee_fincall:
        return {"message": "No Fincall found"}

    return {
        "employee_fincall": employee_fincall[0].name,
        "link_name": employee_fincall[0].link_name,
        "link_to": employee_fincall[0].link_to,
        "contact": employee_fincall[0].contact,
        "calltype": employee_fincall[0].calltype,
        "fincall_log_ref": employee_fincall[0].fincall_log_ref,
        "spoke_about": employee_fincall[0].spoke_about,
    }


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def create_fincall(
    employee,
    employee_mobile,
    customer_no,
    call_datetime,
    calltype,
    duration,
    note=None,
    raw_log=None,
    client=None,
):
    employee_details = frappe.db.get_value(
        "Employee",
        employee,
        ["name", "employee_name"],
        as_dict=True,
    )
    if customer_no[0] == "0":
        customer_no = "+91" + customer_no[1:]
    elif customer_no[0] != "+" and customer_no[0] != "0":
        customer_no = "+91" + customer_no

    ec_doc = frappe.new_doc("Employee Fincall")
    ec_doc.employee = employee_details["name"]
    ec_doc.employee_name = employee_details["employee_name"]
    ec_doc.employee_mobile = employee_mobile
    ec_doc.client = client if client else None
    ec_doc.customer_no = customer_no
    ec_doc.call_datetime = call_datetime
    ec_doc.duration = duration
    ec_doc.date = get_datetime(call_datetime).date()
    ec_doc.calltype = calltype
    contact_query = f"""
        SELECT 
            c.name, 
            dl.link_doctype, 
            dl.link_name 
        FROM 
            `tabContact` AS c 
        JOIN 
            `tabContact Phone` AS cp 
            ON cp.parent = c.name 
        JOIN 
            `tabDynamic Link` AS dl 
            ON dl.parent = c.name 
        WHERE 
            LENGTH(cp.phone) >= 10 
            AND (cp.phone = '{customer_no}' 
            OR cp.phone LIKE '%{customer_no}' 
            OR '{customer_no}' LIKE CONCAT("%", cp.phone))
        ORDER BY 
            CASE dl.link_doctype
                WHEN 'Employee' THEN 1
                WHEN 'Customer' THEN 2
                WHEN 'Lead' THEN 3
                ELSE 4
            END,
            c.modified DESC
        LIMIT 1;
    """

    contact_details = frappe.db.sql(contact_query, as_dict=True)
    if contact_details == []:
        contact_details = frappe.db.sql(f"""select name as link_name, 'Job Applicant' as link_doctype from `tabJob Applicant`
                                        WHERE 
                                            LENGTH(mobile_number) >= 10 
                                            AND (mobile_number = '{customer_no}' 
                                            OR mobile_number LIKE '%{customer_no}' 
                                            OR '{customer_no}' LIKE CONCAT("%", mobile_number))""", as_dict=True)
    if (
        contact_details
        and contact_details[0].get("link_doctype", "")
        and contact_details[0].get("link_name", "")
    ):
        contact = contact_details[0]
        ec_doc.link_to = contact.get("link_doctype", "")
        ec_doc.contact = contact.get("name", None)
        ec_doc.link_name = contact.get("link_name", "")
        if contact.get("link_doctype") == "Customer":    
            # Fetch all projects for the customer
            projects = frappe.get_all(
                "Project",
                filters={"customer": contact.get("link_name")},
                fields=["name", "resource_based_project", "based_on_hourly_package"]
            )
            selected_project = None
            # Priority 1: resource_based_project
            for proj in projects:
                if proj.get("resource_based_project"):
                    selected_project = proj["name"]
                    break
            # Priority 2: based_on_hourly_package
            if not selected_project:
                for proj in projects:
                    if proj.get("based_on_hourly_package"):
                        selected_project = proj["name"]
                        break
            # Priority 3: any other project
            if not selected_project and projects:
                selected_project = projects[0]["name"]
            ec_doc.project = selected_project
    ec_doc.flags.ignore_permissions = True
    ec_doc.save()

    return {
        "employee_fincall": ec_doc.name,
        "employee": ec_doc.employee,
        "employee_name": ec_doc.employee_name,
        "link_to": ec_doc.link_to or None,
        "contact": ec_doc.contact or None,
        "link_name": ec_doc.link_name or None,
        "fincall_log_ref": ec_doc.fincall_log_ref,
        "spoke_about": ec_doc.spoke_about or None,
    }


@frappe.whitelist(allow_guest=False, methods=["GET"])
def is_stop_disabled():
    """
    API_PATH: /api/method/productivity_next.api.is_stop_disabled"""
    subscription = frappe.get_doc("Productify Subscription")
    current_user = frappe.db.get_value(
        "Employee", filters={"user_id": frappe.session.user}, fieldname="name"
    )

    user = next(
        filter(lambda user: user.employee == current_user, subscription.list_of_users),
        None,
    )
    return user.get("disable_stop_button", False)

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_productify_subsription():
    """
    API_PATH: /api/method/productivity_next.api.is_stop_disabled"""
    subscription = frappe.get_doc("Productify Subscription")
    current_user = frappe.db.get_value(
        "Employee", filters={"user_id": frappe.session.user}, fieldname="name"
    )

    user = next(
        filter(lambda user: user.employee == current_user, subscription.list_of_users),
        None,
    )
    return {
        "is_stop_disabled": user.get("disable_stop_button", False),
        "enable_blurred_screenshot": subscription.get("enable_blurred_screenshot",False),
    }

from datetime import timedelta, datetime
import frappe
@frappe.whitelist()
def calculate_total_working_hours(employee, from_date, to_date, daily_working_hours, saturday_working_hours):
    from_date = datetime.strptime(str(from_date), '%Y-%m-%d')
    to_date = datetime.strptime(str(to_date), '%Y-%m-%d')
    date_range = [from_date + timedelta(days=x) for x in range((to_date - from_date).days + 1)]

    holidays = frappe.db.sql("""
        SELECT holiday_date 
        FROM `tabHoliday` 
        WHERE holiday_date BETWEEN %s AND %s
    """, (from_date, to_date), as_dict=True)
    holiday_dates = set(holiday.holiday_date for holiday in holidays)
    
    if not frappe.db.exists("DocType", "Leave Application"):
        leaves = []
    else:
        leaves = frappe.db.sql("""
            SELECT from_date, to_date, half_day
            FROM `tabLeave Application`
            WHERE employee = %s
            AND status = 'Approved'
            AND ((from_date BETWEEN %s AND %s) OR (to_date BETWEEN %s AND %s) OR (from_date <= %s AND to_date >= %s))
        """, (employee, from_date, to_date, from_date, to_date, from_date, to_date), as_dict=True)

    total_working_hours = 0
    for date in date_range:
        current_date = date.date()

        if current_date in holiday_dates:
            continue

        # Check if it's a Saturday (weekday 5) or Sunday (weekday 6)
        is_saturday = date.weekday() == 5
        is_sunday = date.weekday() == 6
        
        # Set initial hours based on day type
        if is_sunday:
            day_hours = 0  # No hours on Sunday
        elif is_saturday:
            day_hours = saturday_working_hours
        else:
            day_hours = daily_working_hours
            
        # Skip further calculations if already 0
        if day_hours == 0:
            continue
            
        # Apply leave deductions
        for leave in leaves:
            if leave.from_date <= current_date <= leave.to_date:
                if leave.half_day:
                    # For half-day leaves:
                    # If Saturday, set to 0 hours (skip the day)
                    # For other days, apply half of the daily hours
                    if is_saturday:
                        day_hours = 0
                    else:
                        day_hours *= 0.5
                else:
                    day_hours = 0  # Full day leave
                break

        total_working_hours += day_hours

    return total_working_hours


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_home_dashboard_data_for_mobile_app(employee, start_date, end_date):
    data = {}
    weekday_hours = frappe.db.get_single_value('Productify Configuration', 'active_hours_per_day')
    saturday_hours = frappe.db.get_single_value('Productify Configuration', 'active_hours_on_saturday')

    hours_per_weekday = float(weekday_hours) if weekday_hours else 7.5
    hours_on_saturday = float(saturday_hours) if saturday_hours else 2.5
    # Calculate total working hours
    productivity_score = calculate_total_working_hours(
        employee,
        start_date,
        end_date,
        hours_per_weekday,
        hours_on_saturday
    )

    idle_time_data = frappe.db.sql(f"""
        SELECT from_time as start_time, to_time as end_time
        FROM `tabEmployee Idle Time`
        WHERE date >= '{start_date}' AND date <= '{end_date}' AND employee = '{employee}'
    """, as_dict=True)

    # Fetch fincall time logs
    fincall_time_data = frappe.db.sql(f"""
        SELECT call_datetime as start_time, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time
        FROM `tabEmployee Fincall`
        WHERE date >= '{start_date}' AND date <= '{end_date}' AND employee = '{employee}' AND (calltype != 'Missed' AND calltype != 'Rejected')
    """, as_dict=True)

    # Fetch meeting time logs
    meeting_time_data = frappe.db.sql(f"""
        SELECT meeting_from as start_time, meeting_to as end_time
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE m.meeting_from >= '{start_date} 00:00:00' AND m.meeting_to <= '{end_date} 23:59:59' AND m.docstatus = 1 AND mcr.employee = '{employee}'
    """, as_dict=True)

    # Combine all non-idle periods (meetings and calls)
    non_idle_periods = fincall_time_data + meeting_time_data

    total_idle_seconds = 0

    for idle_period in idle_time_data:
        idle_start = idle_period['start_time']
        idle_end = idle_period['end_time']

        adjusted_start = idle_start
        adjusted_end = idle_end

        for non_idle in non_idle_periods: 
            non_idle_start = non_idle['start_time']
            non_idle_end = non_idle['end_time']

            # Check for overlap and adjust idle periods accordingly
            if non_idle_start <= adjusted_end and non_idle_end >= adjusted_start:
                if non_idle_start <= adjusted_start < non_idle_end:
                    adjusted_start = non_idle_end
                if non_idle_start < adjusted_end <= non_idle_end:
                    adjusted_end = non_idle_start
                if adjusted_start >= adjusted_end:
                    adjusted_start = adjusted_end
                    break

        # Calculate the duration of the adjusted idle period
        idle_duration = (adjusted_end - adjusted_start).total_seconds()
        if idle_duration > 0:
            total_idle_seconds += idle_duration
    total_idle_time = flt(total_idle_seconds) 

    list_data = []
    meeting_total_data = frappe.db.sql(f"""
        SELECT m.meeting_from as start_time, m.meeting_to as end_time
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE m.meeting_from >= '{start_date} 00:00:00' and m.meeting_to <= '{end_date} 23:59:59' and m.docstatus = 1 and mcr.employee ='{employee}' 
    """, as_dict=True)
    calls_total_data = frappe.db.sql(f"""
        SELECT call_datetime as start_time, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time
        FROM `tabEmployee Fincall`
        WHERE date >= '{start_date}' and date <= '{end_date}' and employee = '{employee}' and (calltype != 'Missed' and calltype != 'Rejected')
    """, as_dict=True)
    application_total_data = frappe.db.sql(f"""
        SELECT from_time as start_time, to_time as end_time
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' and date <= '{end_date}' and employee = '{employee}'
    """, as_dict=True)

    list_data.append(meeting_total_data)
    list_data.append(calls_total_data)
    list_data.append(application_total_data) 

    if list_data != [[], [], []]:

        # Flatten the list of intervals
        flat_intervals = [interval for sublist in list_data for interval in sublist]

        # Sort intervals by start time
        flat_intervals.sort(key=lambda x: x['start_time'])

        # Merge overlapping intervals
        merged_intervals = []
        current_interval = flat_intervals[0]

        for interval in flat_intervals[1:]:
            if interval['start_time'] and interval['end_time'] and current_interval['end_time']:
                if interval['start_time'] <= current_interval['end_time']:
                    # There is overlap, so merge the intervals
                    current_interval['end_time'] = max(current_interval['end_time'], interval['end_time'])
                else:
                    # No overlap, so add the current interval to the list and start a new one
                    merged_intervals.append(current_interval)
                    current_interval = interval
            elif interval['start_time']:
                # No overlap, so add the current interval to the list and start a new one
                merged_intervals.append(current_interval)
                current_interval = interval

        # Don't forget to add the last interval
        if current_interval:
            merged_intervals.append(current_interval)


        # Calculate the total time
        total_time = timedelta()
        for interval in merged_intervals:
            if interval['start_time'] and interval['end_time']:
                total_time += interval['end_time'] - interval['start_time']
   
        total_time = total_time.total_seconds()
    else:
        total_time = 0 

    total_active_hours = total_time - total_idle_time

    data["toal_active_hours"] = total_active_hours
    data["total_time"] = total_time
    data["total_idle_time"] = total_idle_time

        
    total_call_data = frappe.db.sql(f"""
        SELECT 
            SUM(duration) AS total_duration, calltype, count(calltype) as total_calls
        FROM `tabEmployee Fincall`
        WHERE date >= '2023-09-09' AND date <= '2024-09-09' and employee = 'HR-EMP-00022' and (calltype != 'Missed' and calltype != 'Rejected')
        GROUP BY calltype
    """, as_dict=True)
    total_call_duration = 0
    for call in total_call_data:
        if call["calltype"] == "Incoming":
            data["total_incoming_calls"] = call["total_calls"]
            data["total_incoming_duration"] = call["total_duration"]
            total_call_duration += call["total_duration"]
        elif call["calltype"] == "Outgoing":
            data["total_outgoing_calls"] = call["total_calls"]
            data["total_outgoing_duration"] = call["total_duration"]
            total_call_duration += call["total_duration"]
    
    data["total_call_duration"] = total_call_duration

    total_meeting_data = frappe.db.sql(f"""
        SELECT 
            SUM(TIME_TO_SEC(TIMEDIFF(meeting_to, meeting_from))) AS total_duration, internal_meeting, count(internal_meeting) as total_meetings
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE m.meeting_from >= '{start_date} 00:00:00' and m.meeting_to <= '{end_date} 23:59:59' and m.docstatus = 1 AND mcr.employee = '{employee}' 
        GROUP BY internal_meeting
  `  """, as_dict=True)

    total_meeting_duration = 0.0
    data["total_internal_meetings"] = 0
    data["total_internal_meeting_duration"] = 0.0
    data["total_external_meetings"] = 0
    data["total_external_meeting_duration"] = 0.0
    data["total_meeting_duration"] = 0.0
    for meeting in total_meeting_data:
        if meeting["internal_meeting"]:
            data["total_internal_meetings"] = meeting["total_meetings"]
            data["total_internal_meeting_duration"] = meeting["total_duration"]
            total_meeting_duration += meeting["total_duration"]
        else:
            data["total_external_meetings"] = meeting["total_meetings"]
            data["total_external_meeting_duration"] = meeting["total_duration"]
            total_meeting_duration += meeting["total_duration"]

    data["total_meeting_duration"] = total_meeting_duration

    total_web_data = frappe.db.sql(f"""
        SELECT sum(duration) as total_web_duration, count(*) as total_web_count
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' and date <= '{end_date}' and employee = '{employee}' and url is not null
    """, as_dict=True)

    total_app_data = frappe.db.sql(f"""
        SELECT sum(duration) as total_app_duration, count(*) as total_app_count
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' and date <= '{end_date}' and employee = '{employee}' and url is null
    """, as_dict=True)


    data["total_web_duration"] = total_web_data[0]["total_web_duration"] or 0.0
    data["total_web_count"] = total_web_data[0]["total_web_count"]
    data["total_app_duration"] = total_app_data[0]["total_app_duration"] or 0.0
    data["total_app_count"] = total_app_data[0]["total_app_count"]
    data["total_system_duration"] = (total_web_data[0]["total_web_duration"] or 0.0)+ (total_app_data[0]["total_app_duration"] or 0.0)
    data["productivity_score"] = round(((total_active_hours / 3600) / productivity_score) * 100, 2)
    return data

@frappe.whitelist(allow_guest=False, methods=["POST"])
def set_token_to_productify_subscription(token):
    subscription = frappe.get_doc("Productify Subscription")
    subscription.token = token
    subscription.token_updated_on = frappe.utils.today()
    subscription.flags.ignore_permissions = True
    subscription.save(ignore_permissions=True)


import re
@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_meeting_data_for_mobile_app(user, start_date, end_date):
    meetings = frappe.db.sql(f"""
    SELECT
        m.name, 
        m.meeting_from AS start_time, 
        m.meeting_to AS end_time, 
        m.purpose, 
        m.party, 
        m.party_type, 
        m.discussion, 
        m.internal_meeting,
        u.full_name AS meeting_arranged_by
    FROM `tabMeeting` AS m
    JOIN `tabMeeting Company Representative` AS mcr ON m.name = mcr.parent
    JOIN `tabUser` AS u ON u.name = m.meeting_arranged_by
    WHERE m.meeting_from >= '{start_date} 00:00:00' 
      AND m.meeting_to <= '{end_date} 23:59:59' 
      AND m.docstatus = 1 
      AND (mcr.employee = '{user}' OR mcr.employee IS NULL)
    GROUP BY m.name
    Order by m.meeting_from desc
    """, as_dict=True)
    company = []
    party = []
    for meet in meetings:
        meet["discussion"] = re.sub(r'<[^>]+>', '', meet["discussion"])
        company_representative = frappe.db.sql(f"""
            SELECT employee_name
            FROM `tabMeeting Company Representative`
            WHERE parent = '{meet["name"]}'
        """, as_dict=True)
        for rep in company_representative:
            company.append(rep["employee_name"])
        party_representative = frappe.db.sql(f"""
            SELECT c.full_name as contact_name
            FROM `tabMeeting Party Representative` as mpr
            JOIN `tabContact` as c ON mpr.contact = c.name
            WHERE mpr.parent = '{meet["name"]}'
        """, as_dict=True)
        for rep in party_representative:
            party.append(rep["contact_name"])
        meet["company_representative"] = company
        meet["party_representative"] = party
        company = []
        party = []
    
    return {"meetings": meetings}



@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_application_data_for_mobile_app(user, start_date, end_date):
    data = {}
    total_web_data = frappe.db.sql(f"""
        SELECT sum(duration) as total_web_duration, count(DISTINCT domain) as total_web_count
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' and date <= '{end_date}' and employee = '{user}' and (url is not null or url != '')
    """, as_dict=True)

    total_app_data = frappe.db.sql(f"""
        SELECT sum(duration) as total_app_duration, count(DISTINCT application_name) as total_app_count
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' and date <= '{end_date}' and employee = '{user}' and (url is null or url = '')
    """, as_dict=True)

    data["total_web_duration"] = total_web_data[0]["total_web_duration"] or 0.0 
    data["total_web_count"] = total_web_data[0]["total_web_count"]
    data["total_app_duration"] = total_app_data[0]["total_app_duration"] or 0.0
    data["total_app_count"] = total_app_data[0]["total_app_count"]
    data["total_system_duration"] = (total_web_data[0]["total_web_duration"] or 0.0)+ (total_app_data[0]["total_app_duration"] or 0.0)
    return data



import base64
import os
import frappe
from frappe.utils.file_manager import get_file_path
from frappe.utils import cstr

@frappe.whitelist(allow_guest=False)
def get_profile_photo(**kwargs):
    employee = kwargs.get('employee')
    
    if not employee:
        return {
            "status": False,
            "status_response": "Employee not provided",
            "file_name": None,
            "file_url": None,
            "file_id": None,
            "encoded_string": None,
        }

    file_id = frappe.get_value("Employee", employee, "image")
    if not file_id:
        return {
            "status": False,
            "status_response": "Employee has no profile photo",
            "file_name": None,
            "file_url": None,
            "file_id": None,
            "encoded_string": None,
        }

    try:
        file = frappe.get_doc("File", {"file_url": file_id})
        file.flags.ignore_permissions = True
        file_url = os.path.abspath(get_file_path(file_id))

        with open(file_url, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

        return {
            "status": True,
            "status_response": "Success",
            "file_name": file.file_name,
            "file_url": file.file_url,
            "file_id": file.name,
            "encoded_string": encoded_string,
        }
    except Exception as e:
        return {
            "status": False,
            "status_response": f"Error: {cstr(e)}",
            "file_name": None,
            "file_url": None,
            "file_id": None,
            "encoded_string": None,
        }

@frappe.whitelist(allow_guest=True)
def get_allowed_modules(employee=None):
    if not employee:
        return []
    modules = {}
    data = frappe.get_value("List of User", filters = {"employee": employee}, fieldname = ["fincall", "application_usage", "sales_person"])
    modules["fincall"] = data[0]
    modules["application_usage"] = data[1]
    modules["sales_person"] = data[2]
    return modules


# Mobile App APIs
@frappe.whitelist(allow_guest=True, methods=['POST', 'GET'])
def location():
    if frappe.request.method == "POST":
        data = json.loads(frappe.request.data)
        if locations := data.get("location"):
            if isinstance(locations, dict):
                row = locations.copy()
                location_log_create(row, data.get('employee') or (row.get("extras") or {}).get("employee"))

            if isinstance(locations, list):
                for row in data.get("location") or []:
                    location_log_create(row, data.get('employee') or (row.get("extras") or {}).get("employee"))

def location_log_create(row: dict, employee: str):
    if frappe.db.exists("Location History", {"employee": employee, "uuid": row.get("uuid")}):
        return
    if row.get("timestamp"):
        row['timestamp'] = convert_utc_to_system_timezone(get_datetime(row['timestamp'])).replace(tzinfo=None)
    else:
        return

    doc = frappe.new_doc("Location History")
    if frappe.db.exists("Location History", {"employee": employee, "timestamp": row['timestamp']}):
        if row['activity']['type'] == 'still':
            return
        else:
            location_log_name = frappe.db.get_value("Location History", {"employee": employee, "timestamp": row['timestamp']}, "name")
            doc = frappe.get_doc("Location History", location_log_name)
    
    
    doc.employee = employee
    doc.event = row.get('event') or row.get("extras", {}).get("event", "N/A")
    doc.is_moving = row.get('is_moving') or False
    doc.uuid = row.get("uuid")
    doc.timestamp = row['timestamp']
    doc.date = doc.timestamp.date()
    doc.time = doc.timestamp.time().replace(microsecond=0)
    doc.age = row.get("age") or 0
    doc.odometer = row.get("odometer") or 0

    for key, value in (row.get("coords") or {}).items():
        setattr(doc, f"coords_{key}".lower(), value)
    
    for key, value in (row.get("activity") or {}).items():
        setattr(doc, f"activity_{key}".lower(), value)
    
    for key, value in (row.get("battery") or {}).items():
        setattr(doc, f"battery_{key}".lower(), value)
    
    for key, value in (row.get("provider") or {}).items():
        setattr(doc, f"provider_{key}".lower(), value)
    
    doc.save()

@frappe.whitelist(methods=['GET','POST'])
def get_map_plot(employee, start_date, end_date):
    return frappe.get_list(
        "Location History",
        filters={
            "employee": employee,
            "date": ['between', (getdate(start_date), getdate(end_date))],
            "event": ["not in", ('getCurrentPosition', 'heartbeat')],
        },
        fields=[
            "CAST(timestamp AS DATETIME) AS timestamp",
            "coords_latitude as latitude",
            "coords_longitude as longitude",
            "coords_heading as heading",
        ]
    )

@frappe.whitelist(methods=['GET','POST'])
def get_timeline(employee, start_date, end_date):
    """
    Comprehensive timeline tracking with stop time filtering and meeting integration
    
    :param employee: Employee identifier
    :param start_date: Start date for tracking
    :param end_date: End date for tracking
    :return: Detailed location and activity tracking
    """
    import math
    import traceback
    from geopy.distance import geodesic

    def calculate_total_distance(coordinates):
        """
        Calculate total distance traveled for a set of coordinates
        """
        total_distance = 0
        for i in range(1, len(coordinates)):
            point1 = coordinates[i-1]
            point2 = coordinates[i]
            total_distance += geodesic(point1, point2).kilometers
        return total_distance

    try:
        # Fetch location history
        data = frappe.get_list(
            "Location History",
            filters={
                "employee": employee,
                "date": ['between', (frappe.utils.getdate(start_date), frappe.utils.getdate(end_date))],
                "event": ["not in", ('getCurrentPosition', 'heartbeat')],
            },
            fields=[
                "date",
                "time",
                "event",
                "timestamp",
                "coords_latitude",
                "coords_longitude",
                "activity_type"
            ],
            order_by = "timestamp asc"
        )

        # Validate data
        if not data:
            return {
                "total_distance": 0,
                "total_duration": 0,
                "data": [],
                "total_driving_time": 0,
                "total_stop_time": 0,
                "total_company_stop_time": 0,
                "total_internal_meeting_duration": 0,
                "total_external_meeting_duration": 0
            }

        # Fetch company locations for stop time filtering
        company_locations = frappe.db.sql("""
            select a.latitude, a.longitude, a.address_line1, a.city, a.state, dl.link_name as company_name
            from `tabAddress` as a
            join `tabDynamic Link` as dl on dl.parent = a.name
            where dl.link_doctype = 'Company'
        """, as_dict=True)

        user = frappe.db.sql(f"""select user_id from `tabEmployee` where name = '{employee}'""", as_dict=True)
        
        # Modify the ignored locations query to use correct user comparison
        ignored_locations = frappe.db.sql(f"""
            select description, latitude, longitude
            from `tabIgnore Locations`
            where user = '{user[0]['user_id']}'
        """, as_dict=True)
        
        company_coords = [
            {
                'coords': (float(loc['latitude']), float(loc['longitude'])),
                'address': f"{loc['address_line1']}, {loc['city']}, {loc['state']}",
                'company_name': loc['company_name']
            }
            for loc in company_locations 
            if loc['latitude'] and loc['longitude']
        ]

        ignored_coords = [
            {
                'coords': (float(loc['latitude']), float(loc['longitude'])),
                'description': loc['description']
            }
            for loc in ignored_locations
            if loc['latitude'] and loc['longitude']
        ]

        # Automatic tracking implementation
        final_data = []
        timestamp_data = {}

        # Organize data by date
        for row in data:
            if not timestamp_data.get(row['date']):
                timestamp_data[row['date']] = []
            
            timestamp_data[row['date']].append(row)
        
        for date, date_data in timestamp_data.items():
            date_wise_final_data = []
            
            for idx, row in enumerate(date_data):
                if idx == 0:
                    start_time = row['timestamp']
                    activity_type = row['activity_type']
                    lat_long = [(row['coords_latitude'], row['coords_longitude'])]
                    continue
                
                lat_long.append((row['coords_latitude'], row['coords_longitude']))

                if row['activity_type'] != activity_type or row['event'] in ["activityChange", "motionchange"]:
                    # Calculate distance for the current segment
                    distance = calculate_total_distance(lat_long)
                    
                    # Determine if the activity is still based on distance
                    if distance < 0.1:
                        activity_type = 'still'
                    
                    # Check if current point is near a company location
                    nearest_company = None
                    for company in company_coords:
                        if geodesic(lat_long[-1], company['coords']).kilometers <= 0.05:
                            nearest_company = company
                            break
                    
                    # Check if current point is near an ignored location
                    ignored_location_desc = None
                    for ignored_loc in ignored_coords:
                        if geodesic(lat_long[-1], ignored_loc['coords']).kilometers <= 0.05:
                            ignored_location_desc = ignored_loc['description']
                            break
                    
                    # Add to date-wise data
                    entry = {
                        "start_time": start_time,
                        "end_time": row['timestamp'],
                        "activity_type": activity_type,
                        "lat_long_cordinates": lat_long,
                        "distance": distance if activity_type != "still" else 0,
                        "near_company": nearest_company is not None,
                        "company_address": nearest_company['address'] if nearest_company else None,
                        "company_name": nearest_company['company_name'] if nearest_company else None,
                        "ignored_location_description": ignored_location_desc
                    }
                    
                    # If not the first entry and activity is the same, merge
                    if date_wise_final_data and date_wise_final_data[-1]['activity_type'] == activity_type:
                        date_wise_final_data[-1]['end_time'] = row['timestamp']
                        date_wise_final_data[-1]['lat_long_cordinates'] += lat_long
                        date_wise_final_data[-1]['distance'] = (
                            0 if date_wise_final_data[-1]['activity_type'] == "still" 
                            else calculate_total_distance(date_wise_final_data[-1]['lat_long_cordinates'])
                        )
                    else:
                        date_wise_final_data.append(entry)

                    # Reset for next segment
                    start_time = row['timestamp']
                    activity_type = row['activity_type']
                    lat_long = [(row['coords_latitude'], row['coords_longitude'])]
            
            # Handle the last segment (similar modifications as above)
            if lat_long:
                distance = calculate_total_distance(lat_long)
                if distance < 0.1:
                    activity_type = 'still'
                
                # Check if current point is near a company location
                nearest_company = None
                for company in company_coords:
                    if geodesic(lat_long[-1], company['coords']).kilometers <= 0.05:
                        nearest_company = company
                        break
                
                # Check if current point is near an ignored location
                ignored_location_desc = None
                for ignored_loc in ignored_coords:
                    if geodesic(lat_long[-1], ignored_loc['coords']).kilometers <= 0.05:
                        ignored_location_desc = ignored_loc['description']
                        break
                
                entry = {
                    "start_time": start_time,
                    "end_time": row['timestamp'],
                    "activity_type": activity_type,
                    "lat_long_cordinates": lat_long,
                    "distance": distance if activity_type != "still" else 0,
                    "near_company": nearest_company is not None,
                    "company_address": nearest_company['address'] if nearest_company else None,
                    "company_name": nearest_company['company_name'] if nearest_company else None,
                    "ignored_location_description": ignored_location_desc
                }
                
                if date_wise_final_data and date_wise_final_data[-1]['activity_type'] == activity_type:
                    date_wise_final_data[-1]['end_time'] = row['timestamp']
                    date_wise_final_data[-1]['lat_long_cordinates'] += lat_long
                    date_wise_final_data[-1]['distance'] = (
                        0 if date_wise_final_data[-1]['activity_type'] == "still" 
                        else calculate_total_distance(date_wise_final_data[-1]['lat_long_cordinates'])
                    )
                else:
                    date_wise_final_data.append(entry)
            
            final_data.extend(date_wise_final_data)

        # Calculate totals
        total_distance = 0
        total_duration = 0
        total_internal_meeting_duration = 0
        total_external_meeting_duration = 0
        total_stop_time = 0
        total_company_stop_time = 0
        total_driving_time = 0

        for row in final_data:
            start_time = row['start_time']
            end_time = row['end_time']
            
            # Calculate duration
            row['duration'] = 0
            if row['activity_type'] != 'still':
                row['duration'] = int((end_time - start_time).total_seconds())
            
            # Aggregate distances and times
            total_distance += row['distance']
            total_duration += row['duration']

            # Handle stop times
            if row['activity_type'] == 'still':
                stop_duration = int((end_time - start_time).total_seconds())
            
            elif row['activity_type'] != 'still':
                total_driving_time += int((end_time - start_time).total_seconds())

            # Fetch and process meeting data (rest of the code remains the same)
            meeting_data = frappe.db.sql(f"""
                SELECT 
                    m.name, 
                    CASE 
                        WHEN m.party_type = 'Lead' THEN m.organization 
                        ELSE m.party 
                    END as party,
                    m.party_type,
                    m.meeting_arranged_by,
                    CAST(m.meeting_from AS DATE) as date, 
                    CAST(m.meeting_from AS TIME) AS meeting_from, 
                    CAST(m.meeting_to AS TIME) AS meeting_to, 
                    m.internal_meeting,
                    TIMESTAMPDIFF(SECOND, m.meeting_from, m.meeting_to) AS duration
                FROM `tabMeeting` AS m 
                JOIN `tabMeeting Company Representative` AS mcr ON mcr.parent = m.name
                WHERE mcr.employee = '{employee}' 
                    AND m.docstatus = 1 
                    AND CAST(m.meeting_from AS DATETIME) BETWEEN CAST('{start_time}' AS DATETIME) AND CAST('{end_time}' AS DATETIME)
            """, as_dict=True)

            row['meetings'] = meeting_data if meeting_data else []
            if row['activity_type'] == 'still':
                stop_duration = int((end_time - start_time).total_seconds())
                # Skip stop time if it's near an ignored location
                if not row.get('ignored_location_description') and row.get("near_company")!= True and not row.get("meeting_from"):
                    total_stop_time += stop_duration
                
                # Separate company stop time
                if row.get('near_company', False):
                    total_company_stop_time += stop_duration
            # Calculate meeting durations
            for meeting in row['meetings']:
                if meeting['internal_meeting']:
                    total_internal_meeting_duration += meeting['duration']
                else:
                    total_external_meeting_duration += meeting['duration']

        return {
            "total_distance": total_distance,
            "total_duration": total_duration,
            "data": final_data,
            "total_driving_time": total_driving_time,
            "total_stop_time": total_stop_time ,
            "total_company_stop_time": total_company_stop_time,
            "total_internal_meeting_duration": total_internal_meeting_duration,
            "total_external_meeting_duration": total_external_meeting_duration
        }

    except Exception as e:
        frappe.log_error(f"Timeline generation error: {traceback.format_exc()}")
        frappe.msgprint(f"Error generating timeline: {str(e)}")
        return {
            "error": str(e),
            "total_distance": 0,
            "total_duration": 0,
            "data": [],
            "total_driving_time": 0,
            "total_stop_time": 0,
            "total_company_stop_time": 0,
            "total_internal_meeting_duration": 0,
            "total_external_meeting_duration": 0
        }

# Function to calculate the total distance for the given route
def calculate_total_distance(route):
    total_distance = 0
    # Iterate through the list and calculate the distance between consecutive points
    for i in range(1, len(route)):
        loc1 = route[i - 1]
        loc2 = route[i]
        # Calculate the geodesic distance between two consecutive points
        distance = geodesic(loc1, loc2).kilometers
        total_distance += distance
    return total_distance

@frappe.whitelist()
def ignore_location(latitude,longitude,user,description):
    doc = frappe.new_doc("Ignore Locations")
    doc.user = user
    doc.latitude = latitude
    doc.longitude = longitude
    doc.description = description
    doc.save()
    return "Success"


@frappe.whitelist()
def task_mail_remainder():
    # Enqueue the task for sending reminder emails
    try:
        frappe.enqueue(
            task_mails,  # Renamed function to send_task_mails for clarity
            queue='long',
            timeout=5000,
            job_name='Task Reminder Mails'
        )

        return "Task Reminder Mails Enqueued"
    except Exception as e:
        return f"Error: {str(e)}"

@frappe.whitelist()
def task_mails():
    """
    Sends reminder emails for tasks, but only to users who are listed in the "List of Users"
    child table of the "Productify Subscription" doctype and have "Active" status.
    """

    today = date.today() - timedelta(days=1)  # Past Date
    formatted_date = today.strftime("%d-%m-%Y")
    new_formatted_date = today.strftime("%d %B %Y")
    tomorrow = date.today()  # Current Date

    # Fetch active users
    active_users = frappe.db.sql("""
        SELECT user_id FROM `tabList of User`
    """, as_dict=True)

    active_user_ids = {user["user_id"] for user in active_users}
    # Check if task reminder emails should be sent
    do_not_send_task_reminder_email = get_do_not_send_task_reminder_email_value()

    if isinstance(do_not_send_task_reminder_email, dict) and do_not_send_task_reminder_email.get("do_not_send_task_reminder_email") in [1, "1", True]:
        return "Task Reminder Emails are disabled."
    
    # Fetch all tasks
    tasks = frappe.get_all(
        "Task",
        filters={"assignee": ["in", list(active_user_ids)]},
        fields=["name as task_no", "subject", "status", "project", "exp_end_date as due_date", "assignee", "exp_start_date", "completed_by"],
        order_by="exp_end_date asc"
    )

    if not tasks:
        return "No tasks found for sending reminders."

    # Check if the Email Template "Task Reminder" exists
    if not frappe.db.exists("Email Template", "Daily Task Reminder"):
        return "Email Template 'Task Reminder' does not exist."

    email_template = frappe.get_doc("Email Template", "Daily Task Reminder")
    sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id")

    if not sender_email:
        return "Default sender email is not configured in Email Account settings."

    sender_name = frappe.db.get_value("User", {"email": sender_email}, "full_name") or "Task Notification System"

    # Categorize tasks
    overdue_tasks = []
    today_tasks = []
    tomorrow_tasks = []
    future_tasks = []

    for task in tasks:
        task_due_date = task.due_date
        if not task_due_date:
            continue

        if task.project:
            task.project_name = frappe.db.get_value("Project", task.project, "project_name")
            task.project_link = frappe.utils.get_url_to_form("Project", task.project)
        else:
            task.project_name = None
            task.project_link = None

        if task_due_date < today and task.status not in ("Completed", "Unplanned", "Cancelled"):
            overdue_tasks.append(task)
        elif task_due_date == today and task.status != "Cancelled":
            today_tasks.append(task)
        elif task_due_date == tomorrow and task.status not in ("Completed", "Unplanned", "Cancelled"):
            tomorrow_tasks.append(task)
        elif task_due_date > tomorrow and task.status not in ("Completed", "Unplanned", "Cancelled"):
            future_tasks.append(task)

    # Group tasks by assignee
    tasks_by_user = {}
    for task_list, task_type in [
        (overdue_tasks, "overdue_tasks"),
        (today_tasks, "today_tasks"),
        (tomorrow_tasks, "tomorrow_tasks"),
        (future_tasks, "future_tasks")
    ]:
        for task in task_list:
            if task.assignee:
                if task.assignee not in tasks_by_user:
                    tasks_by_user[task.assignee] = {
                        "overdue_tasks": [],
                        "today_tasks": [],
                        "tomorrow_tasks": [],
                        "future_tasks": []
                    }
                tasks_by_user[task.assignee][task_type].append(task)

    # Send emails only to active users and if checkbox is unchecked
    for assignee, task_groups in tasks_by_user.items():
        if assignee not in active_user_ids:
            continue 

        recipient_email = frappe.db.get_value("User", assignee, "email")
        assignee_name = frappe.db.get_value("User", assignee, "full_name")

        if not recipient_email:
            continue

        # Fetch Employee Details to Get Reports To (Manager) Email
        employee_record = frappe.db.get_value(
            "Employee",
            {"user_id": recipient_email},
            ["name", "user_id", "reports_to"],
            as_dict=True
        )

        employee_cc_emails = []
        manager_cc_email = None

        if employee_record:
            if employee_record.get("user_id"):
                employee_cc_emails.append({
                    "email": employee_record["user_id"],
                    "name": frappe.db.get_value("User", employee_record["user_id"], "full_name")
                })

            if employee_record.get("reports_to"):
                manager_email = frappe.db.get_value("Employee", employee_record["reports_to"], "user_id")
                if manager_email:
                    manager_cc_email = {
                        "email": manager_email,
                        "name": frappe.db.get_value("User", manager_email, "full_name")
                    }

        # Prepare CC email list
        dynamic_cc_emails = employee_cc_emails
        if manager_cc_email:
            dynamic_cc_emails.append(manager_cc_email)

        cc_recipients = [f'{cc["name"]} <{cc["email"]}>' for cc in dynamic_cc_emails if cc["email"]]

        # Prepare email context
        context = {
            "assignee_name": assignee_name,
            "sender_name": sender_name,
            "overdue_tasks": task_groups["overdue_tasks"],
            "today_tasks": task_groups["today_tasks"],
            "tomorrow_tasks": task_groups["tomorrow_tasks"],
            "future_tasks": task_groups["future_tasks"],
            "sender_email": sender_email,
            "today_date": formatted_date,
            "new_formatted_date": new_formatted_date
        }

        # Render email subject and body
        email_subject = frappe.render_template(email_template.subject, context)
        email_message = frappe.render_template(email_template.response_html, context)

        try:
            frappe.sendmail(
                recipients=[recipient_email],
                sender=sender_email,
                subject=email_subject,
                message=email_message,
                cc=cc_recipients if cc_recipients else None
            )
        except Exception as e:
            print(f"Error sending email to {recipient_email}: {e}")
            logger = logging.getLogger(__name__)
            logger.info("Inside task_mails function")
            logger.error(f"Error sending email to {recipient_email}: {e}")

    return "Task Reminder Emails Sent Successfully."



@frappe.whitelist()
def get_do_not_send_task_reminder_email_value():
    result = frappe.db.sql("""
        SELECT 
            field,
            value
        FROM 
            `tabSingles`
        WHERE 
            doctype = 'Productify Configuration' 
            AND field IN (
                'do_not_send_task_reminder_email'
            )
    """, as_dict=True)

    if result:
        return {row["field"]: row["value"] for row in result}
    return {}



@frappe.whitelist()
def get_user_avatar(email:str):
    return {
        "user_image": frappe.get_value("User", email, "user_image"),
        "full_name": frappe.get_value("User", email, "full_name")
    }

@frappe.whitelist()
def get_user_time_on_tasks(employee, tasks, from_date = None, to_date = None):
    tasks = json.loads(tasks)
    if not tasks:
        return []
    
    filters = {}
    
    if from_date and to_date:
        filters["date"] = ["between", (from_date, to_date)]

    filters['employee'] = employee
    filters["task"] = ["in", tasks]
    
    data = frappe.db.get_all(
        "Application Usage log",
        filters=filters,
        fields=["task", "sum(duration) as total_duration"],
        group_by="task"
    )
    
    data_tasks = [row.task for row in data]
    
    for task in set(tasks):
        if task not in data_tasks:
            data.append(frappe._dict({
                "task": task,
                "total_duration": 0
            }))
            data_tasks.append(task)

    return data


@frappe.whitelist()
def get_tasks(assignee=None, start_date=None, end_date=None,filters=None):
    if filters:
        filters = frappe.parse_json(filters)
        return {
            "data": frappe.get_list("Task",filters=filters,fields=['*'])
        }
    Task = DocType("Task")
    
    query = (
        frappe.qb.from_(Task)
        .select("*")
        .where(
            (
                (Task.status.notin(["Unplanned", "Template", "Cancelled", "Completed"]))
                & (Task.exp_start_date.lte(end_date))
                & (
                    (Task._assign.like(f'%"{assignee}"%')) | (Task.assignee == assignee)
                )
            )
            | (
                (Task.status == "Completed")
                & (Task.completed_on.between(start_date, end_date))
                & (Task.completed_by == assignee)
            )
        )
        .orderby(Task.modified, order=Order.desc)
    )

    tasks = query.run(as_dict=True)
    
    completed_tasks = list(filter(lambda task:task.status == 'Completed',tasks))
    non_completed_tasks = list(filter(lambda task:task.status != 'Completed',tasks))
    return {
        "data": [*non_completed_tasks, *completed_tasks]
    }


@frappe.whitelist(methods=['POST'])
def complete_todo(doctype, name, todo=None, assign_to=None, status="Completed", ignore_permissions=False):

    if not ignore_permissions:
        frappe.get_doc(doctype, name).check_permission()
    try:
        if not todo:
            todo = frappe.db.get_value(
                "ToDo",
                {
                    "reference_type": doctype,
                    "reference_name": name,
                    "allocated_to": assign_to,
                    "status": ("!=", status),
                },
            )
        if todo:
            todo = frappe.get_doc("ToDo", todo)
            todo.status = status
            todo.save(ignore_permissions=True)

            notify_assignment(todo.assigned_by, todo.allocated_to, todo.reference_type, todo.reference_name)
    except frappe.DoesNotExistError:
        pass

    return get({"doctype": doctype, "name": name})


# @frappe.whitelist()
# def get_defaults():
#     result = frappe.db.sql("""
#         SELECT 
#             default_marketing_project,
#             task_type 
#         FROM 
#             `tabProductify Subscription`
#     """, as_dict=True)
    
#     if result and len(result) > 0:
#         return result[0]
#     return {}

# @frappe.whitelist()
# def get_defaults_productivity():
#     result = frappe.db.sql("""
#         SELECT 
#             field,
#             value
#         FROM 
#             `tabSingles`
#         WHERE 
#             doctype = 'Productify Subscription' 
#             AND field IN ('default_marketing_project', 'task_type')
#     """, as_dict=True)

#     if result:
#         return {row["field"]: row["value"] for row in result}
#     return {}

@frappe.whitelist()
def get_defaults_productivity():
    result = frappe.db.sql("""
        SELECT 
            field,
            value
        FROM 
            `tabSingles`
        WHERE 
            doctype = 'Productify Configuration' 
            AND field IN (
                'default_marketing_project', 
                'task_type', 
                'create_task_instead_of_todo_for_lead_follow_up',
                'create_task_instead_of_todo_for_opportunity_follow_up'
            )
    """, as_dict=True)

    if result:
        return {row["field"]: row["value"] for row in result}
    return {}



@frappe.whitelist()
def get_employee_working_tasks():
    employees = frappe.get_list('Employee', fields=['name', 'employee_name', 'user_id'], filters={'status': 'Active'})
    latest_logs = frappe.db.sql(f"""
        WITH ranked_logs AS (
            SELECT 
                log.employee, 
                log.task, 
                log.project, 
                log.name AS log_id, 
                log.to_time, 
                log.application_name,
                log.application_title,
                ROW_NUMBER() OVER (PARTITION BY log.employee ORDER BY log.to_time DESC) AS rn
            FROM `tabApplication Usage log` log
            WHERE date = CURDATE() -- Filter logs from today
        )
        SELECT 
            rl.employee, 
            rl.task, 
            rl.project, 
            project.project_name, 
            rl.log_id, 
            rl.to_time, 
            rl.application_name,
            rl.application_title,
            task.subject AS task_subject, 
            task._assign, 
            task.assignee
        FROM ranked_logs rl
        LEFT JOIN `tabTask` task ON rl.task = task.name
        LEFT JOIN `tabProject` project ON rl.project = project.name
        WHERE rl.rn = 1;
    """, as_dict=True)

    log_dict = {log["employee"]: log for log in latest_logs}

    employee_tasks = {}

    for employee in employees:
        log = log_dict.get(employee.name) 
        task_details = {}

        if log:
            assignees = json.loads(log._assign or '[]')

            if log.assignee and log.assignee not in assignees:
                assignees.append(log.assignee)
            spent_time = get_user_time_on_tasks(employee.name,json.dumps([log.task]),from_date=today(),to_date=today())
            if not spent_time:
                spent_time = 0
            spent_time = spent_time[0].total_duration
            task_details = {
                'log_id': log.log_id,
                'application_name': log.application_name,
                'application_title': log.application_title,
                'project': log.project,
                'project_name': log.project_name,
                'task': log.task,
                'task_subject': log.task_subject,
                'to_time': log.to_time,
                'assignees': assignees,
                'spent_time': spent_time
            }

        employee_tasks[employee.name] = {
            'employee_name': employee.employee_name,
            'employee_email': employee.user_id,
            **task_details
        }

    return employee_tasks


@frappe.whitelist()
def working_hour_exception_details(doc_id):
    if not doc_id:
        frappe.throw("Document ID is required")

    data = frappe.db.sql("""
        SELECT employee_name, starting_date, total_hours, productivity_score
        FROM `tabWorking Hours Exception`
        WHERE name = %s
    """, (doc_id,), as_dict=True)

    if not data:
        frappe.throw("No record found for the given Document ID")

    return data[0]

@frappe.whitelist(allow_guest=True)
def submit_working_hour_exception_reason(doc_id,reason):
    if not doc_id or not reason:
        frappe.throw("Both Document ID and Reason are required")

    doc = frappe.get_doc("Working Hours Exception", doc_id)

    # Store JSON as string (only if short enough)
    if doc.reason:
        frappe.throw("Reason has already been submitted and cannot be changed.")
    doc.reason = reason
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return "success"

@frappe.whitelist()
def make_developer_document_meetings(source_name, doctype, ref_doctype, target_doc=None):
    def set_missing_values(source, target):
        target.party_type = doctype
        now = now_datetime()
        if ref_doctype == "Meeting Schedule":
            target.scheduled_from = target.scheduled_to = now
        else:
            target.meeting_from = target.meeting_to = now

    def update_contact(source, target, source_parent):
        if doctype == "Developer Document":
            target.contact = source.contact_person

    doclist = get_mapped_doc(
        doctype,
        source_name,
        {
            doctype: {
                "doctype": ref_doctype,
                "field_map": {
                    "name": "developer_document",
                    "contact_person": "contact",
                    "contact_email": "email_id",
                    "contact_mobile": "mobile_no",
                },
                "field_no_map": ["naming_series"],
                "postprocess": update_contact,
            }
        },
        target_doc,
        set_missing_values,
    )

    return doclist

@frappe.whitelist()
def is_users_added_in_productify_subscription() -> bool:
    try:
        count = frappe.db.count('List of User', {
            'parent': "Productify Subscription",
            'parenttype': 'Productify Subscription',
            'parentfield': 'list_of_users'
        })
    except Exception as e:
        return True

    return count > 0

@frappe.whitelist(methods=["POST"])
def fetch_followup_contacts(link_doctype,link_name):
    query = """
        SELECT DISTINCT
            c.full_name,
            p.phone,
            l.link_title
        FROM `tabContact` c
        JOIN `tabContact Phone` p ON p.parent = c.name
        JOIN `tabDynamic Link` l ON l.parent = c.name
        WHERE l.link_name = %s
          AND l.link_doctype = %s
    """
    # pass params as a tuple (order must match the %s placeholders)
    contacts = frappe.db.sql(query, (link_name, link_doctype), as_dict=True)
    return contacts


@frappe.whitelist(methods=["GET"])
def get_time_utilization_daily(from_date=None, to_date=None, employee=None, project=None):
    if not project:
        return []
    projects = get_projects()
    project = projects[0].name
    portal_users = frappe.db.sql(f"""select pu.user from `tabProject` as p join `tabPortal User` as pu on p.customer = pu.parent where p.name = '{project}'""", as_dict=1)
    if frappe.session.user not in [user['user'] for user in portal_users]:
        raise frappe.PermissionError
    # Build filters for the report
    filters = {
        "from_date": from_date,
        "to_date": to_date,
        "project": project,
        "show_employee": 1,
        "show_daily_data": 1,
    }

    # Include employee filter only if provided
    if employee:
        filters["employee"] = employee

    # Import and execute the report
    try:
        from productivity_next.productivity_next.report.project_time_analysis.project_time_analysis import execute as project_time_analysis_execute
    except Exception:
        # Fallback using dynamic import if direct import path changes
        project_time_analysis_execute = frappe.get_attr(
            "productivity_next.productivity_next.report.project_time_analysis.project_time_analysis.execute"
        )

    columns, data = project_time_analysis_execute(filters)
    return data    

@frappe.whitelist()
def get_projects(user):
    if not project:
        return []
    projects = get_projects()
    project = projects[0].name
    portal_users = frappe.db.sql(f"""select pu.user from `tabProject` as p join `tabPortal User` as pu on p.customer = pu.parent where p.name = '{project}'""", as_dict=1)
    if frappe.session.user not in [user['user'] for user in portal_users]:
        raise frappe.PermissionError
    user2 = frappe.session.user
    projects = frappe.db.sql(f"""
        SELECT DISTINCT p.name as name, p.project_name 
        from `tabProject` as p 
        join `tabPortal User` as pu on p.customer = pu.parent 
        where pu.user = '{user2}'
        order by  p.resource_based_project DESC""",as_dict=1)
    return projects
from dateutil.parser import parse
@frappe.whitelist()
def user_activity_images(user=None, start_date=None, end_date=None, project=None, offset=0):
    projects = get_projects()
    project = projects[0].name
    # parsed_datetime = datetime.strptime(start_date, '%d/%m/%Y, %I:%M:%S %p')
    # start_date = parsed_datetime.strftime('%Y-%m-%d  %H:%M:%S')
    # parsed_datetime_ = datetime.strptime(end_date, '%d/%m/%Y, %I:%M:%S %p')
    # end_date = parsed_datetime_.strftime('%Y-%m-%d  %H:%M:%S')
    if not project:
        return []
    portal_users = frappe.db.sql(f"""select pu.user from `tabProject` as p join `tabPortal User` as pu on p.customer = pu.parent where p.name = '{project}'""", as_dict=1)
    if frappe.session.user not in [user['user'] for user in portal_users]:
        raise frappe.PermissionError
    else:
        data = frappe.get_all("Screen Screenshot Log", filters={ "project":project, "employee":user,"time": ["BETWEEN", [start_date, end_date]]}, order_by="time desc", group_by="time", fields=["screenshot", "time","active_app"])
        for i in data:
            i["time_"] = frappe.format(i["time"], "Datetime")
        return data


@frappe.whitelist(methods=["GET"]) 
def get_task_list(from_date, to_date, project, assignee=None):
    """
    Return list of completed tasks within the given period, optionally filtered by project.

    Params:
    - from_date (YYYY-MM-DD)
    - to_date (YYYY-MM-DD)
    - project (optional)

    Response rows contain: task_id, subject, assignee, completed_on
    """
    if not project:
        return []
    projects = get_projects()
    project = projects[0].name
    portal_users = frappe.db.sql(f"""select pu.user from `tabProject` as p join `tabPortal User` as pu on p.customer = pu.parent where p.name = '{project}'""", as_dict=1)
    if frappe.session.user not in [user['user'] for user in portal_users]:
        raise frappe.PermissionError
    if not from_date or not to_date:
        return []

    filters = {
        "status": "Completed",
        "completed_on": ["between", [from_date, to_date]],
    }

    if project:
        filters["project"] = project

    if assignee:
        filters["assignee"] = assignee

    tasks = frappe.get_all(
        "Task",
        filters=filters,
        fields=[
            "name as task_id",
            "subject",
            "assignee",
            "completed_on",
        ],
        order_by="completed_on desc",
    )

    return tasks

@frappe.whitelist()
def get_projects():
    current_user = frappe.session.user
    projects = frappe.db.sql(f"""
        SELECT DISTINCT p.name as name, p.project_name 
        from `tabProject` as p 
        join `tabPortal User` as pu on p.customer = pu.parent 
        where pu.user = '{current_user}'
        order by  p.resource_based_project DESC
        LIMIT 1""",as_dict=1)
    return projects
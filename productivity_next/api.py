import json
import frappe
from frappe.auth import LoginManager
import frappe.utils
from productivity_next.utils.auth import get_bearer_token, update_expiry_time
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


@frappe.whitelist(allow_guest=False, methods=["GET"])
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


@frappe.whitelist(allow_guest=False, methods=["GET", "POST"])
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
                WHEN 'Customer' THEN 1
                WHEN 'Lead' THEN 2
                ELSE 3
            END,
            c.modified DESC
        LIMIT 1;
    """
    contact_details = frappe.db.sql(contact_query, as_dict=True)
    if (
        contact_details
        and contact_details[0].get("link_doctype", "")
        and contact_details[0].get("link_name", "")
    ):
        contact = contact_details[0]
        ec_doc.link_to = contact.get("link_doctype", "")
        ec_doc.contact = contact.get("name", None)
        ec_doc.link_name = contact.get("link_name", "")

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

        day_hours = daily_working_hours

        # Check if it's a Saturday (weekday 5)
        if date.weekday() == 5:
            day_hours = saturday_working_hours
        for leave in leaves:
            if leave.from_date <= current_date <= leave.to_date:
                if leave.half_day:
                    day_hours *= 0.5
                else:
                    day_hours = 0
                break

        total_working_hours += day_hours

    return total_working_hours



@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_home_dashboard_data_for_mobile_app(employee, start_date, end_date):
    data = {}
    weekday_hours = frappe.db.get_single_value('Productify Subscription', 'working_hours_per_day')
    saturday_hours = frappe.db.get_single_value('Productify Subscription', 'working_hours_on_saturday')

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
    """, as_dict=True)

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
        WHERE date >= '{start_date}' and date <= '{end_date}' and employee = '{user}' and url is not null
    """, as_dict=True)

    total_app_data = frappe.db.sql(f"""
        SELECT sum(duration) as total_app_duration, count(DISTINCT application_name) as total_app_count
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' and date <= '{end_date}' and employee = '{user}' and url is null
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
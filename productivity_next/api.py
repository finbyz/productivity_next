import json
import frappe
from frappe.auth import LoginManager
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
    }


@frappe.whitelist(allow_guest=False)
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


@frappe.whitelist(allow_guest=True, methods=["POST"])
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

@frappe.whitelist(allow_guest=True, methods=["POST"])
def send_user_list(user_list):
    url = "https://productivity.finbyz.tech/api/method/productivity_backend.api.receive_user_list"
    organization_name = frappe.db.get_single_value(
        "Productify Subscription", "organization_name"
    )

    if not organization_name:
        return {"message": "Organization name is not set in Productify Subscription"}
    productify_subscription = frappe.get_doc(
        "Productify Subscription", organization_name
    )

    payload = json.dumps({"users": user_list, "organization_id": organization_name})
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

    return {
        "employee": last_call_data[0].employee,
        "employee_name": last_call_data[0].employee_name,
        "call_datetime": last_call_data[0].call_datetime,
    }


@frappe.whitelist(allow_guest=True, methods=["GET"])
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
    employee_fincall_generated,
    contact_created,
    note=None,
    raw_log=None,
    client=None,
):
    fincall = frappe.new_doc("Fincall Log")
    fincall.employee = employee
    fincall.employee_mobile = employee_mobile
    fincall.customer_no = customer_no
    fincall.call_datetime = call_datetime
    fincall.calltype = calltype
    fincall.duration = duration
    fincall.employee_fincall_generated = employee_fincall_generated
    fincall.contact_created = contact_created
    fincall.note = note if note else None
    fincall.raw_log = raw_log if raw_log else None
    fincall.client = client if client else None
    fincall.save(ignore_permissions=True)

    employee_details = frappe.db.get_value(
        "Employee",
        fincall.employee,
        ["name", "employee_name"],
        as_dict=True,
    )

    if fincall.customer_no[0] == "0":
        fincall.customer_no = "+91" + fincall.customer_no[1:]
    elif fincall.customer_no[0] != "+" and fincall.customer_no[0] != "0":
        fincall.customer_no = "+91" + fincall.customer_no

    ec_doc = frappe.new_doc("Employee Fincall")
    ec_doc.employee = employee_details["name"]
    ec_doc.employee_name = employee_details["employee_name"]
    ec_doc.employee_mobile = fincall.employee_mobile
    ec_doc.client = fincall.client if fincall.client else None
    ec_doc.customer_no = fincall.customer_no
    ec_doc.call_datetime = fincall.call_datetime
    ec_doc.duration = fincall.duration
    ec_doc.date = get_datetime(fincall.call_datetime).date()
    ec_doc.calltype = fincall.calltype
    ec_doc.fincall_log_ref = fincall.name
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
            AND (cp.phone = '{fincall.customer_no}' 
            OR cp.phone LIKE '%{fincall.customer_no}' 
            OR '{fincall.customer_no}' LIKE CONCAT("%", cp.phone))
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

    # Update flag indicating that employee fincall is generated
    fincall.db_set("employee_fincall_generated", 1)

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
    return user.get('disable_stop_button',False)

from datetime import timedelta, datetime
import frappe
@frappe.whitelist()
def calculate_total_working_hours(employee, from_date, to_date, daily_working_hours, saturday_working_hours):
    from_date = datetime.strptime(from_date, '%Y-%m-%d')
    to_date = datetime.strptime(to_date, '%Y-%m-%d')
    date_range = [from_date + timedelta(days=x) for x in range((to_date - from_date).days + 1)]

    holidays = frappe.db.sql("""
        SELECT holiday_date 
        FROM `tabHoliday` 
        WHERE holiday_date BETWEEN %s AND %s
    """, (from_date, to_date), as_dict=True)
    holiday_dates = set(holiday.holiday_date for holiday in holidays)

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
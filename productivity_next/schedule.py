import frappe
from frappe.utils import nowdate, get_datetime, format_time, format_duration,today
import frappe.utils
from frappe.utils.data import cint, today
from productivity_next.productivity_next.page.productify_consolidated_analysis.productify_consolidated_analysis import user_analysis_data
from productivity_next.productivity_next.report.productify_activity_summary.productify_activity_summary import execute,get_data
from datetime import timedelta
from datetime import datetime
import traceback

import requests
from .api import (
    set_application_checkin_checkout,
    set_application_idletime_checkin_checkout,
)


def get_all_employee_status():
    all_logs = frappe.db.get_list(
        "Application Checkin Checkout",
        filters={"time": ["Between", [nowdate(), nowdate()]]},
        fields=["employee", "status", "time"],
        order_by="creation asc",
    )

    employe_map = {}

    for row in all_logs:
        employe_map[row.employee] = row

    return [row for row in employe_map.values() if row.status == "In"]


def get_last_activity_time_of_user(employee, time):
    screen_shot_log_time = frappe.db.get_all(
        "Screen Screenshot Log",
        filters={"datetime": [">=", time], "employee": employee},
        fields=["max(datetime) as time"],
        order_by="creation desc",
        limit=1,
    )
    application_usage_log_time = frappe.db.get_all(
        "Application Usage log",
        filters={"date": nowdate(), "employee": employee, "to_time": [">=", time]},
        fields=["to_time as time"],
        order_by="creation desc",
        limit=1,
    )

    times = [time]
    if screen_shot_log_time and screen_shot_log_time[0]["time"]:
        times.append(screen_shot_log_time[0]["time"])

    if application_usage_log_time and application_usage_log_time[0]["time"]:
        times.append(application_usage_log_time[0]["time"])
    return max(times)


def get_time_difference(current_time):
    data = get_all_employee_status()

    for row in data:
        row["last_activity_time"] = get_datetime(
            get_last_activity_time_of_user(row.employee, row.time)
        )
        row["time_difference"] = current_time - row["last_activity_time"]

    return data


def checkout_inactive_users():
    current_time = get_datetime().replace(microsecond=0)
    data = get_time_difference(current_time)

    for row in data:
        if row.time_difference > timedelta(minutes=10):
            if user := frappe.db.get_value("Employee", row.employee, "user_id"):
                set_application_checkin_checkout(
                    row.employee, "Out", current_time, 1, user
                )
                set_application_idletime_checkin_checkout(
                    row.employee, "end", current_time, 1, user
                )
                for obt in frappe.db.get_all(
                    "OAuth Bearer Token",
                    {"user": user, "purpose": "productivity_desktop"},
                ):
                    frappe.delete_doc(
                        "OAuth Bearer Token", obt.name, ignore_permissions=True
                    )


def delete_older_screenshots():
    delete_files_before = (
        frappe.db.get_single_value(
            "Application Log Settings", "delete_files_before_days"
        )
        or 15
    )
    current_date = get_datetime().replace(microsecond=0, hour=0, minute=0, second=0)
    to_datetime = current_date - timedelta(days=delete_files_before)

    screenshot_logs = frappe.db.get_all(
        "Screen Screenshot Log", filters={"creation": ["<", to_datetime]}, pluck="name"
    )

    for row in screenshot_logs:
        frappe.delete_doc("Screen Screenshot Log", row)


def bg_employee_log_generation():
    call_logs = frappe.db.get_all(
        "Fincall Log",
        {"employee_fincall_generated": 0, "ignore_contact": 0, "duplicate_contact": 0},
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

        if fincall_log.customer_no[0] == "0":
            fincall_log.customer_no = "+91" + fincall_log.customer_no[1:]
        elif fincall_log.customer_no[0] != "+" and fincall_log.customer_no[0] != "0":
            fincall_log.customer_no = "+91" + fincall_log.customer_no

        # Check if an Employee Fincall document with the same data exists in the last 15 days
        existing_fincall = frappe.db.sql(
            """
            SELECT name 
            FROM `tabEmployee Fincall` 
            WHERE employee = %(employee)s
            AND customer_no = %(customer_no)s
            AND calltype = %(calltype)s
            AND call_datetime BETWEEN %(fifteen_days_ago)s AND %(call_datetime)s
            and call_datetime = %(call_datetime)s
        """,
            {
                "employee": employee_details["name"],
                "customer_no": fincall_log.customer_no,
                "calltype": fincall_log.calltype,
                "fifteen_days_ago": fifteen_days_ago,
                "call_datetime": fincall_log.call_datetime,
            },
        )

        if existing_fincall:
            # Update flag indicating that employee fincall is generated
            fincall_log.db_set("duplicate_contact", 1)

        if not existing_fincall:
            # Create new Employee Fincall document
            ec_doc = frappe.new_doc("Employee Fincall")
            ec_doc.employee = employee_details["name"]
            ec_doc.employee_name = employee_details["employee_name"]
            ec_doc.employee_mobile = fincall_log.employee_mobile
            ec_doc.client = fincall_log.client if fincall_log.client else None
            ec_doc.customer_no = fincall_log.customer_no
            ec_doc.call_datetime = fincall_log.call_datetime
            ec_doc.duration = fincall_log.duration
            ec_doc.date = get_datetime(fincall_log.call_datetime).date()
            ec_doc.calltype = fincall_log.calltype
            ec_doc.fincall_log_ref = fincall_log.name
            print(fincall_log.customer_no)
            # Try to get contact details

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
                    AND (cp.phone = '{fincall_log.customer_no}' 
                    OR cp.phone LIKE '%{fincall_log.customer_no}' 
                    OR '{fincall_log.customer_no}' LIKE CONCAT("%", cp.phone))
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
            if contact_details == []:
                contact_details = frappe.db.sql(f"""select name as link_name, 'Job Applicant' as link_doctype from `tabJob Applicant`
                                                WHERE 
                                                    LENGTH(mobile_number) >= 10 
                                                    AND (mobile_number = '{fincall_log.customer_no}' 
                                                    OR mobile_number LIKE '%{fincall_log.customer_no}' 
                                                    OR '{fincall_log.customer_no}' LIKE CONCAT("%", mobile_number))""", as_dict=True)
            if contact_details and contact_details[0].get("link_doctype", "") and contact_details[0].get("link_name", ""):
                contact = contact_details[0]
                ec_doc.link_to = contact.get("link_doctype", "")
                ec_doc.contact = contact.get("name", None)
                ec_doc.link_name = contact.get("link_name", "")

            ec_doc.flags.ignore_permissions = True
            
            try:
                ec_doc.save()
                fincall_log.db_set("employee_fincall_generated", 1)
            except frappe.exceptions.UniqueValidationError:
                fincall_log.db_set("duplicate_contact", 1)
            except Exception as e:
                error_message = f"Error occurred while saving Employee Fincall: {str(e)}"
                frappe.log_error(error_message, "Employee Fincall Creation Error")

def schedule_comments():
    calls = frappe.db.get_list(
        "Employee Fincall",
        {
            "comment": ('is','not set'),
            "link_name":("is",'set'),
        },
        order_by="call_datetime ASC",
        page_length=100,
    )

    for call in calls:
        doc = frappe.get_doc("Employee Fincall", call.name)
        employee_fincall_url = doc.get_url()
        
        comment_text = doc.get_comment_text(employee_fincall_url)
        comment = frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": doc.link_to,
                "reference_name": doc.link_name,
                "comment_by": doc.employee,
                "subject": doc.calltype,
                "content": comment_text,
            }
        )
        
            
        comment.save()
        frappe.db.set_value('Comment',comment.name, 'creation', doc.call_datetime)
        doc.comment = comment.name
        doc.flags.ignore_mandatory = True
        doc.save()

@frappe.whitelist()
def create_productify_work_summary():
    from frappe.utils import nowdate, get_datetime, format_datetime,add_to_date, today, date_diff
    date = add_to_date(today(), days=-1)
    if frappe.db.exists('Productify Work Summary', {'date': date}):
        pws_docs = frappe.get_all('Productify Work Summary', filters={'date': date})
        for PWS in pws_docs:
            frappe.delete_doc('Productify Work Summary', PWS['name'])

    employees = frappe.get_all('List of User', fields=['employee'])
    for i in employees:
        employee = i['employee']
        date = date
        def productify_work_summary(employee,date):
            print('employee',employee)
            calls_data = frappe.db.sql(f"""
            SELECT call_datetime as start, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end, 'call' as type,  COALESCE(
                (SELECT first_name FROM `tabContact` WHERE name = COALESCE(contact, client, customer_no)),
                COALESCE(contact, client, customer_no)
            ) AS caller
            from `tabEmployee Fincall`
            where employee = '{employee}' and date = '{date}'
            """, as_dict=True)
            print('calls_data',len(calls_data))
            internal_meetings_data = frappe.db.sql(f"""
            SELECT m.meeting_from as start, m.meeting_to as end, 'meeting' as type, m.internal_meeting as meeting_type, Null as party
            FROM `tabMeeting` as m
            JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
            WHERE mcr.employee = '{employee}' and m.docstatus = 1 and m.meeting_from >= '{date} 00:00:00' and m.meeting_to <= '{date} 23:59:59' and m.internal_meeting = 1
            """, as_dict=True)

            external_meeting_data = frappe.db.sql(f"""
            SELECT m.meeting_from as start, m.meeting_to as end, 'meeting' as type, m.party as party,  m.internal_meeting as meeting_type
            FROM `tabMeeting` as m
            JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
            WHERE mcr.employee = '{employee}' and m.docstatus = 1 and m.meeting_from >= '{date} 00:00:00' and m.meeting_to <= '{date} 23:59:59' and m.internal_meeting = 0
            """, as_dict=True)                         

            idle_logs = frappe.db.sql(f"""
            select from_time as start, to_time as end, 'idle' as type
            from `tabEmployee Idle Time`
            where employee = '{employee}' and from_time >= '{date} 00:00:00' and to_time <= '{date} 23:59:59'
            """, as_dict=True)

            applications_data = frappe.db.sql(f"""
            select from_time as start, to_time as end, 'application' as type, task, issue, project
            from `tabApplication Usage log`
            where employee = '{employee}' and date = '{date}'
            """, as_dict=True)
            print('applications_data',applications_data)
            data = calls_data + internal_meetings_data + idle_logs + applications_data + external_meeting_data
            data = sorted(data, key=lambda x: x['start'])

            priority_order = {'call': 3, 'meeting': 2, 'idle': 1, 'application': 0}

            for i in data:
                i['priority'] = priority_order[i['type']]

            return data
        def remove_overlapping(data):
            i = 0
            while i < len(data) - 1:
                j = i + 1
                while j < len(data):
                    if data[i]['end'] > data[j]['start']:
                        if data[i]['priority'] > data[j]['priority']:
                            if data[j]['end'] <= data[i]['end'] and data[j]['start'] >= data[i]['start']:
                                data.pop(j)
                                continue
                            else:
                                from datetime import datetime, timedelta
                                new_start = data[i]['end'] + timedelta(seconds=1)
                                data[j]['start'] = new_start
                                if j + 1 < len(data) and data[j]['end'] <= data[j + 1]['start']:
                                    j += 1
                                else:
                                    data.sort(key=lambda x: x['start'])
                                    i = 0
                        else:
                            if data[i]['end'] <= data[j]['end'] and data[i]['start'] >= data[j]['start']:
                                data.pop(i)
                                break
                            else:
                                from datetime import datetime, timedelta
                                new_end = data[j]['start'] - timedelta(seconds=1)
                                data[i]['end'] = new_end
                                if i > 0 and data[i]['start'] <= data[i - 1]['end']:
                                    i -= 1
                                    break
                    else:
                        j += 1
                i += 1
            
            return data

        data = productify_work_summary(employee, date)
        final_data = remove_overlapping(data)
        combined_applications = []
        current_app = None
        if len(final_data) == 0:
            continue
        for entry in final_data:
            if entry['type'] == 'application':
                if current_app is None or (entry['start'] - current_app['end']).total_seconds() <= 20:
                    if current_app is None:
                        current_app = entry.copy()
                    else:
                        current_app['end'] = entry['end']
                if (entry['start'] - current_app['end']).total_seconds() <= 20:
                    current_app['end'] = entry['end']
                else:
                    combined_applications.append(current_app)
                    current_app = entry.copy()
            else:
                if current_app is not None:
                    combined_applications.append(current_app)
                    current_app = None
        if current_app is not None:
            combined_applications.append(current_app)
        PWS = frappe.new_doc('Productify Work Summary')
        PWS.employee = employee
        PWS.date = date

        for app_entry in combined_applications:
            PWS.append('applications', {
                'from_time': app_entry['start'],
                'to_time': app_entry['end'],
                'task': app_entry.get('task'),
                'issue': app_entry.get('issue'),
                'project': app_entry.get('project')
            })
        try:
            PWS.save()
        except frappe.exceptions.LinkValidationError as le:
            keys = {"project":"Project","issue":"Issue","Task":"task","Employee Fincall":"call","Meeting":"meeting"}
            for app in PWS.get('applications',[]):
                for doc,field in keys.items():
                    if not frappe.db.exists(doc,app.get(field)):
                        app.set(field,None)
            PWS.save()
        except Exception as e:
            frappe.log_error('work summary today error',traceback.print_exc())
        print(PWS.name)

@frappe.whitelist()
def create_productify_work_summary_today():
    from frappe.utils import today
    date = today()
    employees = frappe.get_all('List of User', fields=['employee'])
    for i in employees:
        employee = i['employee']
        if not frappe.db.exists('Productify Work Summary', {'date': date,'employee':i['employee']}):
            # print("DOES NOT EXIST")
            date = date
            def productify_work_summary(employee,date):
                print('employee',employee)
                calls_data = frappe.db.sql(f"""
                SELECT call_datetime as start, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end, 'call' as type,  COALESCE(
                    (SELECT first_name FROM `tabContact` WHERE name = COALESCE(contact, client, customer_no)),
                    COALESCE(contact, client, customer_no)
                ) AS caller, name as call_id, task, issue, project
                from `tabEmployee Fincall`
                where employee = '{employee}' and date = '{date}'
                """, as_dict=True)
                # print('calls_data',len(calls_data))
                internal_meetings_data = frappe.db.sql(f"""
                SELECT m.name as meeting, m.meeting_from as start, m.meeting_to as end, 'meeting' as type, m.internal_meeting as meeting_type, Null as party, m.task, m.issue, m.project
                FROM `tabMeeting` as m
                JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
                WHERE mcr.employee = '{employee}' and m.docstatus = 1 and m.meeting_from >= '{date} 00:00:00' and m.meeting_to <= '{date} 23:59:59' and m.internal_meeting = 1
                """, as_dict=True)

                external_meeting_data = frappe.db.sql(f"""
                SELECT m.name as meeting, m.meeting_from as start, m.meeting_to as end, 'meeting' as type, m.party as party,  m.internal_meeting as meeting_type, m.task, m.issue, m.project
                FROM `tabMeeting` as m
                JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
                WHERE mcr.employee = '{employee}' and m.docstatus = 1 and m.meeting_from >= '{date} 00:00:00' and m.meeting_to <= '{date} 23:59:59' and m.internal_meeting = 0
                """, as_dict=True)                         

                idle_logs = frappe.db.sql(f"""
                select from_time as start, to_time as end, 'idle' as type
                from `tabEmployee Idle Time`
                where employee = '{employee}' and from_time >= '{date} 00:00:00' and to_time <= '{date} 23:59:59'
                """, as_dict=True)
                # print("employee",employee)
                # print("date",date)
                applications_data = frappe.db.sql(f"""
                select from_time as start, to_time as end, 'application' as type, task, issue, project
                from `tabApplication Usage log`
                where employee = '{employee}' and date = '{date}'
                """, as_dict=True)
                # print('applications_data',applications_data)
                data = calls_data + internal_meetings_data + idle_logs + applications_data + external_meeting_data
                data = sorted(data, key=lambda x: x['start'])

                priority_order = {'call': 3, 'meeting': 2, 'idle': 1, 'application': 0}

                for i in data:
                    i['priority'] = priority_order[i['type']]

                return data
            def remove_overlapping(data):
                i = 0
                while i < len(data) - 1:
                    j = i + 1
                    while j < len(data):
                        if data[i]['end'] > data[j]['start']:
                            if data[i]['priority'] > data[j]['priority']:
                                if data[j]['end'] <= data[i]['end'] and data[j]['start'] >= data[i]['start']:
                                    data.pop(j)
                                    continue
                                else:
                                    from datetime import datetime, timedelta
                                    new_start = data[i]['end'] + timedelta(seconds=1)
                                    data[j]['start'] = new_start
                                    if j + 1 < len(data) and data[j]['end'] <= data[j + 1]['start']:
                                        j += 1
                                    else:
                                        data.sort(key=lambda x: x['start'])
                                        i = 0
                            else:
                                if data[i]['end'] <= data[j]['end'] and data[i]['start'] >= data[j]['start']:
                                    data.pop(i)
                                    break
                                else:
                                    from datetime import datetime, timedelta
                                    new_end = data[j]['start'] - timedelta(seconds=1)
                                    data[i]['end'] = new_end
                                    if i > 0 and data[i]['start'] <= data[i - 1]['end']:
                                        i -= 1
                                        break
                        else:
                            j += 1
                    i += 1
                
                return data

            data = productify_work_summary(employee, date)
            final_data = remove_overlapping(data)
            if len(final_data) == 0:
                continue
            combined_applications = []
            current_app = None

            for entry in final_data:
                if entry['type'] == 'application':
                    if current_app is None or (entry['start'] - current_app['end']).total_seconds() <= 20:
                        if current_app is None:
                            current_app = entry.copy()
                        else:
                            current_app['end'] = entry['end']
                    if (entry['start'] - current_app['end']).total_seconds() <= 20:
                        current_app['end'] = entry['end']
                    else:
                        combined_applications.append(current_app)
                        current_app = entry.copy()
                else:
                    if current_app is not None:
                        combined_applications.append(current_app)
                        current_app = None
            if current_app is not None:
                combined_applications.append(current_app)
            PWS = frappe.new_doc('Productify Work Summary')
            PWS.employee = employee
            PWS.date = date

            for app_entry in combined_applications:
                PWS.append('applications', {
                    'from_time': app_entry['start'],
                    'to_time': app_entry['end'],
                    'task': app_entry.get('task'),
                    'issue': app_entry.get('issue'),
                    'project': app_entry.get('project'),
                    'meeting': app_entry.get('meeting'),
                    'call': app_entry.get('call_id'),
                })
            try:
                PWS.save()
            except frappe.exceptions.LinkValidationError as le:
                keys = {"project":"Project","issue":"Issue","Task":"task","Employee Fincall":"call","Meeting":"meeting"}
                for app in PWS.get('applications',[]):
                    for doc,field in keys.items():
                        if not frappe.db.exists(doc,app.get(field)):
                            app.set(field,None)
                PWS.save()
            except Exception as e:
                frappe.log_error('work summary today error',traceback.print_exc())
            # print(PWS.name)
        else:
            PWS_DOC = frappe.get_doc('Productify Work Summary',{'date': date,'employee':i['employee']})
            employee = i['employee']
            print("else"+ employee)
            print("else"+ date) 
            print("else"+ PWS_DOC.name)
            if PWS_DOC.applications:
                last_activity = PWS_DOC.applications[-1].to_time
            else:
                last_activity = f"{date} 00:00:00"
            def productify_work_summary(employee,date,last_activity):
                calls_data = frappe.db.sql(f"""
                SELECT call_datetime as start, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end, 'call' as type,  COALESCE(
                    (SELECT first_name FROM `tabContact` WHERE name = COALESCE(contact, client, customer_no)),
                    COALESCE(contact, client, customer_no)
                ) AS caller
                from `tabEmployee Fincall`
                where employee = '{employee}' and date = '{date}' and call_datetime >= '{last_activity}'
                """, as_dict=True)
                # print('calls_data',len(calls_data))
                internal_meetings_data = frappe.db.sql(f"""
                SELECT m.meeting_from as start, m.meeting_to as end, 'meeting' as type, m.internal_meeting as meeting_type, Null as party
                FROM `tabMeeting` as m
                JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
                WHERE mcr.employee = '{employee}' and m.docstatus = 1 and m.meeting_from >= '{date} 00:00:00' and m.meeting_to <= '{date} 23:59:59' and m.internal_meeting = 1 and m.meeting_from >= '{last_activity}'
                """, as_dict=True)

                external_meeting_data = frappe.db.sql(f"""
                SELECT m.meeting_from as start, m.meeting_to as end, 'meeting' as type, m.party as party,  m.internal_meeting as meeting_type
                FROM `tabMeeting` as m
                JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
                WHERE mcr.employee = '{employee}' and m.docstatus = 1 and m.meeting_from >= '{date} 00:00:00' and m.meeting_to <= '{date} 23:59:59' and m.internal_meeting = 0 and m.meeting_from >= '{last_activity}'
                """, as_dict=True)                         

                idle_logs = frappe.db.sql(f"""
                select from_time as start, to_time as end, 'idle' as type
                from `tabEmployee Idle Time`
                where employee = '{employee}' and from_time >= '{date} 00:00:00' and to_time <= '{date} 23:59:59' and from_time >= '{last_activity}'
                """, as_dict=True)

                applications_data = frappe.db.sql(f"""
                select from_time as start, to_time as end, 'application' as type, task, issue, project
                from `tabApplication Usage log`
                where employee = '{employee}' and date = '{date}' and from_time >= '{last_activity}'
                """, as_dict=True)
                # print('applications_data',applications_data)
                data = calls_data + internal_meetings_data + idle_logs + applications_data + external_meeting_data
                data = sorted(data, key=lambda x: x['start'])

                priority_order = {'call': 3, 'meeting': 2, 'idle': 1, 'application': 0}

                for i in data:
                    i['priority'] = priority_order[i['type']]

                return data
            def remove_overlapping(data):
                i = 0
                while i < len(data) - 1:
                    j = i + 1
                    while j < len(data):
                        if data[i]['end'] > data[j]['start']:
                            if data[i]['priority'] > data[j]['priority']:
                                if data[j]['end'] <= data[i]['end'] and data[j]['start'] >= data[i]['start']:
                                    data.pop(j)
                                    continue
                                else:
                                    from datetime import datetime, timedelta
                                    new_start = data[i]['end'] + timedelta(seconds=1)
                                    data[j]['start'] = new_start
                                    if j + 1 < len(data) and data[j]['end'] <= data[j + 1]['start']:
                                        j += 1
                                    else:
                                        data.sort(key=lambda x: x['start'])
                                        i = 0
                            else:
                                if data[i]['end'] <= data[j]['end'] and data[i]['start'] >= data[j]['start']:
                                    data.pop(i)
                                    break
                                else:
                                    from datetime import datetime, timedelta
                                    new_end = data[j]['start'] - timedelta(seconds=1)
                                    data[i]['end'] = new_end
                                    if i > 0 and data[i]['start'] <= data[i - 1]['end']:
                                        i -= 1
                                        break
                        else:
                            j += 1
                    i += 1
                
                return data

            data = productify_work_summary(employee, date, last_activity)
            final_data = remove_overlapping(data)
            if len(final_data) == 0:
                continue
            combined_applications = []
            current_app = None

            for entry in final_data:
                if entry['type'] == 'application':
                    if current_app is None or (entry['start'] - current_app['end']).total_seconds() <= 20:
                        if current_app is None:
                            current_app = entry.copy()
                        else:
                            current_app['end'] = entry['end']
                    if (entry['start'] - current_app['end']).total_seconds() <= 20:
                        current_app['end'] = entry['end']
                    else:
                        combined_applications.append(current_app)
                        current_app = entry.copy()
                else:
                    if current_app is not None:
                        combined_applications.append(current_app)
                        current_app = None
            if current_app is not None:
                combined_applications.append(current_app)
            PWS = frappe.get_doc('Productify Work Summary', {'date': date,'employee':i['employee']})
            for app_entry in combined_applications:
                PWS.append('applications', {
                    'from_time': app_entry['start'],
                    'to_time': app_entry['end'],
                    'task': app_entry.get('task'),
                    'issue': app_entry.get('issue'),
                    'project': app_entry.get('project')
                })
            try:
                PWS.save()
            except frappe.exceptions.LinkValidationError as le:
                PWS.reload()
                keys = {"project":"Project","issue":"Issue","Task":"task","Employee Fincall":"call","Meeting":"meeting"}
                for app in PWS.get('applications',[]):
                    for doc,field in keys.items():
                        if not frappe.db.exists(doc,app.get(field)):
                            app.set(field,None)
                PWS.save()
            except Exception as e:
                frappe.log_error('work summary today error',traceback.print_exc())



def get_employee_data(start_date, end_date):
    userdata = user_analysis_data(start_date, end_date)  # Fetch data with provided dates

    # Debug: Print the structure and content of userdata
    print("Userdata fetched:", userdata)

    # Initializing the data dictionary
    data = {
        "total_hours_per_employee": {},
        "total_idle_time": {},
        "employee_fincall_data": {},
        "meeting_employee_data": {},
        "total_days": {},
        "work_intensity_data": {}
    }

    # Fetching employees with non-empty user_id
    employees = frappe.get_all("Employee", filters={"name": "HR-EMP-00011"}, fields=["name", "employee_name", "user_id"])
    
    # Debug: Print employees fetched
    print("Employees fetched:", employees)

    for employee in employees:
        employee_name = employee.employee_name
        employee_id = employee.name  # Use employee ID instead of user_id

        # Debug: Print current employee details
        print("Processing employee:", employee_name, "with employee_id:", employee_id)

        # Initialize data structures for the employee
        data["total_hours_per_employee"][employee_name] = {
            "total_hours": 0,
            "active_hours": 0,
            "idle_hours": 0,
            "average_active_hours": 0,
            "incoming_calls": 0,
            "outgoing_calls": 0,
            "missed_calls": 0,
            "rejected_calls": 0,
            "keystrokes": 0,
            "mouse_clicks": 0,
            "scrolls": 0,
            "meetings": 0,
            "meeting_duration": 0
        }
        data["total_idle_time"][employee_name] = 0
        data["employee_fincall_data"][employee_name] = {
            "incoming_fincall_count": 0,
            "outgoing_fincall_count": 0,
            "missed_fincall_count": 0,
            "rejected_fincall_count": 0,
            "total_incoming_duration": 0,
            "total_outgoing_duration": 0,
        }
        data["meeting_employee_data"][employee_name] = {"count": 0, "duration": 0}
        data["total_days"][employee_name] = 1
        data["work_intensity_data"][employee_name] = {
            "total_keystrokes": 0,
            "total_mouse_clicks": 0,
            "total_scroll": 0,
        }

        # Update data with values from userdata
        if employee_id in userdata.get("total_hours_per_employee", {}):
            data["total_hours_per_employee"][employee_name].update({
                "total_hours": userdata.get("total_hours_per_employee", {}).get(employee_id, 0)
            })

        if employee_id in userdata.get("total_idle_time", {}):
            data["total_idle_time"][employee_name] = userdata.get("total_idle_time", {}).get(employee_id, 0)

        if employee_id in userdata.get("employee_fincall_data", {}):
            data["employee_fincall_data"][employee_name].update(userdata.get("employee_fincall_data", {}).get(employee_id, {}))

        if employee_id in userdata.get("meeting_employee_data", {}):
            data["meeting_employee_data"][employee_name].update(userdata.get("meeting_employee_data", {}).get(employee_id, {}))

        if employee_id in userdata.get("total_days", {}):
            data["total_days"][employee_name] = userdata.get("total_days", {}).get(employee_id, 1)

        if employee_id in userdata.get("work_intensity_data", {}):
            data["work_intensity_data"][employee_name].update(userdata.get("work_intensity_data", {}).get(employee_id, {}))

    return employees, data


def generate_html_table(data, employees, start_date, end_date):
    base_url = frappe.utils.get_url()
    table_rows = ""
    count = 1

    for employee in employees:
        employee_name = employee.employee_name
        employee_data = data["total_hours_per_employee"].get(employee_name, {})

        employee_url = f"{base_url}/app/Productify Activity Analysis?start_date={start_date}&end_date={end_date}&employee={employee.name}"
        employee_meeting_url = f"{base_url}/app/meeting?employee={employee.name}&meeting_from=[\"Between\",[\"{start_date}\",\"{end_date}\"]]&docstatus=1"
        employee_fincall_url = f"{base_url}/app/employee-fincall?employee={employee.name}&date=[\"Between\",[\"{start_date}\",\"{end_date}\"]]"
        
        table_rows += f"""
            <tr>
                <td align="left">
                    <a href="{employee_url}" target="_blank">{count}. {employee_name}</a>
                </td>
                <td align="center" style="color:#00A6E0;">{format_duration(employee_data.get('total_hours', 0))}</td>
                <td align="center" style="color:#00A6E0;">{format_duration(employee_data.get('total_hours', 0) - employee_data.get('idle_hours', 0))}</td>
                <td align="center" style="color:#00A6E0;">{format_duration(employee_data.get('idle_hours', 0))}</td>
                <td align="center" style="color:#00A6E0;">{format_duration((employee_data.get('total_hours', 0) / data['total_days'][employee_name]) - (employee_data.get('idle_hours', 0) / data['total_days'][employee_name]))}</td>
                <td align="center"><a href="{employee_fincall_url}&calltype=Incoming" style="color:#62BA46;" target="_blank">{employee_data.get('incoming_calls', 0)} ({format_duration(data['employee_fincall_data'][employee_name].get('total_incoming_duration', 0))} H)</a></td>
                <td align="center"><a href="{employee_fincall_url}&calltype=Outgoing" style="color:#62BA46;" target="_blank">{employee_data.get('outgoing_calls', 0)} ({format_duration(data['employee_fincall_data'][employee_name].get('total_outgoing_duration', 0))} H)</a></td>
                <td align="center"><a href="{employee_fincall_url}&calltype=Missed" style="color:#62BA46;" target="_blank">{employee_data.get('missed_calls', 0)}</a></td>
                <td align="center"><a href="{employee_fincall_url}&calltype=Rejected" style="color:#62BA46;" target="_blank">{employee_data.get('rejected_calls', 0)}</a></td>
                <td align="center" style="color:#FF4001;">{employee_data.get('keystrokes', 0)}</td>
                <td align="center" style="color:#FF4001;">{employee_data.get('mouse_clicks', 0)}</td>
                <td align="center" style="color:#FF4001;">{employee_data.get('scrolls', 0)}</td>
                <td align="center"><a href="{employee_meeting_url}" style="color:#6420AA;" target="_blank">{employee_data.get('meetings', 0)}</a></td>
                <td align="center"><a href="{employee_meeting_url}" style="color:#6420AA;" target="_blank">{format_duration(employee_data.get('meeting_duration', 0))}</a></td>
            </tr>
        """
        count += 1

    html_table = f"""
    <table border="1">
        <thead>
            <tr>
                <th>Employee Name</th>
                <th>Total Hours</th>
                <th>Active Hours</th>
                <th>Idle Hours</th>
                <th>Average Active Hours</th>
                <th>Incoming Calls</th>
                <th>Outgoing Calls</th>
                <th>Missed Calls</th>
                <th>Rejected Calls</th>
                <th>Keystrokes</th>
                <th>Mouse Clicks</th>
                <th>Scrolls</th>
                <th>Meetings</th>
                <th>Meeting Duration</th>
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
    """
    return html_table

def send_email(user_email, user_name, html_table):
    try:
        frappe.sendmail(
            recipients=[user_email],
            subject="Weekly Activity Report",
            message=f"""
            <p>Dear {user_name},</p>
            <p>Please find your weekly activity report below:</p>
            {html_table}
            """,
        )
    except Exception as e:
        frappe.log_error(f"Failed to send email to {user_email}: {e}", "Email Sending Error")

def send_weekly_report():
    start_date = "2024-07-10"  # replace with dynamic date logic
    end_date = "2024-07-10"  # replace with dynamic date logic
    employees, data = get_employee_data(start_date, end_date)
    html_table = generate_html_table(data, employees, start_date, end_date)
               
    for employee in employees:
        send_email(employee.user_id, employee.employee_name, html_table)
        return data


def submit_timesheet_created_by_productify():
    if not frappe.db.exists("Custom Field", {"fieldname": "is_created_by_productify"}):
        frappe.throw("Custom Field 'is_created_by_productify' not found")
    yeasterday = get_datetime().replace(hour=0,minute=0,second=0) - timedelta(days=1)
    timesheets = frappe.get_all(
        "Timesheet",
        filters={"docstatus": 0, "is_created_by_productify": 1,"creation": (">=", yeasterday)},
        fields=["name"],
    )
    errors = ""
    for timesheet in timesheets:
        try:
            doc = frappe.get_doc("Timesheet", timesheet.name)
            doc.submit()
        except Exception as e:
            errors += f'error {timesheet.name} {e}\n'
    if errors:
        frappe.log_error(
            title="Error while timesheet auto submission",
            message=errors
        )



def delete_productify_error_logs():
    time_for_error_logs = 10

    date_for_error_logs = get_datetime() - timedelta(days=time_for_error_logs)

    frappe.db.sql("""
        DELETE FROM `tabProductify Error Log`
        WHERE error_datetime < %s
    """, (date_for_error_logs.strftime("%Y-%m-%d %H:%M:%S"),))


def delete_screenshots():
    time_for_screenshots = frappe.db.get_single_value("Productify Configuration", "keep_screenshots_for_days") or 60
    time_for_screenshots = int(time_for_screenshots)
    date_for_screenshots = get_datetime() - timedelta(days=time_for_screenshots)
    screenshots = frappe.get_all("Screen Screenshot Log", {"time": ("<", date_for_screenshots.strftime("%Y-%m-%d %H:%M:%S"))})
    for screenshot in screenshots:
        frappe.delete_doc("Screen Screenshot Log", screenshot.name)

def delete_application_logs():
    time_for_application_logs = frappe.db.get_single_value("Productify Configuration", "keep_application_logs_for_days") or 60
    time_for_application_logs = int(time_for_application_logs)
    date_for_application_logs = get_datetime() - timedelta(days=time_for_application_logs)
    frappe.db.sql("""
        DELETE FROM `tabApplication Usage log`
        WHERE date < %s
    """, (date_for_application_logs.date(),))


def set_challenge():
    productify_subscription = frappe.get_doc("Productify Subscription")
    headers = {
        "Authorization" : f"token {productify_subscription.api_key}:{productify_subscription.get_password('api_secret')}",
    }

    if not productify_subscription.token_updated_on or get_datetime(productify_subscription.token_updated_on) < get_datetime(nowdate()):
        print(productify_subscription.token_updated_on)
        response = requests.post(
            "https://productivity.finbyz.tech/api/method/productivity_backend.api.get_challenge",
            data={"erpnext_url": productify_subscription.site_url},
            headers=headers
        )

        if response.status_code != 200:
            frappe.log_error(title="Productify Challenge Error", message=f"Failed to get challenge: {response.text}")
            return
        
        data = response.json().get("message")

        if not data.get("token"):
            frappe.log_error(title="Productify Challenge Error", message=f"Failed to get challenge: {response.text}")
            return
        
        frappe.db.set_value("Productify Subscription", "Productify Subscription", "token", data.get("token"))
        frappe.db.set_value("Productify Subscription", "Productify Subscription", "token_call", data.get("token_call"))
        frappe.db.set_value("Productify Subscription", "Productify Subscription", "token_updated_on", nowdate())

        date = get_datetime()
        for user in productify_subscription.list_of_users:
            expiration_time = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=7)
            outh_bearer_token_name_call = frappe.db.get_value(
                "OAuth Bearer Token",
                filters={"purpose": "productivity_desktop", "user": user.user_id}, fieldname="name"
            )
            call_expiration = frappe.db.get_value(
                "OAuth Bearer Token",
                filters={"purpose": "productivity_desktop", "user": user.user_id}, fieldname="name"
            )
            outh_bearer_token_name_app = frappe.db.get_value(
                "OAuth Bearer Token",
                filters={"purpose": "productivity_call_log", "user": user.user_id}, fieldname="name"
            )
            app_expiration = frappe.db.get_value(
                "OAuth Bearer Token",
                filters={"purpose": "productivity_call_log", "user": user.user_id}, fieldname="name"
            )

            if outh_bearer_token_name_call and call_expiration != expiration_time:
                frappe.db.set_value("OAuth Bearer Token", outh_bearer_token_name_call, "expiration_time", expiration_time)
                frappe.db.set_value("OAuth Bearer Token", outh_bearer_token_name_call, "expires_in", (expiration_time - get_datetime()).total_seconds())
            if outh_bearer_token_name_app and app_expiration != expiration_time:
                frappe.db.set_value("OAuth Bearer Token", outh_bearer_token_name_app, "expiration_time", expiration_time)
                frappe.db.set_value("OAuth Bearer Token", outh_bearer_token_name_app, "expires_in", (expiration_time - get_datetime()).total_seconds())

import frappe
from typing import Literal, Dict, Any, Optional

def get_email_template(report_type: Literal["daily", "weekly"]) -> str:
    """Returns the appropriate email template based on report type."""
    # Ensure consistent single forward slash in URL
    base_url = frappe.utils.get_url().rstrip('/')  # Remove any trailing slashes
    dashboard_url = f"{base_url}/app/Productify%20Consolidated%20Analysis"
    
    templates = {
        "daily": f"""<div class='ql-editor read-mode'>
            <p>Dear Team,</p>
            <p>Here's your daily Productify performance summary for yesterday. The report provides detailed insights into:</p>
            <ul>
                <li><strong>Activity Timeline:</strong> Hour-by-hour breakdown of user activities including:
                    <ul>
                        <li>Application usage periods</li>
                        <li>Meeting times (Internal & External)</li>
                        <li>Active vs Idle time</li>
                        <li>Call durations</li>
                    </ul>
                </li>
                <li><strong>User Analysis Metrics:</strong>
                    <ul>
                        <li>Productivity Scores</li>
                        <li>Activity Hours (Total, Active, Idle)</li>
                        <li>Phone Call Statistics (Incoming, Outgoing, Missed, Rejected)</li>
                        <li>Work Intensity (Keyboard, Mouse, Scroll activity)</li>
                        <li>Meeting Hours</li>
                    </ul>
                </li>
            </ul>
            <p>For interactive visualizations and deeper insights, visit the <a href="{dashboard_url}"><strong>Productify Consolidated Analysis</strong></a> dashboard.</p>
            <p><strong>Key Actions:</strong></p>
            <ul>
                <li>Review your productivity scores and activity patterns</li>
                <li>Analyze your time distribution across different activities</li>
                <li>Check your meeting attendance and call handling efficiency</li>
                <li>Monitor your work intensity metrics</li>
            </ul>
            <p><strong>Note:</strong> This report reflects yesterday's activities. For real-time data, please visit the dashboard.</p>
            <p>Best regards,<br>Your Productify Analytics Team</p>
        </div>""",
        "weekly": f"""<div class='ql-editor read-mode'>
            <p>Dear Team,</p>
            <p>Welcome to your weekly Productify performance analysis. This comprehensive report aggregates last week's productivity data, providing valuable insights into:</p>
            <ul>
                <li><strong>Weekly Activity Patterns:</strong>
                    <ul>
                        <li>Daily productivity trends and scores</li>
                        <li>Application usage patterns across the week</li>
                        <li>Meeting time distribution</li>
                        <li>Peak productivity periods</li>
                    </ul>
                </li>
                <li><strong>Consolidated Metrics:</strong>
                    <ul>
                        <li>Overall productivity scoring</li>
                        <li>Total active vs idle time analysis</li>
                        <li>Communication patterns (calls and meetings)</li>
                        <li>Work intensity trends</li>
                    </ul>
                </li>
            </ul>
            <p>For detailed analytics and trend visualization, access the <a href="{dashboard_url}"><strong>Productify Consolidated Analysis</strong></a> dashboard.</p>
            <p><strong>Weekly Insights:</strong></p>
            <ul>
                <li>Compare your daily productivity patterns</li>
                <li>Identify your most productive days and times</li>
                <li>Review your meeting and communication efficiency</li>
                <li>Track progress on work intensity metrics</li>
            </ul>
            <p><strong>Note:</strong> This report summarizes last week's activities. For current week trends, please check the live dashboard.</p>
            <p>Best regards,<br>Your Productify Analytics Team</p>
        </div>"""
    }
    return templates[report_type]

def get_report_config(frequency: Literal["Daily", "Weekly"]) -> Dict[str, Any]:
    """Returns the configuration for the auto email report based on frequency."""
    auto_email_name = f"Employee Productivity Matrix {frequency}"
    
    config = {
        "doctype": "Auto Email Report",
        "report": "Employee Productivity Matrix",
        "name": auto_email_name,
        "user": "Administrator",
        "enabled": 1,
        "report_type": "Script Report",
        "send_if_data": 1,
        "format": "HTML",
        "frequency": frequency,
        "filters": frappe.as_json({"timespan": "Yesterday" if frequency == "Daily" else "Last Week"})
    }
    
    if frequency == "Weekly":
        config["day_of_week"] = "Monday"
        
    return config

def setup_auto_email_report(frequency: Literal["Daily", "Weekly"]) -> None:
    """Sets up or updates an auto email report based on frequency."""
    try:
        # Get email configuration
        email_account = frappe.get_value("Email Account", filters={"default_outgoing": 1})
            
        # Get user emails
        employees = frappe.get_all("List of User", fields=["user_id"])
        if not employees:
            frappe.throw("No users found in List of User")
            
        email_to_field = "\n".join(user['user_id'] for user in employees)
        
        # Check for existing reports with this frequency
        existing_reports = frappe.get_all(
            "Auto Email Report",
            filters={
                "report": "Employee Productivity Matrix",
                "frequency": frequency
            }
        )
        
        if existing_reports:
            # Update the first existing report
            doc = frappe.get_doc("Auto Email Report", existing_reports[0].name)
            doc.email_to = email_to_field
            doc.description = get_email_template("daily" if frequency == "Daily" else "weekly")
            doc.save()
                
            frappe.msgprint(f"Updated existing {frequency} report")
        else:
            # Create new report only if none exist
            doc = frappe.new_doc("Auto Email Report")
            doc.update(get_report_config(frequency))
            doc.sender = email_account
            doc.email_to = email_to_field
            doc.description = get_email_template("daily" if frequency == "Daily" else "weekly")
            doc.insert()
            frappe.msgprint(f"Created new {frequency} report")
        
        frappe.db.commit()
        frappe.msgprint(f"{frequency} report setup completed successfully")
        
    except Exception as e:
        frappe.log_error(f"Failed to setup {frequency} auto email report: {str(e)}")

def create_auto_email_report():
    """Creates or updates daily auto email report."""
    setup_auto_email_report("Daily")

def create_auto_email_report_weekly():
    """Creates or updates weekly auto email report."""
    setup_auto_email_report("Weekly")


import frappe
from datetime import datetime, timedelta
from frappe.utils import getdate, nowdate, add_days, get_first_day, get_last_day

def update_due_period():
    today = getdate(nowdate())
    start_of_week = today - timedelta(days=today.weekday() + 1)  # Sunday
    end_of_week = start_of_week + timedelta(days=6)         # Saturday

    start_of_next_month = get_first_day(today + timedelta(days=30))
    end_of_next_month = get_last_day(today + timedelta(days=30))

    start_of_this_month = get_first_day(today)
    end_of_this_month = get_last_day(today)

    # Fetch records with exp_start_date and exp_end_date
    exclude_status = ["Completed","Cancelled"]
    records = frappe.get_all(
        "Task",
        fields=["name", "exp_start_date", "exp_end_date", "status"],
        filters={
            "exp_start_date": ["is", "set"],
            "exp_end_date": ["is", "set"],
            "status":['not in',exclude_status]
        }
    )

    for record in records:
        exp_start_date = getdate(record.get("exp_start_date"))
        exp_end_date = getdate(record.get("exp_end_date"))
        due_period = None
        if exp_end_date < today:
            due_period = "Overdue"
        elif exp_end_date == today:
            due_period = "Today"
        elif exp_end_date <= end_of_week:
            due_period = "This Week"
        elif exp_end_date <= end_of_this_month:
            due_period = "This Month"
        elif start_of_next_month <= exp_start_date or exp_end_date >= end_of_next_month:
            due_period = "Next Month"

        frappe.db.set_value("Task", record.get("name"), "due_period", due_period)

    frappe.db.commit()



def merge_logs(logs):
    logs.sort(key=lambda x: x["from_time"])
    
    merged_logs = []
    
    for log in logs:
        if not merged_logs:
            merged_logs.append(log)
            continue
        
        last_log = merged_logs[-1]
        time_gap = (log["from_time"] - last_log["to_time"]).total_seconds()
        
        priority_keys = ["task", "issue", "project"]
        
        key_changed = any(
            log.get(key) and log[key] != last_log.get(key)
            for key in priority_keys
        )
        
        both_none = all(log.get(key) is None and last_log.get(key) is None for key in priority_keys)
        
        if time_gap <= 10 and not key_changed and (both_none or any(log.get(key) == last_log.get(key) for key in priority_keys)):
            last_log["to_time"] = max(last_log["to_time"], log["to_time"])
        
        elif log["from_time"] <= last_log["to_time"]:
            if log["to_time"] <= last_log["to_time"]:
                continue
            if log["from_time"] < last_log["to_time"]:
                last_log["to_time"] = log["from_time"]
            
            merged_logs.append(log)        
        else:
            log["from_time"] = max(log["from_time"], last_log["to_time"] + timedelta(seconds=1))
            merged_logs.append(log)
    
    return merged_logs

def split_logs(merged_logs, new_logs):
    updated_logs = []
    i, j = 0, 0

    while i < len(merged_logs) or j < len(new_logs):
        if j >= len(new_logs): 
            updated_logs.append(merged_logs[i])
            i += 1
            continue

        if i >= len(merged_logs): 
            updated_logs.append(new_logs[j])
            j += 1
            continue

        old_log = merged_logs[i]
        new_log = new_logs[j]

        if new_log["to_time"] <= old_log["from_time"]:
            updated_logs.append(new_log)
            j += 1
        elif new_log["from_time"] >= old_log["to_time"]:
            updated_logs.append(old_log)
            i += 1
        else:
            if old_log["from_time"] < new_log["from_time"]:
                updated_logs.append({
                    **old_log,
                    "to_time": new_log["from_time"]
                })
            updated_logs.append(new_log)
            j += 1
            
            if old_log["to_time"] > new_log["to_time"]:
                merged_logs[i]["from_time"] = new_log["to_time"]
            else:
                i += 1
    for k in range(1, len(updated_logs)):
        if updated_logs[k]["from_time"] < updated_logs[k - 1]["to_time"]:
            updated_logs[k]["from_time"] = updated_logs[k - 1]["to_time"]
    return updated_logs

def get_employee_meetings(employee, date):
    data = frappe.db.sql(f"""
        SELECT m.name as meeting, m.meeting_from as from_time, m.meeting_to as to_time, m.internal_meeting
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE mcr.employee = '{employee}' and m.docstatus = 1 and m.meeting_from >= '{date} 00:00:00' and m.meeting_to <= '{date} 23:59:59'
        """, as_dict=True)
    return data

def group_logs_by_employee(logs):
    employee_logs = {}
    for log in logs:
        employee = log.get("employee")
        if employee not in employee_logs:
            employee_logs[employee] = []
        employee_logs[employee].append(log)
    return employee_logs

    
def create_timesheet_logs():
    applications = frappe.get_all(
        "Application Usage log",
        fields=["employee","from_time","to_time","task","issue","project"],
        filters={
            "date": ["between",[today(),today()]],
        }
    )
    
    calls = frappe.get_all(
        "Employee Fincall",
        fields=["name as call_id","employee","call_datetime as from_time","ADDTIME(call_datetime, SEC_TO_TIME(duration)) as to_time", "issue", "task", "project"],
        filters={
            "call_datetime": ["between",[today(),today()]],
        }
    )
    
    merged_logs = {}
    applications = group_logs_by_employee(applications)
    calls = group_logs_by_employee(calls)
    employees = frappe.get_all('List of User', fields=['employee'],pluck='employee')
    
    # merge application logs
    for employee, logs in applications.items():
        merged_logs[employee] = merge_logs(logs)
    

    # split meeting logs
    for employee in employees:
        meetings = get_employee_meetings(employee, today())
        merged_logs[employee] = split_logs(merged_logs.get(employee,[]),meetings)
    
    # split call logs
    for employee, logs in calls.items():
        merged_logs[employee] = split_logs(merged_logs.get(employee,[]),logs)
    
    for employee in employees:
        
        existing_timesheets = frappe.get_list(
            "Timesheet",
            filters={
                "employee": employee,
                "status": "Draft",
                "is_created_by_productify": 1,
                "start_date": today(),
            },
            fields=["name"],
            limit=1
        )

        if existing_timesheets:
            timesheet = frappe.get_doc("Timesheet", existing_timesheets[0]["name"])
            timesheet.time_logs = []
        else:
            timesheet = frappe.new_doc("Timesheet")
            timesheet.employee = employee
        timesheet.is_created_by_productify = True
        employee_merged_logs = merged_logs.get(employee, [])
        if not employee_merged_logs:
            continue
        for log in employee_merged_logs:
            log["to_time"] = log["to_time"] - timedelta(seconds=1)
            seconds = (log["to_time"] - log["from_time"]).total_seconds()
            hours = seconds / 3600
            if seconds <= 0:
                continue
            activity_type = ""
            if log.get("meeting"):
                activity_type = "Meeting"
            elif log.get("issue"):
                activity_type = "Issue"
            elif log.get("task"):
                activity_type = "Task"
            elif log.get("project"):
                activity_type = "Project"
            elif log.get("call_id"):
                activity_type = "Call"

            description = get_activity_description(log)
            timesheet.append("time_logs", {
                "activity_type": activity_type,
                "task": log.get("task"),
                "project": log.get("project"),
                "issue": log.get("issue"),
                "hours": hours,
                "from_time": log["from_time"],
                "to_time": log["to_time"],
                "description": description
            })
        try:
            if timesheet.time_logs:
                timesheet.save()
        except Exception as e:
            frappe.log_error(f"Failed to create timesheet for {employee}",e)

def generate_daily_timesheets():
    """Generate timesheets for all employees based on application usage logs, meetings, and calls"""
    yesterday = frappe.utils.add_days(frappe.utils.today(), -1)
    print(f"\n=== Starting Timesheet Generation for date: {yesterday} ===")
    
    # Get all employees from List of User
    employees = frappe.db.sql("""
        SELECT employee, employee_name 
        FROM `tabList of User`
        WHERE employee IS NOT NULL
    """, as_dict=True)
    
    print(f"Found {len(employees)} employees to process")
    
    for emp in employees:
        print(f"\nProcessing employee: {emp.employee} ({emp.employee_name})")
        try:
            # Get all activities for the employee
            activities = get_employee_activities(emp.employee, yesterday)
            print(f"Found {len(activities)} total activities for {emp.employee}")
            
            # Create timesheet if activities exist
            if activities:
                print(f"Creating timesheet for {emp.employee}")
                create_timesheet(emp.employee, yesterday, activities)
            else:
                print(f"No activities found for {emp.employee}, skipping timesheet creation")
                
        except Exception as e:
            print(f"ERROR processing {emp.employee}: {str(e)}")
            frappe.log_error(
                title=f"Timesheet Generation Error - {emp.employee}",
                message=str(e)
            )

def get_employee_activities(employee, date):
    """Get all activities for an employee on a given date"""
    activities = []
    print(f"\nGetting activities for {employee} on {date}")
    
    # Get calls (highest priority)
    calls = frappe.db.sql("""
        SELECT 
            name as call_id,
            call_datetime as from_time,
            ADDTIME(call_datetime, SEC_TO_TIME(duration)) as to_time,
            project, task, issue,
            'Call' as activity_type,
            1 as priority
        FROM `tabEmployee Fincall`
        WHERE 
            employee = %s 
            AND DATE(call_datetime) = %s
            AND (project IS NOT NULL OR task IS NOT NULL OR issue IS NOT NULL)
    """, (employee, date), as_dict=True)
    print(f"Found {len(calls)} calls with tasks/projects")
    activities.extend(calls)
    
    # Get meetings (medium priority)
    meetings = frappe.db.sql("""
        SELECT 
            m.name as meeting_id,
            m.meeting_from as from_time,
            m.meeting_to as to_time,
            m.project, m.task, m.issue,
            'Meeting' as activity_type,
            2 as priority
        FROM `tabMeeting` m
        JOIN `tabMeeting Company Representative` mcr ON m.name = mcr.parent
        WHERE 
            mcr.employee = %s
            AND DATE(m.meeting_from) = %s
            AND m.docstatus = 1
            AND (m.project IS NOT NULL OR m.task IS NOT NULL OR issue IS NOT NULL)
    """, (employee, date), as_dict=True)
    print(f"Found {len(meetings)} meetings with tasks/projects")
    activities.extend(meetings)
    
    # Get application logs (lowest priority)
    app_logs = frappe.db.sql("""
        SELECT 
            from_time,
            to_time,
            project, task, issue,
            'Application' as activity_type,
            3 as priority
        FROM `tabApplication Usage log`
        WHERE 
            employee = %s 
            AND date = %s
            AND (project IS NOT NULL OR task IS NOT NULL OR issue IS NOT NULL)
        ORDER BY from_time
    """, (employee, date), as_dict=True)
    print(f"Found {len(app_logs)} application logs with tasks/projects")
    
    # Combine consecutive application logs with same project/task/issue
    combined_app_logs = []
    if app_logs:
        current_log = app_logs[0].copy()
        for next_log in app_logs[1:]:
            current_end = get_datetime(current_log['to_time'])
            next_start = get_datetime(next_log['from_time'])
            time_gap = (next_start - current_end).total_seconds()
            
            # Check if logs have same project/task/issue and are within 60 seconds of each other
            if (time_gap <= 60 and 
                current_log.get('project') == next_log.get('project') and
                current_log.get('task') == next_log.get('task') and
                current_log.get('issue') == next_log.get('issue')):
                # Extend current log
                current_log['to_time'] = next_log['to_time']
            else:
                combined_app_logs.append(current_log)
                current_log = next_log.copy()
        combined_app_logs.append(current_log)
    
    activities.extend(combined_app_logs)
    
    # Sort by time and priority
    activities.sort(key=lambda x: (x['from_time'], x['priority']))
    print(f"Total activities before overlap resolution: {len(activities)}")
    
    resolved = resolve_overlaps(activities)
    print(f"Total activities after overlap resolution: {len(resolved)}")
    return resolved

def resolve_overlaps(activities):
    """Resolve overlapping time periods based on priority"""
    if not activities:
        return []
        
    resolved = []
    current = activities[0]
    
    for next_activity in activities[1:]:
        current_end = get_datetime(current['to_time'])
        next_start = get_datetime(next_activity['from_time'])
        next_end = get_datetime(next_activity['to_time'])
        
        if current_end > next_start:
            # Handle overlap based on priority
            if current['priority'] <= next_activity['priority']:
                # Current activity has higher or equal priority
                if current_end >= next_end:
                    # Current activity completely encompasses next activity
                    continue
                else:
                    # Current activity partially overlaps next activity
                    next_activity['from_time'] = current_end
            else:
                # Next activity has higher priority
                if next_end >= current_end:
                    # Split current activity if it extends beyond next activity
                    if get_datetime(current['from_time']) < next_start:
                        resolved.append({
                            **current,
                            'to_time': next_start
                        })
                    current = next_activity
                else:
                    # Next activity is contained within current activity
                    if get_datetime(current['from_time']) < next_start:
                        resolved.append({
                            **current,
                            'to_time': next_start
                        })
                    resolved.append(next_activity)
                    current = {
                        **current,
                        'from_time': next_end
                    }
        else:
            resolved.append(current)
            current = next_activity
            
    resolved.append(current)
    
    # Merge any adjacent activities with same properties
    final_resolved = []
    if resolved:
        current = resolved[0]
        for next_activity in resolved[1:]:
            current_end = get_datetime(current['to_time'])
            next_start = get_datetime(next_activity['from_time'])
            
            if ((next_start - current_end).total_seconds() <= 60 and
                current['activity_type'] == next_activity['activity_type'] and
                current.get('project') == next_activity.get('project') and
                current.get('task') == next_activity.get('task') and
                current.get('issue') == next_activity.get('issue')):
                # Merge activities
                current['to_time'] = next_activity['to_time']
            else:
                final_resolved.append(current)
                current = next_activity
        final_resolved.append(current)
    
    return final_resolved

def get_activity_description(activity):
    """Generate description using Task and Issue subject lines."""
    description_parts = []

    if activity.get('task'):
        task_subject = frappe.db.get_value("Task", activity['task'], "subject") or ""
        if task_subject:
            description_parts.append(f"Task - {task_subject}")

    if activity.get('issue'):
        issue_subject = frappe.db.get_value("Issue", activity['issue'], "subject") or ""
        if issue_subject:
            description_parts.append(f"Issue - {issue_subject}")

    return "\n".join(description_parts)

def create_timesheet(employee, date, activities):
    """Create timesheet from activities"""
    print(f"\nCreating timesheet for {employee} on {date}")
    
    # Check for existing timesheet
    existing_timesheet = frappe.db.get_value(
        "Timesheet",
        {
            "employee": employee,
            "start_date": date,
            "is_created_by_productify": 1,
            "docstatus": 0
        },
        "name"
    )
    
    if existing_timesheet:
        print(f"Found existing timesheet: {existing_timesheet}")
        timesheet = frappe.get_doc("Timesheet", existing_timesheet)
        timesheet.time_logs = []  # Clear existing logs
    else:
        print("Creating new timesheet")
        timesheet = frappe.new_doc("Timesheet")
        timesheet.employee = employee
        timesheet.start_date = date
        timesheet.end_date = date
        timesheet.is_created_by_productify = 1
    
    print("\nProcessing activities for timesheet:")
    
    # Group activities by project/task/issue
    activity_groups = {}
    for activity in activities:
        key = (
            activity.get('project'),
            activity.get('task'),
            activity.get('issue'),
            activity.get('activity_type')
        )
        if key not in activity_groups:
            activity_groups[key] = []
        activity_groups[key].append(activity)
    
    # Process each group of activities
    for (project, task, issue, activity_type), group in activity_groups.items():
        current_activity = None
        
        for activity in sorted(group, key=lambda x: x['from_time']):
            from_time = get_datetime(activity['from_time'])
            to_time = get_datetime(activity['to_time'])
            
            # Validate time range
            if from_time.date() != get_datetime(date).date() or to_time.date() != get_datetime(date).date():
                print(f"Skipping activity outside date range: {from_time} - {to_time}")
                continue
                
            if not current_activity:
                current_activity = activity.copy()
                continue
            
            current_end = get_datetime(current_activity['to_time'])
            time_gap = (from_time - current_end).total_seconds()
            
            # If activities are close enough, merge them
            if time_gap <= 30:  # 5 minutes gap threshold
                current_activity['to_time'] = to_time
            else:
                # Add current activity to timesheet and start new one
                hours = frappe.utils.time_diff_in_hours(
                    get_datetime(current_activity['to_time']),
                    get_datetime(current_activity['from_time'])
                )
                description = get_activity_description(current_activity) 
                if hours > 0:
                    timesheet.append("time_logs", {
                        "activity_type": activity_type,
                        "from_time": current_activity['from_time'],
                        "to_time": current_activity['to_time'],
                        "hours": hours,
                        "project": project,
                        "task": task,
                        "issue": issue,
                        "billable": 1 if project else 0,
                        "description": description
                    })
                current_activity = activity.copy()
               
        # Add final activity from the group
        if current_activity:
            hours = frappe.utils.time_diff_in_hours(
                get_datetime(current_activity['to_time']),
                get_datetime(current_activity['from_time'])
            )
            
            if hours > 0:
                timesheet.append("time_logs", {
                    "activity_type": activity_type,
                    "from_time": current_activity['from_time'],
                    "to_time": current_activity['to_time'],
                    "hours": hours,
                    "project": project,
                    "task": task,
                    "issue": issue,
                    "billable": 1 if project else 0,
                    "description": description
                })
    
    # Sort time logs by start time
    if timesheet.time_logs:
        timesheet.time_logs.sort(key=lambda x: x.from_time)
        
        # Validate no overlaps in final timesheet
        for i in range(len(timesheet.time_logs) - 1):
            current = timesheet.time_logs[i]
            next_log = timesheet.time_logs[i + 1]
            if current.to_time > next_log.from_time:
                current.to_time = next_log.from_time
                current.hours = frappe.utils.time_diff_in_hours(current.to_time, current.from_time)
        
        print(f"Saving timesheet with {len(timesheet.time_logs)} entries")
        try:
            timesheet.save(ignore_permissions=True)
            print("Timesheet saved successfully")
        except Exception as e:
            print(f"ERROR saving timesheet: {str(e)}")
            raise
    else:
        print("No time logs to save, skipping timesheet creation")

def parse_duration(duration):
    """Parse duration string into seconds"""
    try:
        if not duration:
            return None
        hours, minutes, seconds = map(int, duration.split(':'))
        return hours * 3600 + minutes * 60 + seconds
    except:
        return None
    
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
                'active_hours_per_day',
                'active_hours_on_saturday',
                'email_alert_on_time_violation',
                'total_hours_per_day',
                'total_hours_on_saturday'
            )
    """, as_dict=True)

    if result:
        return {row["field"]: row["value"] for row in result}
    return {}

def create_working_hours_exceptions():
    from_date = add_days(today(), -1)
    to_date = add_days(today(), -1)


    active_users = frappe.db.sql("""
        SELECT employee_name, employee FROM `tabList of User`
    """, as_dict=True)

    filters = {
        "from_date": from_date,
        "to_date": to_date,
        "frequency": "Daily"
    }

    all_data = get_data(filters)
    data = all_data[0]

    config_defaults = get_defaults_productivity()
  
    total_hours_on_saturday = float(config_defaults.get("total_hours_on_saturday", 0))
    total_hours_per_day = float(config_defaults.get("total_hours_per_day", 0))

    day_name = datetime.strptime(from_date, "%Y-%m-%d").strftime("%A")

    for row in data:
        if not isinstance(row, dict) or not row:
            continue

        employee = row.get("emp_id")
        if not employee:
            continue

        if not any(emp["employee"] == employee for emp in active_users):
            continue
        
        productivity_score = float(row.get("productivity_score") or 0)
        total_hours = parse_hours(row.get("total_hours"))
        active_hours = parse_hours(row.get("active_hours"))
        
        
        if day_name == "Sunday":
            continue
        
        required_productivity_score = 100
        required_total_hours = total_hours_per_day if day_name != "Saturday" else total_hours_on_saturday
        
        leave = frappe.db.get_value(
            "Leave Application",
            {
                "employee": employee,
                "from_date": ["<=", from_date],
                "to_date": [">=", from_date],
                "status": "Approved"
            },
            ["name", "half_day"],
            as_dict=True
        )
        
        if leave:
            if leave.half_day: 
                if day_name == "Saturday":
                    continue
                required_productivity_score /= 2
                required_total_hours /= 2
            else:
                continue

        if total_hours >= required_total_hours or productivity_score >= required_productivity_score:
            continue

        try:
            emp_id = row.get("emp_id")
            employee_name = row.get("employee")
            starting_date = row.get("starting_date")
            ending_date = row.get("ending_date") or starting_date
            idle_hours = parse_hours(row.get("idle_hours"))
            average_active = parse_hours(row.get("average_active"))
            incoming_calls = float(row.get("incoming_calls") or 0)
            incoming_hours = parse_hours(row.get("incoming_hours"))
            outgoing_calls = float(row.get("outgoing_calls") or 0)
            outgoing_hours = parse_hours(row.get("outgoing_hours"))
            missed_calls = float(row.get("missed_calls") or 0)
            rejected_calls = float(row.get("rejected_calls") or 0)
            keyboard = float(row.get("keyboard") or 0)
            mouse = float(row.get("mouse") or 0)
            scroll = float(row.get("scroll") or 0)
            meetings = float(row.get("meetings") or 0)
            meetings_hours = parse_hours(row.get("meetings_hours"))

            doc = frappe.new_doc("Working Hours Exception")
            doc.employee = emp_id
            doc.employee_name = employee_name
            doc.starting_date = starting_date
            doc.ending_date = ending_date
            doc.productivity_score = productivity_score
            doc.total_hours = total_hours
            doc.active_hours = active_hours
            doc.idle_hours = idle_hours
            doc.average_active = average_active
            doc.incoming_calls = incoming_calls
            doc.incoming_hours = incoming_hours
            doc.outgoing_calls = outgoing_calls
            doc.outgoing_hours = outgoing_hours
            doc.missed_calls = missed_calls
            doc.rejected_calls = rejected_calls
            doc.keyboard = keyboard
            doc.mouse = mouse
            doc.scroll = scroll
            doc.meetings = meetings
            doc.meetings_hours = meetings_hours
            doc.email_alert_on_time_violation = cint(config_defaults.get("email_alert_on_time_violation", 0))

            doc.insert(ignore_permissions=True)
            frappe.msgprint(f"Inserted exception for {employee_name}")

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Working Hours Exception Insert Failed")
            frappe.msgprint(f"Failed to insert for {employee}: {str(e)}")

    frappe.db.commit()

def parse_hours(duration_str):
    try:
        if not duration_str:
            return 0
        hours, minutes = duration_str.split("h")
        return int(hours.strip()) + int(minutes.replace("m", "").strip()) / 60
    except Exception:
        return 0

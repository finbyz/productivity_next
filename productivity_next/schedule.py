import frappe
from frappe.utils import nowdate, get_datetime, format_time, format_duration
import frappe.utils
from frappe.utils.data import cint
from productivity_next.productivity_next.page.productify_consolidated_analysis.productify_consolidated_analysis import user_analysis_data
from datetime import timedelta

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
            "contact":("is",'set'),
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
            select from_time as start, to_time as end, 'application' as type
            from `tabApplication Usage log`
            where employee = '{employee}' and date = '{date}'
            """, as_dict=True)

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
                'to_time': app_entry['end']
            })
        PWS.save()
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
                ) AS caller
                from `tabEmployee Fincall`
                where employee = '{employee}' and date = '{date}'
                """, as_dict=True)
                # print('calls_data',len(calls_data))
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
                # print("employee",employee)
                # print("date",date)
                applications_data = frappe.db.sql(f"""
                select from_time as start, to_time as end, 'application' as type
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
                    'to_time': app_entry['end']
                })
            PWS.save()
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
                select from_time as start, to_time as end, 'application' as type
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
                    'to_time': app_entry['end']
                })
            PWS.save()
            # print(PWS.name)


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
    yeasterday = get_datetime() - timedelta(days=1)
    timesheets = frappe.get_all(
        "Timesheet",
        filters={"docstatus": 0, "is_created_by_productify": 1,"creation": (">", yeasterday)},
        fields=["name"],
    )

    for timesheet in timesheets:
        doc = frappe.get_doc("Timesheet", timesheet.name)
        doc.submit()
        frappe.db.set_value("Timesheet", doc.name, "docstatus", 1)
        frappe.db.set_value("Timesheet", doc.name, "status", "Submitted")


def submit_timesheet_created_by_productify():
    if not frappe.db.exists("Custom Field", {"fieldname": "is_created_by_productify"}):
        frappe.throw("Custom Field 'is_created_by_productify' not found")
    yeasterday = get_datetime() - timedelta(days=1)
    timesheets = frappe.get_all(
        "Timesheet",
        filters={"docstatus": 0, "is_created_by_productify": 1,"creation": (">", yeasterday)},
        fields=["name"],
    )
    for timesheet in timesheets:
        doc = frappe.get_doc("Timesheet", timesheet.name)
        doc.submit()
        frappe.db.set_value("Timesheet", doc.name, "docstatus", 1)
        frappe.db.set_value("Timesheet", doc.name, "status", "Submitted")


def delete_productify_error_logs():
    time_for_error_logs = 10

    date_for_error_logs = get_datetime() - timedelta(days=time_for_error_logs)

    frappe.db.sql("""
        DELETE FROM `tabProductify Error Log`
        WHERE error_datetime < %s
    """, (date_for_error_logs.strftime("%Y-%m-%d %H:%M:%S"),))


def delete_screenshots():
    time_for_screenshots = int(frappe.db.get_single_value("Productify Subscription", "keep_screen_shots_for_days")) or 60
    date_for_screenshots = get_datetime() - timedelta(days=time_for_screenshots)
    screenshots = frappe.get_all("Screen Screenshot Log", {"time": ("<", date_for_screenshots.strftime("%Y-%m-%d %H:%M:%S"))})
    for screenshot in screenshots:
        frappe.delete_doc("Screen Screenshot Log", screenshot.name)

def delete_application_logs():
    time_for_application_logs = int(frappe.db.get_single_value("Productify Subscription", "keep_application_logs_for_days")) or 60
    
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
        productify_subscription.token = data.get("token")
        productify_subscription.token_updated_on = nowdate()
        productify_subscription.flags.ignore_permissions = True
        productify_subscription.save()
        
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

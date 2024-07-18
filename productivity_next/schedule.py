import frappe
from frappe.utils import nowdate, get_datetime, format_datetime,add_to_date, today, date_diff

from datetime import timedelta
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
            ec_doc.save()

            # Update flag indicating that employee fincall is generated
            fincall_log.db_set("employee_fincall_generated", 1)

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
    date = add_to_date(today(), days=-1)
    if not frappe.db.exists('Productify Work Summary', {'date': date}):
        employees = frappe.get_all('Employee', filters={'status': 'Active','enable_productify_analysis':1}, fields=['name'])
        for i in employees:
            employee = i['name']
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
    date = today()
    if not frappe.db.exists('Productify Work Summary', {'date': date}):
        employees = frappe.get_all('Employee', filters={'status': 'Active','enable_productify_analysis':1}, fields=['name'])
        for i in employees:
            employee = i['name']
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
    else:
        pws_docs = frappe.get_all('Productify Work Summary', filters={'date': date})
        for PWS in pws_docs:
            PWS_DOC = frappe.get_doc('Productify Work Summary', PWS['name'])
            employee = PWS_DOC.employee
            if PWS_DOC.applications:
                last_activity = PWS_DOC.applications[-1].to_time
                def productify_work_summary(employee,date,last_activity):
                    print('employee',employee)
                    calls_data = frappe.db.sql(f"""
                    SELECT call_datetime as start, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end, 'call' as type,  COALESCE(
                        (SELECT first_name FROM `tabContact` WHERE name = COALESCE(contact, client, customer_no)),
                        COALESCE(contact, client, customer_no)
                    ) AS caller
                    from `tabEmployee Fincall`
                    where employee = '{employee}' and date = '{date}' and call_datetime >= '{last_activity}'
                    """, as_dict=True)
                    print('calls_data',len(calls_data))
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
                    select pwsa.from_time as start, pwsa.to_time as end, 'application' as type
                    from `tabProductify Work Summary` as pws
                    JOIN `tabProductify Work Summary Application` as pwsa ON pws.name = pwsa.parent
                    where pws.employee = '{employee}' and pws.date = '{date}'
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

                data = productify_work_summary(employee, date, last_activity)
                final_data = remove_overlapping(data)
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
                PWS = frappe.get_doc('Productify Work Summary', PWS['name'])
                for app_entry in combined_applications:
                    PWS.append('applications', {
                        'from_time': app_entry['start'],
                        'to_time': app_entry['end']
                    })
                PWS.save()
                print(PWS.name)

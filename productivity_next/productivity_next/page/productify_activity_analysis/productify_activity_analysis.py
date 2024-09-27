
from datetime import datetime,time,timedelta
import frappe
from frappe import utils
from frappe.utils import now
from frappe.utils import add_months,getdate
from collections import defaultdict
from frappe import _
import json
from productivity_next.api import calculate_total_working_hours


from dateutil.parser import parse

# Sidebar Activity Data code starts
@frappe.whitelist(allow_guest=True)
def get_activity_chart_data(user,start_date=None, end_date=None):
    if user == "Administrator":
        return {}
    # Fetch idle time logs
    idle_time_data = frappe.db.sql(f"""
        SELECT from_time as start_time, to_time as end_time
        FROM `tabEmployee Idle Time`
        WHERE date >= '{start_date}' AND date <= '{end_date}' AND employee = '{user}'
    """, as_dict=True)

    # Fetch fincall time logs
    fincall_time_data = frappe.db.sql(f"""
        SELECT call_datetime as start_time, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time
        FROM `tabEmployee Fincall`
        WHERE date >= '{start_date}' AND date <= '{end_date}' AND employee = '{user}' AND (calltype != 'Missed' AND calltype != 'Rejected')
    """, as_dict=True)

    # Fetch meeting time logs
    meeting_time_data = frappe.db.sql(f"""
        SELECT meeting_from as start_time, meeting_to as end_time
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE m.meeting_from >= '{start_date} 00:00:00' AND m.meeting_to <= '{end_date} 23:59:59' AND m.docstatus = 1 AND mcr.employee = '{user}'
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
    total_idle_time = round(total_idle_seconds) 

    total_call_data = frappe.db.sql(f"""
        SELECT 
            SUM(duration) AS total_duration
        FROM `tabEmployee Fincall`
        WHERE date >= '{start_date}' AND date <= '{end_date}' and employee = '{user}'
    """, as_dict=True)

    total_meeting_data = frappe.db.sql(f"""
        SELECT 
            SUM(TIME_TO_SEC(TIMEDIFF(meeting_to, meeting_from))) AS total_duration  
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE m.meeting_from >= '{start_date} 00:00:00' and m.meeting_to <= '{end_date} 23:59:59' and m.docstatus = 1 AND mcr.employee = '{user}' 
    """, as_dict=True)

    list_data = []
    meeting_total_data = frappe.db.sql(f"""
        SELECT m.meeting_from as start_time, m.meeting_to as end_time
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE m.meeting_from >= '{start_date} 00:00:00' and m.meeting_to <= '{end_date} 23:59:59' and m.docstatus = 1 and mcr.employee ='{user}' 
    """, as_dict=True)
    calls_total_data = frappe.db.sql(f"""
        SELECT call_datetime as start_time, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time
        FROM `tabEmployee Fincall`
        WHERE date >= '{start_date}' and date <= '{end_date}' and employee = '{user}' and (calltype != 'Missed' and calltype != 'Rejected')
    """, as_dict=True)
    application_total_data = frappe.db.sql(f"""
        SELECT from_time as start_time, to_time as end_time
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' and date <= '{end_date}' and employee = '{user}'
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
    total_application_hours = frappe.db.sql(f"""
        select sum(duration) as total_duration
        from `tabApplication Usage log`
        where date >= '{start_date}' and date <= '{end_date}' and employee = '{user}'
        """, as_dict=True)

    total_idle_hours = frappe.db.sql(f"""
        select sum(duration) as total_duration
        from `tabEmployee Idle Time`
        where date >= '{start_date}' and date <= '{end_date}' and employee = '{user}'
        """, as_dict=True)
    total_application_duration = total_application_hours[0].total_duration if total_application_hours and total_application_hours[0].total_duration is not None else 0
    total_idle_duration = total_idle_hours[0].total_duration if total_idle_hours and total_idle_hours[0].total_duration is not None else 0
    total_system_hours = total_application_duration - total_idle_duration
    toal_hours_to_show = max(32400, total_time)
    total_active_hours = total_time - total_idle_time
    weekday_hours = frappe.db.get_single_value('Productify Subscription', 'working_hours_per_day')
    saturday_hours = frappe.db.get_single_value('Productify Subscription', 'working_hours_on_saturday')
    return {
        "total_time": total_time or 0,
        "total_system_hours": total_system_hours or 0,
        "total_idle_time": total_idle_time or 0,
        "total_call_data": total_call_data[0].total_duration or 0,
        "total_meeting_data": total_meeting_data[0].total_duration or 0,
        "total_active_hours": total_active_hours or 0,
        "total_inactive_hours": (toal_hours_to_show or 0) - ((total_active_hours or 0) + (total_idle_time or 0)),
        "total_hours": toal_hours_to_show,
    }
# Sidebar Activity Code Ends

# Work Intensity Code Starts
@frappe.whitelist()
def work_intensity(user=None, start_date=None, end_date=None):
    if not user:
        return []
    
    intensity_data = frappe.db.sql(f"""
        SELECT 
            HOUR(time) as hour, 
            DAYNAME(time) as day_of_week,
            SUM(key_strokes) as total_keystrokes, 
            SUM(mouse_clicks) as total_mouse_clicks,
            SUM(mouse_scrolls) as total_mouse_scrolls
        FROM `tabWork Intensity`
        WHERE employee = '{user}'
            AND time >= '{start_date} 00:00:00'      
            AND time <= '{end_date} 23:59:59' 
            AND HOUR(time) BETWEEN 7 AND 23
        GROUP BY hour, day_of_week
    """, as_dict=True)

    # Define the expected days list
    days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

    data = []

    # Fill in the intensity data
    for entry in intensity_data:
        hour = entry['hour']
        keystrokes = entry['total_keystrokes'] or 0
        mouse_clicks = entry['total_mouse_clicks'] or 0
        mouse_scrolls = entry['total_mouse_scrolls'] or 0
        value = keystrokes + mouse_clicks + mouse_scrolls
        # Ensure day_of_week is converted to abbreviated form
        day_of_week = entry['day_of_week'][:3]  # Assuming day_of_week is returned as full name
        data.append([hour, value, day_of_week])

    # Ensure all hours from 7 to 23 are included for each day of the week
    for hour in range(7, 24):
        for day in days:
            if not any(d[0] == hour and d[2] == day for d in data):
                data.append([hour, 0, day])

    # Sort data by day and then hour within each day
    data.sort(key=lambda x: (days.index(x[2]), x[0]))

    return data
# Work Intensity Code Ends

# Overall Performance Code Starts
@frappe.whitelist()
def overall_performance(employee=None, start_date=None, end_date=None):
    if not employee:
        return {
            "labels": [],
            "values": []
        }
    calls = frappe.db.sql(f"""
        SELECT name AS parent, 
            call_datetime AS call_start, ADDTIME(call_datetime, SEC_TO_TIME(duration)) AS call_end,
            employee, date,COALESCE(contact, client, customer_no) as caller, calltype
        FROM `tabEmployee Fincall`
        WHERE date >= '{start_date}' and date <= '{end_date}' and employee ='{employee}'
        ORDER BY date
    """, as_dict=True)

    meetings = frappe.db.sql(f"""
         SELECT m.name AS parent, 
            m.meeting_from AS meeting_start, m.meeting_to AS meeting_end, m.party as client, m.internal_meeting AS internal,DATE(m.meeting_from) as date,
            mcr.employee, mcr.employee_name, m.organization as organization, m.party_type as party_type, m.meeting_arranged_by as meeting_arranged_by
        FROM `tabMeeting` AS m
        JOIN `tabMeeting Company Representative` AS mcr ON mcr.parent = m.name
        WHERE m.meeting_from >= '{start_date} 00:00:00' and m.meeting_to <= '{end_date} 23:59:59' and m.docstatus = 1 and mcr.employee = '{employee}'
        ORDER BY date(m.meeting_from)
    """, as_dict=True)

    idle = frappe.db.sql(f"""
        SELECT name AS parent, 
            from_time AS idle_start, to_time AS idle_end,
            employee, date(from_time) as date
        FROM `tabEmployee Idle Time`
        WHERE date >= '{start_date}' and date <= '{end_date}' and employee = '{employee}'
        ORDER BY DATE(from_time)
    """, as_dict=True)

    applications = frappe.db.sql(f"""
        SELECT dwsp.name AS parent, 
            a.from_time AS application_start, a.to_time AS application_end,
            dwsp.employee, dwsp.date
        FROM `tabProductify Work Summary` AS dwsp
        JOIN `tabProductify Work Summary Application` AS a ON a.parent = dwsp.name
        WHERE dwsp.date between '{start_date}' and '{end_date}' and dwsp.employee = '{employee}'
        ORDER BY dwsp.date
    """, as_dict=True)

    base_data = []
    for app in applications:
        base_data.append([
            "Application",
            app['date'],
            app['application_start'],
            app['application_end'],
        ])
    
    for call in calls:
        base_data.append([
            "Call",
            call['date'],
            call['call_start'],
            call['call_end'],
            call['caller'],
            call['calltype']
        ])

    for meeting in meetings:
        if meeting['internal']:
            base_data.append([
                "Internal Meeting",
                meeting['date'],
                meeting['meeting_start'],
                meeting['meeting_end'],
                meeting['meeting_arranged_by'],
                meeting['client']
            ])
        else:
            base_data.append([
                "External Meeting",
                meeting['date'],
                meeting['meeting_start'],
                meeting['meeting_end'],
                meeting['internal'],
                meeting['organization'],
                meeting['party_type'],
                meeting['meeting_arranged_by']
            ])
    for i in idle:
        base_data.append([
            "Idle",
            i['date'],
            i['idle_start'],
            i['idle_end'],
        ])
    base_data = sorted(base_data, key=lambda x: x[2])
    data = list(set([item[1] for item in base_data]))

    return{
        "base_dimensions":['Activity', 'Employee', 'Start Time', 'End Time'],
        "dimensions":['Employee', 'Employee Name'],
        "base_data":base_data,
        "data":data
    }
# Overall Performance Code Ends

@frappe.whitelist()
def overall_performance_timely(employee=None, date=None, hour=None):
    if not employee:
        return {
            "labels": [],
            "values": []
        }
    
    # Convert hour to integer
    hour = int(hour)

    # Calculate the start and end of the specified hour
    hour_start = f"{hour:02d}:00:00"
    hour_end = f"{(hour + 1) % 24:02d}:00:00"

    applications = frappe.db.sql(f"""
    SELECT 
        application_name AS name, 
        from_time AS application_start, 
        to_time AS application_end, 
        date, 
        LEFT(application_title, 80) AS application_title, 
        LEFT(url, 80) AS url, 
        project, 
        issue, 
        task,
        process_name
    FROM `tabApplication Usage log`
    WHERE date = '{date}' 
      AND employee = '{employee}' 
      AND application_name != '' 
      AND application_name IS NOT NULL 
      AND (
          (HOUR(from_time) = {hour}) OR
          (HOUR(from_time) < {hour} AND HOUR(to_time) >= {hour})
      )
    """, as_dict=True)

    idle = frappe.db.sql(f"""
        SELECT from_time AS idle_start, to_time AS idle_end, date
        FROM `tabEmployee Idle Time`
        WHERE date = '{date}' AND employee = '{employee}' 
        AND (
            (HOUR(from_time) = {hour}) OR
            (HOUR(from_time) < {hour} AND HOUR(to_time) >= {hour})
        )
    """, as_dict=True)

    calls = frappe.db.sql(f"""
        SELECT name AS parent, 
            call_datetime AS call_start, ADDTIME(call_datetime, SEC_TO_TIME(duration)) AS call_end,
            employee, date, COALESCE(contact, client, customer_no) as caller, calltype, link_to as link_to, link_name as link_name
        FROM `tabEmployee Fincall`
        WHERE date = '{date}' AND employee ='{employee}' 
        AND (
            (HOUR(call_datetime) = {hour}) OR
            (HOUR(call_datetime) < {hour} AND HOUR(ADDTIME(call_datetime, SEC_TO_TIME(duration))) >= {hour})
        )
        ORDER BY date
    """, as_dict=True)


    meetings = frappe.db.sql(f"""
        SELECT m.name AS parent, 
            m.meeting_from AS meeting_start, m.meeting_to AS meeting_end, m.party as client, m.internal_meeting AS internal,
            DATE(m.meeting_from) as date, mcr.employee, mcr.employee_name, m.organization as organization, m.discussion as description,
            m.party_type as party_type, m.meeting_arranged_by as meeting_arranged_by
        FROM `tabMeeting` AS m
        JOIN `tabMeeting Company Representative` AS mcr ON mcr.parent = m.name
        WHERE DATE(m.meeting_from) = '{date}' AND mcr.employee = '{employee}' AND m.docstatus = 1
        AND (
            (HOUR(m.meeting_from) = {hour}) OR
            (HOUR(m.meeting_from) < {hour} AND HOUR(m.meeting_to) >= {hour})
        )
        ORDER BY m.meeting_from
    """, as_dict=True)

    def split_activity(activity_type, start, end, *args):
        start_time = datetime.strptime(str(start), "%Y-%m-%d %H:%M:%S")
        end_time = datetime.strptime(str(end), "%Y-%m-%d %H:%M:%S")
        
        hour_start_time = start_time.replace(hour=hour, minute=0, second=0)
        hour_end_time = hour_start_time + timedelta(hours=1)
        
        if start_time < hour_start_time:
            start_time = hour_start_time
        if end_time > hour_end_time:
            end_time = hour_end_time
        
        return [activity_type, start_time.date(), start_time, end_time] + list(args)

    base_data = []
    for app in applications:
        activity_type = "Browser" if app['process_name'] in ["chrome.exe", "firefox.exe", "msedge.exe", "opera.exe", "iexplore.exe", "brave.exe", "safari.exe", "vivaldi.exe", "chromium.exe", "microsoftedge.exe"] else "Application"
        base_data.append(split_activity(
            activity_type,
            app['application_start'],
            app['application_end'],
            app['application_title'].split(" - ")[0] if app['application_title'] else None,
            app['url'] if app['url'] else None,
            app['project'] if app['project'] else None,
            app['issue'] if app['issue'] else None,
            app['task'] if app['task'] else None,
            app['name']
        ))

    for app in idle:
        base_data.append(split_activity(
            "Idle",
            app['idle_start'],
            app['idle_end']
        ))

    for call in calls:
        base_data.append(split_activity(
            "Call",
            call['call_start'],
            call['call_end'],
            call['caller'],
            call['calltype'],
            call['link_to'],
            call['link_name']
        ))

    for meeting in meetings:
        if meeting['internal']:
            base_data.append(split_activity(
                "Internal Meeting",
                meeting['meeting_start'],
                meeting['meeting_end'],
                meeting['meeting_arranged_by'],
                meeting['description'],
                meeting['client']
            ))
        else:
            base_data.append(split_activity(
                "External Meeting",
                meeting['meeting_start'],
                meeting['meeting_end'],
                meeting['meeting_arranged_by'],
                meeting['description'],
                meeting['internal'],
                meeting['client'],
                meeting['party_type'],
            ))

    base_data = sorted(base_data, key=lambda x: x[2])
    data = list(set([item[1] for item in base_data]))

    return {
        "base_dimensions": ['Activity', 'Employee', 'Start Time', 'End Time'],
        "dimensions": ['Employee', 'Employee Name'],
        "base_data": base_data,
        "data": data
    }

# Applications Used Code Starts
@frappe.whitelist(allow_guest=True)
def application_usage_time(user=None, start_date=None, end_date=None):
    if not user or user is None:
        return {
            "labels": [],
            "values": []
        }
    
    application_name = frappe.db.sql(f"""
        SELECT 
            LEFT(application_name, 25) AS application_name, 
            SUM(duration) AS total_duration
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' AND date <= '{end_date}' AND employee = '{user}'
        GROUP BY LEFT(application_name, 25)
        ORDER BY total_duration DESC
        LIMIT 10
    """, as_dict=True)

    data = []
    for app in application_name:
        # Convert total_duration to hours and minutes
        hours = int(app['total_duration'] // 3600)
        minutes = int((app['total_duration'] % 3600) / 60)
        
        # Calculate total value in hours with two decimal places
        value = round(hours + (minutes / 60), 2)
        
        data.append({
            "name": app['application_name'],
            "value": value,
            "hours": hours,
            "minutes": minutes
        })

    return data
# Applications Used Code Ends

# Web Browsing Time code starts
@frappe.whitelist(allow_guest=True)
def web_browsing_time(user = None,start_date=None,end_date=None):
    if not user or user == None:
        return {
            "labels": [],
            "values": []
        }
    domain_data = frappe.db.sql(f"""
        SELECT domain, round(SUM(duration)/3600,2) as total_duration
        FROM `tabApplication Usage log`
        Where date >= '{start_date}' and date <= '{end_date}' and employee = '{user}' and domain != '' and domain is not null
        GROUP BY domain
        ORDER BY total_duration DESC
        LIMIT 10
    """, as_dict=True)

    data = []

    for app in domain_data:
        data.append({
            "name": app['domain'],
            "value": app['total_duration'],
        })

    
    return data
# Web Browsing Time code ends

# Top Phone Calls Code Starts
@frappe.whitelist()
def top_phone_calls(user=None, start_date=None, end_date=None):
    if not user:
        return {
            "caller_details": [],
            "company_details": []
        }

    caller_name = frappe.db.sql(f"""
    SELECT 
    CASE 
        WHEN link_name IS NOT NULL AND link_name != '' THEN link_name
        ELSE 'Others'
    END AS customname,
    COALESCE(
        (SELECT first_name FROM `tabContact` WHERE name = COALESCE(ef.contact, ef.client, ef.customer_no)),
        COALESCE(ef.contact, ef.client, ef.customer_no)
    ) AS identifier,
    ef.link_to AS ref_doctype, 
    ROUND(SUM(ef.duration)/60, 2) AS total_duration,
    COUNT(*) AS call_count
    FROM `tabEmployee Fincall` ef
    WHERE ef.date >= '{start_date}' 
        AND ef.date <= '{end_date}'
        AND ef.employee = '{user}' 
    GROUP BY COALESCE(ef.contact, ef.client, ef.customer_no), ef.link_name
    HAVING SUM(ef.duration) > 60
    ORDER BY total_duration DESC
""", as_dict=True)

    caller_details = []
    company_details = []

    others_duration = 0
    main_categories = {'Customer', 'Supplier', 'Lead', 'Company'}
    for row in caller_name:
        ref_doctype = row['ref_doctype']
        total_duration = row['total_duration']

        if ref_doctype in main_categories:
            found = False
            for detail in company_details:
                if detail['name'] == ref_doctype:
                    detail['value'] += total_duration
                    found = True
                    break
            if not found:
                if ref_doctype == 'Customer':
                    company_details.append({
                        'name': ref_doctype,
                        'value': total_duration,
                        "selected": True
                    })
                else:
                    company_details.append({
                        'name': ref_doctype,
                        'value': total_duration
                    })
        else:
            others_duration += total_duration

    others_duration = round(others_duration, 2)

    if others_duration > 0:
        company_details.append({
            'name': 'Others',
            'value': others_duration
        })
    count = 0
    customNames = []
    for app in caller_name:
        caller_details.append({
            "name": app['identifier'],
            "value": app['total_duration'],
            "customIndex": count
        })
        customNames.append(app['customname'])
        count += 1

    return {
        "caller_details": caller_details,
        "company_details": company_details,
        "customNames": customNames
    }
# Top Phone Calls Code Ends

# Type Of Calls Code Starts
@frappe.whitelist()
def type_of_calls(user = None,start_date=None,end_date=None):
    if not user or user == None:
        return {
            "labels": [],
            "values": []
        }
    internal_fincall_data = frappe.db.sql(f"""
        SELECT 
            COUNT(*) AS fincall_count,
            round(SUM(duration)/60,2) as total_duration
        FROM `tabEmployee Fincall`
        Where date >= '{start_date}' and date <= '{end_date}' and employee = '{user}' and (link_to = 'Company' and link_to is not null)
    """, as_dict=True)

    external_fincall_data = frappe.db.sql(f"""
        SELECT 
            COUNT(*) AS fincall_count,
            round(SUM(duration)/60,2) as total_duration
        FROM `tabEmployee Fincall`
        Where date >= '{start_date}' and date <= '{end_date}' and employee = '{user}' and (link_to != 'Company' or link_to is null)
    """, as_dict=True)
    data = []
    data.append({
        "name": "Internal",
        "value": internal_fincall_data[0]['total_duration'],
    })
    data.append({
        "name": "External",
        "value": external_fincall_data[0]['total_duration'],
    })  
    return data
# Type Of Calls Code Ends

# URL DATA AND SIDEBAR DATA CODE STARTS
@frappe.whitelist(allow_guest=True)
def fetch_url_data(user,start_date=None, end_date=None):
    version_conditions_str = version_conditions(user,start_date,end_date)
    ignore_doctype = ['File',"Communication","Fincall Log","Custom Field","DocType","Web Page","Attendance"]
    ignore_doctype_str = ','.join(f"'{doc}'" for doc in ignore_doctype)
    if ignore_doctype_str:
        ignore_condition = f"AND ref_doctype NOT IN ({ignore_doctype_str})"
    else:
        ignore_condition = ""

    fincall_data = frappe.db.sql(f"""
        SELECT 
            calltype,
            COUNT(*) AS fincall_count,
            COALESCE(SUM(duration), 0) AS total_duration
        FROM `tabEmployee Fincall`
        WHERE date >= '{start_date}' AND date <= '{end_date}' and employee = '{user}' and (link_to != 'Company' or link_to is null)
        GROUP BY calltype
    """, as_dict=True)

    # Initialize counts and total durations
    incoming_fincall_count = outgoing_fincall_count = missed_fincall_count = rejected_fincall_count = 0
    total_incoming_duration = total_outgoing_duration = 0

    # Extracting data for each call type in a single pass
    for item in fincall_data:
        calltype = item['calltype']
        count = item['fincall_count']
        duration = item['total_duration']
        
        if calltype == 'Incoming':
            incoming_fincall_count = count
            total_incoming_duration = duration
        elif calltype == 'Outgoing':
            outgoing_fincall_count = count
            total_outgoing_duration = duration
        elif calltype == 'Missed':
            missed_fincall_count = count
        elif calltype == 'Rejected':
            rejected_fincall_count = count

    internal_fincall_data = frappe.db.sql(f"""
        SELECT 
            calltype,
            COUNT(*) AS fincall_count,
            COALESCE(SUM(duration), 0) AS total_duration
        FROM `tabEmployee Fincall`
        WHERE date >= '{start_date}' AND date <= '{end_date}' and employee = '{user}' and link_to = 'Company' and link_to is not null
        GROUP BY calltype
    """, as_dict=True)

    # Initialize counts and total durations
    internal_incoming_fincall_count = internal_outgoing_fincall_count = 0
    internal_missed_fincall_count = internal_rejected_fincall_count = 0
    internal_total_incoming_duration = internal_total_outgoing_duration = 0

    # Extracting data for each call type in a single pass
    for item in internal_fincall_data:
        calltype = item['calltype']
        count = item['fincall_count']
        duration = item['total_duration']
        
        if calltype == 'Incoming':
            internal_incoming_fincall_count = count
            internal_total_incoming_duration = duration
        elif calltype == 'Outgoing':
            internal_outgoing_fincall_count = count
            internal_total_outgoing_duration = duration
        elif calltype == 'Missed':
            internal_missed_fincall_count = count
        elif calltype == 'Rejected':
            internal_rejected_fincall_count = count                             

    application_usage_days = frappe.db.sql(f"""
        SELECT DISTINCT DATE(`date`) AS date 
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' AND date <= '{end_date}' and employee = '{user}';
    """, as_dict=True, pluck='date')

    # Fetch meeting usage days
    meeting_usage_days = frappe.db.sql(f"""
        SELECT DISTINCT DATE(m.meeting_from) AS date 
        FROM `tabMeeting` AS m 
        JOIN `tabMeeting Company Representative` AS mcr 
        ON m.name = mcr.parent 
        WHERE m.meeting_from >= '{start_date} 00:00:00' AND m.meeting_to <= '{end_date} 23:59:59' AND m.docstatus = 1 AND mcr.employee = '{user}'
    """, as_dict=True, pluck='date')

    total_days = len(set(application_usage_days + meeting_usage_days)) or 1

    meetings_external_employee = frappe.db.sql(f"""
    SELECT 
        SUM(CASE 
                WHEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from)) > 0 THEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))
                ELSE 0 
            END) AS total_meeting_duration,
        COUNT(DISTINCT m.name) as meeting_count
    FROM `tabMeeting` as m
    JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent WHERE m.meeting_from >= '{start_date} 00:00:00' 
    AND m.meeting_to <= '{end_date} 23:59:59' AND m.docstatus = 1 AND mcr.employee = '{user}' and m.internal_meeting = 0
    GROUP BY mcr.employee
    """, as_dict=True)

    meetings_internal_employee = frappe.db.sql(f"""
    SELECT 
        SUM(CASE 
                WHEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from)) > 0 THEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))
                ELSE 0 
            END) AS total_meeting_duration,
        COUNT(DISTINCT m.name) as meeting_count
    FROM `tabMeeting` as m
    JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent 
    WHERE m.meeting_from >= '{start_date} 00:00:00' AND m.meeting_to <= '{end_date} 23:59:59' AND m.docstatus = 1 AND mcr.employee = '{user}' and m.internal_meeting = 1
    GROUP BY mcr.employee
    """, as_dict=True)

    # Documents Accessed
    total_unique_doc = frappe.db.sql(f"""
    SELECT COUNT(DISTINCT docname) AS activity_count
    FROM `tabVersion`
    {version_conditions_str}
    {ignore_condition}
    """, as_dict=True)

    # Application Usage Log Count, Top 10 Doc's Used Cards
    total_counts = frappe.db.sql(f"""
        SELECT
            (SELECT COUNT(DISTINCT application_name) FROM `tabApplication Usage log` WHERE date >= '{start_date}' AND date <= '{end_date}' and employee = '{user}')  AS application_usage,
            (SELECT COUNT(*) FROM `tabVersion` {version_conditions_str} {ignore_condition})  AS version_count
        """, as_dict=1)[0]

    domain_data = frappe.db.sql(f"""
        SELECT domain, SUM(duration) as total_duration, application_name,count(domain) as count
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' AND date <= '{end_date}' and employee = '{user}' and domain != '' and domain is not null
        GROUP BY domain
        ORDER BY total_duration DESC
        LIMIT 10
        """,as_dict=True)
    process_id_names = {"chrome.exe":"Google Chrome","firefox.exe":"Mozilla Firefox","msedge.exe":"Microsoft Edge","opera.exe":"Opera","iexplore.exe":"Internet Explorer","brave.exe":"Brave","safari.exe":"Safari","vivaldi.exe":"Vivaldi","chromium.exe":"Chromium","microsoftedge.exe":"Microsoft Edge"}
    result_list = []
    for i in domain_data:
        if i["application_name"]:
            application_name = process_id_names.get(i["application_name"].lower())
            if application_name:
                app_name = application_name
            else:
                app_name = (i["application_name"]).lower().split(".exe")[0].capitalize()
        else:
            app_name = "Unknown"    
        result_list.append({
            "domain": i['domain'],
            "total_duration": i['total_duration'],
            "application_name": app_name,
            "count": i['count'],
        })
    # Retrieve working hours per day and on Saturday from the database
    weekday_hours = frappe.db.get_single_value('Productify Subscription', 'working_hours_per_day')
    saturday_hours = frappe.db.get_single_value('Productify Subscription', 'working_hours_on_saturday')

    hours_per_weekday = float(weekday_hours) if weekday_hours else 7.5
    hours_on_saturday = float(saturday_hours) if saturday_hours else 2.5

    # Calculate total working hours
    score = calculate_total_working_hours(
        user,
        start_date,
        end_date,
        hours_per_weekday,
        hours_on_saturday
    )

    return {
        "application_usage": total_counts['application_usage'],
        "version_count": total_counts['version_count'],
        "incoming_fincall_count": incoming_fincall_count,
        "outgoing_fincall_count": outgoing_fincall_count,
        "missed_fincall_count": missed_fincall_count,
        "rejected_fincall_count": rejected_fincall_count,
        "total_incoming_duration": total_incoming_duration,
        "total_outgoing_duration": total_outgoing_duration,
        "internal_incoming_fincall_count": internal_incoming_fincall_count,
        "internal_outgoing_fincall_count": internal_outgoing_fincall_count,
        "internal_missed_fincall_count": internal_missed_fincall_count,
        "internal_rejected_fincall_count": internal_rejected_fincall_count,
        "internal_total_incoming_duration": internal_total_incoming_duration,
        "internal_total_outgoing_duration": internal_total_outgoing_duration,
        "total_days": total_days,
        "total_unique_doc": total_unique_doc[0]['activity_count'] if total_unique_doc else 0,
        "total_time_on_calls": fincall_data[0]['total_duration'] if fincall_data else 0,
        "total_meeting_duration_internal": meetings_internal_employee[0].total_meeting_duration if meetings_internal_employee else 0,
        "total_meeting_count_internal": meetings_internal_employee[0].meeting_count if meetings_internal_employee else 0,
        "total_meeting_duration_external": meetings_external_employee[0].total_meeting_duration if meetings_external_employee else 0,
        "total_meeting_count_external": meetings_external_employee[0].meeting_count if meetings_external_employee else 0,
        "url_full_data": result_list[:10],
        "score": score
    }

@frappe.whitelist()
def get_url_brief_data(url_data,user,start_date=None, end_date=None):
    data_query = frappe.db.sql(f"""
        SELECT url, SUM(duration) AS duration, COUNT(url) as count, application_title
        FROM `tabApplication Usage log` 
        WHERE date >= '{start_date}' AND date <= '{end_date}' and employee = '{user}' and domain = '{url_data}'
        GROUP BY url
        ORDER BY SUM(duration) DESC
        """, as_dict=True)
    return {
        "data":data_query
    }
# URL DATA AND SIDEBAR DATA CODE ENDS


# Hourly Calls Analysis (In Minutes) Code Starts
@frappe.whitelist()
def hourly_calls_analysis(user, start_date=None, end_date=None):
    # SQL query to group by contact, client, or customer_no
    data = frappe.db.sql(f"""
        select sum(duration) as total_count, calltype, hour(call_datetime) as hour
        FROM `tabEmployee Fincall`
        WHERE date >= '{start_date}' AND date <= '{end_date}' and employee = '{user}' and (calltype = 'Incoming' or calltype = 'Outgoing')
        group by HOUR(call_datetime), calltype
        """, as_dict=1)
    
    aggregated_data = defaultdict(lambda: {'incoming_count': 0, 'outgoing_count': 0})
    
    # Step 2: Aggregate the total_count for each hour based on calltype
    for record in data:
        hour = record['hour']
        if record['calltype'] == 'Incoming':
            aggregated_data[hour]['incoming_count'] += record['total_count']
        elif record['calltype'] == 'Outgoing':
            aggregated_data[hour]['outgoing_count'] += record['total_count']
    
    # Step 3: Convert the aggregated data back to a list of dictionaries
    aggregated_list = [
        {'hour': hour, 'incoming_count': counts['incoming_count'], 'outgoing_count': counts['outgoing_count']}
        for hour, counts in aggregated_data.items()
    ]
    
    # Prepare data for line chart
    return {
        "labels": [str(i["hour"])+":00" for i in aggregated_list],
        "datasets": [
            {
                "name": "Incoming",
                "values": [round(i["incoming_count"] / 60, 2) for i in aggregated_list]
            },
            {
                "name": "Outgoing",
                "values": [round(i["outgoing_count"] / 60, 2) for i in aggregated_list]
            }
        ],
        "legend_names": ["Incoming", "Outgoing"],  
    }
# Hourly Calls Analysis (In Minutes) Code Ends

# Top 7 Document Analysis(Changes Per Doctype) code Starts
@frappe.whitelist()
def top_document_analysis(user, start_date=None, end_date=None):
    now = frappe.utils.now_datetime()
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d')
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d')
    
    if end_date is None:
        end_date = now.strftime('%Y-%m-%d') 
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d') 
    
    version_conditions_str = version_conditions(user, start_date, end_date)
    ignore_doctype = ['File', "Communication", "Fincall Log", "Custom Field", "DocType", "Web Page", "Attendance"]

    ignore_doctype_str = ','.join(f"'{doc}'" for doc in ignore_doctype)
    ignore_condition = f"AND ref_doctype NOT IN ({ignore_doctype_str})" if ignore_doctype_str else ""
    
    data = frappe.db.sql(f"""
        SELECT COUNT(DISTINCT docname) AS activity_count, ref_doctype
        FROM `tabVersion`
        {version_conditions_str}
        {ignore_condition}
        GROUP BY ref_doctype
        ORDER BY activity_count DESC 
        LIMIT 7
    """, as_dict=1)
    
    chart_data = []
    for i in data:
        chart_data.append([i['activity_count'],i['ref_doctype']])

    return chart_data
# Top 7 Document Analysis(Changes Per Doctype) code Ends

# User Activity Images Code Starts
@frappe.whitelist()
def user_activity_images(user, start_date=None, end_date=None, offset=0):
    data = frappe.get_all("Screen Screenshot Log", filters={"employee": user,"time": ["BETWEEN", [parse(start_date, dayfirst=True), parse(end_date, dayfirst=True)]]}, order_by="time desc", group_by="time", fields=["screenshot", "time","active_app"])
    for i in data:
        i["time_"] = frappe.format(i["time"], "Datetime")
    return data
# User Activity Images Code Ends

# Conditions to be applied to get data from versions table code starts 
@frappe.whitelist() 
def version_conditions(user,start_date=None, end_date=None):
    if user != "Administrator":
        email = frappe.db.get_value("Employee", user, "company_email")
        condition = f"WHERE modified_by = '{email}' and creation >= '{start_date} 00:00:00' AND creation <= '{end_date} 23:59:59'"
    else:
        condition = f"WHERE creation >= '{start_date} 00:00:00' AND creation <= '{end_date} 23:59:59'"

    return condition
# Conditions to be applied to get data from versions table code ends


@frappe.whitelist()
def get_project_enabled():
    # Load the document while ignoring permissions
    doc = frappe.get_doc('Productify Subscription', None, ignore_permissions=True)
    project_value = doc.project
    return project_value

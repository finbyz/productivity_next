
import frappe
from datetime import datetime,timedelta
from frappe.utils import now
from collections import defaultdict
from frappe.utils import now_datetime
from productivity_next.api import calculate_total_working_hours

# Convert start date from 2024-07-17 to 2024-07-17 00:00:00 and end date from 2024-07-17 to 2024-07-17 23:59:59 code starts
def set_dates(start_date=None, end_date=None):
    """
    Determine start and end dates for a range, formatted with specific time stamps.
    Args:
    - start_date (str, optional): Start date in 'YYYY-MM-DD' format. Defaults to 365 days ago.
    - end_date (str, optional): End date in 'YYYY-MM-DD' format. Defaults to today.

    Returns:
    - tuple: A tuple containing formatted start and end dates as strings.
    """
    now = frappe.utils.now_datetime()
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00')
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d 00:00:00')
    
    if end_date is None:
        end_date = now.strftime('%Y-%m-%d 23:59:59')
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d 23:59:59')

    return start_date, end_date
# Convert start date from 2024-07-17 to 2024-07-17 00:00:00 and end date from 2024-07-17 to 2024-07-17 23:59:59 code ends

@frappe.whitelist()
def get_employees():
    employees = frappe.get_list("Employee", filters={"status": "Active"}, fields=["name", "employee_name"])
    employee_analysis = frappe.get_all('List of User', fields=['employee', 'employee_name'])
    all_analysed_employees = []
    for employee in employees:
        if employee['name'] in [emp['employee'] for emp in employee_analysis]:
            all_analysed_employees.append(employee)
    employees = all_analysed_employees

    if not employees:
        frappe.throw("No data found for the selected date.")
    return employees

@frappe.whitelist()
def get_employees_version():
    employees = frappe.get_list("Employee", filters={"status": "Active"}, fields=["user_id","name"])
    employee_analysis = frappe.get_all('List of User', fields=['employee', 'employee_name'])
    all_analysed_employees = []
    for employee in employees:
        if employee['name'] in [emp['employee'] for emp in employee_analysis]:
            all_analysed_employees.append({"user_id":employee['user_id']})
    employees = all_analysed_employees
    if not employees:
        frappe.throw("No data found for the selected date.")
    return employees

@frappe.whitelist()
def get_employees_overall_performance(end_date):
    employees = frappe.get_list("Productify Work Summary", filters={"date": end_date}, fields=["employee","employee_name"])
    if not employees:
        frappe.throw("No data found for the selected date.")
    return employees

# Conditions to be applied to get data from versions table code starts
@frappe.whitelist() 
def version_conditions(start_date=None, end_date=None):
    start_date, end_date = set_dates(start_date, end_date)
    condition = f"AND creation >= '{start_date}' AND creation <= '{end_date}'"
    return condition
# Conditions to be applied to get data from versions table code ends

# Document Analysis (Numbers Of Document Modified) Code Starts
@frappe.whitelist()
def document_analysis_chart(start_date=None, end_date=None):
    employees = get_employees_version()
    if not employees:
        return {}
    version_conditions_str = version_conditions(start_date,end_date)
    ignore_doctype = ['File',"Communication","Fincall Log","Custom Field","DocType","Web Page","Attendance"]
    ignore_doctype_str = ','.join(f"'{doc}'" for doc in ignore_doctype)

    # Check if the list is not empty to add a condition to the query
    if ignore_doctype_str:
        ignore_condition = f"AND ref_doctype NOT IN ({ignore_doctype_str})"
    else:
        ignore_condition = ""
    # Check if the list is not empty to add a condition to the query
    if ignore_doctype_str:
        ignore_condition = f"AND ref_doctype NOT IN ({ignore_doctype_str})"
    else:
        ignore_condition = ""
    start_date, end_date = set_dates(start_date, end_date)

    documents_modified = frappe.db.sql(f"""
            SELECT COUNT(DISTINCT docname) AS activity_count,ref_doctype
            FROM `tabVersion`
            WHERE modified_by IN ({','.join(f"'{employee['user_id']}'" for employee in employees)})
            {version_conditions_str}
            {ignore_condition} 
            GROUP BY ref_doctype
            ORDER BY activity_count DESC
        """, as_dict=1)
        
    return {
        "labels": [document["ref_doctype"] for document in documents_modified],
        "datasets": [{"values": [(document["activity_count"]) for document in documents_modified]}]
    }
# Document Analysis (Numbers Of Document Modified) Code Ends

# Top 10 Clients Call Analysis (In Minutes) Code Starts

@frappe.whitelist()
def client_calls_chart(start_date=None, end_date=None):
    employees = get_employees()
    if not employees:
        return {}
    caller_name = frappe.db.sql(f"""
    SELECT 
        CASE 
            WHEN link_name IS NOT NULL AND link_name != '' THEN link_name
            ELSE 'Others'
        END AS customname,
        CASE
            WHEN link_to IS NOT NULL AND link_to != '' THEN link_to
            ELSE 'Others'
        END AS party_type,
        link_to AS ref_doctype, 
        ROUND(SUM(duration)/60, 2) AS total_duration,
        COUNT(*) AS call_count
    FROM `tabEmployee Fincall`
    WHERE date >= '{start_date}' 
        AND date <= '{end_date}'
        AND employee IN ({','.join(f"'{employee['name']}'" for employee in employees)})
    GROUP BY link_name
    ORDER BY total_duration DESC
    LIMIT 10
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
            "name": app["customname"] if app["customname"] != "Others" else "Others",
            "value": round(app['total_duration'],2),
            "customIndex": count
        })
        customNames.append(app['party_type'])
        count += 1
    

    return {
        "caller_details": caller_details,
        "company_details": company_details,
        "customNames": customNames
    }
# Top 10 Clients Call Analysis (In Minutes) Code Ends

# Top 10 Employees Call Analysis Code Starts
@frappe.whitelist()
def employee_calls_chart(user, start_date=None, end_date=None):
    employees_list = get_employees()
    if not employees_list:
        return {}
    conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"
    
    employees_calls_data = frappe.db.sql(f"""
    SELECT employee,employee_name,
           SUM(CASE WHEN calltype = 'Incoming' THEN 1 ELSE 0 END) as incoming_count,
           SUM(CASE WHEN calltype = 'Outgoing' THEN 1 ELSE 0 END) as outgoing_count,
           SUM(CASE WHEN calltype = 'Rejected' THEN 1 ELSE 0 END) as rejected_count,
           SUM(CASE WHEN calltype = 'Missed' THEN 1 ELSE 0 END) as missed_count,
           ROUND(SUM(CASE WHEN calltype = 'Incoming' THEN duration ELSE 0 END) / 60, 2) as incoming_duration,
           ROUND(SUM(CASE WHEN calltype = 'Outgoing' THEN duration ELSE 0 END) / 60, 2) as outgoing_duration,
           ROUND(SUM(CASE WHEN calltype = 'Rejected' THEN duration ELSE 0 END) / 60, 2) as rejected_duration,
           ROUND(SUM(CASE WHEN calltype = 'Missed' THEN duration ELSE 0 END) / 60, 2) as missed_duration,
           COUNT(*) as total  
    FROM `tabEmployee Fincall` 
    {conditions} AND employee IN ({','.join(f"'{employee['name']}'" for employee in employees_list)})
    GROUP BY employee
    ORDER BY total DESC
    LIMIT 10
    """, as_dict=1)

    # Filter out employees with no data
    employees_with_data = [entry['employee'] for entry in employees_calls_data if any(entry[f'{calltype}_count'] for calltype in ['incoming', 'outgoing', 'rejected', 'missed'])]
    
    datasets = {
        'Incoming': [],
        'Outgoing': [],
        'Missed': [],
        'Rejected': [],
        'Incoming Duration': [],
        'Outgoing Duration': [],
        'Missed Duration': [],
        'Rejected Duration': []
    }
    
    for entry in employees_calls_data:
        if entry['employee'] in employees_with_data:
            datasets['Incoming'].append(entry['incoming_count'])
            datasets['Outgoing'].append(entry['outgoing_count'])
            datasets['Missed'].append(entry['missed_count'])
            datasets['Rejected'].append(entry['rejected_count'])
            datasets['Incoming Duration'].append(entry['incoming_duration'])
            datasets['Outgoing Duration'].append(entry['outgoing_duration'])
            datasets['Missed Duration'].append(entry['missed_duration'])
            datasets['Rejected Duration'].append(entry['rejected_duration'])
    
    formatted_datasets = []
    all_zero = True

    for calltype in ['Incoming', 'Outgoing', 'Missed', 'Rejected']:
        counts = datasets[calltype]
        durations = datasets[f"{calltype} Duration"]
        
        if any(count != 0 for count in counts):
            all_zero = False
        
        formatted_datasets.append({
            "name": calltype,
            "counts": counts,
            "durations": durations
        })

    if all_zero:
        formatted_datasets = []
    
    # Get employee names only for employees with data
    employee_names = []
    for employee in employees_list:
        if employee['name'] in employees_with_data:
            employee_names.append(employee['employee_name'])
    
    return {
        "labels": [entry['employee_name'] for entry in employees_calls_data if entry['employee'] in employees_with_data],
        "datasets": formatted_datasets
    }
# Top 10 Employees Call Analysis Code Ends

# Overall Performance (All Employees) Code Starts
@frappe.whitelist()
def overall_performance_chart(start_date=None, end_date=None):
    employees = get_employees()
    employees_overall = get_employees_overall_performance(end_date)
    if not employees:
        return {}
    calls = frappe.db.sql(f"""
        SELECT name AS parent, 
            call_datetime AS call_start, ADDTIME(call_datetime, SEC_TO_TIME(duration)) AS call_end,
            employee, employee_name,COALESCE(contact, client, customer_no) as caller, calltype
        FROM `tabEmployee Fincall`
        WHERE date >= '{end_date}' and date <= '{end_date}' and employee IN ({','.join(f"'{employee['name']}'" for employee in employees)})
        ORDER BY employee
    """, as_dict=True)

    meetings = frappe.db.sql(f"""
        SELECT m.name AS parent, 
            m.meeting_from AS meeting_start, m.meeting_to AS meeting_end, m.party as client, m.internal_meeting AS internal,
            mcr.employee, mcr.employee_name, m.organization as organization, m.party_type as party_type, m.meeting_arranged_by as meeting_arranged_by
        FROM `tabMeeting` AS m
        JOIN `tabMeeting Company Representative` AS mcr ON mcr.parent = m.name
        WHERE m.meeting_from >= '{end_date} 00:00:00' and m.meeting_to <= '{end_date} 23:59:59' and m.docstatus = 1 and mcr.employee IN ({','.join(f"'{employee['name']}'" for employee in employees)})
        ORDER BY mcr.employee
    """, as_dict=True)

    idle = frappe.db.sql(f"""
        SELECT name AS parent, 
            from_time AS idle_start, to_time AS idle_end,
            employee, employee_name
        FROM `tabEmployee Idle Time`
        WHERE date >= '{end_date}' and date <= '{end_date}' and employee IN ({','.join(f"'{employee['name']}'" for employee in employees)})
        ORDER BY employee
    """, as_dict=True)

    applications = frappe.db.sql(f"""
        SELECT dwsp.name AS parent, 
            a.from_time AS application_start, a.to_time AS application_end,
            dwsp.employee, dwsp.employee_name
        FROM `tabProductify Work Summary` AS dwsp
        JOIN `tabProductify Work Summary Application` AS a ON a.parent = dwsp.name
        WHERE dwsp.date >= '{end_date}' and dwsp.date <= '{end_date}' AND dwsp.employee IN ({','.join(f"'{employee['employee']}'" for employee in employees_overall)})
        ORDER BY dwsp.employee
    """, as_dict=True)
    base_data = []
    for app in applications:
        base_data.append([
            "Application",
            app['employee_name'].split()[0] + " " + app['employee_name'].split()[-1][0] + "." if app['employee_name'] else "",
            app['application_start'],
            app['application_end'],
        ])
    
    for call in calls:
        base_data.append([
            "Call",
            call['employee_name'].split()[0] + " " + call['employee_name'].split()[-1][0] + "." if call['employee_name'] else "",
            call['call_start'],
            call['call_end'],
            call['caller'],
            call['calltype']
        ])

    for meeting in meetings:
        if meeting['internal']:
            base_data.append([
                "Internal Meeting",
                meeting['employee_name'].split()[0] + " " + meeting['employee_name'].split()[-1][0] + "." if meeting['employee_name'] else "",
                meeting['meeting_start'],
                meeting['meeting_end'],
                meeting['meeting_arranged_by'],
                meeting['client']
            ])
        else:
            base_data.append([
                "External Meeting",
                meeting['employee_name'].split()[0] + " " + meeting['employee_name'].split()[-1][0] + "." if meeting['employee_name'] else "",
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
            i['employee_name'].split()[0] + " " + i['employee_name'].split()[-1][0] + "." if i['employee_name'] else "",
            i['idle_start'],
            i['idle_end'],
        ])
    base_data = sorted(base_data, key=lambda x: x[2])
    data = []
    for i in employees:
        data.append([
            i['employee_name'].split()[0] + " " + i['employee_name'].split()[-1][0] + "." if i['employee_name'] else "",
            i['name'],
        ])

    return{
        "base_dimensions":['Activity', 'Employee', 'Start Time', 'End Time'],
        "dimensions":['Employee', 'Employee Name'],
        "base_data":base_data,
        "data":data
    }
# Overall Performance (All Employees) Code Ends

# User Analysis (User Productivity Stats) Code Starts
@frappe.whitelist()
def user_analysis_data(start_date=None, end_date=None):
    employees = get_employees()
    if not employees:
        return {}
    start_date_, end_date_ = set_dates(start_date, end_date)
    list_data = []
    meeting_total_data = frappe.db.sql(f"""
        SELECT m.meeting_from as start_time, m.meeting_to as end_time, mcr.employee
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE m.meeting_from >= '{start_date_}' and m.meeting_to <= '{end_date_}' and m.docstatus = 1 and mcr.employee IN ({','.join(f"'{employee['name']}'" for employee in employees)})
    """, as_dict=True)
    calls_total_data = frappe.db.sql(f"""
        SELECT call_datetime as start_time, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time, employee
        FROM `tabEmployee Fincall`
        WHERE date >= '{start_date}' and date <= '{end_date}' and employee IN ({','.join(f"'{employee['name']}'" for employee in employees)}) and (calltype != 'Missed' and calltype != 'Rejected')
    """, as_dict=True)
    application_total_data = frappe.db.sql(f"""
        SELECT from_time AS start_time, to_time AS end_time, employee as employee
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' and date <= '{end_date}' AND employee IN ({','.join(f"'{employee['name']}'" for employee in employees)})
        ORDER BY employee
    """, as_dict=True)

    list_data.append(meeting_total_data)
    list_data.append(calls_total_data)
    list_data.append(application_total_data) 

    if list_data:
        # Flatten the list of intervals
        flat_intervals = [interval.copy() for sublist in list_data for interval in sublist]

        # Sort intervals by employee and start time
        flat_intervals.sort(key=lambda x: (x['employee'], x['start_time']))

        # Group intervals by employee
        grouped_intervals = {}
        for interval in flat_intervals:
            employee = interval['employee']
            if employee not in grouped_intervals:
                grouped_intervals[employee] = []
            grouped_intervals[employee].append(interval)

        total_hours_per_employee = {}
        for employee, intervals in grouped_intervals.items():
            # Merge overlapping intervals
            merged_intervals = []
            current_interval = intervals[0]

            for interval in intervals[1:]:
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

            total_hours_per_employee[employee] = total_time.total_seconds() # Convert seconds to hours
    else:
        total_hours_per_employee = {}

    total_days_employee = frappe.db.sql(f"""
        SELECT COUNT(DISTINCT date) as days, employee FROM
        (
            SELECT DATE(m.meeting_from) AS date, mcr.employee
            FROM `tabMeeting` AS m 
            JOIN `tabMeeting Company Representative` AS mcr ON m.name = mcr.parent 
            WHERE m.meeting_from >= DATE('{start_date}') AND m.meeting_to <= DATE('{end_date}') AND m.docstatus = 1
            UNION
            SELECT DATE(`date`) AS date, employee
            FROM `tabApplication Usage log`
            WHERE `date` >= DATE('{start_date}') AND `date` <= DATE('{end_date}') and employee IN ({','.join(f"'{employee['name']}'" for employee in employees)})
        ) AS combined_data
        GROUP BY employee;
        """,as_dict=True)
    
    total_days = {}
    for i in total_days_employee:
        total_days[i['employee']] = i['days']

    # Fetch idle time logs for all employees
    idle_time_data = frappe.db.sql(f"""
        SELECT employee, from_time as start_time, to_time as end_time
        FROM `tabEmployee Idle Time`
        WHERE date >= '{start_date}' AND date <= '{end_date}' and employee IN ({','.join(f"'{employee['name']}'" for employee in employees)})
    """, as_dict=True)

    # Combine all non-idle periods (meetings and calls)
    non_idle_periods = calls_total_data + meeting_total_data

    # Organize non-idle periods by employee
    non_idle_by_employee = {}
    for period in non_idle_periods:
        employee = period['employee']
        if employee not in non_idle_by_employee:
            non_idle_by_employee[employee] = []
        non_idle_by_employee[employee].append(period)

    # Calculate total idle time for each employee
    total_idle_time_by_employee = {}

    for idle_period in idle_time_data:
        employee = idle_period['employee']
        idle_start = idle_period['start_time']
        idle_end = idle_period['end_time']

        adjusted_start = idle_start
        adjusted_end = idle_end
 
        if employee in non_idle_by_employee:
            for non_idle in non_idle_by_employee[employee]:
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
            if employee not in total_idle_time_by_employee:
                total_idle_time_by_employee[employee] = 0
            total_idle_time_by_employee[employee] += idle_duration

    total_idle_time = {employee: round(seconds) for employee, seconds in total_idle_time_by_employee.items()}
    
    fincall_data = frappe.db.sql(f"""
        SELECT 
            employee,
            calltype,
            COUNT(*) AS fincall_count,
            COALESCE(SUM(duration), 0) AS total_duration
        FROM `tabEmployee Fincall`
        WHERE date >= '{start_date}' AND date <= '{end_date}' and employee IN ({','.join(f"'{employee['name']}'" for employee in employees)})
        GROUP BY employee, calltype
    """, as_dict=True)

    # Initialize a dictionary to store counts and total durations by employee
    employee_fincall_data = {}

    # Process the fetched data
    for item in fincall_data:
        employee = item['employee']
        calltype = item['calltype']
        count = item['fincall_count']
        duration = item['total_duration']
        
        if employee not in employee_fincall_data:
            employee_fincall_data[employee] = {
                'incoming_fincall_count': 0,
                'outgoing_fincall_count': 0,
                'missed_fincall_count': 0,
                'rejected_fincall_count': 0,
                'total_incoming_duration': 0,
                'total_outgoing_duration': 0
            }
        
        if calltype == 'Incoming':
            employee_fincall_data[employee]['incoming_fincall_count'] = count
            employee_fincall_data[employee]['total_incoming_duration'] = duration
        elif calltype == 'Outgoing':
            employee_fincall_data[employee]['outgoing_fincall_count'] = count
            employee_fincall_data[employee]['total_outgoing_duration'] = duration
        elif calltype == 'Missed':
            employee_fincall_data[employee]['missed_fincall_count'] = count
        elif calltype == 'Rejected':
            employee_fincall_data[employee]['rejected_fincall_count'] = count
    
    # Fetch external meeting data for all employees
    sql_query_external = f"""
        SELECT 
            mcr.employee,
            SUM(CASE 
                    WHEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from)) > 0 THEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))
                    ELSE 0 
                END) AS total_meeting_duration,
            COUNT(DISTINCT m.name) AS meeting_count
        FROM `tabMeeting` AS m
        JOIN `tabMeeting Company Representative` AS mcr ON m.name = mcr.parent
        WHERE m.meeting_from >= '{start_date} 00:00:00' AND m.meeting_to <= '{end_date} 23:59:59' and m.docstatus = 1 and mcr.employee IN ({','.join(f"'{employee['name']}'" for employee in employees)})
        GROUP BY mcr.employee
    """
    meetings_external_employee_raw = frappe.db.sql(sql_query_external, as_dict=True)
    meetings_external_employee = {}
    for i in meetings_external_employee_raw:
        meetings_external_employee[i['employee']] = { "duration":i['total_meeting_duration'], "count":i['meeting_count']}

    work_intensity = frappe.db.sql(f"""
        SELECT 
            employee,
            COALESCE(SUM(key_strokes), 0) AS total_keystrokes,
            COALESCE(SUM(mouse_clicks), 0) AS total_mouse_clicks,
            COALESCE(SUM(mouse_scrolls), 0) AS total_scroll
        FROM `tabWork Intensity`
        WHERE employee IN ({','.join(f"'{employee['name']}'" for employee in employees)}) and time >= '{start_date_}' AND time <= '{end_date_}'
        GROUP BY employee
    """, as_dict=True)
    
    work_intensity_data = {}
    for item in work_intensity:
        employee = item['employee']
        work_intensity_data[employee] = {
            'total_keystrokes': item['total_keystrokes'],
            'total_mouse_clicks': item['total_mouse_clicks'],
            'total_scroll': item['total_scroll']
        }
    
    productivity_score = {}
    # Retrieve working hours per day and on Saturday from the database
    weekday_hours = frappe.db.get_single_value('Productify Subscription', 'working_hours_per_day')
    saturday_hours = frappe.db.get_single_value('Productify Subscription', 'working_hours_on_saturday')

    hours_per_weekday = float(weekday_hours) if weekday_hours else 7.5
    hours_on_saturday = float(saturday_hours) if saturday_hours else 2.5

    for employee in employees:
        score = calculate_total_working_hours(employee['name'],start_date, end_date, hours_per_weekday, hours_on_saturday)
        productivity_score[employee['name']] = score
    
    return {
        "total_days": total_days,
        "total_hours_per_employee": total_hours_per_employee,
        "total_idle_time": total_idle_time,
        "employee_fincall_data": employee_fincall_data,
        "meeting_employee_data": meetings_external_employee,
        "work_intensity_data": work_intensity_data,
        "productivity_score": productivity_score
    }
# User Analysis (User Productivity Stats) Code Ends
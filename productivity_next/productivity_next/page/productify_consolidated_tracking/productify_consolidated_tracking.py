import frappe
from datetime import datetime,timedelta
from frappe.utils import now
from collections import defaultdict
from finbyz.finbyz.page.productify_employee_tracking_finbyz.productify_employee_tracking_finbyz import get_user_data
from finbyz.finbyz.page.productify_employee_tracking_finbyz.productify_employee_tracking_finbyz import get_issue_data
@frappe.whitelist()
def get_admin_data(start_date=None, end_date=None):
    start_date_, end_date_ = set_dates(start_date, end_date)
    conditions_2 = f"AND m.meeting_from >= '{start_date_}' AND m.meeting_to <= '{end_date_}'"

    list_data = []
    meeting_total_data = frappe.db.sql(f"""
        SELECT m.meeting_from as start_time, m.meeting_to as end_time, mcr.employee
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE m.docstatus = 1 and m.meeting_from >= '{start_date_}' and m.meeting_to <= '{end_date_}'
    """, as_dict=True)
    calls_total_data = frappe.db.sql(f"""
        SELECT call_datetime as start_time, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time, employee
        FROM `tabEmployee Fincall`
        WHERE call_datetime >= '{start_date_}' and call_datetime <= '{end_date_}' and (calltype != 'Missed' and calltype != 'Rejected')
    """, as_dict=True)
    application_total_data = frappe.db.sql(f"""
        SELECT from_time as start_time, to_time as end_time, employee
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' and date <= '{end_date}'
    """, as_dict=True)

    list_data.append(meeting_total_data)
    list_data.append(calls_total_data)
    list_data.append(application_total_data) 

    if list_data:
        # Flatten the list of intervals
        flat_intervals = [interval for sublist in list_data for interval in sublist]

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
            WHERE m.docstatus = 1 AND m.meeting_from >= DATE('2024-05-30') AND m.meeting_to <= DATE('2024-06-06')

            UNION

            SELECT DATE(`date`) AS date, employee
            FROM `tabApplication Usage log`
            WHERE `date` >= DATE('{start_date}') AND `date` <= DATE('{end_date}')
        ) AS combined_data
        GROUP BY employee;
        """,as_dict=True)
    
    total_days = {}
    for i in total_days_employee:
        total_days[i['employee']] = i['days']

    # Fetch idle time logs for all employees
    idle_time_data = frappe.db.sql(f"""
        SELECT employee, start_time, end_time
        FROM `tabEmployee Idle Time`
        WHERE start_time > '{start_date_}' AND end_time < '{end_date_}'
    """, as_dict=True)

    # Fetch fincall time logs for all employees
    fincall_time_data = frappe.db.sql(f"""
        SELECT employee, call_datetime as start_time, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time
        FROM `tabEmployee Fincall`
        WHERE call_datetime > '{start_date_}' AND ADDTIME(call_datetime, SEC_TO_TIME(duration)) < '{end_date_}'
        AND (calltype != 'Missed' AND calltype != 'Rejected')
    """, as_dict=True)

    # Fetch meeting time logs for all employees
    meeting_time_data = frappe.db.sql(f"""
        SELECT mcr.employee, meeting_from as start_time, meeting_to as end_time
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE m.meeting_from >= '{start_date_}' AND m.meeting_to <= '{end_date_}'
    """, as_dict=True)

    # Combine all non-idle periods (meetings and calls)
    non_idle_periods = fincall_time_data + meeting_time_data

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
        WHERE date >= '{start_date}' AND date <= '{end_date}'
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
    
    conditions_2 = f"AND m.meeting_from >= '{start_date}' AND m.meeting_to <= '{end_date}'"
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
        WHERE m.docstatus = 1
        {conditions_2}
        GROUP BY mcr.employee
    """
    meetings_external_employee_raw = frappe.db.sql(sql_query_external, as_dict=True)
    meetings_external_employee = {}
    for i in meetings_external_employee_raw:
        meetings_external_employee[i['employee']] = { "duration":i['total_meeting_duration'], "count":i['meeting_count']}

    issue_time_count_data = frappe.db.sql(f"""
        SELECT 
            COUNT(DISTINCT i.subject) AS no_of_issues,
            SUM(ti.time_involvement) AS time_in_issues,
            ti.user_name
        FROM `tabIssue` as i
        JOIN `tabTime Involvement` as ti ON i.name = ti.parent
        WHERE ti.date >= '{start_date}' AND ti.date <= '{end_date}'
        group by ti.user_name
    """, as_dict=1)
    issue_data = {}
    for i in issue_time_count_data:
            # Fetch employee name based on user_id
            employee = frappe.db.get_value("Employee", filters={"user_id": i['user_name']}, fieldname="name")
            
            # Populate the issue_data dictionary with issues and time in issues
            issue_data[employee] = {
                "no_of_issues": i['no_of_issues'],
                "time_in_issues": i['time_in_issues']
            }
    
    return {
        "total_days": total_days,
        "total_hours_per_employee": total_hours_per_employee,
        "total_idle_time": total_idle_time,
        "employee_fincall_data": employee_fincall_data,
        "meeting_employee_data": meetings_external_employee,
        "issue_data": issue_data
    }

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

@frappe.whitelist() 
def version_conditions(start_date=None, end_date=None):
    now = frappe.utils.now_datetime()
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00')
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d 00:00:00')
    
    if end_date is None:
        end_date = now.strftime('%Y-%m-%d 23:59:59')
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d 23:59:59')
    
    condition = f"WHERE creation >= '{start_date}' AND creation <= '{end_date}'"

    return condition

@frappe.whitelist()
def get_barchart_data(start_date=None, end_date=None):
    version_conditions_str = version_conditions(start_date,end_date)
    ignore_doctype = ['File',"Communication","Fincall Log","Custom Field","DocType","Web Page","Attendance"]
    # Convert the list into a format suitable for SQL query ("'DocType1', 'DocType2', 'DocType3'")
    ignore_doctype_str = ','.join(f"'{doc}'" for doc in ignore_doctype)

    # Check if the list is not empty to add a condition to the query
    if ignore_doctype_str:
        ignore_condition = f"AND ref_doctype NOT IN ({ignore_doctype_str})"
    else:
        ignore_condition = ""
    start_date, end_date = set_dates(start_date, end_date)
    data = frappe.db.sql(f"""
            SELECT COUNT(DISTINCT docname) AS activity_count,ref_doctype
            FROM `tabVersion`
            {version_conditions_str}
            {ignore_condition}
            GROUP BY ref_doctype
            ORDER BY activity_count DESC
        """, as_dict=1)
        
    return {
        "labels": [i["ref_doctype"] for i in data],
        "datasets": [{"values": [(i["activity_count"]) for i in data]}]
    }
@frappe.whitelist()
def get_client_calls_chart_data(user, start_date=None, end_date=None):
    conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"
    data = frappe.db.sql(f"""
        select link_name,round(SUM(duration)/60,2) as total_duration
        from `tabEmployee Fincall`
        {conditions} and link_name is not null
        group by link_name
        order by total_duration desc
        limit 20
    """, as_dict=1)
    labels = []
    datasets = []
    for i in data:
        labels.append(i['link_name'])
        datasets.append(i['total_duration'])
    return {
        "labels": labels,
        "datasets": datasets
    }

@frappe.whitelist()
def get_linechart_data(user, start_date=None, end_date=None):
    if user != "Administrator":
        conditions = f"WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}'"
    else:
        conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"
    
    data = frappe.db.sql(f"""
    SELECT employee,
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
    {conditions}
    GROUP BY employee
    ORDER BY total DESC
    LIMIT 10
    """, as_dict=1)
    
    employees = sorted(set(entry['employee'] for entry in data))
    
    datasets = {
        'Incoming': [0] * len(employees),
        'Outgoing': [0] * len(employees),
        'Missed': [0] * len(employees),
        'Rejected': [0] * len(employees),
        'Incoming Duration': [0] * len(employees),
        'Outgoing Duration': [0] * len(employees),
        'Missed Duration': [0] * len(employees),
        'Rejected Duration': [0] * len(employees)
    }
    
    employee_index = {employee: idx for idx, employee in enumerate(employees)}
    for entry in data:
        employee = entry['employee']
        index = employee_index[employee]
        datasets['Incoming'][index] = entry['incoming_count']
        datasets['Outgoing'][index] = entry['outgoing_count']
        datasets['Missed'][index] = entry['missed_count']
        datasets['Rejected'][index] = entry['rejected_count']
        datasets['Incoming Duration'][index] = entry['incoming_duration']
        datasets['Outgoing Duration'][index] = entry['outgoing_duration']
        datasets['Missed Duration'][index] = entry['missed_duration']
        datasets['Rejected Duration'][index] = entry['rejected_duration']
    
    formatted_datasets = []
    for calltype in ['Incoming', 'Outgoing', 'Missed', 'Rejected']:
        formatted_datasets.append({
            "name": calltype,
            "counts": datasets[calltype],
            "durations": datasets[f"{calltype} Duration"]
        })
    
    employee_names = []
    for employee in employees:
        name = frappe.db.get_value("Employee", employee, "employee_name")
        employee_names.append(name)
    
    return {
        "labels": employee_names,
        "datasets": formatted_datasets
    }

@frappe.whitelist()
def get_app_brief_data(app_data, start_date=None, end_date=None):
    data = frappe.db.sql(f"""
        SELECT employee, SUM(duration) AS total_duration,application_name
        FROM `tabApplication Usage log`
        WHERE application_name = '{app_data}' AND date >= '{start_date}' AND date <= '{end_date}'
        GROUP BY employee
        ORDER BY total_duration DESC
        """, as_dict=1)
    return {"app_data":data}

@frappe.whitelist()
def get_url_brief_data(url_data, start_date=None, end_date=None):
    data = frappe.db.sql(f"""
        SELECT employee, SUM(duration) AS total_duration,domain
        FROM `tabApplication Usage log`
        WHERE domain = '{url_data}' AND date >= '{start_date}' AND date <= '{end_date}'
        GROUP BY employee
        ORDER BY total_duration DESC
        """, as_dict=1)
    return {"url_data":data}

@frappe.whitelist()
def get_issue_data_admin(start_date=None, end_date=None):
    data = frappe.db.sql(f"""
        SELECT 
            COUNT(DISTINCT i.subject) AS no_of_issues,
            SUM(ti.time_involvement) AS time_in_issues
        FROM `tabIssue` as i
        JOIN `tabTime Involvement` as ti ON i.name = ti.parent
        WHERE ti.date >= '{start_date}' AND ti.date <= '{end_date}'
    """, as_dict=1)
    # Parsing the result to return counts
    if data:
        no_of_issues = data[0]['no_of_issues'] if 'no_of_issues' in data[0] else 0
        time_in_issues = data[0]['time_in_issues'] if 'time_in_issues' in data[0] else 0
    else:
        no_of_issues = 0
        time_in_issues = 0

    return {
        "no_of_issues": no_of_issues,
        "time_in_issues": time_in_issues
    }

@frappe.whitelist()
def client_time_data(start_date=None, end_date=None):
    start_date_, end_date_ = set_dates(start_date, end_date)
    
    # Query to get issue data
    # Fetch issue data
    issue_data = frappe.db.sql(f"""
        SELECT 
            p.customer,
            SUM(ti.time_involvement) AS time_in_issues
        FROM `tabIssue` as i
        JOIN `tabTime Involvement` as ti ON i.name = ti.parent
        JOIN `tabProject` as p ON p.name = i.project
        WHERE ti.date >= '{start_date}' AND ti.date <= '{end_date}'
        GROUP BY p.customer                 
    """, as_dict=1)

    # Fetch meeting data
    meeting_data = frappe.db.sql(f"""
        SELECT 
            SUM(CASE 
                    WHEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from)) > 0 THEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))
                    ELSE 0 
                END) AS total_meeting_duration,
            m.party as customer
        FROM `tabMeeting` as m
        WHERE m.meeting_from >= '{start_date_}' AND m.meeting_to <= '{end_date_}'
        AND m.docstatus = 1 
        GROUP BY m.party
    """, as_dict=1)

    # Convert meeting duration from seconds to hours
    for meeting in meeting_data:
        meeting['total_meeting_duration'] = meeting['total_meeting_duration'] / 3600

    # Merge results based on customer
    combined_data = {}

    # Add issue data to the combined data
    for issue in issue_data:
        customer = issue['customer']
        combined_data[customer] = {
            'time_in_issues': issue['time_in_issues'],
            'total_meeting_duration': 0  # Initialize with 0
        }

    # Add meeting data to the combined data
    for meeting in meeting_data:
        customer = meeting['customer']
        if customer in combined_data:
            combined_data[customer]['total_meeting_duration'] = meeting['total_meeting_duration']
        else:
            combined_data[customer] = {
                'time_in_issues': 0,  # Initialize with 0
                'total_meeting_duration': meeting['total_meeting_duration']
            }

    # Compute total time for each customer
    result = []
    for customer, times in combined_data.items():
        total_time = times['time_in_issues'] + times['total_meeting_duration']
        result.append({
            'customer': customer,
            'total_time': total_time
        })

    # Sort the result by total_time in descending order and get the top 10
    result = sorted(result, key=lambda x: x['total_time'], reverse=True)[:10]

    # Return the result in the desired format
    return {
        "labels": [i["customer"] for i in result],
        "datasets": [{"values": [i["total_time"] for i in result]}]
    }

@frappe.whitelist()
def get_issue_active_chart_data(start_date=None, end_date=None):
    pass
import frappe
from frappe.utils import nowdate, add_days, getdate,get_datetime, time_diff_in_seconds
from datetime import datetime,timedelta
from collections import defaultdict
from productivity_next.productivity_next.page.employee_productivity_dashboard.employee_productivity_dashboard import get_user_data
@frappe.whitelist()
def get_admin_data(user, start_date=None, end_date=None):
    combined_data = []
    if user != "Administrator":
        employees = frappe.db.get_all("Employee", filters={"status": "Active"}, fields=["name"])
        for employee in employees:
            employee_data = get_user_data(employee['name'], start_date, end_date)
            employee_data['employee'] = employee['name']
            combined_data.append(employee_data)
    else: 
        employee_data = get_user_data(user, start_date, end_date)
        combined_data.append(employee_data)

    # frappe.throw(str(combined_data))
    # total_idle_time_list, total_hours_data_list, fincall_data, meeting_data = fetch_and_calculate_times(start_date, end_date)
    # combined_data = combine_employee_data(total_idle_time_list, total_hours_data_list, fincall_data, meeting_data)
    # frappe.throw(str(combined_data))    
    # Return result as a dictionary
    return {"combined_employee_data": combined_data}

# def calculate_idle_times_per_employee(data):
#     from datetime import datetime, timedelta

#     employee_idle_times = defaultdict(timedelta)
    
#     for entry in data:
#         employee = entry['employee']
#         start_time = datetime.strptime(entry['start_time'], "%H:%M:%S")
#         end_time = datetime.strptime(entry['end_time'], "%H:%M:%S")
        
#         duration = end_time - start_time
#         employee_idle_times[employee] += duration

#     # Ensure no negative idle times
#     for employee in employee_idle_times:
#         if employee_idle_times[employee] < timedelta(0):
#             employee_idle_times[employee] = timedelta(0)

#     return employee_idle_times


def set_dates(start_date=None, end_date=None):
    """
    Determine start and end dates for a range, formatted with specific time stamps.
    Args:
    - start_date (str, optional): Start date in 'YYYY-MM-DD' format. Defaults to 365 days ago.
    - end_date (str, optional): End date in 'YYYY-MM-DD' format. Defaults to today.

    Returns:
    - tuple: A tuple containing formatted start and end dates as strings.
    """
    now = datetime.now()
    
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00')
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d 00:00:00')
    
    if end_date is None:
        end_date = now.strftime('%Y-%m-%d 23:59:59')
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d 23:59:59')

    return start_date, end_date

# def fetch_and_calculate_times(start_date, end_date):
#     conditions = f"WHERE call_datetime >= '{start_date}' AND call_datetime <= '{end_date}'"
#     conditions_2 = f"AND m.meeting_from >= '{start_date}' AND m.meeting_to <= '{end_date}'"
#     conditions_3 = f"WHERE DATE(time) >= '{start_date}' AND DATE(time) <= '{end_date}'"

#     # Fetch data from different sources
#     idle_time_data = fetch_idle_time_data(conditions_3)
#     fincall_time_data = fetch_fincall_data(conditions)
#     meeting_time_data = fetch_meeting_time_data(conditions_2)
    
#     # Fetch total hours from application check-in checkout logs
#     total_hours_data = fetch_total_hours(start_date, end_date)
#     # frappe.throw(str(idle_time_data))
#     return idle_time_data, total_hours_data, fincall_time_data, meeting_time_data

# def fetch_idle_time_data(conditions):
#     # SQL Query to fetch idle time logs
#     sql_query = f"""
#     SELECT DATE_FORMAT(time, '%H:%i:%s') as start_time, status, employee
#     FROM `tabIdle Time Log`
#     {conditions}
#     """
#     data = frappe.db.sql(sql_query, as_dict=True)
#     # frappe.throw(str(data))
#     return calculate_idle_time_user(data)

# def fetch_fincall_data(conditions):
#     # Correctly apply conditions and ensure `employee` and `calltype` are both grouped
#     sql_query = f"""
#     SELECT 
#         employee,
#         calltype,
#         COUNT(*) AS fincall_count,
#         COALESCE(SUM(duration), 0) AS total_duration
#     FROM `tabFincall Log`
#     {conditions}
#     GROUP BY employee, calltype
#     """
#     return frappe.db.sql(sql_query, as_dict=True)

# def fetch_meeting_time_data(conditions):
#     # SQL Query to fetch meeting data with total duration and count by employee
#     sql_query = f"""
#     SELECT 
#         mcr.employee,
#         SUM(CASE 
#                 WHEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from)) > 0 THEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))
#                 ELSE 0 
#             END) AS total_meeting_duration,
#         COUNT(DISTINCT m.name) as meeting_count
#     FROM `tabMeeting` as m
#     JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
#     WHERE m.docstatus = 1 {conditions}
#     GROUP BY mcr.employee
#     """
#     return frappe.db.sql(sql_query, as_dict=True)


# def calculate_idle_time_user(data):
#     # frappe.throw(str(data))
#     time_format = "%H:%M:%S"
#     employee_times = defaultdict(list)
#     results = []

#     # Organize records by employee and sort by time
#     for record in data:
#         employee_times[record['employee']].append((record['start_time'], record['status']))
#     for employee, times in employee_times.items():
#         times.sort()

#     # Calculate idle time by finding the gap between 'end' of one and 'start' of next activity
#     idle_times = defaultdict(int)
#     for employee, times in employee_times.items():
#         last_end_time = None
#         for time, status in times:
#             current_time = datetime.strptime(time, time_format)
#             if status == 'start' and last_end_time is not None:
#                 idle_seconds = (current_time - last_end_time).total_seconds()
#                 # if idle_seconds <= 7200:  # Ignore idle time greater than 2 hours
#                 idle_times[employee] += idle_seconds
#             if status == 'end':
#                 last_end_time = current_time

#     # Prepare final results
#     for employee, total_idle_seconds in idle_times.items():
#         results.append({
#             'employee': employee,
#             'total_idle_time': total_idle_seconds / 3600  # Convert seconds to hours
#         })
#     # frappe.throw(str(results))
#     return results



# def fetch_total_hours(start_date, end_date, user=None):
#     all_logs = frappe.db.sql(f"""
#     SELECT employee, status, time
#     FROM `tabApplication Checkin Checkout`
#     WHERE time >= '{start_date}' AND time <= '{end_date}'
#     ORDER BY employee, time
#     """, as_dict=True)
#     total_hours_by_employee = {}
#     last_status = {}
#     last_time = {}

#     # Loop through logs to calculate total duration of logged "In" sessions for each employee
#     for log in all_logs:
#         employee = log['employee']
#         if employee not in total_hours_by_employee:
#             total_hours_by_employee[employee] = 0
#             last_status[employee] = None
#             last_time[employee] = None

#         if log['status'] == "In" and last_status[employee] != "In":
#             last_time[employee] = get_datetime(log['time'])
#         elif log['status'] == "Out" and last_status[employee] == "In":
#             if last_time[employee]:
#                 end_time = get_datetime(log['time'])
#                 total_hours_by_employee[employee] += time_diff_in_seconds(end_time, last_time[employee])
#                 last_time[employee] = None  # Reset last time after calculating the period

#         last_status[employee] = log['status']

#     # Convert total duration from seconds to hours and return it
#     for employee in total_hours_by_employee:
#         total_hours_by_employee[employee] /= 3600.0
#     data = []
#     for i in total_hours_by_employee:
#         data.append({
#             'employee': i,
#             'total_hours': total_hours_by_employee[i]
#         })
#     return data

# from collections import defaultdict

# def combine_employee_data(idle_time_data, total_hours_data_list, fincall_data, meeting_data):
#     # Process into dictionaries
#     idle_time_dict = {item['employee']: item['total_idle_time'] for item in idle_time_data}
#     hours_data_dict = {item['employee']: item['total_hours'] for item in total_hours_data_list}
    
#     # Setup default fincall structure
#     default_fincall_structure = {
#         'Incoming': {'count': 0, 'total_duration': 0},
#         'Outgoing': {'count': 0, 'total_duration': 0},
#         'Missed': {'count': 0, 'total_duration': 0},
#         'Rejected': {'count': 0, 'total_duration': 0}
#     }
    
#     # Handling fincall data with defaultdict
#     fincall_dict = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'total_duration': 0}))
#     for item in fincall_data:
#         fincall_dict[item['employee']][item['calltype']]['count'] += item['fincall_count']
#         fincall_dict[item['employee']][item['calltype']]['total_duration'] += item['total_duration']
    
#     # Convert defaultdict to dict and merge with default structure
#     fincall_results = {}
#     for employee, calls in fincall_dict.items():
#         employee_data = default_fincall_structure.copy()
#         for calltype, details in calls.items():
#             employee_data[calltype] = dict(details)  # Override the default structure with actual data
#         fincall_results[employee] = employee_data
    
#     meeting_dict = {item['employee']: {'total_meeting_duration': item['total_meeting_duration'], 'meeting_count': item['meeting_count']} for item in meeting_data}

#     # Combine all data
#     all_employees = set(idle_time_dict.keys()) | set(hours_data_dict.keys()) | set(fincall_results.keys()) | set(meeting_dict.keys())
#     combined_data = []
#     for employee in all_employees:
#         combined_data.append({
#             "employee": employee,
#             "total_idle_time": idle_time_dict.get(employee, 0),
#             "total_hours": hours_data_dict.get(employee, 0),
#             "fincall_details": fincall_results.get(employee, default_fincall_structure),
#             "meeting_details": meeting_dict.get(employee, {'total_meeting_duration': 0, 'meeting_count': 0})
#         })
#     return combined_data
@frappe.whitelist() 
def version_conditions(start_date=None, end_date=None):
    now = datetime.now()
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00')
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d 00:00:00')
    
    if end_date is None:
        end_date = now.strftime('%Y-%m-%d 23:59:59')
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d 23:59:59')
    
    condition = f"WHERE DATE(creation) >= '{start_date}' AND DATE(creation) <= '{end_date}'"

    return condition

@frappe.whitelist()
def get_barchart_data(start_date=None, end_date=None):
    version_conditions_str = version_conditions(start_date,end_date)
    ignore_doctype = ['File']
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
import frappe
from frappe.utils import nowdate, add_days, getdate
from datetime import datetime,timedelta
from collections import defaultdict

@frappe.whitelist()
def get_admin_data(user, start_date=None, end_date=None):
    # Ensure dates are properly set
    start_date, end_date = set_dates(start_date, end_date)

    # Calculate and fetch required data
    total_idle_time_list, total_hours_data_list, fincall_data, meeting_data = fetch_and_calculate_times(start_date, end_date)
    # frappe.throw(str(total_idle_time_list))
    # Combine the results into a single list of dictionaries
    combined_data = combine_employee_data(total_idle_time_list, total_hours_data_list, fincall_data, meeting_data)
    # frappe.throw(str(combined_data))    
    # Return result as a dictionary
    return {"combined_employee_data": combined_data}

def calculate_idle_times_per_employee(data):
    from datetime import datetime, timedelta

    employee_idle_times = defaultdict(timedelta)
    
    for entry in data:
        employee = entry['employee']
        start_time = datetime.strptime(entry['start_time'], "%H:%M:%S")
        end_time = datetime.strptime(entry['end_time'], "%H:%M:%S")
        
        duration = end_time - start_time
        employee_idle_times[employee] += duration

    # Ensure no negative idle times
    for employee in employee_idle_times:
        if employee_idle_times[employee] < timedelta(0):
            employee_idle_times[employee] = timedelta(0)

    return employee_idle_times
def set_dates(start_date, end_date):
    if not start_date:
        start_date = nowdate()
    if not end_date or getdate(end_date) < getdate(start_date):
        end_date = add_days(start_date, 1)  # Default to one day range if end_date is before start_date
    return start_date, end_date

def fetch_and_calculate_times(start_date, end_date):
    conditions = f"WHERE call_datetime >= '{start_date}' AND call_datetime <= '{end_date}'"
    conditions_2 = f"AND m.meeting_from >= '{start_date}' AND m.meeting_to <= '{end_date}'"
    conditions_3 = f"WHERE time >= '{start_date}' AND time <= '{end_date}'"

    # Fetch data from different sources
    idle_time_data = fetch_idle_time_data(conditions_3)
    fincall_time_data = fetch_fincall_data(conditions)
    meeting_time_data = fetch_meeting_time_data(conditions_2)
    
    # Fetch total hours from application check-in checkout logs
    total_hours_data = fetch_total_hours(start_date, end_date)
    
    return idle_time_data, total_hours_data, fincall_time_data, meeting_time_data

def fetch_idle_time_data(conditions):
    # SQL Query to fetch idle time logs
    sql_query = f"""
    SELECT DATE_FORMAT(time, '%H:%i:%s') as start_time, status, employee
    FROM `tabIdle Time Log`
    {conditions}
    """
    data = frappe.db.sql(sql_query, as_dict=True)
    # frappe.throw(str(data))
    return calculate_idle_time_user(data)

def fetch_fincall_data(conditions):
    # Correctly apply conditions and ensure `employee` and `calltype` are both grouped
    sql_query = f"""
    SELECT 
        employee,
        calltype,
        COUNT(*) AS fincall_count,
        COALESCE(SUM(duration), 0) AS total_duration
    FROM `tabFincall Log`
    {conditions}
    GROUP BY employee, calltype
    """
    return frappe.db.sql(sql_query, as_dict=True)

def fetch_meeting_time_data(conditions):
    # SQL Query to fetch meeting data with total duration and count by employee
    sql_query = f"""
    SELECT 
        mcr.employee,
        SUM(TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))) AS total_meeting_duration,
        COUNT(DISTINCT m.name) as meeting_count
    FROM `tabMeeting` as m
    JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
    WHERE m.docstatus = 1 {conditions}
    GROUP BY mcr.employee
    """
    return frappe.db.sql(sql_query, as_dict=True)


def calculate_idle_time_user(data):
    time_format = "%H:%M:%S"
    employee_active_time = {}

    for record in data:
        employee = record['employee']
        status = record['status']
        current_time = datetime.strptime(record['start_time'], time_format)

        if status == 'start':
            # Initialize employee record if not already present
            if employee not in employee_active_time:
                employee_active_time[employee] = {'total_active_seconds': 0, 'last_start_time': None}
            # Store the start time for the current activity period
            employee_active_time[employee]['last_start_time'] = current_time
        elif status == 'end':
            if employee in employee_active_time and employee_active_time[employee]['last_start_time'] is not None:
                # Calculate the active time for this period
                start_time = employee_active_time[employee]['last_start_time']
                active_seconds = (current_time - start_time).total_seconds()
                employee_active_time[employee]['total_active_seconds'] += active_seconds
                # Reset the last start time
                employee_active_time[employee]['last_start_time'] = None

    # Prepare final results
    results = []
    for employee, details in employee_active_time.items():
        if details['total_active_seconds'] > 0:  # Only include employees with active time
            results.append({
                'employee': employee,
                'total_active_time': details['total_active_seconds']  # Total active time in seconds
            })
    
    # frappe.throw(str(results))  
    return results

def fetch_total_hours(start_date, end_date):
    sql_query = f"""
    SELECT employee, SUM(CASE WHEN status = 'Out' THEN TIMESTAMPDIFF(SECOND, prev_time, time) ELSE 0 END) / 3600.0 AS total_hours
    FROM (SELECT employee, status, time, LAG(time) OVER (PARTITION BY employee ORDER BY time) AS prev_time, LAG(status) OVER (PARTITION BY employee ORDER BY time) AS prev_status FROM `tabApplication Checkin Checkout` WHERE time BETWEEN '{start_date}' AND '{end_date}') AS log_details WHERE status = 'Out' AND prev_status = 'In' GROUP BY employee;
    """
    return frappe.db.sql(sql_query, as_dict=True)

def combine_employee_data(total_idle_time_list, total_hours_data_list, fincall_data, meeting_data):
    idle_time_dict = {item['employee']: item for item in total_idle_time_list}
    hours_data_dict = {item['employee']: item for item in total_hours_data_list}
    fincall_details = {}
    meeting_details = {}

    # Process fincall data
    for item in fincall_data:
        emp = item['employee']
        if emp not in fincall_details:
            fincall_details[emp] = {
                'Incoming': {'count': 0, 'total_duration': 0},
                'Outgoing': {'count': 0, 'total_duration': 0},
                'Missed': {'count': 0, 'total_duration': 0},
                'Rejected': {'count': 0, 'total_duration': 0}
            }
        fincall_details[emp][item['calltype']]['count'] += item['fincall_count']
        fincall_details[emp][item['calltype']]['total_duration'] += item['total_duration']

    # Process meeting data
    for item in meeting_data:
        emp = item['employee']
        if emp not in meeting_details:
            meeting_details[emp] = {'total_meeting_duration': 0, 'meeting_count': 0}
        meeting_details[emp]['total_meeting_duration'] += item['total_meeting_duration']
        meeting_details[emp]['meeting_count'] += item['meeting_count']

    # Merge all data into a combined structure
    combined_data = []
    all_employees = set(idle_time_dict.keys()) | set(hours_data_dict.keys()) | set(fincall_details.keys()) | set(meeting_details.keys())
    for employee in all_employees:
        combined_dict = {
            "employee": employee,
            "total_idle_time": idle_time_dict.get(employee, {}).get('total_idle_time', 0),
            "total_hours": hours_data_dict.get(employee, {}).get('total_hours', 0),
            "fincall_details": fincall_details.get(employee, {
                'Incoming': {'count': 0, 'total_duration': 0},
                'Outgoing': {'count': 0, 'total_duration': 0},
                'Missed': {'count': 0, 'total_duration': 0},
                'Rejected': {'count': 0, 'total_duration': 0}
            }),
            "meeting_details": meeting_details.get(employee, {'total_meeting_duration': 0, 'meeting_count': 0})
        }
        combined_data.append(combined_dict)

    return combined_data
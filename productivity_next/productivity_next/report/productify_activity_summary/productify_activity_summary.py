import frappe
from datetime import datetime, timedelta
from frappe import _
import frappe
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
def execute(filters=None):
    columns = get_columns()
    all_data = get_data(filters)
    data = all_data[0]
    summarized_data = all_data[1]
    
    chart = get_chart_data(summarized_data)
    summary_data = get_summary_data(summarized_data)
    
    return columns, data, None, chart, summary_data

def get_columns(filters=None):
    columns = [
        {
            "fieldname": "employee",
            "label": _("Employee"),
            "fieldtype": "Link",
            "options": "Employee",
            "width": 200
        },
        {
            "fieldname": "starting_date",
            "label": _("Starting Date"),
            "fieldtype": "Date",
        },
        {
            "fieldname": "ending_date",
            "label": _("Ending Date"),
            "fieldtype": "Date",
        },
        {
            "fieldname": "total_hours",
            "label": _("Total Hours"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "active_hours",
            "label": _("Active Hours"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "idle_hours",
            "label": _("Idle Hours"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "average_active",
            "label": _("Average Active"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "incoming_calls",
            "label": _("Incoming Calls"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "incoming_hours",
            "label": _("Incoming Hours"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "outgoing_calls",
            "label": _("Outgoing Calls"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "outgoing_hours",
            "label": _("Outgoing Hours"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "missed_calls",
            "label": _("Missed Calls"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "rejected_calls",
            "label": _("Rejected Calls"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "keyboard",
            "label": _("Keyboard"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "mouse",
            "label": _("Mouse"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "scroll",
            "label": _("Scroll"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "meetings",
            "label": _("Meetings"),
            "fieldtype": "Data",
        },
        {
            "fieldname": "meetings_hours",
            "label": _("Meetings Hours"),
            "fieldtype": "Data",
        }
    ]

    return columns

def format_duration(duration_seconds):
    try:
        duration_seconds = float(duration_seconds)
        total_hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        return f"{total_hours}h {minutes}m"
    except ValueError:
        return "0h 0m"

def get_data(filters):
    try:
        from_date = datetime.strptime(filters.get("from_date"), "%Y-%m-%d")
        to_date = datetime.strptime(filters.get("to_date"), "%Y-%m-%d")
        frequency = filters.get("frequency", "Daily")
        
        data = []
        summarized_data = []
        
        if frequency == "Daily":
            date_ranges = [(d, d) for d in date_range(from_date, to_date)]
        elif frequency == "Weekly":
            date_ranges = weekly_ranges(from_date, to_date)
        elif frequency == "Monthly":
            date_ranges = monthly_ranges(from_date, to_date)
        else:
            frappe.throw("Invalid frequency")
 
        
        for start, end in date_ranges:
            current_filters = filters.copy()
            current_filters["from_date"] = start.strftime("%Y-%m-%d")
            current_filters["to_date"] = end.strftime("%Y-%m-%d")
            
            user_analysis = user_analysis_data(current_filters.get("from_date"), current_filters.get("to_date"), current_filters)
            
    
            summary = {
                "starting_date": current_filters["from_date"],
                "ending_date": current_filters["to_date"],
                "total_hours": 0,
                "active_hours": 0,
                "idle_hours": 0,
                "average_active": 0,
                "incoming_calls": 0,
                "incoming_hours": 0,
                "outgoing_calls": 0,
                "outgoing_hours": 0,
                "missed_calls": 0,
                "rejected_calls": 0,
                "keyboard": 0,
                "mouse": 0,
                "scroll": 0,
                "meetings": 0,
                "meetings_hours": 0
            }
            
            for employee in user_analysis.get("total_hours_per_employee", {}):
                employee_data = user_analysis.get("employee_fincall_data", {}).get(employee, {})
                total_hours = user_analysis.get("total_hours_per_employee", {}).get(employee, 0)
                total_idle_time = user_analysis.get("total_idle_time", {}).get(employee, 0)
                total_days = user_analysis.get("total_days", {}).get(employee, 1)  # Avoid division by zero

                active_hours = total_hours - total_idle_time
                average_active = active_hours / total_days if total_days else 0

                employee_record = {
                    "employee": frappe.get_value("Employee", employee, "employee_name"),
                    "starting_date": current_filters["from_date"],
                    "ending_date": current_filters["to_date"],
                    "total_hours": total_hours,
                    "active_hours": active_hours,
                    "idle_hours": total_idle_time,
                    "average_active": average_active,
                    "incoming_calls": employee_data.get("incoming_fincall_count", 0),
                    "incoming_hours": employee_data.get("total_incoming_duration", 0),
                    "outgoing_calls": employee_data.get("outgoing_fincall_count", 0),
                    "outgoing_hours": employee_data.get("total_outgoing_duration", 0),
                    "missed_calls": employee_data.get("missed_fincall_count", 0),
                    "rejected_calls": employee_data.get("rejected_fincall_count", 0),
                    "keyboard": user_analysis.get("work_intensity_data", {}).get(employee, {}).get("total_keystrokes", 0),
                    "mouse": user_analysis.get("work_intensity_data", {}).get(employee, {}).get("total_mouse_clicks", 0),
                    "scroll": user_analysis.get("work_intensity_data", {}).get(employee, {}).get("total_scroll", 0),
                    "meetings": user_analysis.get("meeting_employee_data", {}).get(employee, {}).get("count", 0),
                    "meetings_hours": user_analysis.get("meeting_employee_data", {}).get(employee, {}).get("duration", 0)
                }

     
                data.append({k: format_duration(v) if k in ['total_hours', 'active_hours', 'idle_hours', 'average_active', 'incoming_hours', 'outgoing_hours', 'meetings_hours'] else v for k, v in employee_record.items()})


                for key in summary:
                    if key not in ['starting_date', 'ending_date']:
                        summary[key] += employee_record[key]

            if len(user_analysis.get("total_hours_per_employee", {})) > 0:
                summary['average_active'] /= len(user_analysis.get("total_hours_per_employee", {}))

            for key in ['total_hours', 'active_hours', 'idle_hours', 'average_active', 'incoming_hours', 'outgoing_hours', 'meetings_hours']:
                summary[key] = format_duration(summary[key])

            summarized_data.append(summary)

        return data, summarized_data

    except Exception as e:
        frappe.log_error(f"Error in get_data: {str(e)}")
        return [], []
def date_range(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)

def weekly_ranges(start_date, end_date):
    ranges = []
    current = start_date
    while current <= end_date:
        # Find the next Sunday
        week_end = current + timedelta(days=(6 - current.weekday() + 7) % 7)
        # If the week_end is beyond the end_date, use end_date instead
        week_end = min(week_end, end_date)
        ranges.append((current, week_end))
        # Start the next week from the day after week_end
        current = week_end + timedelta(days=1)
    return ranges

def monthly_ranges(start_date, end_date):
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

    print(f"Start date: {start_date}, End date: {end_date}")

    ranges = []
    current = start_date.replace(day=1)
    iteration_count = 0
    max_iterations = 100

    while current <= end_date and iteration_count < max_iterations:
        month_end = min(current + relativedelta(months=1, days=-1), end_date)
        ranges.append((current, month_end))  # Changed to return datetime objects
        print(f"Iteration {iteration_count}:")
        print(f"  Current: {current}")
        print(f"  Month end: {month_end}")
        print(f"  Added range: {current} to {month_end}")
        
        new_current = (month_end + timedelta(days=1)).replace(day=1)
        print(f"  Next current: {new_current}")
        
        if new_current <= current:
            print(f"  WARNING: New current ({new_current}) is not greater than current ({current})")
            break
        
        current = new_current
        iteration_count += 1

    if iteration_count == max_iterations:
        frappe.throw(f"Potential infinite loop detected in monthly_ranges function. Last current: {current}, Last month_end: {month_end}")

    return ranges

# User Analysis (User Productivity Stats) Code Starts
@frappe.whitelist()
def user_analysis_data(start_date=None, end_date=None, filters=None):
    employee_condition = ""
    meeting_employee_condition = ""
    if filters.get("employee"):
        employee_condition = f"AND employee = '{filters.get('employee')}'"
        meeting_employee_condition = f"AND mcr.employee = '{filters.get('employee')}'"
    list_data = []
    meeting_total_data = frappe.db.sql(f"""
        SELECT m.meeting_from as start_time, m.meeting_to as end_time, mcr.employee
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE m.meeting_from >= '{start_date} 00:00:00' and m.meeting_to <= '{end_date} 23:59:59' and m.docstatus = 1 {meeting_employee_condition}
    """, as_dict=True)
    calls_total_data = frappe.db.sql(f"""
        SELECT call_datetime as start_time, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time, employee
        FROM `tabEmployee Fincall`
        WHERE date >= '{start_date}' and date <= '{end_date}' {employee_condition} and (calltype != 'Missed' and calltype != 'Rejected')
    """, as_dict=True)
    application_total_data = frappe.db.sql(f"""
        SELECT from_time AS start_time, to_time AS end_time, employee as employee
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' and date <= '{end_date}' {employee_condition}
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
            WHERE m.meeting_from >= DATE('{start_date}') AND m.meeting_to <= DATE('{end_date}') AND m.docstatus = 1 and mcr.employee = '{filters.get("employee")}'
            UNION
            SELECT DATE(`date`) AS date, employee
            FROM `tabApplication Usage log`
            WHERE `date` >= DATE('{start_date}') AND `date` <= DATE('{end_date}') {employee_condition}
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
        WHERE date >= '{start_date}' AND date <= '{end_date}' {employee_condition}
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
        WHERE date >= '{start_date}' AND date <= '{end_date}' {employee_condition}
        GROUP BY employee, calltype
    """, as_dict=True)

    print("Fincall Data:", fincall_data)  # Add this line for debugging

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
        WHERE m.meeting_from >= '{start_date} 00:00:00' AND m.meeting_to <= '{end_date} 23:59:59' and m.docstatus = 1 {meeting_employee_condition}
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
        WHERE time >= '{start_date} 00:00:00' AND time <= '{end_date} 23:59:59' {employee_condition}
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

    # frappe.throw(str(total_hours_per_employee))                        
    return {
        "total_days": total_days,
        "total_hours_per_employee": total_hours_per_employee,
        "total_idle_time": total_idle_time,
        "employee_fincall_data": employee_fincall_data,
        "meeting_employee_data": meetings_external_employee,
        "work_intensity_data": work_intensity_data
    }
# User Analysis (User Productivity Stats) Code Ends

def get_summary_data(summarized_data):
    # Initialize a dictionary to store the totals
    totals = {
        "total_hours": 0,
        "active_hours": 0,
        "calls_hours": 0,
        "meetings_hours": 0
    }

    # Sum up the values across all periods
    for period in summarized_data:
        for key in ['total_hours', 'active_hours', 'meetings_hours']:
            # Convert time string to minutes and add
            h, m = map(int, period[key].replace('h ', ':').replace('m', '').split(':'))
            totals[key] += h * 60 + m
        
        # Calculate calls_hours as the sum of incoming_hours and outgoing_hours
        incoming_h, incoming_m = map(int, period['incoming_hours'].replace('h ', ':').replace('m', '').split(':'))
        outgoing_h, outgoing_m = map(int, period['outgoing_hours'].replace('h ', ':').replace('m', '').split(':'))
        totals['calls_hours'] += (incoming_h + outgoing_h) * 60 + (incoming_m + outgoing_m)

    # Convert time totals back to string format
    for key in totals.keys():
        hours, minutes = divmod(totals[key], 60)
        totals[key] = f"{hours}h {minutes}m"

    return [
        {
            "value": totals["total_hours"],
            "label": "Total Hours",
            "datatype": "Data"
        },
        {
            "value": totals["active_hours"],
            "label": "Active Hours",
            "datatype": "Data",
        },
        {
            "value": totals["calls_hours"],
            "label": "Calls Hours",
            "datatype": "Data",
        },
        {
            "value": totals["meetings_hours"],
            "label": "Meetings Hours",
            "datatype": "Data",
        }
    ]

def get_chart_data(summarized_data):
    labels = []
    total_hours = []
    active_hours = []
    calls_hours = []
    meetings_hours = []

    for period in summarized_data:
        labels.append(f"{period['starting_date']} to {period['ending_date']}")
        
        # Convert time strings to float hours for better visualization
        total_hours.append(time_str_to_float(period['total_hours']))
        active_hours.append(time_str_to_float(period['active_hours']))
        calls_hours.append(time_str_to_float(period['incoming_hours']) + time_str_to_float(period['outgoing_hours']))
        meetings_hours.append(time_str_to_float(period['meetings_hours']))

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": "Total Hours", "values": total_hours},
                {"name": "Active Hours", "values": active_hours},
                {"name": "Calls Hours", "values": calls_hours},
                {"name": "Meetings Hours", "values": meetings_hours}
            ]
        },
        "type": "line",
        "height": 300,
        "colors": ["#7cd6fd", "#5e64ff", "#ffa00a", "#ff5858"],
        "axisOptions": {
            "xAxisMode": "tick",
            "xIsSeries": 1
        },
        "barOptions": {
            "spaceRatio": 0.2
        },
        "scrollable": True,
        "scrollHeight": 300,
        "scrollWidth": 1000
    }

def time_str_to_float(time_str):
    hours, minutes = map(int, time_str.replace('h ', ':').replace('m', '').split(':'))
    return round(hours + minutes / 60, 2)
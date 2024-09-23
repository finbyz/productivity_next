# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from datetime import datetime, timedelta
from productivity_next.api import calculate_total_working_hours
from frappe.utils import get_timespan_date_range

def execute(filters=None):
    columns = get_columns(filters)
    from_date, to_date = get_timespan_date_range((filters.get("timespan")).lower())
    data = get_data(from_date, to_date)
    return columns, data

def get_columns(filters=None):
    columns = [
        {
            "fieldname": "employee",
            "label": _("Employee"),
            "fieldtype": "Data",
            "options": "Employee",
            "width": 200
        },
        {
            "fieldname": "productivity_score",
            "label": _("Productivity Score"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "total_hours",
            "label": _("Total Hours"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "active_hours",
            "label": _("Active Hours"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "idle_hours",
            "label": _("Idle Hours"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "incoming_calls",
            "label": _("Incoming Calls"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "incoming_hours",
            "label": _("Incoming Hours"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "outgoing_calls",
            "label": _("Outgoing Calls"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "outgoing_hours",
            "label": _("Outgoing Hours"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "missed_calls",
            "label": _("Missed Calls"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "rejected_calls",
            "label": _("Rejected Calls"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "meetings",
            "label": _("Meetings"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "meetings_hours",
            "label": _("Meetings Hours"),
            "fieldtype": "Data",
            "width": 150
        }
    ]

    return columns

def get_data(from_date, to_date):
    data = []
    user_analysis = user_analysis_data(from_date, to_date)

    # Initialize total counters
    total_hours_sum = 0
    active_hours_sum = 0
    idle_hours_sum = 0
    incoming_calls_sum = 0
    incoming_hours_sum = 0
    outgoing_calls_sum = 0
    outgoing_hours_sum = 0
    missed_calls_sum = 0
    rejected_calls_sum = 0
    meetings_sum = 0
    meetings_hours_sum = 0

    for employee in user_analysis.get("total_hours_per_employee", {}):
        employee_data = user_analysis.get("employee_fincall_data", {}).get(employee, {})
        total_hours = user_analysis.get("total_hours_per_employee", {}).get(employee, 0)
        total_idle_time = user_analysis.get("total_idle_time", {}).get(employee, 0)

        active_hours = total_hours - total_idle_time
        employee_record = {
            "employee": frappe.get_value("Employee", employee, "employee_name"),
            "productivity_score": round((((active_hours/3600)/user_analysis.get("productivity_score", {}).get(employee, 0))*100),0),
            "total_hours": total_hours,
            "active_hours": active_hours,
            "idle_hours": total_idle_time,
            "incoming_calls": employee_data.get("incoming_fincall_count", 0),
            "incoming_hours": employee_data.get("total_incoming_duration", 0),
            "outgoing_calls": employee_data.get("outgoing_fincall_count", 0),
            "outgoing_hours": employee_data.get("total_outgoing_duration", 0),
            "missed_calls": employee_data.get("missed_fincall_count", 0),
            "rejected_calls": employee_data.get("rejected_fincall_count", 0),
            "meetings": user_analysis.get("meeting_employee_data", {}).get(employee, {}).get("count", 0),
            "meetings_hours": user_analysis.get("meeting_employee_data", {}).get(employee, {}).get("duration", 0)
        }

        # Accumulate totals
        total_hours_sum += total_hours
        active_hours_sum += active_hours
        idle_hours_sum += total_idle_time
        incoming_calls_sum += employee_data.get("incoming_fincall_count", 0)
        incoming_hours_sum += employee_data.get("total_incoming_duration", 0)
        outgoing_calls_sum += employee_data.get("outgoing_fincall_count", 0)
        outgoing_hours_sum += employee_data.get("total_outgoing_duration", 0)
        missed_calls_sum += employee_data.get("missed_fincall_count", 0)
        rejected_calls_sum += employee_data.get("rejected_fincall_count", 0)
        meetings_sum += user_analysis.get("meeting_employee_data", {}).get(employee, {}).get("count", 0)
        meetings_hours_sum += user_analysis.get("meeting_employee_data", {}).get(employee, {}).get("duration", 0)

        data.append({k: format_duration(v) if k in ['total_hours', 'active_hours', 'idle_hours', 'incoming_hours', 'outgoing_hours', 'meetings_hours'] else v for k, v in employee_record.items()})

    # Add totals row
    totals_row = {
        "employee": "Total",
        "productivity_score": "",  # You might want to leave this blank or calculate a total score if appropriate
        "total_hours": total_hours_sum,
        "active_hours": active_hours_sum,
        "idle_hours": idle_hours_sum,
        "incoming_calls": incoming_calls_sum,
        "incoming_hours": incoming_hours_sum,
        "outgoing_calls": outgoing_calls_sum,
        "outgoing_hours": outgoing_hours_sum,
        "missed_calls": missed_calls_sum,
        "rejected_calls": rejected_calls_sum,
        "meetings": meetings_sum,
        "meetings_hours": meetings_hours_sum
    }

    # Format totals row values
    formatted_totals_row = {k: format_duration(v) if k in ['total_hours', 'active_hours', 'idle_hours', 'incoming_hours', 'outgoing_hours', 'meetings_hours'] else v for k, v in totals_row.items()}
    data.append(formatted_totals_row)

    return data


def format_duration(duration_seconds):
    try:
        duration_seconds = float(duration_seconds)
        total_hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        return f"{total_hours}h {minutes}m"
    except ValueError:
        return "0h 0m"
@frappe.whitelist()
def get_employees():
    employees = frappe.get_all("Employee", filters={"status": "Active"}, fields=["name", "employee_name"])
    if not employees:
        return []
    return employees

# User Analysis (User Productivity Stats) Code Starts
@frappe.whitelist()
def user_analysis_data(start_date=None, end_date=None):
    employees = get_employees()
    if not employees:
        return {}
    start_date_ = str(start_date) + " 00:00:00"
    end_date_ = str(end_date) + " 23:59:59"
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
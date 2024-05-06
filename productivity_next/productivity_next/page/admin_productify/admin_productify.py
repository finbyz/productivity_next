
from datetime import datetime,time,timedelta
import frappe

@frappe.whitelist() 
def version_conditions(user,start_date=None, end_date=None):
    now = datetime.now()
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00')
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d 00:00:00')
    
    if end_date is None:
        end_date = now.strftime('%Y-%m-%d 23:59:59')
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d 23:59:59')
    if user != "Administrator":
        email = frappe.db.get_value("Employee", user, "company_email")
        condition = f"WHERE owner = '{email}' AND DATE(creation) >= '{start_date}' AND DATE(creation) <= '{end_date}'"
    else:
        condition = f"WHERE DATE(creation) >= '{start_date}' AND DATE(creation) <= '{end_date}'"

    return condition

@frappe.whitelist()
def get_user_data(user,start_date=None, end_date=None):
    version_conditions_str = version_conditions(user,start_date,end_date)
    start_date, end_date = set_dates(start_date, end_date)

    conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"
    conditions_2 = f"AND m.meeting_from >= '{start_date}' AND m.meeting_to <= '{end_date}'"
    def calculate_idle_time(start_date,end_date):
        # frappe.throw(f"User: {user}, Start Date: {start_date}, End Date: {end_date}")
        # user = "HR-EMP-00011"
        conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"
        conditions_2 = f"AND DATE(m.meeting_from) >= '{start_date}' AND DATE(m.meeting_to) <= '{end_date}'"
        conditions_3 = f"WHERE DATE(time) >= '{start_date}' and DATE(time) <= '{end_date}'"
            # frappe.throw(conditions)
        def convert_times(data):
            results = []
            start_times = {}
            for record in data:
                employee = record['employee']
                status = record['status']
                time = record['start_time']
                if status == 'start':
                    start_times[employee] = time
                elif status == 'end' and employee in start_times:
                    new_entry = {'type': 'Idle', 'start_time': start_times[employee], 'stop_time': time,"employee":employee}
                    results.append(new_entry)
                    del start_times[employee]
            return results

        # Function to convert fincall logs
        def convert_time_data(time_entries):
            formatted_entries = []
            for entry in time_entries:
                formatted_entry = {'type': 'Call', 'start_time': entry['start_time'], 'stop_time': entry['end_time'][:8],"employee":entry['employee']}
                formatted_entries.append(formatted_entry)
            return formatted_entries

        # Function to convert meeting logs
        def convert_meeting_data(meeting_entries):
            formatted_entries = []
            for entry in meeting_entries:
                formatted_entry = {'type': 'Meeting', 'start_time': entry['start_time'], 'stop_time': entry['end_time'],"employee":entry['employee']}
                formatted_entries.append(formatted_entry)
            return formatted_entries

        # Fetch and process idle time data
        idle_time_data = frappe.db.sql(f"""
        select  DATE_FORMAT(time, '%H:%i:%s') as start_time, status, employee
        from `tabIdle Time Log`
        {conditions_3}
        """, as_dict=True)
        idle_time_data = convert_times(idle_time_data)

        # Fetch and process fincall data
        fincall_time_data = frappe.db.sql(f"""
        SELECT DATE_FORMAT(call_datetime, '%H:%i:%s') AS start_time,
            ADDTIME(DATE_FORMAT(call_datetime, '%H:%i:%s'), SEC_TO_TIME(duration)) AS end_time, employee
        FROM `tabFincall Log`
        {conditions}
        """, as_dict=True)
        fincall_time_data = convert_time_data(fincall_time_data)
        # frappe.throw(str(fincall_time_data))
        # Fetch and process meeting data
        meeting_time_data = frappe.db.sql(f"""
        select DATE_FORMAT(m.meeting_from, '%H:%i:%s') AS start_time, DATE_FORMAT(m.meeting_to, '%H:%i:%s') AS end_time, mcr.employee
        from `tabMeeting` as m
        join `tabMeeting Company Representative` as mcr on m.name = mcr.parent
        WHERE m.docstatus = 1
        {conditions_2}
        """, as_dict=True)
        meeting_time_data = convert_meeting_data(meeting_time_data)
        # frappe.throw(str(meeting_time_data))

        combined_time_data = idle_time_data + fincall_time_data + meeting_time_data
        def calculate_idle_time_user(data):
            employee_idle_time = {}
            
            # Time format in the data
            time_format = "%H:%M:%S"
            
            for record in data:
                start_time = datetime.strptime(record['start_time'], time_format)
                stop_time = datetime.strptime(record['stop_time'], time_format)
                
                # Calculate difference in seconds
                idle_duration = (stop_time - start_time).total_seconds()
                
                # Sum up idle time per employee
                if record['employee'] in employee_idle_time:
                    employee_idle_time[record['employee']] += idle_duration
                else:
                    employee_idle_time[record['employee']] = idle_duration
            
            # Convert to list of dictionaries
            result_list = [{'employee': emp, 'total_idle_time': int(time)} for emp, time in employee_idle_time.items()]
            return result_list

        # Calculate idle time for each employee
        idle_times_list = calculate_idle_time_user(combined_time_data)
        
        # Calculate idle time for each employee

        def parse_times(data):
            idle_periods = []
            active_periods = []
            for entry in data:
                from datetime import datetime
                start_time = datetime.strptime(entry["start_time"], "%H:%M:%S")
                stop_time = datetime.strptime(entry["stop_time"], "%H:%M:%S")
                if entry["type"] == "Idle":
                    idle_periods.append((start_time, stop_time))
                else:
                    active_periods.append((start_time, stop_time))
            return idle_periods, merge_overlapping_times(active_periods)

        def merge_overlapping_times(times):
            # Sort times by start time
            times_sorted = sorted(times, key=lambda x: x[0])
            merged_times = []

            # Merge overlapping times
            for current_start, current_end in times_sorted:
                if merged_times and merged_times[-1][1] >= current_start:
                    merged_times[-1][1] = max(merged_times[-1][1], current_end)
                else:
                    merged_times.append([current_start, current_end])
            
            return merged_times


        def calculate_duration(periods):
            from datetime import timedelta
            total_duration = timedelta()
            for start, stop in periods:
                total_duration += (stop - start)
            return total_duration

        def calculate_overlap(period1, period2):
            start1, end1 = period1
            start2, end2 = period2
            overlap_start = max(start1, start2)
            overlap_end = min(end1, end2)
            if overlap_start < overlap_end:
                return overlap_end - overlap_start
            return timedelta()

        idle_periods, active_periods = parse_times(combined_time_data)

        total_idle_time = calculate_duration(idle_periods)

        for idle_period in idle_periods:
            for active_period in active_periods:
                total_idle_time -= calculate_overlap(idle_period, active_period)

        # print("Net Idle Time:", total_idle_time)

        # frappe.throw(f"Total Idle Time: {str(total_idle_time)}")
        # Time string
        time_str = str(total_idle_time)

        # Parse the string into a datetime object
        time_object = datetime.strptime(time_str, "%H:%M:%S")

        # Calculate the total seconds
        total_seconds = time_object.hour * 3600 + time_object.minute * 60 + time_object.second
        # frappe.throw(str(total_seconds))
        return {"total_seconds":total_seconds,"idle_times_list":idle_times_list}


    # No need to parse and reformat if we're just setting the time part explicitly
    start_date_time = start_date
    end_date_time = end_date

    # If you need date objects for some operations, you can directly convert
    start_datetime_obj = datetime.strptime(start_date_time, "%Y-%m-%d %H:%M:%S")
    end_datetime_obj = datetime.strptime(end_date_time, "%Y-%m-%d %H:%M:%S")

    # The formatted date strings can be obtained without additional parsing if not needed elsewhere
    formatted_start_date = start_datetime_obj.strftime("%Y-%m-%d")
    formatted_end_date = end_datetime_obj.strftime("%Y-%m-%d")

    total_idle_time_in_seconds = calculate_idle_time(formatted_start_date,formatted_end_date).get("total_seconds",0)
    total_idle_time_user = calculate_idle_time(formatted_start_date,formatted_end_date).get("idle_times_list",0)
    # frappe.throw(str(total_idle_time_user))
    # Combined Query for Count and Total Duration of Calls by Call Type
    fincall_data = frappe.db.sql(f"""
        SELECT 
            calltype,
            COUNT(*) AS fincall_count,
            COALESCE(SUM(duration), 0) AS total_duration
        FROM `tabFincall Log`
        {conditions}
        GROUP BY calltype
    """, as_dict=True)

    # Extracting data for each call type
    incoming_fincall_count = next((item['fincall_count'] for item in fincall_data if item['calltype'] == 'Incoming'), 0)
    outgoing_fincall_count = next((item['fincall_count'] for item in fincall_data if item['calltype'] == 'Outgoing'), 0)
    missed_fincall_count = next((item['fincall_count'] for item in fincall_data if item['calltype'] == 'Missed'), 0)
    rejected_fincall_count = next((item['fincall_count'] for item in fincall_data if item['calltype'] == 'Rejected'), 0)

    total_incoming_fincall_count = next((item['total_duration'] for item in fincall_data if item['calltype'] == 'Incoming'), 0)
    total_outgoing_fincall_count = next((item['total_duration'] for item in fincall_data if item['calltype'] == 'Outgoing'), 0)
    total_missed_fincall_count = next((item['total_duration'] for item in fincall_data if item['calltype'] == 'Missed'), 0)

    # TOTAL HOURS CARD
    filters = {"time": ["between", [start_date, end_date]]}

    # Fetch logs from the database
    all_logs = frappe.db.get_list("Application Checkin Checkout",
                                filters=filters,
                                fields=["status", "time"],
                                order_by="creation asc")

    usage_time = 0
    last_status = None

    # Loop through logs to calculate the total duration of logged "In" sessions
    for row in all_logs:
        if row['status'] == "In" and last_status != "In":
            start_time = row['time']  # Set start time when status changes to "In" from non-"In"
        elif row['status'] == "Out" and last_status == "In":
            end_time = row['time']  # Calculate duration when status changes from "In" to "Out"
            usage_time += (end_time - start_time).total_seconds()
        last_status = row['status']  # Update the last_status for the next iteration

    # Convert total usage time from seconds to hours
    total_hours = usage_time # Convert seconds to hours
    # frappe.throw(str(total_hours))
    # frappe.throw(str(total_hours / 60 / 60))  
    # IDLE TIME CARD
    total_idle_time_days = frappe.db.sql(f"""
        SELECT 
        SUM(CASE WHEN TIME_TO_SEC(TIMEDIFF(to_time, from_time)) > 120 THEN TIME_TO_SEC(TIMEDIFF(to_time, from_time)) ELSE 0 END) AS total_idle_duration_seconds,
        COUNT(DISTINCT date) AS application_usage_days
    FROM 
        `tabApplication Usage log`
        {conditions};""",as_dict=1)

    total_days = total_idle_time_days[0]['application_usage_days'] if total_idle_time_days else 0


    # Constructing a SQL query that adapts based on whether the user is an Administrator or not
    sql_query = f"""
    SELECT 
        SUM(TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))) AS total_meeting_duration
    FROM `tabMeeting` as m
    where m.docstatus = 1
    {conditions_2}
    GROUP BY m.docstatus
    """

    # Executing the query
    if user != "Administrator":
        meetings = frappe.db.sql(sql_query, (user,), as_dict=True)
    else:
        meetings = frappe.db.sql(sql_query, as_dict=True)

    # Application Usage Log Count, Top 10 Doc's Used Cards
    total_counts = frappe.db.sql(f"""
        SELECT
            (SELECT COUNT(DISTINCT application_name) FROM `tabApplication Usage log`{conditions})  AS application_usage,
            (SELECT COUNT(*) FROM `tabVersion` {version_conditions_str}) AS version_count
        """, as_dict=1)[0]
    


    return {
        "application_usage": total_counts['application_usage'],
        "version_count": total_counts['version_count'],
        "incoming_fincall_count": incoming_fincall_count,
        "outgoing_fincall_count": outgoing_fincall_count,
        "missed_fincall_count": missed_fincall_count,
        "rejected_fincall_count": rejected_fincall_count,
        "total_hours": total_hours,
        "total_incoming_fincall_count": total_incoming_fincall_count,
        "total_outgoing_fincall_count": total_outgoing_fincall_count,
        "total_missed_fincall_count": total_missed_fincall_count,
        "total_idle_time": total_idle_time_in_seconds,
        "total_days": total_days,
        "total_time_on_calls": fincall_data[0]['total_duration'] if fincall_data else 0,
        "total_meeting_duration": meetings[0].total_meeting_duration if meetings else 0,
        "total_meeting_count": meetings[0].meeting_count if meetings else 0,
        "total_idle_time_user":total_idle_time_user
    }


from datetime import datetime, timedelta

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

# Example of using the function:
# start_date, end_date = set_dates('2022-01-01', '2022-12-31')
# print(start_date, end_date)
# This prints: '2022-01-01 00:00:00' '2022-12-31 23:59:59'


@frappe.whitelist()
def get_admin_data(user,start_date=None, end_date=None):
    version_conditions_str = version_conditions(user,start_date,end_date)
    start_date, end_date = set_dates(start_date, end_date)

    conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"
    conditions_2 = f"AND m.meeting_from >= '{start_date}' AND m.meeting_to <= '{end_date}'"
    def calculate_idle_time(start_date,end_date):
        # frappe.throw(f"User: {user}, Start Date: {start_date}, End Date: {end_date}")
        # user = "HR-EMP-00011"
        conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"
        conditions_2 = f"AND DATE(m.meeting_from) >= '{start_date}' AND DATE(m.meeting_to) <= '{end_date}'"
        conditions_3 = f"WHERE DATE(time) >= '{start_date}' and DATE(time) <= '{end_date}'"
            # frappe.throw(conditions)
        def convert_times(data):
            results = []
            start_times = {}
            for record in data:
                employee = record['employee']
                status = record['status']
                time = record['start_time']
                if status == 'start':
                    start_times[employee] = time
                elif status == 'end' and employee in start_times:
                    new_entry = {'type': 'Idle', 'start_time': start_times[employee], 'stop_time': time,"employee":employee}
                    results.append(new_entry)
                    del start_times[employee]
            return results

        # Function to convert fincall logs
        def convert_time_data(time_entries):
            formatted_entries = []
            for entry in time_entries:
                formatted_entry = {'type': 'Call', 'start_time': entry['start_time'], 'stop_time': entry['end_time'][:8],"employee":entry['employee']}
                formatted_entries.append(formatted_entry)
            return formatted_entries

        # Function to convert meeting logs
        def convert_meeting_data(meeting_entries):
            formatted_entries = []
            for entry in meeting_entries:
                formatted_entry = {'type': 'Meeting', 'start_time': entry['start_time'], 'stop_time': entry['end_time'],"employee":entry['employee']}
                formatted_entries.append(formatted_entry)
            return formatted_entries

        # Fetch and process idle time data
        idle_time_data = frappe.db.sql(f"""
        select  DATE_FORMAT(time, '%H:%i:%s') as start_time, status, employee
        from `tabIdle Time Log`
        {conditions_3}
        """, as_dict=True)
        idle_time_data = convert_times(idle_time_data)

        # Fetch and process fincall data
        fincall_time_data = frappe.db.sql(f"""
        SELECT DATE_FORMAT(call_datetime, '%H:%i:%s') AS start_time,
            ADDTIME(DATE_FORMAT(call_datetime, '%H:%i:%s'), SEC_TO_TIME(duration)) AS end_time, employee
        FROM `tabFincall Log`
        {conditions}
        """, as_dict=True)
        fincall_time_data = convert_time_data(fincall_time_data)
        # frappe.throw(str(fincall_time_data))
        # Fetch and process meeting data
        meeting_time_data = frappe.db.sql(f"""
        select DATE_FORMAT(m.meeting_from, '%H:%i:%s') AS start_time, DATE_FORMAT(m.meeting_to, '%H:%i:%s') AS end_time, mcr.employee
        from `tabMeeting` as m
        join `tabMeeting Company Representative` as mcr on m.name = mcr.parent
        WHERE m.docstatus = 1
        {conditions_2}
        """, as_dict=True)
        meeting_time_data = convert_meeting_data(meeting_time_data)
        # frappe.throw(str(meeting_time_data))

        combined_time_data = idle_time_data + fincall_time_data + meeting_time_data
        def calculate_idle_time_user(data):
            employee_idle_time = {}
            
            # Time format in the data
            time_format = "%H:%M:%S"
            
            for record in data:
                start_time = datetime.strptime(record['start_time'], time_format)
                stop_time = datetime.strptime(record['stop_time'], time_format)
                
                # Calculate difference in seconds
                idle_duration = (stop_time - start_time).total_seconds()
                
                # Sum up idle time per employee
                if record['employee'] in employee_idle_time:
                    employee_idle_time[record['employee']] += idle_duration
                else:
                    employee_idle_time[record['employee']] = idle_duration
            
            # Convert to list of dictionaries
            result_list = [{'employee': emp, 'total_idle_time': int(time)} for emp, time in employee_idle_time.items()]
            return result_list

        # Calculate idle time for each employee
        idle_times_list = calculate_idle_time_user(combined_time_data)
        
        # Calculate idle time for each employee

        def parse_times(data):
            idle_periods = []
            active_periods = []
            for entry in data:
                from datetime import datetime
                start_time = datetime.strptime(entry["start_time"], "%H:%M:%S")
                stop_time = datetime.strptime(entry["stop_time"], "%H:%M:%S")
                if entry["type"] == "Idle":
                    idle_periods.append((start_time, stop_time))
                else:
                    active_periods.append((start_time, stop_time))
            return idle_periods, merge_overlapping_times(active_periods)

        def merge_overlapping_times(times):
            # Sort times by start time
            times_sorted = sorted(times, key=lambda x: x[0])
            merged_times = []

            # Merge overlapping times
            for current_start, current_end in times_sorted:
                if merged_times and merged_times[-1][1] >= current_start:
                    merged_times[-1][1] = max(merged_times[-1][1], current_end)
                else:
                    merged_times.append([current_start, current_end])
            
            return merged_times


        def calculate_duration(periods):
            from datetime import timedelta
            total_duration = timedelta()
            for start, stop in periods:
                total_duration += (stop - start)
            return total_duration

        def calculate_overlap(period1, period2):
            start1, end1 = period1
            start2, end2 = period2
            overlap_start = max(start1, start2)
            overlap_end = min(end1, end2)
            if overlap_start < overlap_end:
                return overlap_end - overlap_start
            return timedelta()

        idle_periods, active_periods = parse_times(combined_time_data)

        total_idle_time = calculate_duration(idle_periods)

        for idle_period in idle_periods:
            for active_period in active_periods:
                total_idle_time -= calculate_overlap(idle_period, active_period)

        # print("Net Idle Time:", total_idle_time)

        # frappe.throw(f"Total Idle Time: {str(total_idle_time)}")
        # Time string
        time_str = str(total_idle_time)

        # Parse the string into a datetime object
        time_object = datetime.strptime(time_str, "%H:%M:%S")

        # Calculate the total seconds
        total_seconds = time_object.hour * 3600 + time_object.minute * 60 + time_object.second
        # frappe.throw(str(total_seconds))
        return {"total_seconds":total_seconds,"idle_times_list":idle_times_list}


    # No need to parse and reformat if we're just setting the time part explicitly
    start_date_time = start_date
    end_date_time = end_date

    # If you need date objects for some operations, you can directly convert
    start_datetime_obj = datetime.strptime(start_date_time, "%Y-%m-%d %H:%M:%S")
    end_datetime_obj = datetime.strptime(end_date_time, "%Y-%m-%d %H:%M:%S")

    # The formatted date strings can be obtained without additional parsing if not needed elsewhere
    formatted_start_date = start_datetime_obj.strftime("%Y-%m-%d")
    formatted_end_date = end_datetime_obj.strftime("%Y-%m-%d")

    total_idle_time_in_seconds = calculate_idle_time(formatted_start_date,formatted_end_date).get("total_seconds",0)
    total_idle_time_user = calculate_idle_time(formatted_start_date,formatted_end_date).get("idle_times_list",0)

    total_hours_data = frappe.db.sql("""
    SELECT 
        employee,
        SUM(
            CASE 
                WHEN status = 'Out' THEN TIMESTAMPDIFF(SECOND, prev_time, time) 
                ELSE 0 
            END
        ) / 3600.0 AS total_hours
    FROM (
        SELECT
            employee,
            status,
            time,
            LAG(time) OVER (PARTITION BY employee ORDER BY time) AS prev_time,
            LAG(status) OVER (PARTITION BY employee ORDER BY time) AS prev_status
        FROM 
            `tabApplication Checkin Checkout`
        WHERE 
            time BETWEEN '2023-05-06' AND '2024-05-06'
    ) AS log_details
    WHERE 
        status = 'Out' AND prev_status = 'In'
    GROUP BY 
        employee;
    """,as_dict=True)

    return { "total_hours_data":total_hours_data}

from datetime import datetime,time,timedelta
import frappe
from frappe import utils

def get_conditions(user):
    """Generates SQL conditions based on the user role."""
    if user != "Administrator":
        email = frappe.db.get_value("Employee", user, "company_email")
        employee_cond = f"employee = '{user}' AND "
        email_cond = f"owner = '{email}' AND "
    else:
        employee_cond = email_cond = ""
    common_cond = "DATE(creation) >= CURDATE() - INTERVAL 1 YEAR"
    
    return {
        "employee_cond": f"WHERE {employee_cond}{common_cond}",
        "email_cond": f"WHERE {email_cond}{common_cond}",
    }

# HEATMAP
@frappe.whitelist()
def get_heatmap_data(user, date):
    conditions = get_conditions(user)
    queries = [
        f"""
        SELECT DATE(creation) as date, COUNT(*) as count
        FROM `tabApplication Usage log`
        {conditions['employee_cond']}
        GROUP BY DATE(creation)
        """,
        f"""
        SELECT DATE(call_datetime) as date, COUNT(*) as fincall_count
        FROM `tabEmployee Fincall`
        {conditions['employee_cond']}
        GROUP BY DATE(call_datetime)
        """,
        f"""
        SELECT DATE(creation) as date, COUNT(*) as activity_count
        FROM `tabVersion`
        {conditions['email_cond']}
        GROUP BY DATE(creation)
        """
    ]

    data = []
    for query in queries:
        data.extend(frappe.db.sql(query, as_dict=1))

    combined_data = {}
    for item in data:
        date = item["date"]
        if date not in combined_data:
            combined_data[date] = {
                "count": 0,
                "fincall_count": 0,
                "activity_count": 0
            }
        combined_data[date]["count"] += item.get("count", 0)
        combined_data[date]["fincall_count"] += item.get("fincall_count", 0)
        combined_data[date]["activity_count"] += item.get("activity_count", 0)

    final_dict = {}
    for date, counts in combined_data.items():
        timestamp = datetime.combine(date, time()).timestamp()
        final_dict[timestamp] = sum(counts.values())

    return final_dict

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
        condition = f"WHERE creation >= '{start_date}' AND creation <= '{end_date}'"

    return condition

@frappe.whitelist()
def get_user_data(user,start_date=None, end_date=None):
    version_conditions_str = version_conditions(user,start_date,end_date)
    ignore_doctype = ['File',"Communication","Fincall Log","Custom Field","DocType","Web Page"]

    # Convert the list into a format suitable for SQL query ("'DocType1', 'DocType2', 'DocType3'")
    ignore_doctype_str = ','.join(f"'{doc}'" for doc in ignore_doctype)

    # Check if the list is not empty to add a condition to the query
    if ignore_doctype_str:
        ignore_condition = f"AND ref_doctype NOT IN ({ignore_doctype_str})"
    else:
        ignore_condition = ""
    start_date, end_date = set_dates(start_date, end_date)

    if user != "Administrator":
        conditions = f"WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}'"
        conditions_2 = f"AND mcr.employee = '{user}' AND DATE(m.meeting_from) >= '{start_date}' AND DATE(m.meeting_to) <= '{end_date}'"
    else:
        conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"
        conditions_2 = f"AND DATE(m.meeting_from) >= '{start_date}' AND DATE(m.meeting_to) <= '{end_date}'"

    
    # Function to convert idle time logs
    def calculate_idle_time(user,start_date,end_date):
        # frappe.throw(f"User: {user}, Start Date: {start_date}, End Date: {end_date}")
        # start_date = "2024-04-29"
        # end_date = "2024-04-29"
        # user = "HR-EMP-00011"
        if user != "Administrator":
            conditions = f"WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}'"
            conditions_2 = f"AND mcr.employee = '{user}' AND DATE(m.meeting_from) >= '{start_date}' AND DATE(m.meeting_to) <= '{end_date}'"
            conditions_3 = f"WHERE employee = '{user}' AND DATE(time) >= '{start_date}' and DATE(time) <= '{end_date}'"
        else:
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
                    new_entry = {'type': 'Idle', 'start_time': start_times[employee], 'stop_time': time}
                    results.append(new_entry)
                    del start_times[employee]
            # frappe.throw(str(results))
            return results

        # Function to convert Employee Fincalls
        def convert_time_data(time_entries):
            formatted_entries = []
            for entry in time_entries:
                formatted_entry = {'type': 'Call', 'start_time': entry['start_time'], 'stop_time': entry['end_time'][:8]}
                formatted_entries.append(formatted_entry)
            return formatted_entries

        # Function to convert meeting logs
        def convert_meeting_data(meeting_entries):
            formatted_entries = []
            for entry in meeting_entries:
                formatted_entry = {'type': 'Meeting', 'start_time': entry['start_time'], 'stop_time': entry['end_time']}
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
        FROM `tabEmployee Fincall`
        {conditions}
        """, as_dict=True)
        fincall_time_data = convert_time_data(fincall_time_data)

        # Fetch and process meeting data
        meeting_time_data_ = frappe.db.sql(f"""
        select DATE_FORMAT(m.meeting_from, '%H:%i:%s') AS start_time, DATE_FORMAT(m.meeting_to, '%H:%i:%s') AS end_time, mcr.employee,m.meeting_from as start_date, m.meeting_to as end_date
        from `tabMeeting` as m
        join `tabMeeting Company Representative` as mcr on m.name = mcr.parent
        WHERE m.docstatus = 1
        {conditions_2}
        """, as_dict=True)
        # frappe.throw(str(meeting_time_data_))
        meeting_time_data = convert_meeting_data(meeting_time_data_)
        # Combine all time data into a single list
        combined_time_data = idle_time_data + fincall_time_data + meeting_time_data
        # frappe.throw(str(combined_time_data))
        # Print or use the combined data
        # print(combined_time_data)

        def parse_times(data):
            idle_periods = []
            active_periods = []
            eight_hours = timedelta(hours=8)
            # frappe.throw(str(data))
            for entry in data:
                # Parse start and stop times
                start_time = datetime.strptime(entry["start_time"], "%H:%M:%S")
                stop_time = datetime.strptime(entry["stop_time"], "%H:%M:%S")
                duration = stop_time - start_time

            # Check duration is not greater than 8 hours and that times are on the same day
                if duration <= eight_hours:
                    # Append periods to the respective lists based on type
                    if entry["type"] == "Idle":
                        idle_periods.append((start_time, stop_time))
                    else:
                        active_periods.append((start_time, stop_time))
                else:
                    # Optionally handle cases where start and stop times span multiple days
                    # This code simply skips such entries, but you could implement additional logic as needed
                    continue
            
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
            total_duration = timedelta()
            max_duration = timedelta(hours=8)  # Define the maximum duration allowed to be added
            day_duration = timedelta(days=1)   # Define the threshold for ignoring long periods
            
            for start, stop in periods:
                duration = stop - start
                # Check if the duration is less than 8 hours and less than a day
                if duration < max_duration and duration < day_duration:
                    total_duration += duration
                    
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
        return total_seconds,meeting_time_data_

    # No need to parse and reformat if we're just setting the time part explicitly
    start_date_time = start_date
    end_date_time = end_date

    # If you need date objects for some operations, you can directly convert
    start_datetime_obj = datetime.strptime(start_date_time, "%Y-%m-%d %H:%M:%S")
    end_datetime_obj = datetime.strptime(end_date_time, "%Y-%m-%d %H:%M:%S")

    # The formatted date strings can be obtained without additional parsing if not needed elsewhere
    formatted_start_date = start_datetime_obj.strftime("%Y-%m-%d")
    formatted_end_date = end_datetime_obj.strftime("%Y-%m-%d")

    total_idle_time_in_seconds,meeting_data_query = calculate_idle_time(user,formatted_start_date,formatted_end_date)
    # Combined Query for Count and Total Duration of Calls by Call Type
    fincall_data = frappe.db.sql(f"""
        SELECT 
            calltype,
            COUNT(*) AS fincall_count,
            COALESCE(SUM(duration), 0) AS total_duration
        FROM `tabEmployee Fincall`
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
    if user != "Administrator":
        filters = {"employee": user, "time": ["Between", [start_date, end_date]]}
    else:
        filters = {"time": ["between", [start_date, end_date]]}

    # Fetch logs from the database
    all_logs = frappe.db.get_list("Application Checkin Checkout",
                                filters=filters,
                                fields=["status", "time"],
                                order_by="creation asc")
    # frappe.throw(str(all_logs))
    # frappe.throw(str(meeting_data_query))
    time_intervals = []

    # Add log intervals
    for i in range(len(all_logs) - 1):
        if all_logs[i]['status'] == 'In' and all_logs[i + 1]['status'] == 'Out':
            time_intervals.append((all_logs[i]['time'], all_logs[i + 1]['time']))

    # Add meeting intervals
    for mtg in meeting_data_query:
        time_intervals.append((mtg['start_date'], mtg['end_date']))

    # Sort intervals by start time
    time_intervals.sort(key=lambda x: x[0])

    # Merge overlapping intervals
    merged_intervals = []
    for start, end in time_intervals:
        if not merged_intervals or merged_intervals[-1][1] < start:
            merged_intervals.append((start, end))
        else:
            merged_intervals[-1] = (merged_intervals[-1][0], max(merged_intervals[-1][1], end))

    # Calculate total usage time in seconds
    usage_time = sum((end - start).total_seconds() for start, end in merged_intervals)

    # Convert total usage time from seconds to hours
    total_hours = usage_time
    # frappe.throw(str(total_hours / 60 / 60))  
    # IDLE TIME CARD
    # Fetch application usage days

    application_usage_days = frappe.db.sql(f"""
        SELECT DISTINCT DATE(`date`) AS date 
        FROM `tabApplication Usage log`
        {conditions};
    """, as_dict=True, pluck='date')

    # Fetch meeting usage days
    meeting_usage_days = frappe.db.sql(f"""
        SELECT DISTINCT DATE(m.meeting_from) AS date 
        FROM `tabMeeting` AS m 
        JOIN `tabMeeting Company Representative` AS mcr 
        ON m.name = mcr.parent 
        {conditions_2}
    """, as_dict=True, pluck='date')

    total_days = len(set(application_usage_days + meeting_usage_days))

    # Extract dates from the query results
    # total_days_set.add(entry['application_usage_day'] for entry in application_usage_days)
    # total_days_set.add(entry['meeting_usage_day'] for entry in meeting_usage_days)
    # frappe.throw(str(total_days_set))
    # total_days = len(total_days_set)

    # Constructing a SQL query that adapts based on whether the user is an Administrator or not
    sql_query = f"""
    SELECT 
        SUM(CASE 
                WHEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from)) > 0 THEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))
                ELSE 0 
            END) AS total_meeting_duration,
        COUNT(DISTINCT m.name) as meeting_count
    FROM `tabMeeting` as m
    JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent WHERE mcr.employee = %s
    and m.docstatus = 1
    {conditions_2}
    GROUP BY mcr.employee
    """

    # Executing the query
    if user != "Administrator":
        meetings = frappe.db.sql(sql_query, (user,), as_dict=True)
    else:
        meetings = frappe.db.sql(sql_query, as_dict=True)

    sql_query = f"""
    SELECT 
        SUM(CASE 
                WHEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from)) > 0 THEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))
                ELSE 0 
            END) AS total_meeting_duration,
        COUNT(DISTINCT m.name) as meeting_count
    FROM `tabMeeting` as m
    JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent WHERE mcr.employee = %s
    and m.docstatus = 1 and internal_meeting = 0
    {conditions_2}
    GROUP BY mcr.employee
    """


    meetings_external_employee = frappe.db.sql(sql_query, (user,), as_dict=True)

    sql_query = f"""
    SELECT 
        SUM(CASE 
                WHEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from)) > 0 THEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))
                ELSE 0 
            END) AS total_meeting_duration,
        COUNT(DISTINCT m.name) as meeting_count
    FROM `tabMeeting` as m
    JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent WHERE mcr.employee = %s
    and m.docstatus = 1 and internal_meeting = 1
    {conditions_2}
    GROUP BY mcr.employee
    """

    # Executing the query
    meetings_internal_employee = frappe.db.sql(sql_query, (user,), as_dict=True)

    sql_query = f"""
    SELECT 
        SUM(CASE 
                WHEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from)) > 0 THEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))
                ELSE 0 
            END) AS total_meeting_duration,
        COUNT(DISTINCT m.name) as meeting_count
    FROM `tabMeeting` as m
    WHERE m.docstatus = 1 and internal_meeting = 0
    AND DATE(m.meeting_from) >= '{start_date}' AND DATE(m.meeting_to) <= '{end_date}'
    """

    # Executing the query
    meetings_admin_data = frappe.db.sql(sql_query, as_dict=True)

    sql_query = f"""
    SELECT 
        SUM(CASE 
                WHEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from)) > 0 THEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))
                ELSE 0 
            END) AS total_meeting_duration,
        COUNT(DISTINCT m.name) as meeting_count
    FROM `tabMeeting` as m
    WHERE m.docstatus = 1 and internal_meeting = 1
    AND DATE(m.meeting_from) >= '{start_date}' AND DATE(m.meeting_to) <= '{end_date}'
    """

    # Executing the query
    meetings_admin_data_internal = frappe.db.sql(sql_query, as_dict=True)

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
            (SELECT COUNT(DISTINCT application_name) FROM `tabApplication Usage log`{conditions})  AS application_usage,
            (SELECT COUNT(*) FROM `tabVersion` {version_conditions_str} {ignore_condition})  AS version_count
        """, as_dict=1)[0]
    
    
    # Employee Fincall Count
    fincall_count = frappe.db.sql(f"""
        SELECT COUNT(*)  AS fincall_count ,calltype FROM `tabEmployee Fincall` {conditions} group by calltype
    """, as_dict=True)
    incoming_fincall_count = next((item['fincall_count'] for item in fincall_count if item['calltype'] == 'Incoming'), 0)
    outgoing_fincall_count = next((item['fincall_count'] for item in fincall_count if item['calltype'] == 'Outgoing'), 0)
    missed_fincall_count = next((item['fincall_count'] for item in fincall_count if item['calltype'] == 'Missed'), 0)
    rejected_fincall_count = next((item['fincall_count'] for item in fincall_count if item['calltype'] == 'Rejected'), 0)


    # Employee Fincall Count
    fincall_count = frappe.db.sql(f"""
        SELECT COUNT(*)  AS fincall_count ,calltype FROM `tabEmployee Fincall` {conditions} group by calltype
    """, as_dict=True)
    incoming_fincall_count = next((item['fincall_count'] for item in fincall_count if item['calltype'] == 'Incoming'), 0)
    outgoing_fincall_count = next((item['fincall_count'] for item in fincall_count if item['calltype'] == 'Outgoing'), 0)
    missed_fincall_count = next((item['fincall_count'] for item in fincall_count if item['calltype'] == 'Missed'), 0)
    rejected_fincall_count = next((item['fincall_count'] for item in fincall_count if item['calltype'] == 'Rejected'), 0)


    # TABLES BELOW CARDS
    application_name = frappe.db.sql(f"""
        SELECT application_name, SUM(duration) AS total_duration
        FROM `tabApplication Usage log`
        {conditions}
        GROUP BY application_name
        ORDER BY total_duration DESC
        LIMIT 10
    """, as_dict=True)


    caller_name = frappe.db.sql(f"""
        SELECT client, SUM(duration) AS total_duration, count(*) as call_count
        FROM `tabEmployee Fincall`
        {conditions}
        GROUP BY client
        ORDER BY total_duration DESC
        LIMIT 10
    """, as_dict=True)

    doc_name = frappe.db.sql(f"""
        SELECT ref_doctype, COUNT(*) AS activity_count
        FROM `tabVersion`
        {version_conditions_str}
        {ignore_condition}
        GROUP BY ref_doctype
        ORDER BY activity_count DESC
        LIMIT 10
    """, as_dict=True)

    query = f"""
        SELECT domain, SUM(duration) AS duration, application_name
        FROM `tabApplication Usage log` 
        {conditions} and domain != '' and domain is not null
        GROUP BY domain
        ORDER BY SUM(duration) DESC
        """
    data = frappe.db.sql(query, as_dict=True)
    result_list = data


    return {
        "application_usage": total_counts['application_usage'],
        "version_count": total_counts['version_count'],
        "incoming_fincall_count": incoming_fincall_count,
        "outgoing_fincall_count": outgoing_fincall_count,
        "missed_fincall_count": missed_fincall_count,
        "rejected_fincall_count": rejected_fincall_count,
        "application_name": application_name,
        "caller_name": caller_name,
        "doc_name": doc_name,
        "total_hours": total_hours,
        "total_incoming_fincall_count": total_incoming_fincall_count,
        "total_outgoing_fincall_count": total_outgoing_fincall_count,
        "total_missed_fincall_count": total_missed_fincall_count,
        "total_idle_time": total_idle_time_in_seconds,
        "total_days": total_days,
        "total_unique_doc": total_unique_doc[0]['activity_count'] if total_unique_doc else 0,
        "total_time_on_calls": fincall_data[0]['total_duration'] if fincall_data else 0,
        "total_meeting_duration": meetings[0].total_meeting_duration if meetings else 0,
        "total_meeting_count": meetings[0].meeting_count if meetings else 0,
        "total_meeting_duration_internal": meetings_internal_employee[0].total_meeting_duration if meetings_internal_employee else 0,
        "total_meeting_count_internal": meetings_internal_employee[0].meeting_count if meetings_internal_employee else 0,
        "total_meeting_duration_external": meetings_external_employee[0].total_meeting_duration if meetings_external_employee else 0,
        "total_meeting_count_external": meetings_external_employee[0].meeting_count if meetings_external_employee else 0,
        "url_full_data": result_list[:10],
        "meeting_admin_data": meetings_admin_data,
        "meetings_admin_data_internal": meetings_admin_data_internal
    }

@frappe.whitelist()
def get_url_brief_data(url_data,user,start_date=None, end_date=None):
    start_date, end_date = set_dates(start_date, end_date)
    if user != "Administrator":
        conditions = f"WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}'"
    else:
        conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"
    query = f"""
        SELECT current_url, SUM(duration) AS duration, application_name
        FROM `tabApplication Usage log` 
        {conditions} and domain = '{url_data}'
        GROUP BY current_url
        ORDER BY SUM(duration) DESC
        """
    data_query = frappe.db.sql(query, as_dict=True)
    return {
        "data":data_query
    }

# PIE CHART
@frappe.whitelist()
def get_piechart_data(user, start_date=None, end_date=None):
    start_date, end_date = set_dates(start_date, end_date)
    if user != "Administrator":
        conditions = f"WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}'"
    else:
        conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"
    
    data = frappe.db.sql(f"""
            SELECT application_name, SUM(duration) as duration
            FROM `tabApplication Usage log`
            {conditions}
            GROUP BY application_name
            ORDER BY duration DESC
            LIMIT 5
        """, as_dict=1)
        
    return {
        "labels": [i["application_name"] for i in data],
        "datasets": [{"values": [round(i["duration"]/60/60,2) for i in data]}]
    }
# LINE CHART
@frappe.whitelist()
def get_linechart_data(user, start_date=None, end_date=None):
    start_date, end_date = set_dates(start_date, end_date)
    if user != "Administrator":
        conditions = f"WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}'"
    else:
        conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"
    
    data = frappe.db.sql(f"""
        SELECT client, SUM(duration) AS total_duration
        FROM `tabEmployee Fincall`
        {conditions}
        GROUP BY client
        ORDER BY total_duration DESC
        LIMIT 10
        """, as_dict=1)
        
    return {
        "labels": [i["client"] for i in data],
        "datasets": [{"values": [round(i["total_duration"]/60,2) for i in data]}]
    }

# BAR CHART
@frappe.whitelist()
def get_barchart_data(user, start_date=None, end_date=None):
    now = datetime.now()
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d')
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d')
    
    if end_date is None:
        end_date = now.strftime('%Y-%m-%d') 
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d') 
    
    version_conditions_str = version_conditions(user,start_date,end_date)
    ignore_doctype = ['File',"Communication","Fincall Log","Custom Field","DocType","Web Page"]

    # Convert the list into a format suitable for SQL query ("'DocType1', 'DocType2', 'DocType3'")
    ignore_doctype_str = ','.join(f"'{doc}'" for doc in ignore_doctype)

    # Check if the list is not empty to add a condition to the query
    if ignore_doctype_str:
        ignore_condition = f"AND ref_doctype NOT IN ({ignore_doctype_str})"
    else:
        ignore_condition = ""
    data = frappe.db.sql(f"""
        SELECT COUNT(DISTINCT docname) AS activity_count, ref_doctype
        FROM `tabVersion`
        {version_conditions_str}
        {ignore_condition}
        group by ref_doctype
        order by activity_count DESC 
        LIMIT 7
        """, as_dict=1)
        
    return {
        "labels": [i["ref_doctype"] for i in data],
        "datasets": [{"values": [i["activity_count"] for i in data]}]
    }

# SCREEN SHOTS
@frappe.whitelist()
def get_images(user, start_date=None, end_date=None, offset=0):
    limit = 20
    start_date, end_date = set_dates(start_date, end_date)
    if user != "Administrator":
        condition = f"WHERE employee = '{user}' AND datetime >= '{start_date}' AND datetime <= '{end_date}'"
    else:
        condition = f"WHERE datetime >= '{start_date}' AND datetime <= '{end_date}'"

    data = frappe.db.sql(f"""
        SELECT screenshot, datetime
        FROM `tabScreen Screenshot Log`
        {condition}
        GROUP BY datetime
        ORDER BY datetime DESC
        LIMIT {limit} OFFSET {offset}
    """, as_dict=1)
    return data


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
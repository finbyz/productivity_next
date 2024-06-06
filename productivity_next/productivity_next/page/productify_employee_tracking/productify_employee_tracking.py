
from datetime import datetime,time,timedelta
import frappe
from frappe.utils import add_months,getdate
from collections import defaultdict
from frappe import _

# HEATMAP
@frappe.whitelist()
def get_heatmap_data(user, date):
    one_year_ago_date = add_months(getdate(), -12)
    email = frappe.db.get_value("Employee", user, "company_email")
    queries = [
        f"""
        SELECT DATE(creation) as date, COUNT(*) as count
        FROM `tabApplication Usage log`
        Where employee = '{user}' and date >= '{one_year_ago_date}'
        GROUP BY DATE(creation)
        """,
        f"""
        SELECT DATE(call_datetime) as date, COUNT(*) as fincall_count
        FROM `tabEmployee Fincall`
        Where employee = '{user}' and date >= '{one_year_ago_date}'
        GROUP BY DATE(call_datetime)
        """,
        f"""
        SELECT DATE(creation) as date, COUNT(*) as activity_count
        FROM `tabVersion`
        Where owner = '{email}' and creation >= '{one_year_ago_date} 00:00:00'
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
    now = frappe.utils.now_datetime()
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
        condition = f"WHERE owner = '{email}' AND creation >= '{start_date}' AND creation <= '{end_date}'"
    else:
        condition = f"WHERE creation >= '{start_date}' AND creation <= '{end_date}'"

    return condition

@frappe.whitelist()
def get_user_data(user,start_date=None, end_date=None):
    version_conditions_str = version_conditions(user,start_date,end_date)
    start_date_,end_date_ = set_dates(start_date, end_date)

    ignore_doctype = ['File',"Communication","Fincall Log","Custom Field","DocType","Web Page","Attendance"]
    ignore_doctype_str = ','.join(f"'{doc}'" for doc in ignore_doctype)
    if ignore_doctype_str:
        ignore_condition = f"AND ref_doctype NOT IN ({ignore_doctype_str})"
    else:
        ignore_condition = ""
    start_date, end_date = set_dates(start_date, end_date)

    conditions = f"WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}'"
    conditions_2 = f"AND mcr.employee = '{user}' AND DATE(m.meeting_from) >= '{start_date}' AND DATE(m.meeting_to) <= '{end_date}'"

    # Fetch idle time logs
    idle_time_data = frappe.db.sql(f"""
        SELECT start_time, end_time
        FROM `tabIdle Time`
        WHERE start_time > '{start_date}' AND end_time < '{end_date}' AND employee = '{user}'
    """, as_dict=True)

    # Fetch fincall time logs
    fincall_time_data = frappe.db.sql(f"""
        SELECT call_datetime as start_time, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time
        FROM `tabEmployee Fincall`
        WHERE date >= '{start_date}' AND date <= '{end_date}' AND (calltype != 'Missed' AND calltype != 'Rejected') AND employee = '{user}'
    """, as_dict=True)

    # Fetch meeting time logs
    meeting_time_data = frappe.db.sql(f"""
        SELECT meeting_from as start_time, meeting_to as end_time
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE m.docstatus = 1
        AND m.meeting_from >= '{start_date}' AND m.meeting_to <= '{end_date}' AND mcr.employee = '{user}'
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
    fincall_data = frappe.db.sql(f"""
        SELECT 
            calltype,
            COUNT(*) AS fincall_count,
            COALESCE(SUM(duration), 0) AS total_duration
        FROM `tabEmployee Fincall`
        {conditions} and (link_to != 'Company' or link_to is null)
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

    internal_fincall_data = frappe.db.sql(f"""
        SELECT 
            calltype,
            COUNT(*) AS fincall_count,
            COALESCE(SUM(duration), 0) AS total_duration
        FROM `tabEmployee Fincall`
        {conditions} and link_to = 'Company' and link_to is not null
        GROUP BY calltype
    """, as_dict=True)

    # Extracting data for each call type
    internal_incoming_fincall_count = next((item['fincall_count'] for item in internal_fincall_data if item['calltype'] == 'Incoming'), 0)
    internal_outgoing_fincall_count = next((item['fincall_count'] for item in internal_fincall_data if item['calltype'] == 'Outgoing'), 0)
    internal_missed_fincall_count = next((item['fincall_count'] for item in internal_fincall_data if item['calltype'] == 'Missed'), 0)
    internal_rejected_fincall_count = next((item['fincall_count'] for item in internal_fincall_data if item['calltype'] == 'Rejected'), 0)

    internal_total_incoming_fincall_count = next((item['total_duration'] for item in internal_fincall_data if item['calltype'] == 'Incoming'), 0)
    internal_total_outgoing_fincall_count = next((item['total_duration'] for item in internal_fincall_data if item['calltype'] == 'Outgoing'), 0)

    list_data = []
    meeting_total_data = frappe.db.sql(f"""
        SELECT m.meeting_from as start_time, m.meeting_to as end_time
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE mcr.employee ='{user}' and m.docstatus = 1 and m.meeting_from >= '{start_date}' and m.meeting_to <= '{end_date}'
    """, as_dict=True)
    calls_total_data = frappe.db.sql(f"""
        SELECT call_datetime as start_time, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time
        FROM `tabEmployee Fincall`
        WHERE employee = '{user}' and call_datetime >= '{start_date}' and call_datetime <= '{end_date}' and (calltype != 'Missed' and calltype != 'Rejected')
    """, as_dict=True)
    application_total_data = frappe.db.sql(f"""
        SELECT from_time as start_time, to_time as end_time
        FROM `tabApplication Usage log`
        WHERE employee = '{user}' and date >= '{start_date}' and date <= '{end_date}'
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
            if interval['start_time'] <= current_interval['end_time']:
                # There is overlap, so merge the intervals
                current_interval['end_time'] = max(current_interval['end_time'], interval['end_time'])
            else:
                # No overlap, so add the current interval to the list and start a new one
                merged_intervals.append(current_interval)
                current_interval = interval

        # Don't forget to add the last interval
        merged_intervals.append(current_interval)

        # Calculate the total time
        total_time = timedelta()
        for interval in merged_intervals:
            total_time += interval['end_time'] - interval['start_time']    


        total_hours = total_time.total_seconds()
    else:
        total_hours = 0                                

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

    total_days = len(set(application_usage_days + meeting_usage_days)) or 1
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
        SELECT COALESCE(contact, client, customer_no) AS identifier, 
               SUM(duration) AS total_duration,
               COUNT(*) AS call_count
        FROM `tabEmployee Fincall`
        {conditions}
        GROUP BY COALESCE(contact, client, customer_no)
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

    domain_used = frappe.db.sql(f"""
        SELECT count(DISTINCT domain) as domain_count
        FROM `tabApplication Usage log`
        {conditions} and domain != '' and domain is not null
        """, as_dict=True)
    

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
        "internal_incoming_fincall_count": internal_incoming_fincall_count,
        "internal_outgoing_fincall_count": internal_outgoing_fincall_count,
        "internal_missed_fincall_count": internal_missed_fincall_count,
        "internal_rejected_fincall_count": internal_rejected_fincall_count,
        "internal_total_incoming_fincall_count": internal_total_incoming_fincall_count,
        "internal_total_outgoing_fincall_count": internal_total_outgoing_fincall_count,
        "total_idle_time": total_idle_time,
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
        "meetings_admin_data_internal": meetings_admin_data_internal,
        "domain_used":domain_used[0].domain_count if domain_used else 0
    }

@frappe.whitelist()
def get_url_brief_data(url_data,user,start_date=None, end_date=None):
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

@frappe.whitelist()
def get_piechart_data(user, start_date=None, end_date=None):
    data = frappe.db.sql(f"""
            SELECT application_name, SUM(duration) as duration
            FROM `tabApplication Usage log`
            WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}'
            GROUP BY application_name
            ORDER BY duration DESC
            LIMIT 5
        """, as_dict=1)
        
    return {
        "labels": [i["application_name"] for i in data],
        "datasets": [{"values": [round(i["duration"]/60/60,2) for i in data]}]
    }
@frappe.whitelist()
def get_linechart_data(user, start_date=None, end_date=None):
    # SQL query to group by contact, client, or customer_no
    data = frappe.db.sql(f"""
        select count(*) as total_count,calltype,hour(call_datetime) as hour
        FROM `tabEmployee Fincall`
        WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}' and (calltype = 'Incoming' or calltype = 'Outgoing')
        group by HOUR(call_datetime),calltype
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
    # frappe.throw(str(aggregated_list))    
    # Prepare data for line chart
    return {
        "labels": [i["hour"] for i in aggregated_list],
        "datasets": [{"name":"Incoming","values": [i["incoming_count"] for i in aggregated_list]},{"name":"Outgoing","values": [i["outgoing_count"] for i in aggregated_list]}]
    }


# BAR CHART
@frappe.whitelist()
def get_barchart_data(user, start_date=None, end_date=None):
    now = frappe.utils.now_datetime()
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d')
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d')
    
    if end_date is None:
        end_date = now.strftime('%Y-%m-%d') 
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d') 
    
    version_conditions_str = version_conditions(user,start_date,end_date)
    ignore_doctype = ['File',"Communication","Fincall Log","Custom Field","DocType","Web Page","Attendance"]

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

@frappe.whitelist()
def get_images(user, start_date=None, end_date=None, offset=0):
    limit = 20
    start_date, end_date = set_dates(start_date, end_date)
    data = frappe.db.sql(f"""
        SELECT screenshot, datetime
        FROM `tabScreen Screenshot Log`
        WHERE employee = '{user}' AND datetime >= '{start_date}' AND datetime <= '{end_date}'
        GROUP BY datetime
        ORDER BY datetime DESC
        LIMIT {limit} OFFSET {offset}
    """, as_dict=1)

    for i in data:
        i["datetime_"] = frappe.format(i["datetime"], "Datetime")

    return data


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

# Example of using the function:
# start_date, end_date = set_dates('2022-01-01', '2022-12-31')
# print(start_date, end_date)
# This prints: '2022-01-01 00:00:00' '2022-12-31 23:59:59'
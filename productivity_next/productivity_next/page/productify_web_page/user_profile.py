
from datetime import datetime,time,timedelta
import frappe

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
        FROM `tabFincall Log`
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
        condition = f"WHERE DATE(creation) >= '{start_date}' AND DATE(creation) <= '{end_date}'"

    return condition


@frappe.whitelist()
def get_user_data(user,start_date=None, end_date=None):
    version_conditions_str = version_conditions(user,start_date,end_date)
    now = datetime.now()
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d')
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d')
    
    if end_date is None:
        end_date = now.strftime('%Y-%m-%d') 
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d') 

    if user != "Administrator":
        conditions = f"WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}'"
        conditions_2 = f"AND mcr.employee = '{user}' AND m.meeting_from >= '{start_date}' AND m.meeting_to <= '{end_date}'"
    else:
        conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"
        conditions_2 = f"AND m.meeting_from >= '{start_date}' AND m.meeting_to <= '{end_date}'"
    # TOTAL HOURS CARD
    if user != "Administrator":
        all_logs = frappe.db.get_list("Application Checkin Checkout", filters={"employee": user,"time": ["Between", [start_date,end_date ]]}, fields=["status", "time"], order_by="creation asc")
    else:
        all_logs = frappe.db.get_list("Application Checkin Checkout", filters={"time": ["Between", [start_date,end_date ]]}, fields=["status", "time"], order_by="creation asc")
    usage_time = 0
    last_status = None
    for row in all_logs:
        if row.status == "In" and last_status != "In":
            start_time = row.time
        elif row.status == "Out" and last_status == "In":
            end_time = row.time
            usage_time += (end_time - start_time).total_seconds()
        last_status = row.status
    total_hours = usage_time

    # IDLE TIME CARD
    total_idle_time = frappe.db.sql(f"""
        SELECT SUM(TIME_TO_SEC(TIMEDIFF(to_time, from_time))) AS total_duration_seconds
        FROM `tabApplication Usage log`{conditions} and
        TIME_TO_SEC(TIMEDIFF(to_time, from_time)) > 120 ;""",as_dict=1)
    
    # AVERAGE HOURS PER DAY CARD
    total_days = frappe.db.sql(f"""SELECT COUNT(DISTINCT date)  AS application_usage FROM `tabApplication Usage log` {conditions}""",as_dict=True)

    # Meetings
    if user != "Administrator":
        meetings = frappe.db.sql(f"""
        SELECT 
        SUM(TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))) AS total_meeting_duration,
        COUNT(DISTINCT m.name) as meeting_count
        FROM `tabMeeting Company Representative` as mcr
        JOIN `tabMeeting` as m ON m.name = mcr.parent
        WHERE m.docstatus = 1 {conditions_2}
        GROUP BY mcr.employee
        """,as_dict=True)
    else:
        meetings = frappe.db.sql(f"""
        SELECT 
        SUM(TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))) AS total_meeting_duration,
        COUNT(DISTINCT m.name) as meeting_count
        FROM `tabMeeting` as m
        WHERE m.docstatus = 1 
        """,as_dict=True)


    # Time On Calls
    total_time_on_calls = frappe.db.sql(f"""
    SELECT SUM(duration) as total_duration,calltype
    FROM `tabFincall Log`
    {conditions}
    group by calltype
    """, as_dict=True)
    total_incoming_fincall_count = next((item['total_duration'] for item in total_time_on_calls if item['calltype'] == 'Incoming'), None)
    total_outgoing_fincall_count = next((item['total_duration'] for item in total_time_on_calls if item['calltype'] == 'Outgoing'), None)
    total_missed_fincall_count = next((item['total_duration'] for item in total_time_on_calls if item['calltype'] == 'Missed'), None)

    # Documents Accessed
    total_unique_doc = frappe.db.sql(f"""
    SELECT COUNT(DISTINCT docname) AS activity_count
    FROM `tabVersion`
    {version_conditions_str}
    """, as_dict=True)

    # Application Usage Log Count, Top 10 Doc's Used Cards
    total_counts = frappe.db.sql(f"""
        SELECT
            (SELECT COUNT(DISTINCT application_name) FROM `tabApplication Usage log`{conditions})  AS application_usage,
            (SELECT COUNT(*) FROM `tabVersion` {version_conditions_str}) AS version_count
        """, as_dict=1)[0]
    
    # Fincall Log Count
    fincall_count = frappe.db.sql(f"""
        SELECT COUNT(*)  AS fincall_count ,calltype FROM `tabFincall Log` {conditions} group by calltype
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
        FROM `tabFincall Log`
        {conditions}
        GROUP BY client
        ORDER BY total_duration DESC
        LIMIT 10
    """, as_dict=True)

    doc_name = frappe.db.sql(f"""
        SELECT ref_doctype, COUNT(*) AS activity_count
        FROM `tabVersion`
        {version_conditions_str}
        GROUP BY ref_doctype
        ORDER BY activity_count DESC
        LIMIT 10
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
        "total_idle_time": total_idle_time[0]['total_duration_seconds'] if total_idle_time else 0,
        "total_days": total_days[0]['application_usage'],
        "total_unique_doc": total_unique_doc[0]['activity_count'] if total_unique_doc else 0,
        "total_time_on_calls": total_time_on_calls[0]['total_duration'] if total_time_on_calls else 0,
        "total_meeting_duration": meetings[0].total_meeting_duration if meetings else 0,
        "total_meeting_count": meetings[0].meeting_count if meetings else 0
    }

# PIE CHART
@frappe.whitelist()
def get_linechart_data(user, start_date=None, end_date=None):
    now = datetime.now()
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d')
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d')
    
    if end_date is None:
        end_date = now.strftime('%Y-%m-%d') 
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d') 

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
            LIMIT 10
        """, as_dict=1)
        
    return {
        "labels": [i["application_name"] for i in data],
        "datasets": [{"values": [i["duration"]/60/60 for i in data]}]
    }

# SCREEN SHOTS
@frappe.whitelist()
def get_images(user, start_date=None, end_date=None):
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
        condition = f"WHERE employee = '{user}' AND datetime >= '{start_date}' AND datetime <= '{end_date}'"
    else:
        condition = f"WHERE datetime >= '{start_date}' AND datetime <= '{end_date}'"
    data = frappe.db.sql(f"""
        SELECT screenshot,datetime as datetime
        FROM `tabScreen Screenshot Log`
        {condition}
        GROUP BY datetime
        ORDER BY datetime DESC
        """, as_dict=1)
    
    return data

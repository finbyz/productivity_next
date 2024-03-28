
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
    else:
        conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"

    total_counts = frappe.db.sql(f"""
        SELECT
            (SELECT COUNT(*) FROM `tabApplication Usage log` {conditions}) AS application_usage,
            (SELECT COUNT(*) FROM `tabFincall Log` {conditions}) AS fincall_count,
            (SELECT COUNT(*) FROM `tabVersion` {version_conditions_str}) AS version_count
        """, as_dict=1)[0]
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
        'application_usage': total_counts['application_usage'],
        'fincall_count': total_counts['fincall_count'],
        'version_count': total_counts['version_count'],
        'application_name': application_name,
        'caller_name': caller_name,
        'doc_name': doc_name
    }


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
            LIMIT 7
        """, as_dict=1)
        
    return {
        "labels": [i["application_name"] for i in data],
        "datasets": [{"values": [i["duration"]/60/60 for i in data]}]
    }


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
        SELECT screenshot
        FROM `tabScreen Screenshot Log`
        {condition}
        GROUP BY datetime
        ORDER BY datetime ASC
        """, as_dict=1)
    
    return [i["screenshot"] for i in data]

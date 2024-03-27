
from datetime import datetime,time
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

import frappe

def get_conditions_user_data(user):
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
        "simple_employee_cond": f"WHERE {employee_cond[:-4]}"
    }

@frappe.whitelist()
def get_user_data(user):
    conditions = get_conditions_user_data(user)

    total_counts = frappe.db.sql(f"""
        SELECT
            (SELECT COUNT(*) FROM `tabApplication Usage log` {conditions['employee_cond']}) AS application_usage,
            (SELECT COUNT(*) FROM `tabFincall Log` {conditions['employee_cond']}) AS fincall_count,
            (SELECT COUNT(*) FROM `tabVersion` {conditions['email_cond']}) AS version_count
        """, as_dict=1)[0]


    where_clause_application = "WHERE 1=1" if conditions['simple_employee_cond'] == "WHERE " else conditions['simple_employee_cond']
    where_clause_version = "WHERE 1=1" if conditions['email_cond'] == "WHERE " else conditions['email_cond']

    application_name = frappe.db.sql(f"""
        SELECT application_name, SUM(duration) AS total_duration
        FROM `tabApplication Usage log`
        {where_clause_application}
        GROUP BY application_name
        ORDER BY total_duration DESC
        LIMIT 10
    """, as_dict=True)


    caller_name = frappe.db.sql(f"""
        SELECT client, SUM(duration) AS total_duration, count(*) as call_count
        FROM `tabFincall Log`
        {where_clause_application}  # Assuming calls also follow the same employee condition
        GROUP BY client
        ORDER BY total_duration DESC
        LIMIT 10
    """, as_dict=True)

    doc_name = frappe.db.sql(f"""
        SELECT ref_doctype, COUNT(*) AS activity_count
        FROM `tabVersion`
        {where_clause_version}
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
def get_linechart_data(user, date):
    conditions = get_conditions(user)['employee_cond']
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
def get_images(user):
    condition = "WHERE employee = '{}'" .format(user) if user != "Administrator" else ""
    data = frappe.db.sql(f"""
        SELECT screenshot
        FROM `tabScreen Screenshot Log`
        {condition}
        GROUP BY datetime
        """, as_dict=1)
    return [i["screenshot"] for i in data]

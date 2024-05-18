import frappe
from datetime import datetime,timedelta
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
    return {"combined_employee_data": combined_data}

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
    
    condition = f"WHERE creation >= '{start_date}' AND creation <= '{end_date}'"

    return condition

@frappe.whitelist()
def get_barchart_data(start_date=None, end_date=None):
    version_conditions_str = version_conditions(start_date,end_date)
    ignore_doctype = ['File',"Communication"]
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
        FROM `tabFincall Log`
        {conditions}
        GROUP BY client
        ORDER BY total_duration DESC
        LIMIT 10
        """, as_dict=1)
        
    return {
        "labels": [i["client"] for i in data],
        "datasets": [{"values": [round(i["total_duration"]/60,2) for i in data]}]
    }

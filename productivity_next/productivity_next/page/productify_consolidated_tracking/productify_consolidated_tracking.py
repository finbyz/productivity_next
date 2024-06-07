import frappe
from datetime import datetime,timedelta
from frappe.utils import now 
from productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking import get_user_data
@frappe.whitelist()
def get_admin_data(user, start_date=None, end_date=None):
    combined_data = []
    apps_data = frappe.db.sql(f"""
        SELECT application_name,SUM(duration) AS total_duration
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' AND date <= '{end_date}'
        GROUP BY application_name
        ORDER BY total_duration DESC
        LIMIT 10
        """, as_dict=1)
    urls_visited = frappe.db.sql(f"""
        SELECT domain,SUM(duration) AS total_duration
        FROM `tabApplication Usage log`
        WHERE date >= '{start_date}' AND date <= '{end_date}' and domain is not null and domain != ''
        GROUP BY domain
        ORDER BY total_duration DESC
        LIMIT 10
        """, as_dict=1)
    if user != "Administrator":
        employees = frappe.db.get_all("Employee", filters={"status": "Active"}, fields=["name"])
        for employee in employees:
            employee_data = get_user_data(employee['name'], start_date, end_date)
            employee_data['employee'] = employee['name']
            combined_data.append(employee_data)
    else: 
        employee_data = get_user_data(user, start_date, end_date)
        combined_data.append(employee_data)
    return {"combined_employee_data": combined_data,"apps_data":apps_data,"urls_visited":urls_visited}

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

@frappe.whitelist() 
def version_conditions(start_date=None, end_date=None):
    now = frappe.utils.now_datetime()
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
    ignore_doctype = ['File',"Communication","Fincall Log","Custom Field","DocType","Web Page","Attendance"]
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
    if user != "Administrator":
        conditions = f"WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}'"
    else:
        conditions = f"WHERE date >= '{start_date}' AND date <= '{end_date}'"
    
    data = frappe.db.sql(f"""
    SELECT employee, calltype, COUNT(*) as count
    FROM `tabEmployee Fincall`
    {conditions}
    GROUP BY employee, calltype
    ORDER BY count DESC
    LIMIT 10""", as_dict=1)
        
    
    # Extract distinct employees
    employees = sorted(set(entry['employee'] for entry in data))

    # Initialize datasets
    datasets = {
        'Incoming': [0] * len(employees),
        'Outgoing': [0] * len(employees),
        'Missed': [0] * len(employees),
        'Rejected': [0] * len(employees),
        'None': [0] * len(employees)
    }

    # Populate the datasets
    employee_index = {employee: idx for idx, employee in enumerate(employees)}
    for entry in data:
        employee = entry['employee']
        calltype = entry['calltype'] if entry['calltype'] else 'None'
        count = entry['count']
        index = employee_index[employee]
        datasets[calltype][index] = count

    # Convert datasets to required format
    formatted_datasets = []
    for calltype, counts in datasets.items():
        if calltype != 'None':
            formatted_datasets.append({
                "name": calltype,
                "values": counts
            })
    employee_name = []
    for i in employees:
        name = frappe.db.get_value("Employee",i,"employee_name")
        employee_name.append(name)
    # frappe.throw(str(result))
    # Create the final data structure
    return {
        "labels": employee_name,
        "datasets": formatted_datasets
    }

@frappe.whitelist()
def get_app_brief_data(app_data, start_date=None, end_date=None):
    data = frappe.db.sql(f"""
        SELECT employee, SUM(duration) AS total_duration,application_name
        FROM `tabApplication Usage log`
        WHERE application_name = '{app_data}' AND date >= '{start_date}' AND date <= '{end_date}'
        GROUP BY employee
        ORDER BY total_duration DESC
        """, as_dict=1)
    return {"app_data":data}

@frappe.whitelist()
def get_url_brief_data(url_data, start_date=None, end_date=None):
    data = frappe.db.sql(f"""
        SELECT employee, SUM(duration) AS total_duration,domain
        FROM `tabApplication Usage log`
        WHERE domain = '{url_data}' AND date >= '{start_date}' AND date <= '{end_date}'
        GROUP BY employee
        ORDER BY total_duration DESC
        """, as_dict=1)
    return {"url_data":data}


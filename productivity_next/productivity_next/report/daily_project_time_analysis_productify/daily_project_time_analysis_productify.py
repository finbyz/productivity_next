# daily_time_report.py

import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}
    
    raw_data = get_raw_data(filters)
    employees = get_employees_from_data(raw_data)
    columns = get_columns(len(employees))  # Pass the length of employees list instead of the list itself
    formatted_data = format_data(raw_data, len(employees),filters)  # Pass employee count instead of list
    
    return columns, formatted_data

def get_raw_data(filters):
    """Get all raw data first to determine which employees have entries"""
    start_date = filters.get('from_date')
    end_date = filters.get('to_date')
    project_filter = filters.get('project')
    customer_filter = filters.get('customer')
    employee_filter = filters.get('employee')
    show_descendants = filters.get('show_descendants')
    is_internal_customer = filters.get('is_internal_customer')  # ✅ New filter for checkbox



    # If "Show Descendants" is checked, fetch the entire hierarchy
    if show_descendants and employee_filter:
        descendant_employees = get_descendant_employees(employee_filter)
        employee_filter = [employee_filter] + descendant_employees  # Include selected employee too
    elif employee_filter:
        employee_filter = [employee_filter]
    else:
        employee_filter = frappe.db.sql("""
            SELECT name FROM `tabEmployee` WHERE status = 'Active'
        """, as_list=True)
        employee_filter = [emp[0] for emp in employee_filter]  # Extract list of employee names
    

    # Build project query with filters
    project_conditions = ["p.status = 'Open'"]
    if project_filter:
        project_conditions.append(f"p.name = '{project_filter}'")
    if customer_filter:
        project_conditions.append(f"p.customer = '{customer_filter}'")
    if not is_internal_customer:
        project_conditions.append("c.is_internal_customer = 0")
    else:
        project_conditions.append("(c.is_internal_customer = 0 OR c.is_internal_customer = 1)")  # Both internal & external customers

    
    project_where_clause = " AND ".join(project_conditions)
    
    projects = frappe.db.sql(f"""
        SELECT DISTINCT p.name as project, p.customer
        FROM `tabProject` p
        JOIN `tabCustomer` c ON p.customer = c.name
        WHERE {project_where_clause}
    """, as_dict=1)
    
    raw_data = []
    
    for project in projects:
        current_date = frappe.utils.getdate(start_date)
        end_date_obj = frappe.utils.getdate(end_date)
        
        while current_date <= end_date_obj:
            for emp in employee_filter:
                time_data = fetch_url_data(
                    start_date=current_date,
                    end_date=current_date,
                    project=project.project,
                    customer=project.customer,
                    user=emp  
                )
            
                if time_data.get('data'):
                    raw_data.append({
                        'date': current_date,
                        'customer': project.customer,
                        'project': project.project,
                        'employee': emp,  # Add employee info
                        'employee_data': time_data['data']
                    })
            
            current_date = frappe.utils.add_days(current_date, 1)
    
    return raw_data


def get_descendant_employees(employee_id):
    """Fetch all employees who report to the given employee"""
    employee_list = []  # Do not include selected employee here (added in get_raw_data)

    def fetch_reports_to(emp_id):
        subordinates = frappe.db.sql(f"""
            SELECT name FROM `tabEmployee`
            WHERE reports_to = '{emp_id}'
        """, as_dict=True)

        for emp in subordinates:
            if emp['name'] not in employee_list:  # Avoid duplicates
                employee_list.append(emp['name'])
                fetch_reports_to(emp['name'])  # Recursively get subordinates

    fetch_reports_to(employee_id)
    return employee_list  # Returns only descendants



def get_employees_from_data(raw_data):
    """Get unique employees that actually have time entries"""
    employees = set()
    for entry in raw_data:
        for emp_data in entry['employee_data']:
            if emp_data['total_duration'] > 0:  # Only include if they have time
                employees.add((emp_data['employee_id'], emp_data['employee']))
    
    return sorted(list(employees), key=lambda x: x[1])  # Sort by employee name

# def seconds_to_time_format(seconds):
#     if seconds == None:
#         return seconds
#     """Convert seconds to HH:MM format"""
#     hours = int(seconds // 3600)
#     minutes = int((seconds % 3600) // 60)
#     return f"{hours:02d}:{minutes:02d}"


def get_columns(employee_count):
    """Generate columns with generic Employee/Time names"""
    columns = [
        {
            "fieldname": "date",
            "label": _( "Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "customer",
            "label": _( "Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "width": 150
        },
        {
            "fieldname": "project",
            "label": _( "Project"),
            "fieldtype": "Link",
            "options": "Project",
            "width": 150
        },
        # {
        #     "fieldname": "total_hours",
        #     "label": _( "Total Hours"),
        #     "fieldtype": "Data",  # Changed to Data to support HH:MM format
        #     "width": 100
        # }
        {
            "fieldname": "total_hours",
            "label": _("Total Hours"),
            "fieldtype": "Float",  # ✅ Corrected to Float
            "width": 100
        }

    ]
    
    # Add generic column pairs for each employee
    for i in range(employee_count):
        employee_num = i + 1
        columns.extend([
            {
                "fieldname": f"employee_{employee_num}",
                "label": f"Employee{employee_num}",
                "fieldtype": "Data",
                "width": 150
            },
            {
                "fieldname": f"time_{employee_num}",
                "label": f"Time{employee_num}",
                "fieldtype": "Data",  # Changed to Data to support HH:MM format
                "width": 100
            }
        ])
    
    return columns


def format_data(raw_data, employee_count, filters=None):
    """Format the raw data into the final report format based on filters."""

    if filters is None:
        filters = {}

    # Check if "Show Project Wise Data" checkbox is checked
    if filters.get("show_project_wise_data", False) == True:  
        return format_project_wise_data(raw_data, employee_count)
    else:
        return format_default_data(raw_data, employee_count)


def format_default_data(raw_data, employee_count):
    """Format the raw data into the default structure (employee-wise)."""
    formatted_data = []
    
    for entry in raw_data:
        row_data = {
            'date': entry['date'],
            'customer': entry['customer'],
            'project': entry['project'],
            'total_hours': "0.00"  # Decimal format instead of HH:MM
        }
        
        # Initialize employee fields
        for i in range(employee_count):
            row_data[f"employee_{i+1}"] = ""
            row_data[f"time_{i+1}"] = None
        
        has_data = False
        total_seconds = 0
        sorted_emp_data = sorted(entry['employee_data'], key=lambda x: x['total_duration'], reverse=True)
        
        for idx, emp_data in enumerate(sorted_emp_data):
            if emp_data['total_duration'] > 0:
                seconds = emp_data['total_duration']
                total_seconds += seconds
                
                if idx < employee_count:
                    row_data[f"employee_{idx+1}"] = emp_data['employee']
                    row_data[f"time_{idx+1}"] = seconds_to_decimal(seconds)
                    has_data = True
        
        if has_data:
            row_data['total_hours'] = seconds_to_decimal(total_seconds)
            formatted_data.append(row_data)
    
    # Add total row
    if formatted_data:
        total_seconds = sum(
            float(row['total_hours']) * 3600 for row in formatted_data if row['total_hours'] != "0.00"
        )

        total_row = {
            'date': "Total",
            'customer': "",
            'project': "",
            'total_hours': seconds_to_decimal(total_seconds)
        }
        for i in range(employee_count):
            total_row[f"employee_{i+1}"] = ""
            total_row[f"time_{i+1}"] = ""

        formatted_data.append(total_row)

    return formatted_data


def format_project_wise_data(raw_data, employee_count):
    """Format data in project-wise structure when checkbox is checked."""
    formatted_data = []
    project_date_map = {}  # Store entries by (date, project, customer)
    grand_total_seconds = 0  

    for entry in raw_data:
        key = (entry['date'], entry['project'], entry['customer'])

        if key not in project_date_map:
            project_date_map[key] = {
                'date': entry['date'],
                'customer': entry['customer'],
                'project': entry['project'],
                'employees': []
            }

        # Add employee work details to the project-date entry
        for emp_data in entry['employee_data']:
            if emp_data['total_duration'] > 0 and emp_data['employee'].strip():
                project_date_map[key]['employees'].append({
                    'name': emp_data['employee'],
                    'time_seconds': emp_data['total_duration']
                })

    # Convert project_date_map to the final formatted data structure
    for key, row in project_date_map.items():
        formatted_row = {
            'date': row['date'],
            'customer': row['customer'],
            'project': row['project'],
        }

        # Initialize employee fields
        for i in range(employee_count):
            formatted_row[f"employee_{i+1}"] = ""
            formatted_row[f"time_{i+1}"] = None

        total_seconds = 0
        has_employee = False  

        for idx, emp_data in enumerate(row['employees']):
            if idx < employee_count:
                formatted_row[f"employee_{idx+1}"] = emp_data['name']
                formatted_row[f"time_{idx+1}"] = seconds_to_decimal(emp_data['time_seconds'])
                total_seconds += emp_data['time_seconds']
                has_employee = True  

        formatted_row['total_hours'] = seconds_to_decimal(total_seconds)
        grand_total_seconds += total_seconds  

        if total_seconds > 0 and has_employee:
            formatted_data.append(formatted_row)

    # Append total row
    if grand_total_seconds > 0:
        total_row = {
            'date': 'TOTAL',
            'customer': '',
            'project': '',
            'total_hours': seconds_to_decimal(grand_total_seconds)
        }
        for i in range(employee_count):
            total_row[f"employee_{i+1}"] = ""
            total_row[f"time_{i+1}"] = None

        formatted_data.append(total_row)

    return formatted_data


def seconds_to_decimal(seconds):
    """Convert seconds into decimal hours format (e.g., 1.50 instead of 01:30)."""
    if seconds is None or seconds <= 0:
        return "0.00"  # Return as a string to maintain consistency
    
    # Convert seconds to decimal hours
    hours = seconds // 3600
    minutes = (seconds % 3600) / 60
    decimal_hours = float(hours) + (float(minutes) / 60)
    
    return f"{decimal_hours:.2f}"  # Return formatted string


def fetch_url_data(user=None, start_date=None, end_date=None, project=None, customer=None):
    if not project:
        return {"data": []}

    # Initialize conditions for SQL queries
    condition = ""  
    app_condition = ""
    
    if user:
        condition += f" AND mcr.employee = '{user}'"
        app_condition += f" AND a.employee = '{user}'"
    if project:
        app_condition += f" AND a.project = '{project}'"
        
    # Application intervals query
    application_intervals = frappe.db.sql(f"""
        SELECT 
            e.employee_name AS employee, 
            a.employee AS employee_id,
            a.from_time as start_time,
            a.to_time as end_time
        FROM `tabApplication Usage log` as a
        Join `tabEmployee` as e on e.name = a.employee
        WHERE a.date >= '{start_date}' 
        AND a.date <= '{end_date}'
        {app_condition}
    """, as_dict=True)

    # Meeting intervals query
    meeting_intervals = frappe.db.sql(f"""
        SELECT 
            mcr.employee AS employee_id,
            e.employee_name AS employee,
            m.meeting_from as start_time,
            m.meeting_to as end_time
        FROM `tabMeeting` AS m
        JOIN `tabMeeting Company Representative` AS mcr ON mcr.parent = m.name
        LEFT JOIN `tabEmployee` e ON e.name = mcr.employee
        WHERE m.meeting_from >= '{start_date} 00:00:00' 
        AND m.meeting_to <= '{end_date} 23:59:59' 
        AND m.docstatus = 1 
        {condition} 
        AND m.project = '{project}'
    """, as_dict=True)

    # Calls intervals query
    calls_intervals = []
    if user and customer:
        calls_intervals = frappe.db.sql(f"""
            SELECT 
                employee AS employee_id,
                employee_name AS employee,
                call_datetime as start_time,
                ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time
            FROM `tabEmployee Fincall` 
            WHERE date >= '{start_date}'
            AND date <= '{end_date}'
            AND link_name = '{customer}'
            AND employee = '{user}'
            AND (calltype != 'Missed' AND calltype != 'Rejected')
        """, as_dict=True)

    # Process employee data
    employee_data = {}
    
    # Helper function to calculate duration in seconds
    def get_duration(start_time, end_time):
        if isinstance(start_time, str):
            start_time = frappe.utils.get_datetime(start_time)
        if isinstance(end_time, str):
            end_time = frappe.utils.get_datetime(end_time)
        return (end_time - start_time).total_seconds()

    # Process each employee's data
    for intervals in [application_intervals, meeting_intervals, calls_intervals]:
        for interval in intervals:
            emp_id = interval['employee_id']
            if emp_id not in employee_data:
                employee_data[emp_id] = {
                    'employee': interval['employee'],
                    'intervals': [],
                    'app_intervals': [],
                    'meeting_intervals': [],
                    'call_intervals': []
                }
            
            if intervals == application_intervals:
                employee_data[emp_id]['app_intervals'].append(interval)
            elif intervals == meeting_intervals:
                employee_data[emp_id]['meeting_intervals'].append(interval)
            elif intervals == calls_intervals:
                employee_data[emp_id]['call_intervals'].append(interval)
            
            employee_data[emp_id]['intervals'].append(interval)

    # Process the intervals for each employee
    result_data = []
    for emp_id, emp_data in employee_data.items():
        if not emp_data['intervals']:
            continue

        sorted_intervals = sorted(emp_data['intervals'], key=lambda x: x['start_time'])
        merged_intervals = []
        current_interval = sorted_intervals[0]
        
        for interval in sorted_intervals[1:]:
            if get_duration(interval['start_time'], current_interval['end_time']) > 0:
                current_interval['end_time'] = max(
                    current_interval['end_time'],
                    interval['end_time'],
                    key=lambda x: frappe.utils.get_datetime(x)
                )
            else:
                merged_intervals.append(current_interval)
                current_interval = interval
        
        merged_intervals.append(current_interval)

        total_duration = sum(get_duration(interval['start_time'], interval['end_time']) 
                           for interval in merged_intervals)

        app_duration = sum(get_duration(interval['start_time'], interval['end_time']) 
                         for interval in emp_data['app_intervals'])
        meeting_duration = sum(get_duration(interval['start_time'], interval['end_time']) 
                             for interval in emp_data['meeting_intervals'])
        call_duration = sum(get_duration(interval['start_time'], interval['end_time']) 
                          for interval in emp_data['call_intervals'])

        result_data.append({
            'employee': emp_data['employee'],
            'employee_id': emp_id,
            'total_duration': total_duration,
            'application_duration': app_duration,
            'meeting_duration': meeting_duration,
            'call_duration': call_duration
        })

    result_data = sorted(result_data, key=lambda x: x['total_duration'], reverse=True)
    
    return {
        "data": result_data
    }

import frappe
from frappe import _
from datetime import datetime, timedelta
from frappe.utils import getdate, get_first_day, get_last_day, add_days
from collections import defaultdict


def execute(filters=None):
    start_time = frappe.utils.now_datetime()
    columns = get_columns(filters)
    data = get_data(filters)
    end_time = frappe.utils.now_datetime()
    duration = (end_time - start_time).total_seconds()
    

    frappe.log_error(
        title=f'full execution {duration}', 
        message=f"time in full execution {start_time} {end_time} {duration}"
    )
    return columns, data


def get_columns(filters):
    columns = []
    
    # If show_deployment_rate, resource_based_project, and show_employee_details are all checked,
    # show employee_name, deployed_hours, available_hours and deployment_rate columns
    if filters.get("show_deployment_rate") and filters.get("resource_based_project") and filters.get("show_employee"):
        columns = [
            {
                "fieldname": "employee_name",
                "label": _("Employee"),
                "fieldtype": "Data",
                "width": 150
            },
            {
                "fieldname": "total_hours",
                "label": _("Deployed Hours"),
                "fieldtype": "Float",
                "width": 100
            },
            {
                "fieldname": "available_hours",
                "label": _("Available Hours"),
                "fieldtype": "Float",
                "width": 100
            },
            {
                "fieldname": "deployment_rate",
                "label": _("Deployment Rate (%)"),
                "fieldtype": "Float",
                "width": 100
            }
        ]
        return columns
    
    # Date column if showing daily data
    if filters.get("show_daily_data"):
        columns.append({
            "fieldname": "date",
            "label": _("Date"),
            "fieldtype": "Date",
            "width": 100
        })
    
    # Employee column if showing employee data
    if filters.get("show_employee"):
        columns.append({
            "fieldname": "employee_name",
            "label": _("Employee"),
            "fieldtype": "Data",
            "width": 150
        })
    
    columns.extend([
        {
            "fieldname": "project",
            "label": _("Project"),
            "fieldtype": "Link",
            "options": "Project",
            "width": 150
        },
        {
            "fieldname": "total_hours",
            "label": _("Total Hours"),
            "fieldtype": "Float",
            "width": 100
        }
    ])
    
    # Add additional columns for detailed breakdown if needed
    if filters.get("show_details"):
        columns.extend([
            {
                "fieldname": "application_hours",
                "label": _("Application Hours"),
                "fieldtype": "Float",
                "width": 100
            },
            {
                "fieldname": "meeting_hours",
                "label": _("Meeting Hours"),
                "fieldtype": "Float",
                "width": 100
            },
            {
                "fieldname": "call_hours",
                "label": _("Call Hours"),
                "fieldtype": "Float",
                "width": 100
            }
        ])
    
    return columns


def get_data(filters):
    # Build date conditions
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    project = filters.get("project")
    employee = filters.get("employee")
    
    # Get daily working hours settings
    daily_working_hours = frappe.db.get_single_value('Productify Subscription', 'working_hours_per_day')
    saturday_working_hours = frappe.db.get_single_value('Productify Subscription', 'working_hours_on_saturday')
    
    # Prepare internal project condition
    is_internal = 1 if filters.get("is_internal_project") else 0
    
    # Optimization: Fetch all projects and their customers in one query to avoid multiple lookups
    project_customer_map = {}
    customer_projects_map = {}
    
    projects_data = frappe.db.sql("""
        SELECT p.name as project, p.customer, c.is_internal_customer
        FROM `tabProject` p
        JOIN `tabCustomer` c ON c.name = p.customer
        WHERE c.is_internal_customer = %s
    """, (is_internal,), as_dict=True)
    
    for p in projects_data:
        project_customer_map[p.project] = p.customer
        if p.customer not in customer_projects_map:
            customer_projects_map[p.customer] = []
        customer_projects_map[p.customer].append(p.project)
    
    # Build the project filter based on the above data if a project is specified
    project_filter = ""
    params = {"project": project} if project else {}
    
    if project:
        project_filter = "AND name = %(project)s"

    # Handle resource_based and hourly_based filters
    if filters.get("resource_based_project") and filters.get("hourly_based_project"):
        project_filter += " AND (resource_based_project = 1 OR based_on_hourly_package = 1)"
    elif filters.get("resource_based_project"):
        project_filter += " AND resource_based_project = 1"
    elif filters.get("hourly_based_project"):
        project_filter += " AND based_on_hourly_package = 1"
    
    # Filter to only get relevant projects
    query = f"""
        SELECT name 
        FROM `tabProject` 
        WHERE customer IN (
            SELECT name FROM `tabCustomer` WHERE is_internal_customer = {is_internal}
        ) {project_filter}
    """
    
    valid_projects = frappe.db.sql(query, params, as_dict=True)
    valid_project_names = [p.name for p in valid_projects]
    
    # If no valid projects, return empty result
    if not valid_project_names:
        return []
    
    # Format the list for IN clause
    project_list = "', '".join(valid_project_names)
    project_list = f"('{project_list}')" if project_list else "(NULL)"
    
    # Application intervals query
    employee_filter = f"AND a.employee = '{employee}'" if employee else ""
    start_time = frappe.utils.now_datetime()
    application_intervals = frappe.db.sql(f"""
        SELECT 
            a.employee_name, 
            a.employee AS employee_id,
            a.project,
            a.from_time as start_time,
            a.to_time as end_time,
            DATE(a.from_time) as date,
            'application' as activity_type
        FROM `tabApplication Usage log` as a
        WHERE a.date BETWEEN '{from_date}' AND '{to_date}'
        {employee_filter}
        AND a.project IN {project_list}
    """, as_dict=True)
    end_time = frappe.utils.now_datetime()
    duration = (end_time - start_time).total_seconds()
    frappe.log_error(
        title=f'application_intervals {duration}', 
        message=f"time in application_intervals {start_time} {end_time} {duration}"
    )
    # Meeting intervals query
    employee_filter = f"AND mcr.employee = '{employee}'" if employee else ""
    meeting_intervals = frappe.db.sql(f"""
        SELECT 
            mcr.employee AS employee_id,
            e.employee_name,
            m.project,
            m.meeting_from as start_time,
            m.meeting_to as end_time,
            DATE(m.meeting_from) as date,
            'meeting' as activity_type
        FROM `tabMeeting` AS m
        JOIN `tabMeeting Company Representative` AS mcr ON mcr.parent = m.name
        LEFT JOIN `tabEmployee` e ON e.name = mcr.employee
        WHERE m.meeting_from >= '{from_date} 00:00:00' 
        AND m.meeting_to <= '{to_date} 23:59:59' 
        AND m.docstatus = 1
        AND m.project IN {project_list}
        {employee_filter}
    """, as_dict=True)
    
    # Get all valid customers for the call query
    valid_customers = list(customer_projects_map.keys()) if customer_projects_map else []
    
    # If specific project is requested, narrow down to just that customer
    if project and project in project_customer_map:
        valid_customers = [project_customer_map[project]]
    
    # Format customer list for IN clause
    if valid_customers:
        customer_list = "', '".join(valid_customers)
        customer_list = f"('{customer_list}')"
    else:
        customer_list = "(NULL)"  # No valid customers
    
    # Calls intervals query
    employee_filter = f"AND employee = '{employee}'" if employee else ""
    calls_intervals = frappe.db.sql(f"""
        SELECT 
            employee AS employee_id,
            employee_name,
            NULL as project,
            call_datetime as start_time,
            ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time,
            date,
            'call' as activity_type,
            link_name as customer
        FROM `tabEmployee Fincall` 
        WHERE date BETWEEN '{from_date}' AND '{to_date}'
        AND calltype NOT IN ('Missed', 'Rejected')
        AND link_to = 'Customer'
        AND link_name IN {customer_list}
        {employee_filter}
    """, as_dict=True)
    
    # Optimization: Map projects to calls once, using the pre-loaded customer-projects mapping
    for call in calls_intervals:
        customer = call.get('customer')
        if customer and customer in customer_projects_map:
            # For simplicity, assign the first project of this customer
            if customer_projects_map[customer]:
                call['project'] = customer_projects_map[customer][0]
    
    # Remove calls without project assignment
    calls_intervals = [call for call in calls_intervals if call.get('project')]
    
    # Convert all datetime strings to actual datetime objects once to avoid repeated conversions
    for intervals in [application_intervals, meeting_intervals, calls_intervals]:
        for interval in intervals:
            if 'start_time' in interval and isinstance(interval['start_time'], str):
                interval['start_time'] = frappe.utils.get_datetime(interval['start_time'])
            if 'end_time' in interval and isinstance(interval['end_time'], str):
                interval['end_time'] = frappe.utils.get_datetime(interval['end_time'])
    
    # Determine grouping keys based on filter settings
    group_keys = []
    if filters.get("show_daily_data"):
        group_keys.append("date")
    if filters.get("show_employee"):
        group_keys.append("employee_id")
    group_keys.append("project")  # Always group by project
    
    # For deployment rate, we need to group by employee
    if filters.get("show_deployment_rate") and filters.get("resource_based_project") and filters.get("show_employee"):
        # Only include employee_id in group_keys if not already there
        if "employee_id" not in group_keys:
            group_keys = ["employee_id"]  # We'll only be grouping by employee for deployment rate
    
    # Process data using optimized aggregation
    result_data = calculate_time_aggregates(
        application_intervals, 
        meeting_intervals, 
        calls_intervals,
        group_keys
    )
    
    # Filter for deployment rate if needed
    if filters.get("show_deployment_rate") and filters.get("resource_based_project") and filters.get("show_employee"):
        # Create a dictionary to aggregate hours by employee
        employee_hours = defaultdict(lambda: {"total_hours": 0, "employee_name": "", "employee_id": ""})
        
        # Collect unique employees for calculating available hours
        unique_employees = set()
        # Aggregate hours for each employee where application_hours > 0
        for row in result_data:
            employee_id = row.get("employee_id")
            if employee_id and row.get("application_hours", 0) > 0:
                employee_hours[employee_id]["total_hours"] += row.get("total_hours", 0)
                employee_hours[employee_id]["employee_name"] = row.get("employee_name", "")
                employee_hours[employee_id]["employee_id"] = employee_id
                unique_employees.add(employee_id)
        # Import the function and calculate available hours for each employee
        from productivity_next.api import calculate_total_working_hours
        # Calculate available hours for each unique employee
        for employee_id in unique_employees:
            available_hours = calculate_total_working_hours(
                employee_id, 
                from_date, 
                to_date, 
                daily_working_hours, 
                saturday_working_hours
            )
            frappe.throw(str(available_hours))
            
            # Add available hours to employee data
            if employee_id in employee_hours:
                employee_hours[employee_id]["available_hours"] = available_hours
                
                # Calculate deployment rate as a percentage
                if available_hours > 0:
                    deployment_rate = (employee_hours[employee_id]["total_hours"] / available_hours) * 100
                    employee_hours[employee_id]["deployment_rate"] = round(deployment_rate, 2)
                else:
                    employee_hours[employee_id]["deployment_rate"] = 0
        
        # Convert to list format
        result_data = [
            {
                "employee_name": data["employee_name"],
                "total_hours": round(data["total_hours"], 2),
                "available_hours": round(data.get("available_hours", 0), 2),
                "deployment_rate": data.get("deployment_rate", 0)
            }
            for employee_id, data in employee_hours.items()
        ]
        
        # Sort by deployed hours (total_hours) in descending order
        result_data.sort(key=lambda x: -x.get('total_hours', 0))
        
        return result_data
    
    # Sort results appropriately based on filters
    if filters.get("show_daily_data"):
        result_data.sort(key=lambda x: (x['date'], -x['total_hours']))
    else:
        result_data.sort(key=lambda x: -x['total_hours'])
    
    return result_data


def calculate_time_aggregates(application_intervals, meeting_intervals, calls_intervals, group_keys):
    
    """
    Optimized function that calculates time aggregates without repeated calls to merge_intervals.
    Processes all intervals at once per group and calculates non-overlapping time.
    """
    start_time = frappe.utils.now_datetime()
    # Group intervals by keys
    grouped_data = defaultdict(lambda: {
        'intervals': {
            'application': [],
            'meeting': [],
            'call': []
        },
        'details': {}
    })
    
    # Helper function to get group key from an interval
    def get_group_key(interval, keys):
        return tuple(str(interval.get(key)) for key in keys)
    
    # Group all intervals
    for interval in application_intervals:
        key = get_group_key(interval, group_keys)
        grouped_data[key]['intervals']['application'].append((interval['start_time'], interval['end_time']))
        # Store group identification info
        for gk in group_keys:
            grouped_data[key]['details'][gk] = interval.get(gk)
        if 'employee_name' in interval:
            grouped_data[key]['details']['employee_name'] = interval['employee_name']
    
    for interval in meeting_intervals:
        key = get_group_key(interval, group_keys)
        grouped_data[key]['intervals']['meeting'].append((interval['start_time'], interval['end_time']))
        # Store group identification info
        for gk in group_keys:
            grouped_data[key]['details'][gk] = interval.get(gk)
        if 'employee_name' in interval:
            grouped_data[key]['details']['employee_name'] = interval['employee_name']
    
    for interval in calls_intervals:
        key = get_group_key(interval, group_keys)
        if interval.get('project'):  # Skip calls without project
            grouped_data[key]['intervals']['call'].append((interval['start_time'], interval['end_time']))
            # Store group identification info
            for gk in group_keys:
                grouped_data[key]['details'][gk] = interval.get(gk)
            if 'employee_name' in interval:
                grouped_data[key]['details']['employee_name'] = interval['employee_name']
    
    # Calculate non-overlapping time for each group
    result_data = []
    
    for key, data in grouped_data.items():
        # Skip if no intervals
        if not any(data['intervals'].values()):
            continue
        
        # Calculate non-overlapping hours for each activity type and total
        app_hours = calculate_non_overlapping_hours(data['intervals']['application'])
        meeting_hours = calculate_non_overlapping_hours(data['intervals']['meeting'])
        call_hours = calculate_non_overlapping_hours(data['intervals']['call'])
        
        # Calculate total non-overlapping hours from all activity types combined
        all_intervals = []
        all_intervals.extend(data['intervals']['application'])
        all_intervals.extend(data['intervals']['meeting'])
        all_intervals.extend(data['intervals']['call'])
        total_hours = calculate_non_overlapping_hours(all_intervals)
        
        # Round to 2 decimal places
        total_hours = round(total_hours, 2)
        app_hours = round(app_hours, 2)
        meeting_hours = round(meeting_hours, 2)
        call_hours = round(call_hours, 2)
        
        # Ensure activity hours don't exceed total hours
        sum_activity_hours = app_hours + meeting_hours + call_hours
        if sum_activity_hours > total_hours and sum_activity_hours > 0:
            # Apply proportional adjustment
            factor = total_hours / sum_activity_hours
            app_hours = round(app_hours * factor, 2)
            meeting_hours = round(meeting_hours * factor, 2)
            call_hours = round(call_hours * factor, 2)
        
        # Create result row with details and hours
        result_row = {
            'total_hours': total_hours,
            'application_hours': app_hours,
            'meeting_hours': meeting_hours,
            'call_hours': call_hours
        }
        
        # Add group keys from details
        for gk in group_keys:
            if gk in data['details']:
                result_row[gk] = data['details'][gk]
        
        # Add employee name if present
        if 'employee_name' in data['details']:
            result_row['employee_name'] = data['details']['employee_name']
        
        result_data.append(result_row)
    end_time = frappe.utils.now_datetime()
    duration = (end_time - start_time).total_seconds()
    

    frappe.log_error(
        title=f'calculate_time_aggregates {duration}', 
        message=f"time in calculate_time_aggregates {start_time} {end_time} {duration}"
    )
    return result_data


def calculate_non_overlapping_hours(intervals):
    """
    Calculate total non-overlapping hours from a list of (start, end) tuples.
    This is a highly optimized version that completely replaces the merge_intervals function.
    """
    start_time = frappe.utils.now_datetime()
    if not intervals:
        return 0
    
    # Sort intervals by start time
    intervals.sort()
    
    total_seconds = 0
    current_start, current_end = intervals[0]
    
    for start, end in intervals[1:]:
        if start <= current_end:
            # Overlapping interval, extend current_end if needed
            current_end = max(current_end, end)
        else:
            # Non-overlapping interval, add current interval to total and start a new one
            total_seconds += (current_end - current_start).total_seconds()
            current_start, current_end = start, end
    
    # Add the last interval
    total_seconds += (current_end - current_start).total_seconds()
    end_time = frappe.utils.now_datetime()
    duration = (end_time - start_time).total_seconds()
    

    frappe.log_error(
        title=f'calculate_non_overlapping_hours {duration}', 
        message=f"time in calculate_non_overlapping_hours {start_time} {end_time} {duration}"
    )
    # Convert to hours
    return total_seconds / 3600
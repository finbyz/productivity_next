import frappe
from frappe import _
from datetime import datetime, timedelta
from frappe.utils import getdate, get_first_day, get_last_day, add_days
from collections import defaultdict
from frappe.utils import flt

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
    if filters.get("show_deployment_rate"):
        columns = [
            {
                "fieldname": "employee_name",
                "label": _("Resource"),
                "fieldtype": "Data",
                "width": 150
            },
            {
                "fieldname": "days_available",
                "label": _("Days Available"),
                "fieldtype": "Int",
                "width": 100
            },
            {
                "fieldname": "hours_per_day",
                "label": _("Hours Per Day"),
                "fieldtype": "Float",
                "width": 100
            },
            {
                "fieldname": "leaves",
                "label": _("Leaves in this period"),
                "fieldtype": "Float",
                "width": 150
            },
            {
                "fieldname": "weekly_hours",
                "label": _("Total Hours"),
                "fieldtype": "Float",
                "width": 100
            },
            {
                "fieldname": "dedicated_hours",
                "label": _("Dedicated Hours"),
                "fieldtype": "Float",
                "width": 100
            },
            {
                "fieldname": "support_hours",
                "label": _("Support Hours"),
                "fieldtype": "Float",
                "width": 100
            },
            {
                "fieldname": "total_billable",
                "label": _("Total Billable"),
                "fieldtype": "Float",
                "width": 100
            },
            {
                "fieldname": "percentage_billable",
                "label": _("% Billable"),
                "fieldtype": "Percent",
                "width": 100
            },
            {
                "fieldname": "internal_hours",
                "label": _("Internal Task Hours"),
                "fieldtype": "Float",
                "width": 100
            },
            {
                "fieldname": "non_hourly_issue_hours",
                "label": _("Non-Hourly Issue Hours"),
                "fieldtype": "Float",
                "width": 150
            },
            {
                "fieldname": "total_utilized_hours",
                "label": _("Total Utilised Hours"),
                "fieldtype": "Float",
                "width": 150
            },
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
    # If deployment rate report is requested
    if filters.get("show_deployment_rate"):
        return get_deployment_rate_data(filters)
    
    # Build date conditions
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    project = filters.get("project")
    employee = filters.get("employee")
    
    # Get daily working hours settings
    daily_working_hours = frappe.db.get_single_value('Productify Subscription', 'deliverable_hours_per_day')
    saturday_working_hours = frappe.db.get_single_value('Productify Subscription', 'deliverable_hours_on_saturday')
    
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
    
    # IMPORTANT FIX: First calculate with employee_id to properly handle overlaps
    # Always include employee_id in initial grouping to correctly calculate non-overlapping time per employee
    calculate_keys = group_keys.copy()
    calculate_keys.append("employee_id")
    calculate_keys.append("project")  # Always group by project
    
    # Process data using optimized aggregation but keeping employee separations
    detailed_result = calculate_time_aggregates(
        application_intervals, 
        meeting_intervals, 
        calls_intervals,
        calculate_keys
    )
    
    # If we don't need to show employee data, aggregate across employees for each project
    if not filters.get("show_employee"):
        # Define display grouping keys (without employee_id)
        display_keys = group_keys.copy()
        display_keys.append("project")
        
        # Group data by project (and date if needed) across employees
        aggregated_result = {}
        for row in detailed_result:
            # Create a key without employee_id
            key_parts = []
            for k in display_keys:
                key_parts.append(str(row.get(k, '')))
            key = tuple(key_parts)
            
            if key not in aggregated_result:
                # Initialize a new entry
                new_row = {k: row.get(k) for k in display_keys}
                new_row.update({
                    'total_hours': 0,
                    'application_hours': 0,
                    'meeting_hours': 0,
                    'call_hours': 0
                })
                aggregated_result[key] = new_row
            
            # Add hours
            aggregated_result[key]['total_hours'] += row.get('total_hours', 0)
            aggregated_result[key]['application_hours'] += row.get('application_hours', 0)
            aggregated_result[key]['meeting_hours'] += row.get('meeting_hours', 0)
            aggregated_result[key]['call_hours'] += row.get('call_hours', 0)
        
        # Convert back to list
        result_data = list(aggregated_result.values())
    else:
        # If showing employee data, use the detailed result
        result_data = detailed_result
    
    # Round values for all rows
    for row in result_data:
        row['total_hours'] = round(row.get('total_hours', 0), 2)
        row['application_hours'] = round(row.get('application_hours', 0), 2)
        row['meeting_hours'] = round(row.get('meeting_hours', 0), 2)
        row['call_hours'] = round(row.get('call_hours', 0), 2)
    
    # Sort results appropriately based on filters
    if filters.get("show_daily_data"):
        result_data.sort(key=lambda x: (x['date'], -x['total_hours']))
    else:
        result_data.sort(key=lambda x: -x['total_hours'])
    
    return result_data

def get_deployment_rate_data(filters):
    """
    Generate deployment rate report data with additional columns for internal tasks, 
    non-hourly issues, and total utilized hours
    """
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    
    # Get all employees
    employees = frappe.db.sql("""
        SELECT employee as name, employee_name, user_id
        FROM `tabList of User`
    """, as_dict=True)
    
    # Get working hours settings
    daily_working_hours = frappe.db.get_single_value('Productify Subscription', 'deliverable_hours_per_day')
    saturday_working_hours = frappe.db.get_single_value('Productify Subscription', 'deliverable_hours_on_saturday')
    
    # Initialize result data
    result_data = []
    
    # Get project types
    project_types = frappe.db.sql("""
        SELECT p.name, p.resource_based_project, p.based_on_hourly_package, p.customer, c.is_internal_customer
        FROM `tabProject` p
        JOIN `tabCustomer` c ON c.name = p.customer
    """, as_dict=True)
    
    # Create project type lookup dictionaries
    resource_projects = {p.name for p in project_types if p.resource_based_project}
    internal_projects = {p.name for p in project_types if p.is_internal_customer}
    
    # For each employee, calculate their hours
    for emp in employees:
        employee_id = emp.name
        
        # Calculate available working hours
        available_hours = calculate_total_working_hours(
            employee_id, 
            from_date, 
            to_date, 
            flt(daily_working_hours), 
            flt(saturday_working_hours)
        )
        
        # Get days in the date range
        from_date_obj = datetime.strptime(str(from_date), '%Y-%m-%d')
        to_date_obj = datetime.strptime(str(to_date), '%Y-%m-%d')
        days_count = (to_date_obj - from_date_obj).days + 1
        
        # Get leave data for this employee
        leaves = frappe.db.sql("""
            SELECT COALESCE(SUM(total_leave_days), 0) as total_leaves
            FROM `tabLeave Application`
            WHERE employee = %s
            AND status = 'Approved'
            AND ((from_date BETWEEN %s AND %s) OR (to_date BETWEEN %s AND %s) OR (from_date <= %s AND to_date >= %s))
        """, (employee_id, from_date, to_date, from_date, to_date, from_date, to_date), as_dict=True)
        
        leave_days = leaves[0].total_leaves if leaves else 0
        combined_projects = resource_projects.union(internal_projects)
        project_list = "', '".join(combined_projects)
        project_list = f"('{project_list}')" if project_list else "(NULL)"
        
        # Application intervals query
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
            AND a.employee = '{employee_id}'
            AND a.project IN {project_list}
        """, as_dict=True)
        
        # Meeting intervals query
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
            AND mcr.employee = '{employee_id}'
        """, as_dict=True)
        
        # Get customer-project mapping
        project_customer_map = {}
        customer_projects_map = {}
        
        projects_data = frappe.db.sql("""
            SELECT name, customer
            FROM `tabProject`
        """, as_dict=True)
        
        for p in projects_data:
            if p.customer:
                project_customer_map[p.name] = p.customer
                if p.customer not in customer_projects_map:
                    customer_projects_map[p.customer] = []
                customer_projects_map[p.customer].append(p.name)
        
        # Get list of customers
        valid_customers = list(customer_projects_map.keys())
        
        # Format customer list for IN clause
        if valid_customers:
            customer_list = "', '".join(valid_customers)
            customer_list = f"('{customer_list}')"
        else:
            customer_list = "(NULL)"  # No valid customers
        
        # Calls intervals query
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
            AND employee = '{employee_id}'
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
        
        # Convert all datetime strings to actual datetime objects
        for intervals in [application_intervals, meeting_intervals, calls_intervals]:
            for interval in intervals:
                if 'start_time' in interval and isinstance(interval['start_time'], str):
                    interval['start_time'] = frappe.utils.get_datetime(interval['start_time'])
                if 'end_time' in interval and isinstance(interval['end_time'], str):
                    interval['end_time'] = frappe.utils.get_datetime(interval['end_time'])
        
        # Prepare interval categorization
        project_intervals = {
            'dedicated': [],     # Resource-based projects (external customers)
            'internal': [],      # Projects with internal customers
            'non_hourly': []     # Non-resource and non-hourly projects
        }
        
        # Categorize intervals by project type
        for interval in application_intervals + meeting_intervals + calls_intervals:
            project = interval.get('project')
            if project in resource_projects and project not in internal_projects:
                project_intervals['dedicated'].append((interval['start_time'], interval['end_time']))
            elif project in internal_projects:
                project_intervals['internal'].append((interval['start_time'], interval['end_time']))
        
        # Calculate hours for each category
        dedicated_hours = calculate_non_overlapping_hours(project_intervals['dedicated'])
        internal_hours = calculate_non_overlapping_hours(project_intervals['internal'])
        
        # Get support hours from Issue's time involvement table (hourly projects)
        user = emp.user_id
        support_hours_data = frappe.db.sql(f"""
            SELECT COALESCE(SUM(ti.time_involvement), 0) as total_support_hours
            FROM `tabIssue` i
            JOIN `tabTime Involvement` ti ON ti.parent = i.name
            JOIN `tabProject` p on i.project = p.name
            WHERE ti.user_name = '{user}'
            AND ti.date BETWEEN '{from_date}' AND '{to_date}'
            AND p.based_on_hourly_package = 1
        """, as_dict=True)
        
        # Get non-hourly issue hours 
        non_hourly_issue_hours_data = frappe.db.sql(f"""
            SELECT COALESCE(SUM(ti.time_involvement), 0) as total_support_hours
            FROM `tabIssue` i
            JOIN `tabTime Involvement` ti ON ti.parent = i.name
            JOIN `tabProject` p on i.project = p.name
            WHERE ti.user_name = '{user}'
            AND ti.date BETWEEN '{from_date}' AND '{to_date}'
            AND p.based_on_hourly_package = 0 
            AND p.resource_based_project = 0
        """, as_dict=True)
        
        support_hours = support_hours_data[0].total_support_hours if support_hours_data else 0
        non_hourly_issue_hours = non_hourly_issue_hours_data[0].total_support_hours if non_hourly_issue_hours_data else 0
        
        # Calculate total billable and utilized hours
        total_billable = dedicated_hours + support_hours
        total_utilized_hours = dedicated_hours + support_hours + internal_hours + non_hourly_issue_hours
        
        # Calculate percentage billable
        percentage_billable = (total_billable / available_hours * 100) if available_hours > 0 else 0
        
        # Create a row for this employee
        employee_row = {
            "employee_name": emp.employee_name,
            "days_available": days_count,
            "hours_per_day": daily_working_hours,
            "leaves": leave_days,
            "weekly_hours": available_hours,
            "dedicated_hours": round(dedicated_hours, 2),
            "support_hours": round(support_hours, 2),
            "internal_hours": round(internal_hours, 2),
            "non_hourly_issue_hours": round(non_hourly_issue_hours, 2),
            "total_billable": round(total_billable, 2),
            "total_utilized_hours": round(total_utilized_hours, 2),
            "percentage_billable": round(percentage_billable, 2)
        }
        
        result_data.append(employee_row)
    
    # Sort by percentage billable in descending order
    result_data.sort(key=lambda x: -x.get('percentage_billable', 0) if x.get('employee_name') != 'Total' else -999)
    
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


@frappe.whitelist()
def calculate_total_working_hours(employee, from_date, to_date, daily_working_hours, saturday_working_hours):
    from_date = datetime.strptime(str(from_date), '%Y-%m-%d')
    to_date = datetime.strptime(str(to_date), '%Y-%m-%d')
    date_range = [from_date + timedelta(days=x) for x in range((to_date - from_date).days + 1)]

    holidays = frappe.db.sql("""
        SELECT holiday_date 
        FROM `tabHoliday` 
        WHERE holiday_date BETWEEN %s AND %s
    """, (from_date, to_date), as_dict=True)
    holiday_dates = set(holiday.holiday_date for holiday in holidays)
    
    if not frappe.db.exists("DocType", "Leave Application"):
        leaves = []
    else:
        leaves = frappe.db.sql("""
            SELECT from_date, to_date, half_day
            FROM `tabLeave Application`
            WHERE employee = %s
            AND status = 'Approved'
            AND ((from_date BETWEEN %s AND %s) OR (to_date BETWEEN %s AND %s) OR (from_date <= %s AND to_date >= %s))
        """, (employee, from_date, to_date, from_date, to_date, from_date, to_date), as_dict=True)

    total_working_hours = 0
    for date in date_range:
        current_date = date.date()

        if current_date in holiday_dates:
            continue

        # Check if it's a Saturday (weekday 5) or Sunday (weekday 6)
        is_saturday = date.weekday() == 5
        is_sunday = date.weekday() == 6
        
        # Set initial hours based on day type
        if is_sunday:
            day_hours = 0  # No hours on Sunday
        elif is_saturday:
            day_hours = saturday_working_hours
        else:
            day_hours = daily_working_hours
            
        # Skip further calculations if already 0
        if day_hours == 0:
            continue
            
        # Apply leave deductions
        for leave in leaves:
            if leave.from_date <= current_date <= leave.to_date:
                if leave.half_day:
                    # For half-day leaves:
                    # If Saturday, set to 0 hours (skip the day)
                    # For other days, apply half of the daily hours
                    if is_saturday:
                        day_hours = 0
                    else:
                        day_hours *= 0.5
                else:
                    day_hours = 0  # Full day leave
                break

        total_working_hours += day_hours

    return total_working_hours
# Copyright (c) 2025, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt


from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cstr, getdate

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
	
    return columns, data

def get_columns(filters):  # Added filters parameter
    columns = [
        {
            "fieldname": "task",
            "label": _("Task"),
            "fieldtype": "Data",
            "width": 300
        },
        {
            "fieldname": "type",
            "label": _("Type"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "progress",
            "label": _(""),
            "fieldtype": "Data",
            "width": 70
        },
        {
            "fieldname": "assignee",
            "label": _("Assignee"),
            "fieldtype": "Link",
            "options": "User",
            "width": 200
        },
        {
            "fieldname": "exp_start_date",
            "label": _("Expected Start Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "exp_end_date",
            "label": _("Expected End Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "status_show",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "expected_time",
            "label": _("Expected Time (In Hours)"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "priority",
            "label": _("Priority"),
            "fieldtype": "Select",
            "options": "Low\nMedium\nHigh",
            "width": 80
        },
        {
            "fieldname": "description",
            "label": _("Description"),
            "fieldtype": "Text Editor",
            "width": 280
        },
        {
            "fieldname": "edit_task",
            "label": _(""),
            "fieldtype": "Button",
            "width": 200
        }
    ]

    if filters.get("show_completed_tasks"):  # Add completed_on column conditionally
        columns.insert(6, {  # Insert after status_show
            "fieldname": "completed_on",
            "label": _("Completed On"),
            "fieldtype": "Date",
            "width": 120
        })

    return columns

def get_data(filters):
    tasks = get_tasks(filters)
    projects = get_projects(filters)
    
    if not tasks and not projects:
        return []
    
    return prepare_data(filters, projects, tasks)

def get_projects(filters):
    conditions = ""
    if filters.get('project'):
        conditions += f" WHERE name = '{filters.get('project')}'"
    
    return frappe.db.sql("""
        SELECT 
            name,
            project_name as subject,
            status,
            priority,
            expected_start_date,
            expected_end_date,
            percent_complete,
            2 as is_group,  /* 2 for project to differentiate from tasks */
            1 as is_project
        FROM
            `tabProject`
        {conditions}
        ORDER BY name
    """.format(conditions=conditions), as_dict=True)

def prepare_data(filters, projects, tasks):
    data = []
    project_task_map = {}
    parent_children_map = {}
    
    for task in tasks:
        parent_children_map.setdefault(task.parent_task or task.project, []).append(task)
        project_task_map.setdefault(task.project, []).append(task)
    
    for project in projects:
        project_tasks = project_task_map.get(project.name, [])
        
        if project_tasks:
            project_progress = calculate_project_progress(project.name)
            project_progress_display = create_progress_display(project_progress)
            
            # Use create_status_display instead of passing colors separately
            project_data = frappe._dict({
                "project_id": project.name,
                "task": cstr(project.subject),
                "progress": project_progress_display,
                "status_show": create_status_display(project.status),  # Now returns formatted HTML
                "status":project.status,
                "expected_time":"",
                "priority": project.priority,
                "description": "",
                "assignee": "",
                "type":"",
                "indent": 0,
                "exp_start_date": project.expected_start_date,
                "exp_end_date": project.expected_end_date,
                "is_group": project.is_group,
                "is_project": project.is_project
            })
            data.append(project_data)
            
            grandparent_tasks = [t for t in project_tasks if t.task_type == 'grandparent']
            other_tasks = [t for t in project_tasks if t.task_type != 'grandparent']
            
            for gp_task in grandparent_tasks:
                add_task_to_data(data, gp_task, parent_children_map, 1, show_progress=True)
            
            if not grandparent_tasks:
                other_tasks.sort(key=lambda x: (x.parent_task or '', x.name))
                
                for task in other_tasks:
                    level = 0
                    current_parent = task.parent_task
                    while current_parent:
                        level += 1
                        parent_info = frappe.db.get_value('Task', current_parent, 
                            ['parent_task'], as_dict=True)
                        current_parent = parent_info.get('parent_task') if parent_info else None
                    
                    show_progress = level <= 1
                    task_name = '  ' * level + cstr(task.subject)
                    task_progress = calculate_task_progress(task.name) if show_progress else None
                    progress_display = create_progress_display(task_progress) if show_progress else ""
                    status_display = create_status_display(task.status)
                    task_data = frappe._dict({
                        "task": task_name,
                        "type":task.type,
                        "progress": progress_display,
                        "assignee": task.assignee,
                        "exp_start_date": task.exp_start_date,
                        "exp_end_date": task.exp_end_date,
                        "status": task.status,
                        "status_show": status_display,  # Now returns formatted HTML
                        "expected_time":task.expected_time,
                        "priority": task.priority,
                        "description": task.description,
                        "project": task.project,
                        "indent": level,
                        "is_group": task.is_group,
                        "is_project": task.is_project,
                        "task_id": task.name,
                        "completed_on":task.completed_on
                    })
                    data.append(task_data)
    
    return data

def add_task_to_data(data, task, parent_children_map, level, show_progress=False):
    # Calculate task progress
    task_progress = calculate_task_progress(task.name) if show_progress else None
    
    # Modify task name to include indentation
    task_name = '  ' * level + cstr(task.subject)
    
    # Create progress display with styling
    progress_display = create_progress_display(task_progress) if show_progress else ""
    
    # Create status display with styling - Fix: Use create_status_display
    status_display = create_status_display(task.status)

    data.append(frappe._dict({
        "task": task_name,
        "type":task.type,
        "progress": progress_display,
        "assignee": task.assignee,
        "exp_start_date": task.exp_start_date,
        "exp_end_date": task.exp_end_date,
        "status": task.status,
        "status_show": status_display,  # Changed: Now using the formatted status
        "expected_time":task.expected_time,
        "priority": task.priority,
        "description": task.description,
        "indent": level,
        "is_group": task.is_group,
        "is_project": task.is_project,
        "project": task.project,
        "task_id": task.name,
        "completed_on": task.completed_on
    }))
    
    if task.name in parent_children_map:
        children = parent_children_map[task.name]
        children.sort(key=lambda x: x.name)
        for child in children:
            # Pass down the current show_progress setting
            add_task_to_data(data, child, parent_children_map, level + 1, show_progress)
 
def get_tasks(filters):
    conditions = []
    task_condition = ""

    # Filter by project
    if filters.get('project'):
        conditions.append(f"project = '{filters.get('project')}'")

    # Filter by task
    if filters.get('task'):
        task_project = frappe.db.get_value('Task', filters.get('task'), 'project')
        if task_project:
            conditions.append(f"project = '{task_project}'")
            task_condition = f"""
                (
                    name = '{filters.get('task')}' OR 
                    parent_task = '{filters.get('task')}' OR 
                    name IN (
                        SELECT name FROM tabTask 
                        WHERE parent_task IN (
                            SELECT name FROM tabTask 
                            WHERE parent_task = '{filters.get('task')}'
                        )
                    )
                )
            """

    # Filter out completed tasks if the flag is not set
    if not filters.get('show_completed_tasks'):
        conditions.append("status != 'Completed'")
    # Filter out cancelled tasks if the flag is not set
    if not filters.get('show_cancelled_tasks'):
        conditions.append("status != 'Cancelled'")

    # Filter by assignee
    if filters.get("assignee"):
        conditions.append(f"assignee = '{filters.get('assignee')}'")

    # Filter by expected start date range
    if filters.get("exp_start_date"):
        conditions.append(f"exp_start_date BETWEEN '{filters.get('exp_start_date')[0]}' AND '{filters.get('exp_start_date')[1]}'")

    if filters.get("completed_on"):
        conditions.append(f"completed_on BETWEEN '{filters.get('completed_on')[0]}' AND '{filters.get('completed_on')[1]}'")

    # Filter by status (multi-select)
    if filters.get("status"):
        statuses = ", ".join([f"'{status}'" for status in filters.get("status")])
        conditions.append(f"status IN ({statuses})")

    # Combine conditions
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    if task_condition:
        where_clause += f" AND {task_condition}"

    fields = """
        name,
        subject,
        IFNULL(parent_task, '') as parent_task,
        project,
        status,
        assignee as assignee,
        priority,
        description,
        exp_start_date,
        exp_end_date,
        completed_on,
        ROUND(expected_time, 2) as expected_time,
        type,
        CASE WHEN EXISTS (
            SELECT 1 FROM tabTask t2 
            WHERE t2.parent_task = tabTask.name
        ) THEN 1 ELSE 0 END as is_group,
        CASE 
            WHEN parent_task IS NULL THEN 'grandparent'
            ELSE 'child'
        END as task_type,
        0 as is_project
    """


    # Execute the query
    return frappe.db.sql(f"""
        SELECT 
            {fields}
        FROM
            tabTask
        WHERE 
            {where_clause}
        ORDER BY project, parent_task, name
    """, as_dict=True)

@frappe.whitelist()
def copy_project_tasks(original_project, new_project_name, new_assignee=None):
    """
    Copy all tasks from an original project to a new project, maintaining task hierarchy
    
    Args:
        original_project (str): Name of the source project
        new_project_name (str): Name of the destination project
        new_assignee (str, optional): New owner for copied tasks. Defaults to original Assignees.
    
    Returns:
        dict: Information about the new project and copied tasks
    """
    # Validate project exists
    if not frappe.db.exists('Project', new_project_name):
        frappe.throw(_('Project {} does not exist').format(new_project_name))
    
    # Use a more efficient query to get tasks
    original_tasks = frappe.get_list('Task', 
        filters={'project': original_project},
        fields=['name', 'subject', 'description', 'priority', 'parent_task', 'assignee'],
        order_by='lft'  # Ensures parent tasks are processed before children
    )
    
    # Batch processing to prevent timeout
    batch_size = 50  # Adjust based on your system's performance
    task_mapping = {}

        
    for i in range(0, len(original_tasks), batch_size):
        batch_tasks = original_tasks[i:i+batch_size]
        
        for task in batch_tasks:
            # Handle subject more robustly
            if ':' in task.subject:
                subject_part = task.subject.split(' : ', 1)[1].strip()
                subject = subject_part
            else:
                subject = task.subject
            
            # Prepare new task data
            new_task_data = {
                'doctype': 'Task',
                'subject': subject,
                'description': task.description,
                'status': 'Unplanned',  # Reset status for new project
                'priority': task.priority,
                'project': new_project_name,
                'assignee': new_assignee or task.assignee,
                # Reset date fields
                'exp_start_date': None,
                'exp_end_date': None,
            }
            
            # Create new task document
            new_task = frappe.get_doc(new_task_data)
            
            # Handle parent-child relationships
            if task.parent_task:
                # If parent task was already copied, use its new task ID
                if task.parent_task in task_mapping:
                    new_task.parent_task = task_mapping[task.parent_task]
            
            # Insert the new task
            new_task.insert(ignore_permissions=True)
            
            # Copy attachments from original task to new task
            copy_attachments('Task', task.name, 'Task', new_task.name)
            
            # Store mapping of original task ID to new task ID
            task_mapping[task.name] = new_task.name
        
        # Commit batch to prevent memory buildup
        frappe.db.commit()
    
    return {
        'message': _('Tasks copied successfully'),
        'new_project': new_project_name,
        'copied_tasks_count': len(task_mapping)
    }


def get_progress_color(progress):
    """
    Get the appropriate color based on the progress percentage
    
    Args:
        progress (int): Progress percentage (0-100)
    
    Returns:
        dict: Color styling for the progress indicator
    """
    if progress is None or progress == 0:
        return {
            'color': '#6b7280',  # Neutral gray
            'background-color': '#f3f4f6'
        }
    
    # If progress is less than 100, return orange/red tones
    if progress < 100:
        return {
            'color': '#c53030',  # Dark red
            'background-color': '#fff5f5'  # Light red background
        }
    # If progress is exactly 100, return green
    elif progress == 100:
        return {
            'color': '#286840',  # Dark green
            'background-color': '#eaf5ee'  # Light green background
        }

def get_status_styles(status):
    """Return color mapping for different statuses"""
    colors = {
        "Unplanned": ("#FFF0F0", "#FF0000"),  # Light red bg, red text
        "Overdue": ("#FFF0F0", "#FF4500"),    # Light red bg, orange-red text
        "In-Progress": ("#FFFFF0", "#997A00"), # Light yellow bg, darker yellow text
        "Open": ("#F8F0FF", "#800080"),        # Light purple bg, purple text
        "Pending Review": ("#FFF8F0", "#FFA500"),
        "Working": ("#FFF8F0", "#FFA500"),
        "Completed": ("#F0FFF0", "#008000"),
        "Cancelled": ("#F0F0F0", "#808080"),
        "Change Pending": ("#F0F8FF", "#4169E1"),
        "Scheduled": ("#F0F8FF", "#0000FF"),
        "Planned": ("#FFF0F8", "#FF69B4"),
        "Template": ("#F0F8FF", "#0000FF")
    }
    return colors.get(status, ("#F0F0F0", "#808080"))

def create_status_display(status):
    """
    Create HTML display for status similar to progress_display
    Returns formatted HTML string with appropriate styling
    """
    if not status:
        return ""
    
    bg_color, text_color = get_status_styles(status)
    
    html = f'''
        <div style="
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            background-color: {bg_color};
            color: {text_color};
            font-size: 12px;
            font-weight: 500;
            white-space: nowrap;
        ">
            {status}
        </div>
    '''
    return html

          
def create_progress_display(progress):
    """
    Create a styled progress display with color
    
    Args:     
        progress (int or None): Progress percentage
    
    Returns:
        str: HTML-formatted progress display with color styling
    """
    if progress is None:
        return ""
    
    # Get color styling
    progress_colors = get_progress_color(progress)
    
    # Create inline style
    progress_style = (
        f"color:{progress_colors['color']};"
        f"background-color:{progress_colors['background-color']};"
        "border-radius:20px;padding:2px 4px;"
    )
    
    # Return styled progress
    return f"<span style='{progress_style}'>{progress}%</span>"
       
def calculate_project_progress(project_name):
    """
    Calculate project progress based on all tasks within the project
    
    Args:
        project_name (str): Name of the project
    
    Returns:
        int: Overall project progress percentage
    """
    # Get all tasks in the project
    project_tasks = frappe.get_all('Task', 
        filters={'project': project_name},
        fields=['name', 'status']
    )
    
    # If no tasks, return None
    if not project_tasks:
        return None
    
    # Count total and completed tasks
    total_tasks = len(project_tasks)
    completed_tasks = sum(1 for task in project_tasks if task.status == 'Completed')
    
    # Calculate and return progress percentage
    return round((completed_tasks / total_tasks) * 100)
     
def calculate_task_progress(task_name):
    """
    Calculate task progress based on child tasks' completion
    
    Args:
        task_name (str): Name of the task to calculate progress for
    
    Returns:
        int or None: Percentage of completed child tasks, or None if no children
    """
    # Get all child tasks
    child_tasks = frappe.get_all('Task', 
        filters={'parent_task': task_name},
        fields=['name', 'status']
    )
    
    # If no child tasks, return None
    if not child_tasks:
        return None
    
    # Count total and completed child tasks
    total_tasks = len(child_tasks)
    completed_tasks = sum(1 for task in child_tasks if task.status == 'Completed')
    
    # Calculate and return progress percentage
    return round((completed_tasks / total_tasks) * 100)


def get_all_related_tasks(task_name):
    """
    Get direct child tasks for a given task
    
    Args:
        task_name (str): Name of the task to find child tasks for
    
    Returns:
        list: List of direct child task documents
    """
    # Find direct child tasks
    children = frappe.get_all('Task',
        filters={'parent_task': task_name},
        fields=['name', 'parent_task']
    )
    
    # Return only the direct children as full task documents
    related_tasks = []
    for child in children:
        related_tasks.append(frappe.get_doc('Task', child.name))
    
    return related_tasks
@frappe.whitelist()
def update_task(task_id, task_data, update_mode='single'):
    """
    Update a task and optionally its direct children
    
    Args:
        task_id (str): Task ID to update
        task_data (dict): Task data to update
        update_mode (str): 'single' or 'all' - determines whether to update direct children
    """
    if not isinstance(task_data, dict):
        task_data = frappe.parse_json(task_data)
        
    if not task_data:
        frappe.throw(_("No task data provided"))
    
    try:
        # Get the actual task name from the display name (removes indentation)
        actual_task_name = task_id
        if not actual_task_name:
            frappe.throw(_("Task not found"))
        
        # Always update the current task
        update_single_task(actual_task_name, task_data, True)
        
        # Only update direct children if update_mode is 'all'
        if update_mode == 'all':
            # Get only direct children tasks
            related_tasks = get_all_related_tasks(actual_task_name)
            
            # Update only direct children
            for related_task in related_tasks:
                update_single_task(related_task.name, task_data, False)
        
        frappe.db.commit()
        
        return {
            "message": _("Task updated successfully")
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), _("Task Update Error"))
        frappe.throw(_("Error updating task and related tasks: {0}").format(str(e)))
def update_single_task(task_name, task_data, update_description):
    """
    Update a single task with the provided data
    
    Args:
        task_name (str): Name of the task to update
        task_data (dict): New data for the task
    """
    task = frappe.get_doc('Task', task_name)
    
    # Map of frontend field names to database field names
    if update_description:
        task.description = task_data.get('description')
    
    task.assignee = task_data.get('assignee')
    task.exp_start_date = task_data.get('exp_start_date')
    task.exp_end_date = task_data.get('exp_end_date')
    task.type = task_data.get('type')
    # Validate task dates
    if task.exp_start_date and task.exp_end_date and task.exp_start_date > task.exp_end_date:
        frappe.throw(_("Expected End Date cannot be before Expected Start Date"))
    
    # Save the task with validate and notify flags
    task.flags.ignore_version = True  # Skip version creation
    task.save(ignore_permissions=True)
    
    # Add a comment to the task
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Task",
        "reference_name": task_name,
        "content": _("Task updated via Task Analysis Report by {0}").format(frappe.session.user)
    }).insert(ignore_permissions=True)

def get_actual_task_name(display_name):
    """
    Get the actual task name from the display name by removing indentation
    
    Args:
        display_name (str): Task name as displayed in the report (may include indentation)
    
    Returns:
        str: Actual task name from the database
    """
    # Remove any leading/trailing spaces and indentation
    clean_name = display_name.strip()
    
    # Try to find the task by subject
    task_name = frappe.db.get_value('Task', 
        {'subject': clean_name}, 
        'name'
    )
    
    if not task_name:
        # If not found, try to find by name directly
        task_name = frappe.db.get_value('Task', 
            {'name': clean_name}, 
            'name'
        )
    
    return task_name

def get_all_child_tasks(parent_task):
    """
    Get all child tasks recursively using a CTE (Common Table Expression)
    
    Args:
        parent_task (str): Parent task name
    
    Returns:
        list: List of child task documents
    """
    # First try using CTE if supported by the database
    try:
        return frappe.db.sql("""
            WITH RECURSIVE task_tree AS (
                -- Base case: direct children
                SELECT name, parent_task, 1 as level
                FROM `tabTask`
                WHERE parent_task = %(parent)s
                
                UNION ALL
                
                -- Recursive case: children of children
                SELECT t.name, t.parent_task, tt.level + 1
                FROM `tabTask` t
                INNER JOIN task_tree tt ON t.parent_task = tt.name
            )
            SELECT name 
            FROM task_tree
            ORDER BY level, name
        """, {'parent': parent_task}, as_dict=1)
    
    except Exception:
        # Fallback to non-recursive approach if CTE is not supported
        child_tasks = []
        tasks_to_process = [parent_task]
        processed_tasks = set()
        
        while tasks_to_process:
            current_task = tasks_to_process.pop(0)
            if current_task in processed_tasks:
                continue
                
            processed_tasks.add(current_task)
            
            children = frappe.get_all('Task',
                filters={'parent_task': current_task},
                fields=['name']
            )
            
            child_tasks.extend(children)
            tasks_to_process.extend([child.name for child in children])
        
        return child_tasks

def validate_task_permissions(task_name):
    """
    Validate if the current user has permission to edit the task
    
    Args:
        task_name (str): Name of the task to check
    """
    if not frappe.has_permission('Task', 'write', task_name):
        frappe.throw(_("No permission to edit task: {0}").format(task_name))

@frappe.whitelist()
def delete_task(task_data, delete_mode='single'):
    """
    Delete task and optionally its child tasks
    
    Args:
        task_data (dict): Task data containing task name
        delete_mode (str): 'single' for current task only, 'all' for task and all children
    """
    if not isinstance(task_data, dict):
        task_data = frappe.parse_json(task_data)
        
    if not task_data:
        frappe.throw(_("No task data provided"))
    
    try:
        # Get the task name (remove any indentation spaces)
        task_name = task_data.get('task', '').strip()
        if not task_name:
            frappe.throw(_("Task name is required"))
            
        # Get the actual task name from the display name
        actual_task_name = get_actual_task_name(task_name)
        if not actual_task_name:
            frappe.throw(_("Task not found"))
        
        # Validate permissions
        validate_task_permissions(actual_task_name)
        
        # Check for child tasks
        child_tasks = get_all_child_tasks(actual_task_name)
        if child_tasks and delete_mode != 'all':
            frappe.throw(_("Task has child tasks. Please delete child tasks first or use 'Delete with Children' option."))
        
        # Begin deletion process
        if delete_mode == 'all':
            # Delete child tasks first (in reverse order to avoid dependency issues)
            for child_task in reversed(child_tasks):
                delete_single_task(child_task.name)
        
        # Delete the main task
        delete_single_task(actual_task_name)
        
        frappe.db.commit()
        
        return {
            "message": _("Task deleted successfully") if delete_mode == 'single' 
                      else _("Task and all child tasks deleted successfully")
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), _("Task Delete Error"))
        frappe.throw(_("Error deleting task: {0}").format(str(e)))

def delete_single_task(task_name):
    """
    Delete a single task
    
    Args:
        task_name (str): Name of the task to delete
    """
    try:
        # Check if task exists
        if not frappe.db.exists("Task", task_name):
            frappe.throw(_("Task {0} does not exist").format(task_name))
        
        # Get task document
        task = frappe.get_doc("Task", task_name)
        
        # Check if task is already deleted
        if task.status == "Deleted":
            frappe.throw(_("Task {0} is already deleted").format(task_name))
        
        # Check if task is part of a project
        if task.project:
            validate_project_permissions(task.project)
        
        # Log deletion activity
        frappe.get_doc({
            "doctype": "Comment",
            "comment_type": "Deleted",
            "reference_doctype": "Task",
            "reference_name": task_name,
            "content": _("Task deleted by {0}").format(frappe.session.user)
        }).insert(ignore_permissions=True)
        
        # Delete the task
        frappe.delete_doc("Task", task_name, ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error deleting task {task_name}")
        raise e

def validate_project_permissions(project_name):
    """
    Validate if the current user has permission to modify tasks in the project
    
    Args:
        project_name (str): Name of the project to check
    """
    if not frappe.has_permission('Project', 'write', project_name):
        frappe.throw(_("No permission to modify tasks in project: {0}").format(project_name))

@frappe.whitelist()
def copy_task_hierarchy(task_data, new_project=None, new_assignee=None):
    """
    Copy a task and its entire hierarchy with attachments and descriptions
    
    Args:
        task_data (dict): Original task data
        new_project (str): Project to assign copied tasks to
        new_assignee (str): User to assign as Assignee for copied tasks
    """
    if not isinstance(task_data, dict):
        task_data = frappe.parse_json(task_data)
    try:
        actual_task_name = task_data.task_id
        if not actual_task_name:
            frappe.throw(_("Task not found"))
        
        # Create mapping to store original task ID to new task ID
        task_id_mapping = {}
        
        # Copy main task and get its children
        new_task = copy_single_task(actual_task_name, new_project, new_assignee, None)
        task_id_mapping[actual_task_name] = new_task.name
        
        # Get and copy all child tasks
        child_tasks = get_all_child_tasks(actual_task_name)
        for child in child_tasks:
            # Get the parent from the mapping
            new_parent = task_id_mapping.get(
                frappe.db.get_value('Task', child.name, 'parent_task')
            )
            # Copy the child task, assigning it to the new project
            new_child = copy_single_task(child.name, new_project, new_assignee, new_parent)
            task_id_mapping[child.name] = new_child.name
        
        frappe.db.commit()
        
        return {
            "message": _("Task hierarchy copied successfully"),
            "new_task_id": new_task.name
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), _("Task Copy Error"))
        frappe.throw(_("Error copying task: {0}").format(str(e)))

def copy_single_task(task_name, new_project, new_assignee, new_parent):
    """
    Copy a single task with its attachments
    
    Args:
        task_name (str): Name of the task to copy
        new_project (str): New project to assign
        new_assignee (str): New Assignee to assign
        new_parent (str): New parent task name
    
    Returns:
        Task: New task document
    """
    # Get original task
    orig_task = frappe.get_doc('Task', task_name)
    
    # Create new task
    new_task = frappe.new_doc('Task')
    
    # Copy all standard fields
    exclude_fields = ['name', 'parent_task', 'project', 'assignee', 'creation', 
                     'modified', 'modified_by', 'owner', 'docstatus', 'idx','depends_on', 'status', 'exp_start_date'
                     'exp_end_date','workflow_state']
    for field in orig_task.meta.fields:
        if field.fieldname not in exclude_fields:
            new_task.set(field.fieldname, orig_task.get(field.fieldname))
    
    # Set new values
    new_task.project = new_project if new_project else None
    new_task.assignee = new_assignee if new_assignee else None
    new_task.parent_task = new_parent if new_parent else None
    new_task.exp_start_date = None
    new_task.exp_end_date = None
    new_task.custom_allow_changing_expected_end = 1
    new_task.custom_allow_changing_expected_start = 1
    new_task.custom_allow_changing_mark_of_week = 1
    
    # Handle subject more robustly
    if ':' in orig_task.subject:
        # If colon exists, take the part after the colon
        subject_part = orig_task.subject.split(' : ', 1)[1].strip()
        new_task.subject = subject_part
    else:
        # If no colon, prepend the new project name
        new_task.subject = orig_task.subject
    
    # Save the new task
    new_task.insert(ignore_permissions=True)
    # Copy attachments
    copy_attachments(orig_task.doctype, orig_task.name, new_task.doctype, new_task.name)
    
    return new_task

def copy_attachments(from_doctype, from_name, to_doctype, to_name):
    """
    Copy attachments from one document to another
    
    Args:
        from_doctype (str): Source doctype
        from_name (str): Source document name
        to_doctype (str): Target doctype
        to_name (str): Target document name
    """
    files = frappe.db.sql("""
        SELECT name, file_url, file_name, is_private
        FROM tabFile 
        WHERE attached_to_doctype = %s 
        AND attached_to_name = %s
    """, (from_doctype, from_name), as_dict=1)
    
    for file in files:
        # Copy file
        new_file = frappe.new_doc('File')
        new_file.update({
            'file_url': file.file_url,
            'file_name': file.file_name,
            'is_private': file.is_private,
            'attached_to_doctype': to_doctype,
            'attached_to_name': to_name
        })
        new_file.insert(ignore_permissions=True)
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
            "fieldname": "id",
            "label": _("ID"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "type",
            "label": _("Type"),
            "fieldtype": "Data",
            "width": 80
        },
        {
            "fieldname": "progress",
            "label": _(""),
            "fieldtype": "Data",
            "width": 50
        },
        {
            "fieldname": "assignee",
            "label": _("Assignee"),
            "fieldtype": "Link",
            "options": "User",
            "width": 120
        },
        {
            "fieldname": "exp_start_date",
            "label": _("Expected Start Date"),
            "fieldtype": "Date",
            "width": 115
        },
        {
            "fieldname": "exp_end_date",
            "label": _("Expected End Date"),
            "fieldtype": "Date",
            "width": 115
        },
        {
            "fieldname": "status_show",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 80
        },
        {
            "fieldname": "expected_time",
            "label": _("Expected Time (In Hours)"),
            "fieldtype": "Data",
            "width": 55
        },
        {
            "fieldname": "priority",
            "label": _("Priority"),
            "fieldtype": "Select",
            "options": "Low\nMedium\nHigh",
            "width": 65
        },
        {
            "fieldname": "description",
            "label": _("Description"),
            "fieldtype": "Text Editor",
            "width": 150
        },
        {
            "fieldname": "edit_task",
            "label": _(""),
            "fieldtype": "Button",
            "width": 150
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
    project_filters = {}
    if filters.get('project'):
        project_filters["name"] = filters["project"]
    
    return frappe.get_all(
        "Project",
        filters=project_filters,
        fields=[
            "name",
            "project_name as subject",
            "status",
            "priority",
            "expected_start_date",
            "expected_end_date",
            "percent_complete",
        ],
        order_by="name"
    )

def prepare_data(filters, projects, tasks):
    data = []
    project_task_map = {}
    parent_children_map = {}
    user_first_names = {}

    # Get all unique assignees
    assignees = set()
    for task in tasks:
        if task.assignee:
            assignees.add(task.assignee)
    
    # Fetch first names for all assignees
    if assignees:
        user_data = frappe.get_all(
            "User",
            filters={"name": ("in", list(assignees))},
            fields=["name", "first_name"]
        )
        user_first_names = {u.name: u.first_name for u in user_data}
    # Build project and parent-child maps
    for task in tasks:
        project_task_map.setdefault(task.project, []).append(task)
        
        # Handle both direct parent-child and orphaned tasks
        if task.parent_task:
            parent_children_map.setdefault(task.parent_task, []).append(task)
        else:
            # For tasks without parent_task, map them directly under their project
            parent_children_map.setdefault(task.project, []).append(task)

    for project in projects:
        project_tasks = project_task_map.get(project.name, [])
        project_progress = calculate_project_progress(project.name)
        project_progress_display = create_progress_display(project_progress)
        
        if project_tasks:
            # Add project header
            project_data = frappe._dict({
                "project_id": project.name,
                "task": cstr(project.subject),
                "progress": project_progress_display,
                "status_show": create_status_display(project.status),
                "status":project.status,
                "expected_time": None,
                "priority": project.priority,
                "description": None,
                "assignee": None,
                "assignee_first_name": None,
                "type": None,
                "indent": 0,
                "exp_start_date": project.expected_start_date,
                "exp_end_date": project.expected_end_date,
                "is_group": 2,
                "is_project": 1
            })
            data.append(project_data)
            
            # Process all tasks for this project
            for task in project_tasks:
                # Only process tasks that don't have a parent or whose parent isn't in our task list
                if not task.parent_task or task.parent_task not in {t.name for t in tasks}:
                    add_task_to_data(data, task, parent_children_map, 1, user_first_names, show_progress=True)

    return data

def add_task_to_data(data, task, parent_children_map, level, user_first_names, show_progress=False):
    if task.is_group and task.status not in ["Cancelled", "Completed"]:
        task.status = "Open"
    # Add the current task
    task_progress = calculate_task_progress(task.name) if show_progress else None
    task_name = '  ' * level + str(task.subject)
    progress_display = create_progress_display(task_progress) if show_progress else ""
    status_display = create_status_display(task.status)
    

    data.append(frappe._dict({
        "task": task_name,
        "id" :  task.name,
        "parent_task":task.parent_task,
        "type":task.type,
        "progress": progress_display,
        "assignee": task.assignee,
        "assignee_first_name": user_first_names.get(task.assignee, ''),
        "exp_start_date": task.exp_start_date,
        "exp_end_date": task.exp_end_date,
        "status": task.status,
        "status_show": status_display,  
        "expected_time":task.expected_time,
        "priority": task.priority,
        "description": task.description,
        "indent": level,
        "is_group": task.is_group,
        "is_project": task.is_project,
        "project": task.project,
        "task_id": task.name,
        "completed_on": task.completed_on,
        "completed_by": task.completed_by
    }))

    # Process children if any exist
    children = parent_children_map.get(task.name, [])
    if children:
        # Sort children by name to maintain consistent order
        children.sort(key=lambda x: x.name)
        for child in children:
            add_task_to_data(data, child, parent_children_map, level + 1, user_first_names, show_progress)
            

def get_tasks(filters): 
    task_filters = {"is_template": 0}
    task_or_filters = {}

    # Filter by project
    if filters.get('project'):
        task_filters["project"] = filters['project']

    # Filter by task
    if filters.get('task'):
        sql = """WITH RECURSIVE `task_tree` AS (
            SELECT * FROM `tabTask` WHERE name = '{0}' or parent_task = '{0}'
            UNION ALL
            SELECT t.* FROM `tabTask` t
            INNER JOIN task_tree tt ON t.parent_task = tt.name
        )
        SELECT distinct name FROM task_tree"""
        
        if names := [row.name for row in frappe.db.sql(sql.format(filters.get('task')), as_dict=True)]:
            task_filters['name'] = ('in', names)

    # Filter by assignee
    if filters.get('assignee'):
        task_filters['assignee'] = filters['assignee']

    # Filter by expected start date
    if filters.get('exp_start_date'):
        task_filters['exp_start_date'] = ['between', filters.get('exp_start_date')]

    # Filter by status
    if filters.get('status'):
        task_filters['status'] = ('in', filters.get('status'))

    # Filter by completed_on date if specified
    if filters.get('completed_on'):
        task_filters['completed_on'] = ['between', filters.get('completed_on')]

    # First get all tasks that match the direct criteria
    direct_tasks = frappe.get_all(
        "Task",
        filters=task_filters,
        fields=[
            "name", "subject", "status", "priority", "exp_start_date", "exp_end_date",
            "expected_time", "description", "is_group", "project", "parent_task",
            "assignee", "type", "completed_on", "completed_by"
        ],
        order_by="name"
    )

    # Get all parent tasks of matching tasks
    parent_tasks = set()
    for task in direct_tasks:
        current = task
        while current.get('parent_task'):
            parent_tasks.add(current.parent_task)
            current = frappe.get_value('Task', 
                current.parent_task, 
                ['name', 'parent_task', 'subject', 'status', 'priority', 'exp_start_date', 
                 'exp_end_date', 'expected_time', 'description', 'is_group', 'project', 
                 'assignee', 'type', 'completed_on', 'completed_by'], 
                as_dict=1)
            if not current:
                break

    # Get the parent task details
    additional_tasks = []
    if parent_tasks:
        additional_tasks = frappe.get_all(
            "Task",
            filters={"name": ("in", list(parent_tasks))},
            fields=[
                "name", "subject", "status", "priority", "exp_start_date", "exp_end_date",
                "expected_time", "description", "is_group", "project", "parent_task",
                "assignee", "type", "completed_on", "completed_by"
            ],
            order_by="name"
        )

    # Combine direct tasks and parent tasks
    all_tasks = direct_tasks + additional_tasks
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tasks = []
    for task in all_tasks:
        if task.name not in seen:
            seen.add(task.name)
            unique_tasks.append(task)

    return unique_tasks

# @frappe.whitelist()
# def copy_project_tasks(original_project, new_project_name, new_assignee=None):
#     """Copy all tasks from one project to another"""
#     try:
#         # Get all tasks from the original project
#         tasks = frappe.get_all(
#             'Task',
#             filters={'project': original_project},
#             fields=['*'],
#             order_by='parent_task, creation'
#         )
        
#         if not tasks:
#             frappe.throw(_('No tasks found in the original project'))
        
#         # Dictionary to store mapping of original task IDs to new task IDs
#         task_mapping = {}
        
#         # First pass: Create all tasks and store their mappings
#         for task in tasks:
#             # Create new task document
#             new_task = frappe.new_doc('Task')
            
#             # Copy all fields except name, parent_task, and system fields
#             exclude_fields = ['name', 'parent_task', 'creation', 'modified', 'modified_by', 
#                             'owner', 'docstatus', 'idx', 'exp_start_date', 'exp_end_date']
            
#             for field, value in task.items():
#                 if field not in exclude_fields:
#                     new_task.set(field, value)
            
#             # Set new project and assignee
#             new_task.project = new_project_name
#             if new_assignee:
#                 new_task.assignee = new_assignee
            
#             # Handle parent-child relationships
#             if task.parent_task:
#                 # If parent task was already copied, use its new task ID
#                 if task.parent_task in task_mapping:
#                     new_task.parent_task = task_mapping[task.parent_task]
            
#             # Set is_group=1 for parent tasks
#             if task.parent_task is None:
#                 new_task.is_group = 1
            
#             # Ensure type field is set
#             if not new_task.type:
#                 new_task.type = "Consulting"
            
#             # Set status to Open for new tasks
#             new_task.status = "Open"
            
#             # Insert the new task
#             new_task.insert(ignore_permissions=True)
            
#             # Copy attachments from original task to new task
#             copy_attachments('Task', task.name, 'Task', new_task.name)
            
#             # Store mapping of original task ID to new task ID
#             task_mapping[task.name] = new_task.name
        
#         # Commit batch to prevent memory buildup
#         frappe.db.commit()
        
#         return {
#             'message': _('Tasks copied successfully'),
#             'new_project': new_project_name
#         }
        
#     except Exception as e:
#         frappe.log_error(f"Error copying tasks from project {original_project} to {new_project_name}: {str(e)}", "Task Copy Error")
#         frappe.throw(_('Failed to copy tasks. Please check the error log for details.'))

# @frappe.whitelist()
# def copy_project_tasks(original_project, new_project_name, new_assignee=None):
#     """Copy all tasks from one project to another, preserving task hierarchy"""
   
#     root_tasks = frappe.get_all(
#         "Task",
#         filters={"project": original_project },
#         fields=["name"],
#         order_by="creation"
#     )

#     if not root_tasks:
#         frappe.throw(_("No tasks found in the original project"))

#     task_mapping = {}

#     for root in root_tasks:
#         copy_task_tree(
#             task_name=root.name,
#             new_project=new_project_name,
#             new_assignee=new_assignee,
#             new_parent=None,
#             task_mapping=task_mapping
#         )

#     frappe.db.commit()

#     return {
#         "message": _("Tasks copied successfully"),
#         "new_project": new_project_name
#     }

# def copy_task_tree(task_name, new_project, new_assignee=None, new_parent=None, task_mapping=None):
#     """Recursively copy a task and its children, preserving the hierarchy."""
#     if task_mapping is None:
#         task_mapping = {}

#     original_task = frappe.get_doc("Task", task_name)

#     new_task = frappe.new_doc("Task")

#     exclude_fields = [
#         'name', 'creation', 'modified', 'modified_by', 'owner', 'docstatus', 'idx',
#         'project', 'parent_task', 'exp_start_date', 'exp_end_date'
#     ]

#     for field in original_task.meta.fields:
#         if field.fieldname and field.fieldname not in exclude_fields:
#             new_task.set(field.fieldname, original_task.get(field.fieldname))

#     new_task.project = new_project
#     new_task.parent_task = new_parent
#     new_task.status = "Open"
#     new_task.type = original_task.type or "Consulting"
#     new_task.is_group = original_task.is_group

#     if new_assignee:
#         new_task.assignee = new_assignee
#     else:
#         new_task.assignee = original_task.assignee

#     new_task.insert(ignore_permissions=True)

#     # Copy attachments
#     copy_attachments("Task", original_task.name, "Task", new_task.name)

#     task_mapping[original_task.name] = new_task.name

#     # Recursively copy children
#     child_tasks = frappe.get_all(
#         "Task",
#         filters={"parent_task": original_task.name},
#         fields=["name"],
#         order_by="creation"
#     )

#     for child in child_tasks:
#         copy_task_tree(
#             task_name=child.name,
#             new_project=new_project,
#             new_assignee=new_assignee,
#             new_parent=new_task.name,
#             task_mapping=task_mapping
#         )

@frappe.whitelist()
def copy_project_tasks_async(original_project, new_project_name, new_assignee=None):
    """Enqueue background job to copy project tasks"""
    frappe.enqueue(
        method="productivity_next.task_enhancement.report.task_analysis.task_analysis.copy_project_tasks",
        queue='long',
        timeout=1800,  # 30 minutes
        original_project=original_project,
        new_project_name=new_project_name,
        new_assignee=new_assignee
    )
    return {"status": "queued", "message": "Task copy started in background."}

@frappe.whitelist()
def copy_project_tasks(original_project, new_project_name, new_assignee=None):
    """Copy all tasks from one project to another, preserving task hierarchy"""
    frappe.log_error(f"Starting task copy: {original_project} ➜ {new_project_name}")

    root_tasks = frappe.get_all(
        "Task",
        filters={"project": original_project},
        fields=["name"],
        order_by="creation"
    )

    if not root_tasks:
        frappe.log_error("No tasks found to copy", original_project)
        return

    task_mapping = {}

    for root in root_tasks:
        try:
            copy_task_tree(
                task_name=root.name,
                new_project=new_project_name,
                new_assignee=new_assignee,
                new_parent=None,
                task_mapping=task_mapping
            )
        except Exception as e:
            frappe.log_error(f"Failed to copy root task {root.name}: {e}")

    frappe.db.commit()
    frappe.publish_realtime("task_copy_done", {"message": f"Tasks copied to {new_project_name}."})

@frappe.whitelist()
def copy_task_tree(task_name, new_project, new_assignee=None, new_parent=None, task_mapping=None):
    """Recursively copy a task and its children"""
    task_mapping = task_mapping or {}

    try:
        original_task = frappe.get_doc("Task", task_name)

        new_task = frappe.new_doc("Task")

        exclude_fields = {
            'name', 'creation', 'modified', 'modified_by', 'owner', 'docstatus', 'idx',
            'project', 'parent_task', 'exp_start_date', 'exp_end_date'
        }

        for field in original_task.meta.fields:
            if field.fieldname and field.fieldname not in exclude_fields:
                new_task.set(field.fieldname, original_task.get(field.fieldname))

        new_task.project = new_project
        new_task.parent_task = new_parent
        new_task.status = "Open"
        new_task.type = original_task.type or "Consulting"
        new_task.is_group = original_task.is_group

        new_task.assignee = new_assignee or original_task.assignee
        new_task.insert(ignore_permissions=True)

        copy_attachments("Task", original_task.name, "Task", new_task.name)

        task_mapping[original_task.name] = new_task.name

        frappe.db.commit()  # Commit in batches to avoid lock/timeout

        # Fetch child tasks and copy recursively
        child_tasks = frappe.get_all(
            "Task",
            filters={"parent_task": original_task.name},
            fields=["name"],
            order_by="creation"
        )

        for child in child_tasks:
            copy_task_tree(
                task_name=child.name,
                new_project=new_project,
                new_assignee=new_assignee,
                new_parent=new_task.name,
                task_mapping=task_mapping
            )

    except Exception as e:
        frappe.log_error(f"Error copying task {task_name}: {e}")

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
    task.parent_task = task_data.get('parent_task')
    task.exp_start_date = task_data.get('exp_start_date')
    task.exp_end_date = task_data.get('exp_end_date')
    task.expected_time = task_data.get('expected_time')
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

# @frappe.whitelist()
# def copy_task_hierarchy(task_data, new_project=None, new_assignee=None):
#     """
#     Copy a task and its entire hierarchy with attachments and descriptions
    
#     Args:
#         task_data (dict): Original task data
#         new_project (str): Project to assign copied tasks to
#         new_assignee (str): User to assign as Assignee for copied tasks
#     """
#     if not isinstance(task_data, dict):
#         task_data = frappe.parse_json(task_data)
#     try:
#         actual_task_name = task_data.task_id
#         if not actual_task_name:
#             frappe.throw(_("Task not found"))
        
#         # Create mapping to store original task ID to new task ID
#         task_id_mapping = {}
        
#         # Copy main task and get its children
#         new_task = copy_single_task(actual_task_name, new_project, new_assignee, None)
#         task_id_mapping[actual_task_name] = new_task.name
        
#         # Get and copy all child tasks
#         child_tasks = get_all_child_tasks(actual_task_name)
#         for child in child_tasks:
#             # Get the parent from the mapping
#             new_parent = task_id_mapping.get(
#                 frappe.db.get_value('Task', child.name, 'parent_task')
#             )
#             # Copy the child task, assigning it to the new project
#             new_child = copy_single_task(child.name, new_project, new_assignee, new_parent)
#             task_id_mapping[child.name] = new_child.name
        
#         frappe.db.commit()
        
#         return {
#             "message": _("Task hierarchy copied successfully"),
#             "new_task_id": new_task.name
#         }
        
#     except Exception as e:
#         frappe.db.rollback()
#         frappe.log_error(frappe.get_traceback(), _("Task Copy Error"))
#         frappe.throw(_("Error copying task: {0}").format(str(e)))


@frappe.whitelist()
def copy_task_hierarchy(task_data, new_project=None, new_assignee=None):
    """
    Copy a task and its entire hierarchy while preserving structure.
    """
    
    if not isinstance(task_data, dict):
        task_data = frappe.parse_json(task_data)

    try:
        actual_task_name = task_data.get("task_id")
        if not actual_task_name:
            frappe.throw(_("Task ID not provided."))

        # Map original task name => new copied task name
        task_id_mapping = {}

        # Copy root task first
        new_task = copy_single_task(actual_task_name, new_project, new_assignee, None)
        task_id_mapping[actual_task_name] = new_task.name

        # Get all child tasks in hierarchical (top-down) order
        child_tasks = get_all_child_tasks_ordered(actual_task_name)

        # Copy children
        for child in child_tasks:
            original_parent = frappe.db.get_value("Task", child.name, "parent_task")
            new_parent = task_id_mapping.get(original_parent)

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

def get_all_child_tasks_ordered(root_task):
    """
    Recursively get all child tasks in depth-first order
    so parents are processed before their children.
    """
    ordered = []

    def fetch_children(task_name):
        children = frappe.get_all("Task", filters={"parent_task": task_name}, fields=["name"])
        for child in children:
            ordered.append(child)  # Add this child first
            fetch_children(child.name)  # Then its children

    fetch_children(root_task)
    return ordered


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
                     'modified', 'modified_by', 'owner', 'docstatus', 'idx','depends_on', 'status', 'exp_start_date',
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
    new_task.allow_changing_expected_end_date = 1
    new_task.allow_changing_expected_start_date = 1
    new_task.is_group = orig_task.is_group
    
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
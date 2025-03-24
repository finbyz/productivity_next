import frappe
from frappe import _

def before_validate(self, method):
    if not self.is_new():
        on_update(self, method)
        
def on_update(doc, method):
    """
    Update expected time in parent tasks when a task is saved
    
    Args:
        doc (Document): Task document being saved
        method (str): Trigger method (before_save, validate, etc.)
    """
    # Skip if this is not a task or if no parent task exists
    if doc.doctype != 'Task' or not doc.parent_task:
        return
    
    try:
        # Update only the parent tasks
        update_parent_tasks(doc.parent_task)
    except Exception as e:
        # Log detailed error for tracking
        frappe.log_error(
            title="Task Hierarchy Update Error", 
            message=f"Error updating task hierarchy for {doc.name}: {str(e)}"
        )
        # Throw a user-friendly error
        frappe.throw(_(f"Could not update task hierarchy: {str(e)}"))

def update_parent_tasks(parent_task):
    """
    Update expected time for parent tasks in the hierarchy
    
    Args:
        parent_task (str): Name of the parent task to update
    """
    task_doc = frappe.get_doc('Task', parent_task)
    
    # Get all direct child tasks of the current task
    child_tasks = frappe.get_all('Task', 
        filters={'parent_task': parent_task},
        fields=['name', 'expected_time']
    )
    # Skip if no child tasks
    if not child_tasks:
        return
    
    # Calculate total expected time from all child tasks
    # If expected_time is None for a child, treat it as 0
    total_expected_time = sum(task.expected_time or 0 for task in child_tasks)
    
    # Update the parent task's expected time
    task_doc.expected_time = total_expected_time

    # Save the task with minimal checks
    try:
        task_doc.flags.ignore_version = True
        task_doc.flags.ignore_validate = True
        task_doc.save(ignore_permissions=True)
    except Exception as save_error:
        frappe.log_error(
            title="Task Group Save Error", 
            message=f"Could not save task group {task_doc.name}: {str(save_error)}"
        )
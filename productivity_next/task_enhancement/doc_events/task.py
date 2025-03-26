import frappe
from frappe import _

def before_validate(self, method):
    validate_parent_task(self)
        
def validate_parent_task(self):
    """
    Validate parent task to ensure that a task is not made a child of itself
    
    Args:
        self (Document): Task document being saved
    """
    
    if self.name == self.parent_task:
        frappe.throw(_("Task cannot be a child of itself"))
    
    if self.parent_task and not frappe.get_cached_value('Task', self.parent_task, 'is_group'):
        frappe.throw(_("Is Group must be checked for parent task"))
    
    if self.parent_task and frappe.get_cached_value("Task", self.parent_task, "project") != self.project:
        frappe.throw(_("Parent Task must belong to the same project"))
        

def on_update(self, method):
    """
    Update expected time in parent tasks when a task is saved
    
    Args:
        doc (Document): Task document being saved
        method (str): Trigger method (before_save, validate, etc.)
    """
    
    if self.is_new():
        return

    # Skip if this is not a task or if no parent task exists
    if self.doctype != 'Task' or not self.parent_task:
        return
    
    try:
        # Update only the parent tasks
        update_parent_tasks(self.parent_task)
    except Exception as e:
        # Log detailed error for tracking
        frappe.log_error(
            title="Task Hierarchy Update Error", 
            message=f"Error updating task hierarchy for {self.name}: {str(e)}"
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
        task_doc.save(ignore_permissions=True)
    except Exception as save_error:
        frappe.log_error(
            title="Task Group Save Error", 
            message=f"Could not save task group {task_doc.name}: {str(save_error)}"
        )
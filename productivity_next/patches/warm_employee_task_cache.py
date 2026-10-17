"""Initialize employee active-task cache once during migration, without sending alerts."""

import frappe

from productivity_next.task_enhancement.employee_task_notifications import warm_active_task_cache


def execute():
    # Custom fields are synced later in migration on a newly installed site.
    if not frappe.db.has_column("Task", "assignee"):
        return
    warm_active_task_cache(notify=False)

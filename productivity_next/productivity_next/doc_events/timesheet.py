import frappe

def update_task_actual_time(self,method):
    # List of statuses where actual_time should NOT be updated
        
        invalid_statuses = ["Open", "Cancelled", "Request For Cancel"]

        for log in self.time_logs:
            if log.task:
                task = frappe.get_doc("Task", log.task)

                # Skip if task has any of the restricted statuses
                if task.status in invalid_statuses:
                    frappe.logger().info(
                        f"Skipped updating Task {task.name} due to invalid status: {task.status}"
                    )
                    continue

                # Update actual_time safely
                task.db_set('actual_time',log.hours or 0, update_modified=True)
                
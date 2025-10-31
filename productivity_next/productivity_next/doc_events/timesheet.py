import frappe

# def update_task_actual_time(self,method):
#     # List of statuses where actual_time should NOT be updated
        
#         invalid_statuses = ["Open", "Cancelled", "Request For Cancel"]

#         for log in self.time_logs:
#             if log.task:
#                 task = frappe.get_doc("Task", log.task)

#                 # Skip if task has any of the restricted statuses
#                 if task.status in invalid_statuses:
#                     frappe.logger().info(
#                         f"Skipped updating Task {task.name} due to invalid status: {task.status}"
#                     )
#                     continue

#                 # Update actual_time safely
#                 task.db_set('actual_time',log.hours or 0, update_modified=True)


def update_task_actual_time(self, method):
    tasks = []

    for data in self.time_logs:
        if data.task and data.task not in tasks:
            task = frappe.get_doc("Task", data.task)
            status = (task.status or "").strip().lower()

            # Skip certain statuses but still reset actual_time
            if status in ["open", "cancelled", "request for cancel"]:
                frappe.log_error(f"Skipped updating time for TaSsk {task.name} (status: {task.status})")
                task.actual_time = 0
                task.save(ignore_permissions=True)  #  Save ensures actual_time is updated
                tasks.append(data.task)
                continue

            # Update task time only for allowed statuses
            task.update_time_and_costing()
            task.save(ignore_permissions=True)

            tasks.append(data.task)
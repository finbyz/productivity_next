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

# def update_task_and_project(self, method):
#     # List of statuses where actual_time should NOT be updated
#     invalid_statuses = ["Open", "Cancelled", "Request For Cancel"]

#     for log in self.time_logs:
#         if log.task:
#             task = frappe.get_doc("Task", log.task)
#             # frappe.throw(str(task))
#             # Skip if task has any of the restricted statuses
#             if task.status in invalid_statuses:
#                 frappe.logger().info(
#                     f"Skipped updating Task {task.name} due to invalid status: {task.status}"
#                 )
#                 continue

#             # Calculate new actual_time by adding the log hours to the existing one
#             current_actual_time = task.actual_time or 0
#             additional_hours = log.hours or 0
#             new_actual_time = current_actual_time + additional_hours

#             # Update the actual_time field safely
#             task.db_set("actual_time", new_actual_time, update_modified=True)
            
# import frappe

# def update_task_and_project(self, method):
#     tasks, projects = [], []

#     for data in self.time_logs:
#         if data.task and data.task not in tasks:
#             task = frappe.get_doc("Task", data.task)
#             status = (task.status or "").strip().lower()

#             #  Skip updating actual time for unwanted statuses
#             if status in ["open", "cancelled", "request for cancel"]:
#                 frappe.log_error(f"Skipped updating time for Task {task.name} (status: {task.status})")
#                 return

#             #  Update task time only for allowed statuses
#             task.update_time_and_costing()
#             task.save(ignore_permissions=True)
#             frappe.logger().info(f" Task {task.name} updated successfully")

#             tasks.append(data.task)

#         # Collect unique projects
#         if data.project and data.project not in projects:
#             projects.append(data.project)

#     #  Update related projects
#     for project in projects:
#         project_doc = frappe.get_doc("Project", project)
#         project_doc.update_project()
#         project_doc.save(ignore_permissions=True)
#         frappe.logger().info(f"📁 Project {project_doc.name} updated successfully")
        

import frappe

# def update_task_and_project(self, method):
#     tasks = []

#     for data in self.time_logs:
#         if data.task and data.task not in tasks:
#             task = frappe.get_doc("Task", data.task)
#             status = (task.status or "").strip().lower()
#             # frappe.throw(str(status))
#             # Check each condition separately
#             if status == "open":
#                 frappe.log_error(f"⏭️ Skipped updating time for Task {task.name} (status: Open)")
#                 task.actual_time = 0
#                 return

#             if status == "cancelled":
#                 frappe.log_error(f"⏭️ Skipped updating time for Task {task.name} (status: Cancelled)")
#                 task.actual_time = 0
#                 return

#             if status == "request for cancel":
#                 frappe.log_error(f"⏭️ Skipped updating time for Task {task.name} (status: Request for Cancel)")
#                 task.actual_time = 0
#                 return

#             # Update task time only for allowed statuses
#             task.update_time_and_costing()
#             task.save(ignore_permissions=True)
#             frappe.logger().info(f"✅ Task {task.name} updated successfully")

#             tasks.append(data.task)


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
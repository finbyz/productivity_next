# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime

class UpdateProjectInUserActivity(Document):
    def validate(self):
        if not self.project or self.project == "":
            self.project = None
        
        if not self.from_time or not self.to_time:
            frappe.throw("Please select valid from and to times")
        
        try:
            # Convert string datetime to datetime objects
            from_datetime = frappe.utils.get_datetime(self.from_time)
            to_datetime = frappe.utils.get_datetime(self.to_time)
            
            # Extract dates
            from_date = from_datetime.date()
            to_date = to_datetime.date()
            
            # Logging for debugging
            frappe.log("Updating Application Usage log and Screen Screenshot Log")
            frappe.log(f"Project: {self.project}, Employee: {self.employee}, From: {from_date}, To: {to_date}")

            application_usage_log = frappe.qb.DocType("Application Usage log")
            screen_screenshot_log = frappe.qb.DocType("Screen Screenshot Log")
            
            # Update Application Usage log
            update_app_usage = (
                frappe.qb.update(application_usage_log)
                .set(application_usage_log.project, self.project)
                .where(application_usage_log.date >= from_date)
                .where(application_usage_log.date <= to_date)
                .where(application_usage_log.employee == self.employee)
                .where(application_usage_log.from_time.between(from_datetime, to_datetime))
            )

            # Update Screen Screenshot Log
            update_screen_log = (
                frappe.qb.update(screen_screenshot_log)
                .set(screen_screenshot_log.project, self.project)
                .where(screen_screenshot_log.employee == self.employee)
                .where(screen_screenshot_log.time.between(from_datetime, to_datetime))
            )

            # Run the updates
            update_app_usage.run()
            update_screen_log.run()

            self.employee = None
            self.project = None
            self.from_time = None
            self.to_time = None
            self.employee_name = None
            
            frappe.msgprint("Project updated successfully")
            # Optionally, you can commit if your changes require it
            # frappe.db.commit()  # Uncomment if necessary
            
        except Exception as e:
            frappe.log_error(f"Error in UpdateProjectInUserActivity: {str(e)}")
            frappe.throw(f"Error processing dates: {str(e)}")
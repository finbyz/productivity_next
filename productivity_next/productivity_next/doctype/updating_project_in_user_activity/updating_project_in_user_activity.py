# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

class UpdatingProjectInUserActivity(Document):
    def validate(self):
        # frappe.throw("Please select a project")
        if not self.project or self.project == "":
            self.project = None
        
        application_usage_log = frappe.qb.DocType("Application Usage log")
        screen_screenshot_log = frappe.qb.DocType("Screen Screenshot Log")
        frappe.qb.update(application_usage_log).set(application_usage_log.project, self.project).where(application_usage_log.employee == self.employee).where(application_usage_log.from_time.between(self.from_time, self.to_time)).run()
        frappe.qb.update(screen_screenshot_log).set(screen_screenshot_log.project, self.project).where(screen_screenshot_log.employee == self.employee).where(screen_screenshot_log.time.between(self.from_time, self.to_time)).run()
  
        
        # frappe.db.sql(f"""Update `tabApplication Usage log` set project = {self.project} where employee = '{self.employee}' and from_time between '{self.from_time}' and '{self.to_time}'""")
        # frappe.db.sql(f"""Update `tabScreen Screenshot Log` set project = {self.project} where employee = '{self.employee}' and time between '{self.from_time}' and '{self.to_time}'""")
        
        frappe.db.commit()
     

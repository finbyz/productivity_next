# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime, timedelta

class LocationHistory(Document):
    def after_insert(self):
        pass
        # self.check_stationary_status()
    
    def check_stationary_status(self):
        """
        Optimized method to check and update stationary status
        """
        if not self.time or not self.employee or not self.date:
            # frappe.log_error(f"Missing required fields - Time: {self.time}, Employee: {self.employee}, Date: {self.date}", "LocationLogs Validation")
            return
        time_difference = frappe.db.get_single_value('Productify Subscription', 'stop_duration_for_meetings') or 15
        # Get last log with direct SQL for better performance
        last_log = frappe.db.sql("""
            SELECT name, time 
            FROM `tabLocation History`
            WHERE employee = %s 
            AND date = %s 
            AND name != %s
            ORDER BY time DESC
            LIMIT 1
        """, (self.employee, self.date, self.name), as_dict=True)
        
        # frappe.log_error(f"Last log found: {last_log}", "LocationLogs Last Log")
        
        if not last_log:
            return  
            
        try:
            # Convert current_time string to datetime
            current_time = datetime.strptime(self.time, '%Y-%m-%d %H:%M:%S')
            last_time = last_log[0].time
            
            # frappe.log_error(f"Current time (after conversion): {current_time}, Last time: {last_time}", "LocationLogs Time/ Values")
            
            # Calculate minutes difference
            time_diff = (current_time - last_time).total_seconds() / 60
            
            # frappe.log_error(f"Time difference in minutes: {time_diff}", "LocationLogs Time Diff")
            
            # Update stationary flag if gap > 10 minutes
            if time_diff > time_difference:
                # Update current log
                frappe.db.set_value('Location History', self.name, 'is_stop', 1, update_modified=False)
                
                # Update previous log
                frappe.db.set_value('Location History', last_log[0].name, 'is_stop', 1, update_modified=False)
                
                frappe.db.commit()
                
                # frappe.log_error(f"Marked as stationary. Time diff: {time_diff} minutes", "LocationLogs Status Update")
                
        except Exception as e:
            frappe.log_error(f"Error in LocationLogs time calculation: {str(e)}\nCurrent Time: {self.time}\nLast Time: {last_log[0].time}", 
                           "LocationLogs Error")
            return
    
    
def on_doctype_update():
    frappe.db.add_unique("Location History", ["date", "employee", "uuid"])
    frappe.db.add_index("Location History", ["date", "employee", "event"])
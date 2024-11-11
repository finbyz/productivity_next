# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime, timedelta

class LocationLogs(Document):
    def after_insert(self):
        self.check_stationary_status()
    
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
            FROM `tabLocation Logs`
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
                frappe.db.set_value('Location Logs', self.name, 'is_stop', 1, update_modified=False)
                
                # Update previous log
                frappe.db.set_value('Location Logs', last_log[0].name, 'is_stop', 1, update_modified=False)
                
                frappe.db.commit()
                
                # frappe.log_error(f"Marked as stationary. Time diff: {time_diff} minutes", "LocationLogs Status Update")
                
        except Exception as e:
            frappe.log_error(f"Error in LocationLogs time calculation: {str(e)}\nCurrent Time: {self.time}\nLast Time: {last_log[0].time}", 
                           "LocationLogs Error")
            return
        
# loop through all location logs and check if the current log time difference is greater than 15 minutes with the previous log time then mark current log is_stop = 1 
employees = frappe.get_all("Employee", fields=["name"])
for employee in employees:
    docs = frappe.get_all("Location Logs", filters={"employee": employee.name}, fields=["name", "time", "employee", "date"], order_by="date asc, time asc")
    previous_time = None
    previous_date = None
    for doc in docs:
        location_log = frappe.get_doc("Location Logs", doc.name)
        
        # Initialize previous_time and previous_date on the first log
        if previous_time and previous_date:
            # Calculate time difference in minutes
            time_difference = (location_log.time - previous_time).total_seconds() / 60
            
            # If the time difference exceeds 15 minutes, mark as stop
            if time_difference > 15 and location_log.date == previous_date:
                location_log.is_stop = 1
                location_log.save()
                print(f"Marked as stationary. Time diff: {time_difference} minutes")
        
        # Update previous_time and previous_date to current log's values
        previous_time = location_log.time
        previous_date = location_log.date
 
        
    
    
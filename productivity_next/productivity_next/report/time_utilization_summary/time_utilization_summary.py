# Copyright (c) 2025, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from datetime import datetime, timedelta

def execute(filters=None):
    if not filters:
        filters = {}
    
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "task",
            "label": _("Task"),
            "fieldtype": "Link",
            "options": "Task",
            "width": 200
        },
        {
            "fieldname": "subject",
            "label": _("Subject"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "project",
            "label": _("Project"),
            "fieldtype": "Link",
            "options": "Project",
            "width": 150
        },
        {
            "fieldname": "employee_name",
            "label": _("Employee Name"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "total_duration",
            "label": _("Total Duration (Hours)"),
            "fieldtype": "Float",
            "precision": 2,
            "width": 150
        }
    ]

def get_data(filters):
    conditions = get_conditions(filters)
    
    # Query to fetch application usage logs grouped by task
    query = """
        SELECT 
            aul.task,
            aul.project,
            t.subject,
            aul.employee_name,
            SUM(aul.duration) as total_seconds
        FROM 
            `tabApplication Usage log` aul
        JOIN 
			`tabTask` as t on aul.task = t.name
        WHERE
            {conditions}
        GROUP BY
            aul.task, aul.project, aul.employee_name
        ORDER BY
            aul.project, aul.task, aul.employee_name
    """.format(conditions=conditions)
    
    result = frappe.db.sql(query, filters, as_dict=1)
    
    # Process the results to convert seconds to hours
    for row in result:
        if row.total_seconds:
            # Convert seconds to hours as a float
            row.total_duration = round(float(row.total_seconds) / 3600, 2)
    
    return result

def get_conditions(filters):
    conditions = []
    
    if filters.get("from_date"):
        conditions.append("aul.date >= %(from_date)s")
    
    if filters.get("to_date"):
        conditions.append("aul.date <= %(to_date)s")
        
    if filters.get("employee"):
        conditions.append("aul.employee = %(employee)s")
        
    if filters.get("project"):
        conditions.append("aul.project = %(project)s")
    
    # Ensure we only get records with tasks
    conditions.append("aul.task IS NOT NULL")
    
    return " AND ".join(conditions) if conditions else "1=1"
# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from datetime import datetime


def execute(filters=None):
    
	columns=get_columns_list()
	data =get_data_list(filters)
	return columns, data

def get_columns_list():
    return [
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee"},
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date"},
        {"label": _("Time Consumed"), "fieldname": "time_consumed", "fieldtype": "Data"}
    ]

def get_data_list(filters):
    from datetime import datetime
    conditions=""
    if  filters.get('date'):
        conditions += f"acc.date  between'{filters.get('opening_date')[0]}' and '{filters.get('opening_date')[1]}'"
    if filters.get('employee'):
        conditions+="AND acc.employee='{}'".format(filters.get('employee'))
        
    data = frappe.db.sql("""
        SELECT 
            acc.employee, 
            acc.status, 
            acc.time as time,
            acc.employee_name
        FROM `tabApplication Checkin Checkout` AS acc
        ORDER BY acc.creation
    """, as_dict=1)

    unique = []
    seen = set()

    for row in data:
        check_time= datetime(2024, 2, 12, 11, 18, 12)
        date = check_time.date()

        employee_date = (row['employee'], date)   
        if employee_date not in seen:
            seen.add(employee_date)
            unique.append(row)

    

    return unique

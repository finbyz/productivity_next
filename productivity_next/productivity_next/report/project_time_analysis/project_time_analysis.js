// Copyright (c) 2025, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Project Time Analysis"] = {
	"filters": [
		{
            "fieldname": "from_date",
            "label": "From Date",
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "to_date",
            "label": "To Date",
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "project",
            "label": "Project",
            "fieldtype": "Link",
            "options": "Project"
        },
        {
            "fieldname": "resource_based_project",
            "label": "Resource Based Project",
            "fieldtype": "Check"
        },
        {
            "fieldname": "hourly_based_project",
            "label": "Hourly Based Project",
            "fieldtype": "Check"
        },
        {
            "fieldname": "show_employee",
            "label": "Show Employee Details",
            "fieldtype": "Check"
        },
        {
            "fieldname": "employee",
            "label": "Employee",
            "fieldtype": "Link",
            "options": "Employee",
            "depends_on": "show_employee"
        },
        {
            "fieldname": "show_daily_data",
            "label": "Show Daily Data",
            "fieldtype": "Check"
        },
        {
            "fieldname": "show_details",
            "label": "Show Activity Details",
            "fieldtype": "Check",
            "default": 1,
            "hidden": 1
        },
        {
            "fieldname": "is_internal_project",
            "label": "Internal Project",
            "fieldtype": "Check",
        }
	]
};

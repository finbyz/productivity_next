// Copyright (c) 2025, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Daily Project Time Analysis Productify"] = {
	"filters": [
		{
            "fieldname": "from_date",
            "label": "From Date",
            "fieldtype": "Date",
            "reqd": 1,
            "default":  frappe.datetime.get_today()
        },
        {
            "fieldname": "to_date",
            "label": "To Date",
            "fieldtype": "Date",
            "reqd": 1,
            "default":  frappe.datetime.get_today()
        },
		{
            "fieldname": "project",
            "label": ("Project"),
            "fieldtype": "Link",
            "options": "Project",
            "reqd": 0
        },
        {
            "fieldname": "customer",
            "label": ("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "reqd": 0
        },
        {
            "fieldname": "employee",
            "label": ("Employee"),
            "fieldtype": "Link",
            "options": "Employee",
            "reqd": 0
        },
        {
            "fieldname": "is_internal_customer",
            "label": ("Is Internal Project"),
            "fieldtype": "Check",
        },
        {
            "fieldname": "show_descendants",
            "label": ("Show Descendants"),
            "fieldtype": "Check",
            "depends_on": "eval: doc.employee",  
        },
        {
            "fieldname": "show_project_wise_data",
            "label": ("Show Project Wise Data"),
            "fieldtype": "Check",   
        }

	]
};

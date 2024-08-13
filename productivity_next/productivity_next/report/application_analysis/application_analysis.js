// Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Application Analysis"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_days(frappe.datetime.get_today(), -1)
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_days(frappe.datetime.get_today(), -1)
		},
		{
			"fieldname": "employee",
			"label": __("Employee"),
			"fieldtype": "Link",
			"options": "Employee"
		},
		
		{
			"fieldname": "group_by_employee_and_application_name",
			"label": __("Group By Employee & Application"),
			"fieldtype": "Check",
			on_change: function (query_report) {
				frappe.query_report.get_filter('group_by_application_name').input.checked = false
				frappe.query_report.refresh();
			},
		
		},
		{
			"fieldname": "group_by_application_name",
			"label": __("Group By Application"),
			"fieldtype": "Check",
			on_change: function (query_report) {
				frappe.query_report.get_filter('group_by_employee_and_application_name').input.checked = false
				frappe.query_report.refresh();
			},
		},
	]
};

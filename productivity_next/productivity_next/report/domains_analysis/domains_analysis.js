// Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Domains Analysis"] = {
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
			"fieldname": "group_by_employee_and_domain",
			"label": __("Group By Employee & Domain"),
			"fieldtype": "Check",
			on_change: function (query_report) {
				frappe.query_report.get_filter('group_by_domain').input.checked = false
				frappe.query_report.refresh();
			},
		
		},
		{
			"fieldname": "group_by_domain",
			"label": __("Group By Domain"),
			"fieldtype": "Check",
			on_change: function (query_report) {
				frappe.query_report.get_filter('group_by_employee_and_domain').input.checked = false
				frappe.query_report.refresh();
			},
		},
	]
};

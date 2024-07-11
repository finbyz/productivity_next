// Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Calls Analysis"] = {

	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_days(frappe.datetime.get_today(), -7)
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "employee",
			"label": __("Employee"),
			"fieldtype": "Link",
			"options": "Employee"
		},
		{
			"fieldname": "group_by_party",
			"label": __("Group By Party"),
			"fieldtype": "Check",
			on_change: function (query_report) {
				frappe.query_report.get_filter('group_by_contact').input.checked = false
				frappe.query_report.refresh();
			}
		},
		{
			"fieldname": "group_by_contact",
			"label": __("Group By Contact"),
			"fieldtype": "Check",
			on_change: function (query_report) {
				frappe.query_report.get_filter('group_by_party').input.checked = false
				frappe.query_report.refresh();
			}
		},

	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname.includes("calltype")) {
			if (data[column.fieldname] == "Incoming") {
				value = "<span style='color:rgb(40, 167, 69)'>" + value + "</span>";
			} else if (data[column.fieldname] == "Outgoing") {
				value = "<span style='color:#78d6ff'>" + value + "</span>";
			}
			else if (data[column.fieldname] == "Missed") {
				value = "<span style='color:rgb(255, 193, 7)'>" + value + "</span>";
			}
			else if (data[column.fieldname] == "Rejected") {
				value = "<span style='color:rgb(224, 54, 54)'>" + value + "</span>";
			}
		}

		return value;
	},

};

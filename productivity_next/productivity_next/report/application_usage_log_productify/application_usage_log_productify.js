// Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Application Usage Log Productify"] = {
	"filters": [
		{
			fieldname: 'employee',
			label: __('Employee'),
			fieldtype: 'Link',
			options: 'Employee',
		},
		{
			fieldname: 'date',
			label: __('Date'),
			fieldtype: 'Date',
		}
	]
};

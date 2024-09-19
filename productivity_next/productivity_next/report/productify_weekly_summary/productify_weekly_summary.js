// Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Productify Weekly Summary"] = {
	"filters": [
		{
            "fieldname": "timespan",
            "label": __("Timespan"),
            "fieldtype": "Select",
            "width": "80",
            "options": "\nToday\nYesterday\nThis Week\nLast Week\nThis Month\nLast Month",
            "default": "Yesterday"
        },
	]
};

# Copyright (c) 2013, Frappe Technologies Pvt. Ltd.
# For license information, please see license.txt

import frappe
from datetime import date
from collections import defaultdict
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    
    chart = get_chart_data(data)

    return columns, data, None, chart

def get_columns():
    return [
        {
            "fieldname": "date",
            "label": _("Date"),
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "fieldname": "domain",
            "label": _("domain"),
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "fieldname": "domain_count",
            "label": _("Domain Count"),
            "fieldtype": "Data",
            "width": 120,
        }
    ]

def get_data(filters):
    data = frappe.db.sql("""
        SELECT domain, date, count(*) as domain_count
        FROM `tabApplication Usage log`
		where domain is not null and domain != ''
        and date between %(from_date)s and %(to_date)s
        GROUP BY domain
		ORDER BY domain_count desc
		Limit 10
        """,
        {
            "from_date": filters.from_date,
            "to_date": filters.to_date,
        },
        as_dict=True,
        )
    return data

def get_chart_data(data):
    labels = [x["domain"] for x in data]
    count = [x["domain_count"] for x in data]
    
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("No of Hits"), "values": count}
            ],
        },
        "type": "bar",
        "colors": ["#7575ff"]
    }

def get_report_summary(data):
    if not data:
        return []

    return [
    ]

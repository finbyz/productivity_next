# Copyright (c) 2013, Frappe Technologies Pvt. Ltd.
# For license information, please see license.txt

import frappe
from datetime import date
from collections import defaultdict
from frappe import _
from frappe.utils.data import format_duration


def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)

    chart = get_chart_data(filters)

    return columns, data, None, chart


def get_columns(filters):
    if filters.group_by_employee_and_application_name:
        return [
            {
                "fieldname": "employee",
                "label": _("Employee"),
                "fieldtype": "Data",
                "width": 200,
                "align": "left",
            },
            {
                "fieldname": "application_name",
                "label": _("Application"),
                "align": "left",
                "fieldtype": "Data",
                "width": 300,
            },
            {
                "fieldname": "duration",
                "label": _("Duration"),
                "fieldtype": "Data",
                "width": 120,
            },            
        ]

    if filters.group_by_application_name:
        return [
            {
                "fieldname": "application_name",
                "label": _("Application"),
                "align": "left",
                "fieldtype": "Data",
                "width": 300,
            },
            {
                "fieldname": "duration",
                "label": _("Duration"),
                "fieldtype": "Data",
                "width": 120,
            },
        ]

    return [
        {
            "fieldname": "employee",
            "label": _("Employee"),
            "fieldtype": "Data",
            "width": 200,
            "align": "left",
        },
         {
            "fieldname": "application_name",
            "label": _("Application Name"),
            "align": "left",
            "fieldtype": "Data",
            "width": 200,
        },
         {
            "fieldname": "application_title",
            "label": _("Application Title"),
            "align": "left",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "from_time",
            "label": _("From Time"),
            "fieldtype": "Datetime",
            "width": 200,
        },
        {
            "fieldname": "to_time",
            "label": _("To Time"),
            "fieldtype": "Datetime",
            "width": 200,
        },
        {
            "fieldname": "duration",
            "label": _("Duration"),
            "fieldtype": "Data",
            "width": 120,
        },
    ]


def get_data(filters):
    kwargs = {
        "filters": {
            "date": ["between", [filters.from_date, filters.to_date]],
            "application_name": ["!=", ""],
        },
        "fields": [
            "application_title",
            "date",
            "employee_name as employee",
            "from_time",
            "to_time",
            "duration",
            "application_name",
            "url",
        ],
        "order_by": "employee asc ,duration desc", 
    }
    if filters.employee:
        kwargs["filters"]["employee"] = filters.employee

    elif filters.group_by_application_name:
        kwargs["group_by"] = "application_name"
        kwargs["fields"].remove("from_time")
        kwargs["fields"].remove("to_time")
        kwargs["fields"].remove("duration")
        kwargs["fields"].append("sum(duration) as duration")
        kwargs["order_by"] = "sum(duration) desc"

    elif filters.group_by_employee_and_application_name:
        kwargs["group_by"] = "employee, application_name"
        kwargs["fields"].remove("from_time")
        kwargs["fields"].remove("to_time")
        kwargs["fields"].remove("duration")
        kwargs["fields"].append("sum(duration) as duration")
        kwargs["order_by"] = "employee asc, sum(duration) desc"
        
    else:
        kwargs["order_by"] = "employee asc, from_time desc"

    data = frappe.get_list(
        "Application Usage log",
        **kwargs,
    )
    for row in data:
        row["duration"] = format_duration(row["duration"], hide_days=True) or "0s"
    return data


def get_chart_data(filters):
    data = frappe.db.sql("""
        SELECT application_name, date, count(*) as application_count
        FROM `tabApplication Usage log`
		where date between %(from_date)s and %(to_date)s and application_name is not null and application_name != ''
        GROUP BY application_name
		ORDER BY application_count desc
		Limit 10
        """,
        {
            "from_date": filters.from_date,
            "to_date": filters.to_date,
        },
        as_dict=True,
        )
    labels = [x["application_name"] for x in data]
    count = [x["application_count"] for x in data]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"application_name": _("No of Hits"), "values": count}],
        },
        "type": "bar",
        "colors": ["#4682B4"],
    }


def get_report_summary(data):
    if not data:
        return []

    return []

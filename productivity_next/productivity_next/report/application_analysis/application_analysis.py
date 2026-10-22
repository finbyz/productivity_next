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
    where = "date BETWEEN %(from_date)s AND %(to_date)s AND application_name IS NOT NULL AND application_name != ''"
    values = {"from_date": filters.from_date, "to_date": filters.to_date}
    if filters.employee:
        where += " AND employee = %(employee)s"
        values["employee"] = filters.employee

    if filters.get("group_by_application_name"):
        sql = f"""SELECT application_name, SUM(duration) AS duration
                  FROM `tabApplication Usage log`
                  WHERE {where}
                  GROUP BY application_name ORDER BY SUM(duration) DESC"""
    elif filters.get("group_by_employee_and_application_name"):
        sql = f"""SELECT employee_name AS employee, application_name, SUM(duration) AS duration
                  FROM `tabApplication Usage log`
                  WHERE {where}
                  GROUP BY employee, application_name ORDER BY employee ASC, SUM(duration) DESC"""
    else:
        sql = f"""SELECT employee_name AS employee, application_name, application_title,
                         from_time, to_time, duration, url
                  FROM `tabApplication Usage log`
                  WHERE {where}
                  ORDER BY employee ASC, from_time DESC"""

    data = frappe.db.sql(sql, values, as_dict=True)
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

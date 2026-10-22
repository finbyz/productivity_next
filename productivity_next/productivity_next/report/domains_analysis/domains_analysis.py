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
    if filters.group_by_employee_and_domain:
        return [
            {
                "fieldname": "employee",
                "label": _("Employee"),
                "fieldtype": "Data",
                "width": 200,
                "align": "left",
            },
            {
                "fieldname": "domain",
                "label": _("Domain"),
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

    if filters.group_by_domain:
        return [
            {
                "fieldname": "domain",
                "label": _("Domain"),
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
        {
            "fieldname": "application",
            "label": _("Application"),
            "align": "left",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "domain",
            "label": _("Domain"),
            "align": "left",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "url",
            "label": _("URL"),
            "align": "left",
            "fieldtype": "Url",
            "width": 250,
        },
    ]


def get_data(filters):
    where = "date BETWEEN %(from_date)s AND %(to_date)s AND domain IS NOT NULL AND domain != ''"
    values = {"from_date": filters.from_date, "to_date": filters.to_date}
    if filters.employee:
        where += " AND employee = %(employee)s"
        values["employee"] = filters.employee

    if filters.get("group_by_domain"):
        sql = f"""SELECT domain, SUM(duration) AS duration
                  FROM `tabApplication Usage log`
                  WHERE {where}
                  GROUP BY domain ORDER BY SUM(duration) DESC"""
    elif filters.get("group_by_employee_and_domain"):
        sql = f"""SELECT employee_name AS employee, domain, SUM(duration) AS duration
                  FROM `tabApplication Usage log`
                  WHERE {where}
                  GROUP BY employee, domain ORDER BY employee ASC, SUM(duration) DESC"""
    else:
        sql = f"""SELECT employee_name AS employee, from_time, to_time, duration,
                         application_name AS application, domain, url
                  FROM `tabApplication Usage log`
                  WHERE {where}
                  ORDER BY employee ASC, from_time DESC"""

    data = frappe.db.sql(sql, values, as_dict=True)
    for row in data:
        row["duration"] = format_duration(row["duration"], hide_days=True) or "0s"
    return data


def get_chart_data(filters):
    data = frappe.db.sql("""
        SELECT domain, date, count(*) as domain_count
        FROM `tabApplication Usage log`
		where date between %(from_date)s and %(to_date)s and domain is not null and domain != ''
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
    labels = [x["domain"] for x in data]
    count = [x["domain_count"] for x in data]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": _("No of Hits"), "values": count}],
        },
        "type": "bar",
        "colors": ["#7575ff"],
    }


def get_report_summary(data):
    if not data:
        return []

    return []

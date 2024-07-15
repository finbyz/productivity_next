# Copyright (c) 2013, Frappe Technologies Pvt. Ltd.
# For license information, please see license.txt

import frappe
from datetime import date
from frappe import _
from frappe.utils import format_duration


def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)

    chart = get_chart_data(filters)
    # report_summary = get_report_summary(data)

    return columns, data, None, chart


def get_contact_group_columns(filters):
    columns = [
        {
            "fieldname": "contact",
            "label": _("Contact"),
            "fieldtype": "Data",
            "width": 200,
            "align": "left",
        },
        {
            "fieldname": "party",
            "label": _("Party"),
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "party_type",
            "label": _("Party Type"),
            "fieldtype": "Link",
            "options": "doctype",
            "width": 120,
        },
        {
            "fieldname": "employee",
            "label": _("Employee"),
            "fieldtype": "Link",
            "options": "Employee",
            "width": 200,
        },
        {
            "fieldname": "duration",
            "label": _("Duration"),
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "fieldname": "incoming_count",
            "label": _("Incoming"),
            "align": "left",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "fieldname": "outgoing_count",
            "label": _("Outgoing"),
            "align": "left",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "fieldname": "missed_count",
            "label": _("Missed"),
            "align": "left",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "fieldname": "rejected_count",
            "label": _("Rejected"),
            "align": "left",
            "fieldtype": "Data",
            "width": 100,
        },
    ]
    return columns


def get_group_by_party_columns(filters):
    return [
        {
            "fieldname": "party",
            "label": _("Party"),
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "party_type",
            "label": _("Party Type"),
            "fieldtype": "Link",
            "options": "doctype",
            "width": 120,
        },
        {
            "fieldname": "employee",
            "label": _("Employee"),
            "fieldtype": "Link",
            "options": "Employee",
            "width": 200,
        },
        {
            "fieldname": "duration",
            "label": _("Duration"),
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "fieldname": "incoming_count",
            "label": _("Incoming"),
            "align": "left",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "fieldname": "outgoing_count",
            "label": _("Outgoing"),
            "align": "left",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "fieldname": "missed_count",
            "label": _("Missed"),
            "align": "left",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "fieldname": "rejected_count",
            "label": _("Rejected"),
            "align": "left",
            "fieldtype": "Data",
            "width": 100,
        },
    ]


def get_columns(filters):
    columns = [
        {
            "fieldname": "employee",
            "label": _("Employee"),
            "fieldtype": "Link",
            "options": "Employee",
            "width": 200,
        },
        {
            "fieldname": "calltype",
            "label": _("Call Type"),
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "fieldname": "contact",
            "label": _("Contact"),
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "party_type",
            "label": _("Party Type"),
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "fieldname": "party",
            "label": _("Party"),
            "fieldtype": "Dynamic Link",
            "options": "party_type",
            "width": 200,
        },
        {
            "fieldname": "from_time",
            "label": _("From Time"),
            "fieldtype": "Datetime",
            "width": 120,
        },
        {
            "fieldname": "to_time",
            "label": _("To Time"),
            "fieldtype": "Datetime",
            "width": 120,
        },
        {
            "fieldname": "duration",
            "label": _("Duration"),
            "fieldtype": "Data",
            "width": 200,
        },
    ]
    if filters.get("group_by_party"):
        columns = get_group_by_party_columns(filters)
    if filters.get("group_by_contact"):
        columns = get_contact_group_columns(filters)
    return columns


def get_data(filters):

    conditions_filters = {
        "date": ["between", [filters.from_date, filters.to_date]],
        "link_name": ["is", "set"],
    }
    if filters.get("employee"):
        conditions_filters["employee"] = filters.employee

    kwargs = {
        "filters": conditions_filters,
        "fields": [
            "employee_name as employee",
            "calltype",
            "call_datetime as from_time",
            "DATE_ADD(call_datetime,INTERVAL duration SECOND) as to_time",
            "link_to as party_type",
            "link_name as party",
            "duration",
            "calltype",
        ],
        "order_by": "call_datetime desc",
    }
    kwargs["fields"].append(
        """
        (CASE
            WHEN contact IS NOT NULL THEN contact
            WHEN client IS NOT NULL THEN client
            WHEN customer_no IS NOT NULL THEN customer_no
        END)
        as contact"""
    )
    kwargs["fields"].append(
        """
        (CASE
            WHEN contact IS NOT NULL THEN contact
            WHEN client IS NOT NULL THEN client
            WHEN customer_no IS NOT NULL THEN customer_no
        END)
        as contact"""
    )
    if filters.get("group_by_party"):
        kwargs["group_by"] = "link_name,employee"
        kwargs["fields"] = [
            "link_name as party",
            "link_to as party_type",
            "employee_name as employee",
            "SUM(duration) as duration",
        ]
        kwargs["order_by"] = "link_name asc"

    if filters.get("group_by_contact"):
        kwargs["group_by"] = "customer_no,employee"
        kwargs["order_by"] = "customer_no asc"

    if filters.get("group_by_contact") or filters.get("group_by_party"):
        kwargs["fields"] = [
            "link_name as party",
            "link_to as party_type",
            "employee_name as employee",
            "SUM(duration) as duration",
        ]
        kwargs["fields"].extend(
            [
                """
                (CASE
                    WHEN contact IS NOT NULL THEN contact
                    WHEN client IS NOT NULL THEN client
                    WHEN customer_no IS NOT NULL THEN customer_no
                END)
                as contact
                """,
                """
                SUM(
                    CASE calltype WHEN 'Incoming' THEN 1 ELSE 0 END
                ) as incoming_count
                """,
                """
                SUM(
                    CASE calltype WHEN 'Outgoing' THEN 1 ELSE 0 END
                ) as outgoing_count
                """,
                """
                SUM(
                    CASE calltype WHEN 'Missed' THEN 1 ELSE 0 END
                ) as missed_count
                """,
                """
                SUM(
                    CASE calltype WHEN 'Rejected' THEN 1 ELSE 0 END
                ) as rejected_count
                """,
            ]
        )

    data = frappe.get_list("Employee Fincall", **kwargs)
    for row in data:
        row["duration"] = format_duration(row["duration"], hide_days=True) or "0s"
    return data


def get_chart_data(filters):
    kwargs = {
        "filters": {
            "date": ["between", [filters.from_date, filters.to_date]],
            "link_name": ["is", "set"],
        },
        "fields": [
            "date",
            """
            SUM(
                CASE calltype WHEN 'Incoming' THEN 1 ELSE 0 END
            ) as incoming_count
            """,
            """
            SUM(
                CASE calltype WHEN 'Outgoing' THEN 1 ELSE 0 END
            ) as outgoing_count
            """,
        ],
        "group_by": "date",
    }
    if filters.get("employee"):
        kwargs["filters"]["employee"] = filters.employee

    data = frappe.get_list("Employee Fincall", **kwargs)
    labels = [call["date"] for call in data]
    incoming = [call["incoming_count"] for call in data]
    outgoing = [call["outgoing_count"] for call in data]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Incoming"), "values": incoming},
                {"name": _("Outgoing"), "values": outgoing},
            ],
        },
        "type": "bar",
        "colors": ["#fc4f51", "#78d6ff"],
        "barOptions": {"stacked": True},
    }


def get_report_summary(data):
    if not data:
        return []

    return []

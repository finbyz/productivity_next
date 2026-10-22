# Copyright (c) 2013, Frappe Technologies Pvt. Ltd.
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import format_duration


def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)

    chart = get_chart_data(filters)

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
            "fieldname": "party_type",
            "label": _("Party Type"),
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "fieldname": "party",
            "label": _("Party"),
            "fieldtype": "Data",
            "width": 200,
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
            "fieldtype": "Duration",
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
            "fieldname": "party_type",
            "label": _("Party Type"),
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "fieldname": "party",
            "label": _("Party"),
            "fieldtype": "Data",
            "width": 200,
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
            "fieldtype": "Duration",
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
    if filters.get("group_by_party"):
        return get_group_by_party_columns(filters)
    if filters.get("group_by_contact"):
        return get_contact_group_columns(filters)

    # Default columns when no grouping is selected
    return [
        {
            "fieldname": "employee_fincall",
            "label": _("Employee Fincall"),
            "fieldtype": "Link",
            "options": "Employee Fincall",
            "width": 200
        },
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
            "fieldname": "client",
            "label": _("Client"),
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "customer_no",
            "label": _("Customer No"),
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
            "fieldtype": "Duration",
            "width": 200,
        },
    ]


def _build_conditions(filters):
    """Return (WHERE clause string, values list) for the shared date/employee filters."""
    conditions = ["date BETWEEN %(from_date)s AND %(to_date)s"]
    values = {"from_date": filters.from_date, "to_date": filters.to_date}

    if filters.get("employee"):
        conditions.append("employee = %(employee)s")
        values["employee"] = filters.employee

    return " AND ".join(conditions), values


def get_data(filters):
    where, values = _build_conditions(filters)

    # ------------------------------------------------------------------ #
    # Grouped by party                                                     #
    # ------------------------------------------------------------------ #
    if filters.get("group_by_party"):
        sql = """
            SELECT
                link_name            AS party,
                link_to              AS party_type,
                employee             AS employee,
                employee_name        AS employee_name,
                SUM(duration)        AS duration,
                SUM(CASE calltype WHEN 'Incoming' THEN 1 ELSE 0 END)  AS incoming_count,
                SUM(CASE calltype WHEN 'Outgoing' THEN 1 ELSE 0 END)  AS outgoing_count,
                SUM(CASE calltype WHEN 'Missed'   THEN 1 ELSE 0 END)  AS missed_count,
                SUM(CASE calltype WHEN 'Rejected' THEN 1 ELSE 0 END)  AS rejected_count
            FROM `tabEmployee Fincall`
            WHERE {where}
            GROUP BY link_name, employee
            ORDER BY duration DESC
        """.format(where=where)
        return frappe.db.sql(sql, values, as_dict=True)

    # ------------------------------------------------------------------ #
    # Grouped by contact                                                   #
    # ------------------------------------------------------------------ #
    if filters.get("group_by_contact"):
        sql = """
            SELECT
                link_name            AS party,
                link_to              AS party_type,
                employee             AS employee,
                employee_name        AS employee_name,
                SUM(duration)        AS duration,
                COALESCE(contact, client, customer_no) AS contact,
                SUM(CASE calltype WHEN 'Incoming' THEN 1 ELSE 0 END)  AS incoming_count,
                SUM(CASE calltype WHEN 'Outgoing' THEN 1 ELSE 0 END)  AS outgoing_count,
                SUM(CASE calltype WHEN 'Missed'   THEN 1 ELSE 0 END)  AS missed_count,
                SUM(CASE calltype WHEN 'Rejected' THEN 1 ELSE 0 END)  AS rejected_count
            FROM `tabEmployee Fincall`
            WHERE {where}
            GROUP BY customer_no, employee
            ORDER BY duration DESC
        """.format(where=where)
        return frappe.db.sql(sql, values, as_dict=True)

    # ------------------------------------------------------------------ #
    # Default (no grouping)                                                #
    # DATE_ADD is used here for to_time — raw SQL is required in v16      #
    # ------------------------------------------------------------------ #
    sql = """
        SELECT
            name                                              AS employee_fincall,
            employee                                          AS employee,
            employee_name                                     AS employee_name,
            calltype,
            call_datetime                                     AS from_time,
            DATE_ADD(call_datetime, INTERVAL duration SECOND) AS to_time,
            link_to                                           AS party_type,
            link_name                                         AS party,
            duration,
            contact,
            client,
            customer_no
        FROM `tabEmployee Fincall`
        WHERE {where}
        ORDER BY call_datetime DESC
    """.format(where=where)
    return frappe.db.sql(sql, values, as_dict=True)


def get_chart_data(filters):
    where, values = _build_conditions(filters)

    sql = """
        SELECT
            date,
            SUM(CASE calltype WHEN 'Incoming' THEN 1 ELSE 0 END) AS incoming_count,
            SUM(CASE calltype WHEN 'Outgoing' THEN 1 ELSE 0 END) AS outgoing_count
        FROM `tabEmployee Fincall`
        WHERE {where}
        GROUP BY date
        ORDER BY date ASC
    """.format(where=where)

    data = frappe.db.sql(sql, values, as_dict=True)

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
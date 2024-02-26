import frappe
from frappe import _
import datetime
import math


def execute(filters=None):
    columns = get_columns_list()
    data, employee_name_map = get_data_list(filters)
    chart = get_chart_data(data, employee_name_map)
    data = [row for row in data if row["time_consumed_hrs"]]
    return columns, data, None, chart


def get_columns_list():
    return [
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 150,
        },
        {
            "label": _("Employee name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": _("Date"),
            "fieldname": "date",
            "fieldtype": "Date",
            "width": 150,
        },
        {
            "label": _("Time Consumed"),
            "fieldname": "time_consumed",
            "fieldtype": "Data",
            "width": 200,
        },
    ]


def get_data_list(filters):
    doc_filters = {"time": ["Between", filters["date"]]}

    if filters.get("employee"):
        doc_filters["employee"] = filters["employee"]

    all_logs = frappe.db.get_list(
        "Application Checkin Checkout",
        filters=doc_filters,
        fields=["employee", "status", "time"],
        order_by="creation asc",
    )

    return get_data(all_logs)


def get_data(all_logs):
    unique_dates = []
    unique_employees = []
    for row in all_logs:
        row["date"] = row.time.date()
        if row["date"] not in unique_dates:
            unique_dates.append(row["date"])

        if row["employee"] not in unique_employees:
            unique_employees.append(row["employee"])

    data = []

    if not unique_employees:
        return data

    employee_name_map = {
        row.name: row.employee_name
        for row in frappe.db.get_all(
            "Employee",
            filters={"employee": ["in", unique_employees]},
            fields=["name", "employee_name"],
        )
    }

    for date in sorted(unique_dates):
        for employee in unique_employees:
            filter_logs = list(
                filter(
                    lambda row: (row["date"] == date and row["employee"] == employee),
                    all_logs,
                )
            )
            time_consumed, time_consumed_hrs = get_usage_time(filter_logs)
            data.append(
                frappe._dict(
                    {
                        "date": date,
                        "employee": employee,
                        "time_consumed": time_consumed,
                        "time_consumed_hrs": time_consumed_hrs,
                        "employee_name": employee_name_map.get(employee) or "",
                    }
                )
            )

    return data, employee_name_map


def get_usage_time(filter_logs):
    usage_time = 0
    last_status = None

    for row in filter_logs:
        if row.status == "In" and last_status != "In":
            start_time = row.time
        elif row.status == "Out" and last_status == "In":
            end_time = row.time
            usage_time += (end_time - start_time).total_seconds()

        last_status = row.status

    hours = str(int(math.floor(usage_time / 3600)))
    minutes = str(int(math.floor((usage_time % 3600) / 60)))

    time_consumed = hours + "hrs" + minutes + "min"

    time_consumed_hours = round(usage_time / 3600, 4)

    return time_consumed, time_consumed_hours


def get_chart_data(data, employee_name_map):
    employees = sorted(set([d.employee for d in data]))

    chart = {
        "data": {"labels": [], "datasets": []},
        "type": "bar",
        "fieldtype": "Float",
        "colors": ["#92CAD1"],
    }

    dates = list(set([d.date for d in data]))
    dates.sort()

    chart["data"]["labels"] = dates

    for employee in employees:
        chart["data"]["datasets"].append(
            {
                "name": employee_name_map.get(employee),
                "values": [
                    row.time_consumed_hrs
                    for row in sorted(
                        filter(
                            lambda row: row["employee"] == employee,
                            data,
                        ),
                        key=lambda row: row["date"],
                    )
                ],
            }
        )

    return chart

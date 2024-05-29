# Copyright (c) 2013, Frappe Technologies Pvt. Ltd.
# For license information, please see license.txt

import frappe
from datetime import date
from collections import defaultdict
from frappe import _
from datetime import datetime
def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    
    chart = get_chart_data(data)
    report_summary = get_report_summary(data)

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
            "fieldname": "incoming_count",
            "label": _("Incoming Calls"),
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "fieldname": "outgoing_count",
            "label": _("Outgoing Calls"),
            "fieldtype": "Data",
            "width": 120,
        }
    ]

def get_data(filters):
    data = frappe.db.sql("""
        SELECT name, date, count(*) as incoming_count, calltype
        FROM `tabEmployee Fincall`
        WHERE calltype = "Incoming"
        and date between %(from_date)s and %(to_date)s
        GROUP BY date,calltype
        """,
        {
            "from_date": filters.from_date,
            "to_date": filters.to_date,
        },
        as_dict=True,
        )
    
    data += frappe.db.sql("""
        SELECT name, date, count(*) as outgoing_count, calltype
        FROM `tabEmployee Fincall`
        WHERE calltype = "Outgoing"
        and date between %(from_date)s and %(to_date)s
        GROUP BY date,calltype
        """,
        {
            "from_date": filters.from_date,
            "to_date": filters.to_date,
        },
        as_dict=True,
        )
    combined_data = defaultdict(lambda: {'incoming_count': 0, 'outgoing_count': 0})
    for record in data:
        record_date = record['date']
        if record['calltype'] == 'Incoming':
            combined_data[record_date]['incoming_count'] += record['incoming_count']
        elif record['calltype'] == 'Outgoing':
            combined_data[record_date]['outgoing_count'] += record['outgoing_count']

    # Step 2: Convert the combined dictionary back to a list of dictionaries
    combined_list = [
        {'date': record_date, 'incoming_count': counts['incoming_count'], 'outgoing_count': counts['outgoing_count']}
        for record_date, counts in combined_data.items()
    ]

    # Step 3: Sort the combined list by date in descending order
    combined_list.sort(key=lambda x: x['date'])
    
    return combined_list

def get_chart_data(data):
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

    return [
    ]

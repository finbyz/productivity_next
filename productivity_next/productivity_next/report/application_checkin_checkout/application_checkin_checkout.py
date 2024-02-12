import frappe

from frappe import _

import datetime

def execute(filters=None):

    columns=get_columns_list()

    data =get_data_list(filters)

    return columns, data

def get_columns_list():

        return [

        {"label": _("Employee"),

        "fieldname": "employee",

        "fieldtype": "Link",

        "options": "Employee",

        "width": 150

        },

        {"label": _("Employee name"),

        "fieldname": "employee_name",

        "fieldtype": "Data",

        "width": 150

        },

        {"label": _("Date"),

        "fieldname": "date",

        "fieldtype": "Date",

        "width": 150

        }

        ]

def get_data_list(filters):

        conditions=""

        if filters.get('date'):

           conditions += f"acc.date between'{filters.get('opening_date')[0]}' and '{filters.get('opening_date')[1]}'"

        if filters.get('employee'):

            conditions+="AND acc.employee='{}'".format(filters.get('employee'))

        data = frappe.db.sql(f"""

        SELECT
        acc.employee,acc.status,acc.time as time,acc.employee_name as employee_name
        FROM `tabApplication Checkin Checkout` AS acc
        WHERE {conditions}
        ORDER BY acc.creation asc

        """, as_dict=1)

        unique = []

        seen = set()

        for row in data:

            check_time = datetime.datetime.strptime(str(row['time']), '%Y-%m-%d %H:%M:%S')

            date = check_time.date()

            employee_date = (row['employee_name'], date)

            if employee_date not in seen:

                seen.add(employee_date)

                row.update({'date':date})

                unique.append(row)

        return unique
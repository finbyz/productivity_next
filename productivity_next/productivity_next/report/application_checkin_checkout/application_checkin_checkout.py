import frappe
from frappe import _
import datetime
import math

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
            },
          {"label": _("Time Consumed"),
            "fieldname": "time_consumed",
            "fieldtype": "Data",
            "width": 200
            }

        ]

def get_data_list(filters):

        conditions=""

        if filters.get('date'):

           conditions += f"acc.creation between'{filters.get('date')[0]}' and '{filters.get('date')[1]}'"

        if filters.get('employee') and filters.get('employee') != "":

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

        #updating the totaltime consumed in for that particular date
        for row in unique:
            time_consumed=get_usage_time(row['employee'],row['date'])
            row.update({'time_consumed':time_consumed})
        return unique


def get_usage_time(employee,date):
    all_logs = frappe.db.get_list("Application Checkin Checkout", filters={"employee": employee, "time": ["Between", [date, date]]}, fields=["status", "time"], order_by="creation asc")
    usage_time = 0
    last_status = None
    
    for row in all_logs:
        if row.status == "In" and last_status != "In":
            start_time = row.time
        elif row.status == "Out" and last_status == "In":
            end_time = row.time
            usage_time += (end_time - start_time).total_seconds()

        last_status = row.status

    hours = str(int(math.floor(usage_time / 3600)))
    minutes = str(int(math.floor((usage_time % 3600) / 60)))

    time_consumed=hours+"hrs"+minutes+"min"
    
    return time_consumed
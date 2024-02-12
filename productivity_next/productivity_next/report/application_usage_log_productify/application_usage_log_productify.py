# import frappe
# from frappe import _

# def execute(filters=None):
#     columns = ['Date', 'Count']
#     data = get_data(filters)
    
#     chart = get_chart_data(data, filters)
#     return columns, data, None, chart

# def get_data(filters):
#     condition = ""
#     if filters and filters.get("employee"):
#         condition = "WHERE employee = '{}'".format(filters.get("employee"))
    
#     data = frappe.db.sql(f"""
# 			select (date) as date, count(*) as count
# 			from `tabApplication Usage log`{condition}
# 			group by date
#     """, as_dict=1)

#     return data



# def get_chart_data(data, filters):
#     condition = ""
#     if filters and filters.get("employee"):
#         condition = "WHERE employee = '{}'".format(filters.get("employee"))
#     data = frappe.db.sql(f"""
#         select unix_timestamp(date) as date, count(*) as count
#             from `tabApplication Usage log` {condition}
#             group by date
#     """, as_dict=1)

#     dict = {}
#     date = []
#     for x in data:
#         dict[x.date]=x.count
#         date.append(x.date)

#     return {
#         "data": {
#             "labels":date,
#             "dataPoints": dict,
#         },
#         "type": "heatmap",
#         "title":"This shows no of activities user performed throughout the day.",
#         "height": 500,
#     }
	
import frappe
from frappe import _

def execute(filters=None):
    columns = ['Hour', 'Count']
    data = get_hourly_data(filters)
    
    chart = get_chart_data(data, filters)
    return columns, data, None, chart

def get_hourly_data(filters):
    condition = ""
    if filters and filters.get("employee"):
        condition = f"WHERE employee = '{filters.get('employee')}'"
    
    data = frappe.db.sql(f"""
        SELECT HOUR(from_time) as hour, count(*) as count
        FROM `tabApplication Usage log` {condition}
        GROUP BY HOUR(from_time)
    """, as_dict=1)

    return data

def get_chart_data(data, filters):
    condition = ""
    if filters and filters.get("employee"):
        condition = "WHERE employee = '{}'".format(filters.get("employee"))
    data = frappe.db.sql(f"""
        SELECT HOUR(from_time) as hour, count(*) as count
        FROM `tabApplication Usage log` {condition}
        GROUP BY HOUR(from_time)
    """, as_dict=1)

    hour = []
    chart_dataset = []
    count = []
    for x in data:
        hour.append(x.hour)
        count.append(x.count)
        dataset = {
            "hour":x.hour,
            "count":x.count
        }
        chart_dataset.append(dataset)
        

    chart = {
        "labels": hour,
        "data": {
            "datasets": count,
        },
        "type": "bar",
    }
    return chart
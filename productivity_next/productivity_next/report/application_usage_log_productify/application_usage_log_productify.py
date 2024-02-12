import frappe
from frappe import _

def execute(filters=None):
    if filters.get("employee") and filters.get("date"):
        columns = ['Hour', 'Count','Fincall Count']
    else:
        columns = ['Date', 'Count']
    data = get_data(filters)
    
    chart = get_chart_data(data, filters)
    return columns, data, None, chart

def get_data(filters):
    if filters.get("employee") and filters.get("date"):
        condition = ""
        if filters and filters.get("employee"):
            condition = f"WHERE employee = '{filters.get('employee')}' and date = '{filters.get('date')}'"
    
        data = frappe.db.sql(f"""
            SELECT HOUR(from_time) as hour, count(*) as count
            FROM `tabApplication Usage log` {condition}
            GROUP BY HOUR(from_time)
        """, as_dict=1)

        data +=  frappe.db.sql(f"""
                SELECT HOUR(call_datetime) as hour, count(*) as fincall_count
                FROM `tabFincall Log` {condition}
                GROUP BY HOUR(call_datetime)
            """, as_dict=1)
        
        def combine_hourly_data(data):
            combined_data = {}
            for item in data:
                hour = item['hour']
                if hour not in combined_data:
                    combined_data[hour] = {'hour': hour, 'count': 0, 'fincall_count': 0}
                combined_data[hour]['count'] += item.get('count', 0)
                combined_data[hour]['fincall_count'] += item.get('fincall_count', 0)
            combined_list = list(combined_data.values())
            return combined_list
        
        data = combine_hourly_data(data)

        return data

    else:
        condition = ""
        if filters and filters.get("employee"):
            condition = "WHERE employee = '{}'".format(filters.get("employee"))
        
        data = frappe.db.sql(f"""
                select (date) as date, count(*) as count
                from `tabApplication Usage log`{condition}
                group by date
        """, as_dict=1)

        return data



def get_chart_data(data, filters):
    if filters.get("employee") and filters.get("date"):
        condition = ""
        if filters and filters.get("employee"):
            condition = f"WHERE employee = '{filters.get('employee')}' and date = '{filters.get('date')}'"
            
            data = frappe.db.sql(f"""
                SELECT HOUR(from_time) as hour, count(*) as count
                FROM `tabApplication Usage log` {condition}
                GROUP BY HOUR(from_time)
            """, as_dict=1)

            data +=  frappe.db.sql(f"""
                    SELECT HOUR(call_datetime) as hour, count(*) as fincall_count
                    FROM `tabFincall Log` {condition}
                    GROUP BY HOUR(call_datetime)
                """, as_dict=1)
            
            def combine_hourly_data(data):
                combined_data = {}
                for item in data:
                    hour = item['hour']
                    if hour not in combined_data:
                        combined_data[hour] = {'hour': hour, 'count': 0, 'fincall_count': 0}
                    combined_data[hour]['count'] += item.get('count', 0)
                    combined_data[hour]['fincall_count'] += item.get('fincall_count', 0)
                combined_list = list(combined_data.values())
                return combined_list
            
            data = combine_hourly_data(data)


            hour = []
            chart_dataset = []
            count = []
            fincall_count=[]
            for x in data:
                hour.append(x["hour"])
                count.append(x["count"])
                fincall_count.append(x["fincall_count"])
                dataset = {
                    "hour":x["hour"],
                    "count":x["count"],
                    "fincall_count":x["fincall_count"]
                }
                chart_dataset.append(dataset)
            

            return {
                'title':"Chart On The Basis of User Usage",
                "data": {
                    "labels": hour,
                    "datasets": [
                        {
                            "name": "Application Log",
                            "values": count,
                        },
                        {
                            "name": "Call Log",
                            "values": fincall_count,
                        },
                        {
                            "name": "Activity Analysis",
                            "values": count,
                        },
                    ]
                },
                "type": "bar",
                "colors": ['#9b5de5',"#f15bb5","#00bbf9"],
                "height": 200,
                "barOptions": { 
                "stacked": 1,
                },
            }
    else:
        condition = ""
        if filters and filters.get("employee"):
            condition = "WHERE employee = '{}'".format(filters.get("employee"))
        data = frappe.db.sql(f"""
            select unix_timestamp(date) as date, count(*) as count
                from `tabApplication Usage log` {condition}
                group by date
        """, as_dict=1)

        dict = {}
        date = []
        for x in data:
            dict[x.date]=x.count
            date.append(x.date)

        return {
            "data": {
                "labels":date,
                "dataPoints": dict,
            },
            "type": "heatmap",
            "title":"This shows no of activities user performed throughout the day.",
            "height": 500,
        }

# def get_hourly_data(filters):
#     condition = ""
#     if filters and filters.get("employee"):
#         condition = f"WHERE employee = '{filters.get('employee')}' and date = '{filters.get('date')}'"
    
#     data = frappe.db.sql(f"""
#         SELECT HOUR(from_time) as hour, count(*) as count
#         FROM `tabApplication Usage log` {condition}
#         GROUP BY HOUR(from_time)
#     """, as_dict=1)

#     return data

# def get_chart_data(data, filters):
#     condition = ""
#     if filters and filters.get("employee"):
#         condition = f"WHERE employee = '{filters.get('employee')}' and date = '{filters.get('date')}'"
#     data = frappe.db.sql(f"""
#         SELECT HOUR(from_time) as hour, count(*) as count
#         FROM `tabApplication Usage log` {condition}
#         GROUP BY HOUR(from_time)
#     """, as_dict=1)

#     hour = []
#     chart_dataset = []
#     count = []
#     for x in data:
#         hour.append(x.hour)
#         count.append(x.count)
#         dataset = {
#             "hour":x.hour,
#             "count":x.count
#         }
#         chart_dataset.append(dataset)
        

#     return {
#         'title':"Chart On The Basis of User Usage",
#         "data": {
#             "labels": hour,
#             "datasets": [
#                 {
#                     "name": "Total Time Involvement",
#                     "values": count,
#                 }
#             ]
#         },
#         "type": "bar",
#     }
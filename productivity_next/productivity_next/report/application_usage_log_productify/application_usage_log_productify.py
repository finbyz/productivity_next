import frappe
from frappe import _
from datetime import datetime,time

def execute(filters=None):
    if filters.get("employee") and filters.get("date"):
        columns = ["Hour", "Count", "Fincall Count","Activity Count"]
    elif not filters.get("employee") and filters.get("date"):
        columns = ["Hour","User ID","Count", "Fincall Count","Activity Count"]
    else:
        columns = ["Date", "Count", "Fincall Count","Activity Count"]
    data = get_data(filters)

    chart = get_chart_data(data, filters)
    # data= sorted(data, key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'), reverse=True)
    # frappe.msgprint(data)
    return columns, data, None, chart

def get_data(filters):
    if filters.get("employee") and filters.get("date"):
        condition = ""
        condition2 = ""
        if filters and filters.get("employee"):
            condition = f"WHERE employee = '{filters.get('employee')}' and date = '{filters.get('date')}'"

        if filters and filters.get("employee"):
            input_date = filters.get('date')
            date_obj = datetime.strptime(input_date, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%Y-%m-%d')
            email = frappe.db.get_value("Employee", filters.get('employee'), "company_email")
            condition2 = f"WHERE owner = '{email}' and Date(creation) = '{formatted_date}'"

        data = frappe.db.sql(
            f"""
            SELECT HOUR(from_time) as hour, count(*) as count
            FROM `tabApplication Usage log` {condition}
            GROUP BY HOUR(from_time)
            ORDER BY date DESC
        """,
            as_dict=1,
        )

        data += frappe.db.sql(
            f"""
                SELECT HOUR(call_datetime) as hour, count(*) as fincall_count
                FROM `tabFincall Log` {condition}
                GROUP BY HOUR(call_datetime)
                ORDER BY date DESC
            """,
            as_dict=1,
        )

        data += frappe.db.sql(
            f"""
                SELECT HOUR(creation) as hour, count(*) as activity_count
                FROM `tabVersion` {condition2}
                GROUP BY HOUR(creation)
            """,
            as_dict=1,
        )

        def combine_hourly_data(data):
            combined_data = {}
            for item in data:
                hour = item["hour"]
                if hour not in combined_data:
                    combined_data[hour] = {"hour": hour, "count": 0, "fincall_count": 0, "activity_count": 0}
                combined_data[hour]["count"] += item.get("count", 0)
                combined_data[hour]["fincall_count"] += item.get("fincall_count", 0)
                combined_data[hour]["activity_count"] += item.get("activity_count", 0)
            combined_list = list(combined_data.values())
            return combined_list

        data = combine_hourly_data(data)

        return data

    elif not filters.get("employee") and filters.get("date"):
        input_date = filters.get('date')
        date_obj = datetime.strptime(input_date, '%Y-%m-%d')
        date = date_obj.strftime('%Y-%m-%d')
        data = frappe.db.sql(
            f"""
            SELECT HOUR(aul.from_time) AS hour, COUNT(*) AS count, emp.user_id AS user_id
            FROM `tabApplication Usage log` aul
            INNER JOIN `tabEmployee` emp ON aul.employee = emp.name
            WHERE DATE(aul.from_time) = '{date}'
            GROUP BY HOUR(aul.from_time), aul.employee
            ORDER BY aul.date DESC
            """,
            as_dict=1,
        )

        data += frappe.db.sql(
            f"""
                SELECT HOUR(fl.call_datetime) AS hour, COUNT(*) AS fincall_count, emp.user_id AS user_id
                FROM `tabFincall Log` fl
                INNER JOIN `tabEmployee` emp ON fl.employee = emp.name
                WHERE DATE(fl.call_datetime) = '{date}'
                GROUP BY HOUR(fl.call_datetime), fl.employee
                ORDER BY fl.date DESC
            """,
            as_dict=1,
        )

        data += frappe.db.sql(
            f"""
                SELECT HOUR(creation) as hour, count(*) as activity_count, owner as person
                FROM `tabVersion` WHERE DATE(creation) = '{date}'
                GROUP BY HOUR(creation), owner
            """,
            as_dict=1,
        )

        def combine_hourly_data(data):
            combined_data = {}
            for item in data:
                hour = item["hour"]
                user_id = item.get("user_id", "")
                if user_id:
                    if hour not in combined_data:
                        combined_data[hour] = {}

                    if user_id not in combined_data[hour]:
                        combined_data[hour][user_id] = {"count": 0, "fincall_count": 0, "activity_count": 0}

                    combined_data[hour][user_id]["count"] += item.get("count", 0)
                    combined_data[hour][user_id]["fincall_count"] += item.get("fincall_count", 0)
                    combined_data[hour][user_id]["activity_count"] += item.get("activity_count", 0)

            combined_list = []
            for hour, users in combined_data.items():
                for user_id, counts in users.items():
                    combined_list.append({
                        "hour": hour,
                        "user_id": user_id,
                        **counts
                    })
            return combined_list

        data = combine_hourly_data(data)
        return data

    else:
        condition1 = ""
        condition2 = ""
        condition3 = ""
        if filters and filters.get("employee"):
            condition1 = "WHERE employee = '{}' AND date >= CURDATE() - INTERVAL 1 YEAR".format(filters.get("employee"))
            condition2 = "WHERE employee = '{}' AND DATE(call_datetime) >= CURDATE() - INTERVAL 1 YEAR".format(filters.get("employee"))
            email = frappe.db.get_value("Employee", filters.get('employee'), "company_email")
            condition3 = f"WHERE owner = '{email}' and DATE(creation) >= CURDATE() - INTERVAL 1 YEAR"
        else:
            condition1 = "WHERE date >= CURDATE() - INTERVAL 1 YEAR"
            condition2 = "WHERE DATE(call_datetime) >= CURDATE() - INTERVAL 1 YEAR"
            condition3 = "WHERE DATE(creation) >= CURDATE() - INTERVAL 1 YEAR"

        data = frappe.db.sql(
            f"""
            SELECT (date) as date, count(*) as count
            FROM `tabApplication Usage log` {condition1}
            GROUP BY date
            ORDER BY date
        """,
            as_dict=1,
        )

        data += frappe.db.sql(
            f"""
                SELECT DATE(call_datetime) as date, count(*) as fincall_count
                FROM `tabFincall Log`
                {condition2}
                GROUP BY DATE(call_datetime)
                ORDER BY date
            """,
            as_dict=1,
        )

        data += frappe.db.sql(
            f"""
                SELECT DATE(creation) as date, count(*) as activity_count
                FROM `tabVersion`
                {condition3}
                GROUP BY DATE(creation)
            """,
            as_dict=1,
        )

        def combine_hourly_data(data):
            combined_data = {}
            for item in data:
                date = item["date"]
                if date not in combined_data:
                    combined_data[date] = {
                        "date": date,
                        "count": 0,
                        "fincall_count": 0,
                        "activity_count": 0
                    }
                combined_data[date]["count"] += item.get("count", 0)
                combined_data[date]["fincall_count"] += item.get("fincall_count", 0)
                combined_data[date]["activity_count"] += item.get("activity_count", 0)
            combined_list = list(combined_data.values())
            return combined_list

        data = combine_hourly_data(data)
        data = sorted(data, key=lambda x: x['date'], reverse=True)
        return data



def get_chart_data(data, filters):
    if filters.get("employee") and filters.get("date"):
        condition = ""
        condition2 = ""
        if filters and filters.get("employee"):
            condition = f"WHERE employee = '{filters.get('employee')}' and date = '{filters.get('date')}'"

        if filters and filters.get("employee"):
            input_date = filters.get('date')
            date_obj = datetime.strptime(input_date, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%Y-%m-%d')
            email = frappe.db.get_value("Employee",filters.get('employee'),"company_email")
            condition2 = f"WHERE owner = '{email}' and Date(creation) = '{formatted_date}'"

            data = frappe.db.sql(
                f"""
                SELECT HOUR(from_time) as hour, count(*) as count
                FROM `tabApplication Usage log` {condition}
                GROUP BY HOUR(from_time)
            """,
                as_dict=1,
            )

            data += frappe.db.sql( 
                f"""
                    SELECT HOUR(call_datetime) as hour, count(*) as fincall_count
                    FROM `tabFincall Log` {condition}
                    GROUP BY HOUR(call_datetime)
                """,
                as_dict=1,
            )

            data += frappe.db.sql(
                f"""
                    SELECT HOUR(creation) as hour, count(*) as activity_count
                    FROM
                        `tabVersion`{condition2}
                    GROUP BY
                        HOUR(creation)
                """,
                as_dict=1,
            )

            def combine_hourly_data(data):
                combined_data = {}
                for item in data:
                    hour = item["hour"]
                    if hour not in combined_data:
                        combined_data[hour] = {
                            "hour": hour,
                            "count": 0,
                            "fincall_count": 0,
                            "activity_count":0
                        }
                    combined_data[hour]["count"] += item.get("count", 0)
                    combined_data[hour]["fincall_count"] += item.get("fincall_count", 0)
                    combined_data[hour]["activity_count"] += item.get("activity_count", 0)
                combined_list = list(combined_data.values())
                return combined_list

            data = combine_hourly_data(data)

            hour = []
            chart_dataset = []
            count = []
            fincall_count = []
            activity_count = []
            for x in data:
                hour.append(x["hour"])
                count.append(x["count"])
                fincall_count.append(x["fincall_count"])
                activity_count.append(x["activity_count"])
                dataset = {
                    "hour": x["hour"],
                    "count": x["count"],
                    "fincall_count": x["fincall_count"],
                    "activity_count":x["activity_count"]
                }
                chart_dataset.append(dataset)

            return {
                "title": "Chart On The Basis of User Usage",
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
                            "values": activity_count,
                        },
                    ],
                },
                "type": "bar",
                "colors": ["#9b5de5", "#f15bb5", "#00bbf9"],
                "height": 200,
                "barOptions": {
                    "stacked": 1,
                },
            }
        
    elif not filters.get("employee") and filters.get("date"):
        input_date = filters.get('date')
        date_obj = datetime.strptime(input_date, '%Y-%m-%d')
        date = date_obj.strftime('%Y-%m-%d')
        data = frappe.db.sql(
        f"""
        SELECT HOUR(aul.from_time) AS hour, COUNT(*) AS count, emp.user_id AS user_id
        FROM `tabApplication Usage log` aul
        INNER JOIN `tabEmployee` emp ON aul.employee = emp.name
        WHERE DATE(aul.from_time) = '{date}'
        GROUP BY HOUR(aul.from_time), aul.employee
        """,
        as_dict=1,
        )

        data += frappe.db.sql(
            f"""
                SELECT HOUR(fl.call_datetime) AS hour, COUNT(*) AS fincall_count, emp.user_id AS user_id
                FROM `tabFincall Log` fl
                INNER JOIN `tabEmployee` emp ON fl.employee = emp.name
                WHERE DATE(fl.call_datetime) = '{date}'
                GROUP BY HOUR(fl.call_datetime), fl.employee
            """,
                as_dict=1,
            )

        data += frappe.db.sql(
                f"""
                    SELECT HOUR(creation) as hour, count(*) as activity_count, owner as person
                    FROM
                        `tabVersion` WHERE DATE(creation) = '{date}'
                    GROUP BY
                        HOUR(creation),owner
                """,
                as_dict=1,
            )
        
        def combine_hourly_data_for_chart(data):
            combined_data = {}
            
            for item in data:
                hour = item["hour"]
                user_id = item.get("user_id", "")
                if user_id:
                    if hour not in combined_data:
                        combined_data[hour] = {}
                    if user_id not in combined_data[hour]:
                        combined_data[hour][user_id] = 0 
                    combined_data[hour][user_id] += sum(item.get(k, 0) for k in ["count", "fincall_count", "activity_count"])
            chart_dataset = {"labels": [], "datasets": []}
            user_ids = set()
            for hour, users in combined_data.items():
                chart_dataset["labels"].append(hour)
                for user_id in users:
                    user_ids.add(user_id)

            for user_id in user_ids:
                chart_dataset["datasets"].append({"name": user_id, "values": [0] * len(chart_dataset["labels"])})

            for i, hour in enumerate(chart_dataset["labels"]):
                for dataset in chart_dataset["datasets"]:
                    user_id = dataset["name"]
                    dataset["values"][i] = combined_data[hour].get(user_id, 0)

            return {
                "title": "Chart On The Basis of User Usage",
                "data": chart_dataset,
                "type": "bar",
                "height": 200,
                "barOptions": {"stacked": True},
            }
        chart_data = combine_hourly_data_for_chart(data) 
        return chart_data  

    else:
        condition1 = ""
        condition2 = ""
        condition3 = ""
        if filters and filters.get("employee"):
            condition1 = "WHERE employee = '{}' AND date >= CURDATE() - INTERVAL 1 YEAR".format(filters.get("employee"))
            condition2 = "WHERE employee = '{}' AND DATE(call_datetime) >= CURDATE() - INTERVAL 1 YEAR".format(filters.get("employee"))
            email = frappe.db.get_value("Employee",filters.get('employee'),"company_email")
            condition3 = f"WHERE owner = '{email}' and DATE(creation) >= CURDATE() - INTERVAL 1 YEAR"
        else:
            condition1 = "WHERE date >= CURDATE() - INTERVAL 1 YEAR"
            condition2 = "WHERE DATE(call_datetime) >= CURDATE() - INTERVAL 1 YEAR"
            condition3 = "WHERE DATE(creation) >= CURDATE() - INTERVAL 1 YEAR"

        data = frappe.db.sql(
        f"""
        SELECT (date) as date, count(*) as count
        FROM `tabApplication Usage log`
        {condition1}
        GROUP BY date
        """,
        as_dict=1,
        )

        data += frappe.db.sql(
        f"""
            SELECT DATE(call_datetime) as date, count(*) as fincall_count
            FROM `tabFincall Log`
            {condition2}
            GROUP BY DATE(call_datetime)
        """,
        as_dict=1,
        )

        data += frappe.db.sql(
            f"""
                SELECT DATE(creation) as date, count(*) as activity_count
                FROM
                    `tabVersion`
                {condition3}
                GROUP BY
                    DATE(creation)
            """,
            as_dict=1,
        )

        def combine_hourly_data(data):
            combined_data = {}
            for item in data:
                date = item["date"]
                if date not in combined_data:
                    combined_data[date] = {
                        "date": date,
                        "count": 0,
                        "fincall_count": 0,
                        "activity_count":0
                    }
                combined_data[date]["count"] += item.get("count", 0)
                combined_data[date]["fincall_count"] += item.get("fincall_count", 0)
                combined_data[date]["activity_count"] += item.get("activity_count", 0)
            combined_list = list(combined_data.values())
            return combined_list

        data = combine_hourly_data(data)

        date = []
        chart_dataset = []
        count = []
        fincall_count = []
        activity_count = []
        for x in data:
            date.append(x["date"])
            count.append(x["count"])
            fincall_count.append(x["fincall_count"])
            activity_count.append(x["activity_count"])
            dataset = {
                "date": x["date"],
                "count": x["count"],
                "fincall_count": x["fincall_count"],
                "activity_count":x["activity_count"]
            }
            chart_dataset.append(dataset)

        dict = {}
        date = []
        for x in chart_dataset:
            datetime_obj = datetime.combine(x["date"], time())
            timestamp = datetime_obj.timestamp()
            dict[timestamp]=x["count"]+x["fincall_count"]+x["activity_count"]
            date.append(x["date"])

        return {
            "data": {
                "labels":date,
                "dataPoints": dict,
            },
            "type": "heatmap",
            "title":"This shows no of activities user performed throughout the day.",
            "height": 500,
        }
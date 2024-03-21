
from datetime import datetime,time
import frappe

@frappe.whitelist()
def get_heatmap_data(user, date):

    data = frappe.db.sql(
        f"""
        SELECT (date) as date, count(*) as count
        FROM `tabApplication Usage log`
        GROUP BY date
        """,
        as_dict=1,
        )

    data += frappe.db.sql(
    f"""
        SELECT DATE(call_datetime) as date, count(*) as fincall_count
        FROM `tabFincall Log`
        GROUP BY DATE(call_datetime)
    """,
    as_dict=1,
    )

    data += frappe.db.sql(
        f"""
            SELECT DATE(creation) as date, count(*) as activity_count
            FROM
                `tabVersion`
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

    return dict

from datetime import datetime,time,timedelta
import frappe
from frappe import utils
from frappe.utils import now
from frappe.utils import add_months,getdate
from collections import defaultdict
from frappe import _
import json

from dateutil.parser import parse

@frappe.whitelist() 
def version_conditions(user,start_date=None, end_date=None):
    now = frappe.utils.now_datetime()
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00')
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d 00:00:00')
    
    if end_date is None:
        end_date = now.strftime('%Y-%m-%d 23:59:59')
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d 23:59:59')
    if user != "Administrator":
        email = frappe.db.get_value("Employee", user, "company_email")
        condition = f"WHERE owner = '{email}' AND creation >= '{start_date}' AND creation <= '{end_date}'"
    else:
        condition = f"WHERE creation >= '{start_date}' AND creation <= '{end_date}'"

    return condition


@frappe.whitelist() 
def issue_time_conditions(user,start_date=None, end_date=None):
    start_date, end_date = set_dates(start_date, end_date)
    if user != "Administrator":
        email = frappe.db.get_value("Employee", user, "company_email")
        condition = f"WHERE ti.user_name = '{email}' AND ti.date >= '{start_date}' AND ti.date <= '{end_date}'"
    else:
        condition = f"WHERE ti.date >= '{start_date}' AND ti.date <= '{end_date}'"

    return condition


@frappe.whitelist()
def get_user_data(user,start_date=None, end_date=None):
    version_conditions_str = version_conditions(user,start_date,end_date)
    start_date_,end_date_ = set_dates(start_date, end_date)
    ignore_doctype = ['File',"Communication","Fincall Log","Custom Field","DocType","Web Page","Attendance"]
    ignore_doctype_str = ','.join(f"'{doc}'" for doc in ignore_doctype)
    if ignore_doctype_str:
        ignore_condition = f"AND ref_doctype NOT IN ({ignore_doctype_str})"
    else:
        ignore_condition = ""
    start_date, end_date = set_dates(start_date, end_date)

    conditions = f"WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}'"
    conditions_2 = f"AND mcr.employee = '{user}' AND m.meeting_from >= '{start_date_}' AND m.meeting_to <= '{end_date_}'"

    fincall_data = frappe.db.sql(f"""
        SELECT 
            calltype,
            COUNT(*) AS fincall_count,
            COALESCE(SUM(duration), 0) AS total_duration
        FROM `tabEmployee Fincall`
        {conditions} and (link_to != 'Company' or link_to is null)
        GROUP BY calltype
    """, as_dict=True)

    # Initialize counts and total durations
    incoming_fincall_count = outgoing_fincall_count = missed_fincall_count = rejected_fincall_count = 0
    total_incoming_duration = total_outgoing_duration = 0

    # Extracting data for each call type in a single pass
    for item in fincall_data:
        calltype = item['calltype']
        count = item['fincall_count']
        duration = item['total_duration']
        
        if calltype == 'Incoming':
            incoming_fincall_count = count
            total_incoming_duration = duration
        elif calltype == 'Outgoing':
            outgoing_fincall_count = count
            total_outgoing_duration = duration
        elif calltype == 'Missed':
            missed_fincall_count = count
        elif calltype == 'Rejected':
            rejected_fincall_count = count

    internal_fincall_data = frappe.db.sql(f"""
        SELECT 
            calltype,
            COUNT(*) AS fincall_count,
            COALESCE(SUM(duration), 0) AS total_duration
        FROM `tabEmployee Fincall`
        {conditions} and link_to = 'Company' and link_to is not null
        GROUP BY calltype
    """, as_dict=True)

    # Initialize counts and total durations
    internal_incoming_fincall_count = internal_outgoing_fincall_count = 0
    internal_missed_fincall_count = internal_rejected_fincall_count = 0
    internal_total_incoming_duration = internal_total_outgoing_duration = 0

    # Extracting data for each call type in a single pass
    for item in internal_fincall_data:
        calltype = item['calltype']
        count = item['fincall_count']
        duration = item['total_duration']
        
        if calltype == 'Incoming':
            internal_incoming_fincall_count = count
            internal_total_incoming_duration = duration
        elif calltype == 'Outgoing':
            internal_outgoing_fincall_count = count
            internal_total_outgoing_duration = duration
        elif calltype == 'Missed':
            internal_missed_fincall_count = count
        elif calltype == 'Rejected':
            internal_rejected_fincall_count = count                             

    application_usage_days = frappe.db.sql(f"""
        SELECT DISTINCT DATE(`date`) AS date 
        FROM `tabApplication Usage log`
        {conditions};
    """, as_dict=True, pluck='date')

    # Fetch meeting usage days
    meeting_usage_days = frappe.db.sql(f"""
        SELECT DISTINCT DATE(m.meeting_from) AS date 
        FROM `tabMeeting` AS m 
        JOIN `tabMeeting Company Representative` AS mcr 
        ON m.name = mcr.parent 
        {conditions_2}
    """, as_dict=True, pluck='date')

    total_days = len(set(application_usage_days + meeting_usage_days)) or 1

    sql_query = f"""
    SELECT 
        SUM(CASE 
                WHEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from)) > 0 THEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))
                ELSE 0 
            END) AS total_meeting_duration,
        COUNT(DISTINCT m.name) as meeting_count
    FROM `tabMeeting` as m
    JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent WHERE mcr.employee = %s
    and m.docstatus = 1 and internal_meeting = 0
    {conditions_2}
    GROUP BY mcr.employee
    """
    meetings_external_employee = frappe.db.sql(sql_query, (user,), as_dict=True)
    sql_query = f"""
    SELECT 
        SUM(CASE 
                WHEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from)) > 0 THEN TIME_TO_SEC(TIMEDIFF(m.meeting_to, m.meeting_from))
                ELSE 0 
            END) AS total_meeting_duration,
        COUNT(DISTINCT m.name) as meeting_count
    FROM `tabMeeting` as m
    JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent WHERE mcr.employee = %s
    and m.docstatus = 1 and internal_meeting = 1
    {conditions_2}
    GROUP BY mcr.employee
    """

    # Executing the query
    meetings_internal_employee = frappe.db.sql(sql_query, (user,), as_dict=True)

    # Documents Accessed
    total_unique_doc = frappe.db.sql(f"""
    SELECT COUNT(DISTINCT docname) AS activity_count
    FROM `tabVersion`
    {version_conditions_str}
    {ignore_condition}
    """, as_dict=True)

    # Application Usage Log Count, Top 10 Doc's Used Cards
    total_counts = frappe.db.sql(f"""
        SELECT
            (SELECT COUNT(DISTINCT application_name) FROM `tabApplication Usage log`{conditions})  AS application_usage,
            (SELECT COUNT(*) FROM `tabVersion` {version_conditions_str} {ignore_condition})  AS version_count
        """, as_dict=1)[0]

    domain_data = frappe.db.sql(f"""
        SELECT domain, SUM(duration) as total_duration, process_id,count(domain) as count
        FROM `tabURL Access Log`
        Where employee = '{user}' and from_time >= '{start_date_}' and to_time <= '{end_date_}' and domain != '' and domain is not null
        GROUP BY domain
        ORDER BY total_duration DESC
        LIMIT 10
        """,as_dict=True)
    process_id_names = {"chrome.exe":"Google Chrome","firefox.exe":"Mozilla Firefox","msedge.exe":"Microsoft Edge","opera.exe":"Opera","iexplore.exe":"Internet Explorer","brave.exe":"Brave","safari.exe":"Safari","vivaldi.exe":"Vivaldi","chromium.exe":"Chromium","microsoftedge.exe":"Microsoft Edge"}
    result_list = []
    for i in domain_data:
        if i["process_id"]:
            application_name = process_id_names.get(i["process_id"].lower())
            if application_name:
                app_name = application_name
            else:
                app_name = (i["process_id"]).lower().split(".exe")[0].capitalize()
        result_list.append({
            "domain": i['domain'],
            "total_duration": i['total_duration'],
            "application_name": app_name,
            "count": i['count'],
        })


    return {
        "application_usage": total_counts['application_usage'],
        "version_count": total_counts['version_count'],
        "incoming_fincall_count": incoming_fincall_count,
        "outgoing_fincall_count": outgoing_fincall_count,
        "missed_fincall_count": missed_fincall_count,
        "rejected_fincall_count": rejected_fincall_count,
        "total_incoming_duration": total_incoming_duration,
        "total_outgoing_duration": total_outgoing_duration,
        "internal_incoming_fincall_count": internal_incoming_fincall_count,
        "internal_outgoing_fincall_count": internal_outgoing_fincall_count,
        "internal_missed_fincall_count": internal_missed_fincall_count,
        "internal_rejected_fincall_count": internal_rejected_fincall_count,
        "internal_total_incoming_duration": internal_total_incoming_duration,
        "internal_total_outgoing_duration": internal_total_outgoing_duration,
        "total_days": total_days,
        "total_unique_doc": total_unique_doc[0]['activity_count'] if total_unique_doc else 0,
        "total_time_on_calls": fincall_data[0]['total_duration'] if fincall_data else 0,
        "total_meeting_duration_internal": meetings_internal_employee[0].total_meeting_duration if meetings_internal_employee else 0,
        "total_meeting_count_internal": meetings_internal_employee[0].meeting_count if meetings_internal_employee else 0,
        "total_meeting_duration_external": meetings_external_employee[0].total_meeting_duration if meetings_external_employee else 0,
        "total_meeting_count_external": meetings_external_employee[0].meeting_count if meetings_external_employee else 0,
        "url_full_data": result_list[:10],
    }

@frappe.whitelist()
def get_url_brief_data(url_data,user,start_date=None, end_date=None):
    start_date_,end_date_ = set_dates(start_date, end_date)
    conditions = f"WHERE employee = '{user}' AND from_time >= '{start_date_}' AND to_time <= '{end_date_}'"
    query = f"""
        SELECT url, SUM(duration) AS duration, COUNT(url) as count, current_title
        FROM `tabURL Access Log` 
        {conditions} and domain = '{url_data}'
        GROUP BY url
        ORDER BY SUM(duration) DESC
        """
    data_query = frappe.db.sql(query, as_dict=True)
    return {
        "data":data_query
    }

# ISSUE DATA
@frappe.whitelist()
def get_issue_data(user,start_date=None, end_date=None):
    issue_time_conditions_str = issue_time_conditions(user, start_date, end_date)
    data = frappe.db.sql(f"""
        SELECT 
            COUNT(DISTINCT i.subject) AS no_of_issues,
            SUM(ti.time_involvement) AS time_in_issues
        FROM `tabIssue` as i
        JOIN `tabTime Involvement` as ti ON i.name = ti.parent
        {issue_time_conditions_str}
    """, as_dict=1)
    # Parsing the result to return counts
    if data:
        no_of_issues = data[0]['no_of_issues'] if 'no_of_issues' in data[0] else 0
        time_in_issues = data[0]['time_in_issues'] if 'time_in_issues' in data[0] else 0
    else:
        no_of_issues = 0
        time_in_issues = 0

    return {
        "no_of_issues": no_of_issues,
        "time_in_issues": time_in_issues
    }
def get_data_for_issue_chart(user, start_date=None, end_date=None):
    issue_time_conditions_str = issue_time_conditions(user, start_date, end_date)
    data = frappe.db.sql(f"""
        SELECT 
            i.project, 
            COUNT(DISTINCT i.subject) AS no_of_issues,
            SUM(ti.time_involvement) AS time_in_issues
        FROM `tabIssue` as i
        JOIN `tabTime Involvement` as ti ON i.name = ti.parent
        {issue_time_conditions_str}
        GROUP BY i.project
        ORDER BY no_of_issues DESC, time_in_issues DESC
    """, as_dict=1)

    return data

# Issue Chart
@frappe.whitelist()
def get_issuechart_data(user, start_date=None, end_date=None):
    data = get_data_for_issue_chart(user, start_date, end_date)    
    return {
        "labels": [i["project"] for i in data],
        "datasets": [{"values": [i["no_of_issues"] for i in data]}]
    }

# Issue Time Chart
@frappe.whitelist()
def get_issue_time_chart_data(user, start_date=None, end_date=None):
    data = get_data_for_issue_chart(user, start_date, end_date)
    return {
        "labels": [i["project"] for i in data],
        "datasets": [{"values": [i["time_in_issues"] for i in data]}]
    }

# PIE CHART
@frappe.whitelist()
def get_piechart_data(user, start_date=None, end_date=None):
    data = frappe.db.sql(f"""
            SELECT application_name, SUM(duration) as duration
            FROM `tabApplication Usage log`
            WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}'
            GROUP BY application_name
            ORDER BY duration DESC
            LIMIT 5
        """, as_dict=1)
        
    return {
        "labels": [i["application_name"] for i in data],
        "datasets": [{"values": [round(i["duration"]/60/60,2) for i in data]}]
    }
@frappe.whitelist()
def get_linechart_data(user, start_date=None, end_date=None):
    # SQL query to group by contact, client, or customer_no
    data = frappe.db.sql(f"""
        select sum(duration) as total_count, calltype, hour(call_datetime) as hour
        FROM `tabEmployee Fincall`
        WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}' and (calltype = 'Incoming' or calltype = 'Outgoing')
        group by HOUR(call_datetime), calltype
        """, as_dict=1)
    
    aggregated_data = defaultdict(lambda: {'incoming_count': 0, 'outgoing_count': 0})
    
    # Step 2: Aggregate the total_count for each hour based on calltype
    for record in data:
        hour = record['hour']
        if record['calltype'] == 'Incoming':
            aggregated_data[hour]['incoming_count'] += record['total_count']
        elif record['calltype'] == 'Outgoing':
            aggregated_data[hour]['outgoing_count'] += record['total_count']
    
    # Step 3: Convert the aggregated data back to a list of dictionaries
    aggregated_list = [
        {'hour': hour, 'incoming_count': counts['incoming_count'], 'outgoing_count': counts['outgoing_count']}
        for hour, counts in aggregated_data.items()
    ]
    
    # Prepare data for line chart
    return {
        "labels": [str(i["hour"])+":00" for i in aggregated_list],
        "datasets": [
            {
                "name": "Incoming",
                "values": [round(i["incoming_count"] / 60, 2) for i in aggregated_list]
            },
            {
                "name": "Outgoing",
                "values": [round(i["outgoing_count"] / 60, 2) for i in aggregated_list]
            }
        ]
    }



# BAR CHART
@frappe.whitelist()
def get_barchart_data(user, start_date=None, end_date=None):
    now = frappe.utils.now_datetime()
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d')
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d')
    
    if end_date is None:
        end_date = now.strftime('%Y-%m-%d') 
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d') 
    
    version_conditions_str = version_conditions(user,start_date,end_date)
    ignore_doctype = ['File',"Communication","Fincall Log","Custom Field","DocType","Web Page","Attendance"]

    # Convert the list into a format suitable for SQL query ("'DocType1', 'DocType2', 'DocType3'")
    ignore_doctype_str = ','.join(f"'{doc}'" for doc in ignore_doctype)

    # Check if the list is not empty to add a condition to the query
    if ignore_doctype_str:
        ignore_condition = f"AND ref_doctype NOT IN ({ignore_doctype_str})"
    else:
        ignore_condition = ""
    data = frappe.db.sql(f"""
        SELECT COUNT(DISTINCT docname) AS activity_count, ref_doctype
        FROM `tabVersion`
        {version_conditions_str}
        {ignore_condition}
        group by ref_doctype
        order by activity_count DESC 
        LIMIT 7
        """, as_dict=1)
        
    return {
        "labels": [i["ref_doctype"] for i in data],
        "datasets": [{"values": [i["activity_count"] for i in data]}]
    }

@frappe.whitelist()
def get_images(user, start_date=None, end_date=None, offset=0):
    # start_date, end_date = set_dates(start_date, end_date)

    data = frappe.get_all("Screen Screenshot Log", filters={"employee": user, "datetime": ["BETWEEN", [parse(start_date), parse(end_date)]]}, order_by="datetime desc", group_by="datetime", fields=["screenshot", "datetime"])

    for i in data:
        i["datetime_"] = frappe.format(i["datetime"], "Datetime")
    return data


def set_dates(start_date=None, end_date=None):
    """
    Determine start and end dates for a range, formatted with specific time stamps.
    Args:
    - start_date (str, optional): Start date in 'YYYY-MM-DD' format. Defaults to 365 days ago.
    - end_date (str, optional): End date in 'YYYY-MM-DD' format. Defaults to today.

    Returns:
    - tuple: A tuple containing formatted start and end dates as strings.
    """
    now = frappe.utils.now_datetime()
    
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00')
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d 00:00:00')
    
    if end_date is None:
        end_date = now.strftime('%Y-%m-%d 23:59:59')
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d 23:59:59')

    return start_date, end_date

@frappe.whitelist()
def get_issue_active_chart_data(user, start_date=None, end_date=None):
    email = frappe.db.get_value("Employee", user, "company_email")
    def get_date_range(start_date, end_date):
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        date_range = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end - start).days + 1)]
        return date_range
    
    def active_hours(user, date):
        # Fetch idle time logs
        idle_time_data = frappe.db.sql(f"""
            SELECT start_time, end_time
            FROM `tabEmployee Idle Time`
            WHERE employee = '{user}' AND start_time > '{date} 00:00:00' AND end_time < '{date} 23:59:59'
        """, as_dict=True)

        # Fetch fincall time logs
        fincall_time_data = frappe.db.sql(f"""
            SELECT call_datetime as start_time, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time
            FROM `tabEmployee Fincall`
            WHERE employee = '{user}' AND date >= '{date}' AND date <= '{date}' AND (calltype != 'Missed' AND calltype != 'Rejected')
        """, as_dict=True)

        # Fetch meeting time logs
        meeting_time_data = frappe.db.sql(f"""
            SELECT meeting_from as start_time, meeting_to as end_time
            FROM `tabMeeting` as m
            JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
            WHERE m.docstatus = 1 AND mcr.employee = '{user}'
            AND m.meeting_from >= '{date} 00:00:00' AND m.meeting_to <= '{date} 23:59:59'
        """, as_dict=True)

        # Combine all non-idle periods (meetings and calls)
        non_idle_periods = fincall_time_data + meeting_time_data

        total_idle_seconds = 0

        for idle_period in idle_time_data:
            idle_start = idle_period['start_time']
            idle_end = idle_period['end_time']

            adjusted_start = idle_start
            adjusted_end = idle_end

            for non_idle in non_idle_periods:
                non_idle_start = non_idle['start_time']
                non_idle_end = non_idle['end_time']

                # Check for overlap and adjust idle periods accordingly
                if non_idle_start <= adjusted_end and non_idle_end >= adjusted_start:
                    if non_idle_start <= adjusted_start < non_idle_end:
                        adjusted_start = non_idle_end
                    if non_idle_start < adjusted_end <= non_idle_end:
                        adjusted_end = non_idle_start
                    if adjusted_start >= adjusted_end:
                        adjusted_start = adjusted_end
                        break

            # Calculate the duration of the adjusted idle period
            idle_duration = (adjusted_end - adjusted_start).total_seconds()
            if idle_duration > 0:
                total_idle_seconds += idle_duration
        total_idle_time_in_seconds = round(total_idle_seconds)

        application_usage_total_time = frappe.db.sql(f"""
            SELECT sum(duration) as total_duration
            FROM `tabApplication Usage log`
            Where employee = '{user}' and date = '{date}'
        """, as_dict=True)
        usage_time = application_usage_total_time[0].get('total_duration', 0) if application_usage_total_time else 0 
        if usage_time == 0 or usage_time is None:
            return 0, 0
        total_hours = usage_time / 3600  # Convert to hours
        active_hours = total_hours - (total_idle_time_in_seconds / 3600)

        return active_hours, total_hours

    date_range = get_date_range(start_date, end_date)

    results = []
    for date in date_range:
        issue_time = frappe.db.sql(f"""
            SELECT 
                SUM(ti.time_involvement) AS time_in_issues
            FROM `tabIssue` as i
            JOIN `tabTime Involvement` as ti ON i.name = ti.parent
            WHERE ti.user_name = '{email}' AND ti.date = '{date}'
            GROUP BY ti.date
        """, as_dict=1)
        issue_time = issue_time[0].get('time_in_issues', 0) if issue_time else 0
        active_time, total_hours = active_hours(user, date)
        
        if issue_time > 0 or active_time > 0:
            results.append({
                "date": date,
                "issue_time": issue_time,
                "active_time": active_time,
                "total_hours": total_hours
            })
            
    for i in results:
        i["date"] = frappe.format(i["date"], "Date")
        i["active_time"] = round(i["active_time"], 2)
        i["total_hours"] = round(i["total_hours"], 2)

    return {
        "labels": [i["date"] for i in results],
        "datasets": [{"name":"Issue Time","values":[i["issue_time"] for i in results]},{"name":"Active Time","values": [i["active_time"] for i in results]},{"name":"Total Time","values": [i["total_hours"] for i in results]}]
    }
@frappe.whitelist()
def work_stats_chart(user, start_date=None, end_date=None):
    pass
    # # Data
    # hours = [f"{i} AM" for i in range(1, 12)] + ["12 PM"] + [f"{i} PM" for i in range(1, 12)] + ["12 Midnight"]
    # num_hours = len(hours)
    # bars_per_hour = 12

    # # Generating random data for demonstration
    # np.random.seed(0)
    # data = np.random.rand(4, num_hours * bars_per_hour)

    # # Normalize data to sum to 1 for each bar to simulate stacked bar chart percentages
    # data = data / data.sum(axis=0)

    # # Colors and labels
    # colors = ['green', 'gray', 'orange', 'red']
    # labels = ['Task A', 'Task B', 'Task C', 'Task D']

    # # Prepare the data for Chart.js
    # chart_data = {
    #     'labels': hours,
    #     'datasets': []
    # }

    # for i in range(4):
    #     chart_data['datasets'].append({
    #         'label': labels[i],
    #         'backgroundColor': colors[i],
    #         'data': data[i].tolist()
    #     })

    # return json.dumps(chart_data)


@frappe.whitelist()
def get_activity_chart_data_():
    sample_data = {
       'incoming' : 50,
       'outgoing' : 20,
       'missed' : 20,
       'rejected' : 10
    }
    return sample_data


@frappe.whitelist()
def get_activity_chart_data(user,start_date=None, end_date=None):
    start_date_,end_date_ = set_dates(start_date, end_date)
    start_date, end_date = set_dates(start_date, end_date)

    # Fetch idle time logs
    idle_time_data = frappe.db.sql(f"""
        SELECT start_time, end_time
        FROM `tabEmployee Idle Time`
        WHERE employee = '{user}' AND start_time > '{start_date_}' AND end_time < '{end_date_}'
    """, as_dict=True)

    # Fetch fincall time logs
    fincall_time_data = frappe.db.sql(f"""
        SELECT call_datetime as start_time, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time
        FROM `tabEmployee Fincall`
        WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}' AND (calltype != 'Missed' AND calltype != 'Rejected')
    """, as_dict=True)

    # Fetch meeting time logs
    meeting_time_data = frappe.db.sql(f"""
        SELECT meeting_from as start_time, meeting_to as end_time
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE m.docstatus = 1 AND mcr.employee = '{user}'
        AND m.meeting_from >= '{start_date_}' AND m.meeting_to <= '{end_date_}'
    """, as_dict=True)

    # Combine all non-idle periods (meetings and calls)
    non_idle_periods = fincall_time_data + meeting_time_data

    total_idle_seconds = 0

    for idle_period in idle_time_data:
        idle_start = idle_period['start_time']
        idle_end = idle_period['end_time']

        adjusted_start = idle_start
        adjusted_end = idle_end

        for non_idle in non_idle_periods:
            non_idle_start = non_idle['start_time']
            non_idle_end = non_idle['end_time']

            # Check for overlap and adjust idle periods accordingly
            if non_idle_start <= adjusted_end and non_idle_end >= adjusted_start:
                if non_idle_start <= adjusted_start < non_idle_end:
                    adjusted_start = non_idle_end
                if non_idle_start < adjusted_end <= non_idle_end:
                    adjusted_end = non_idle_start
                if adjusted_start >= adjusted_end:
                    adjusted_start = adjusted_end
                    break

        # Calculate the duration of the adjusted idle period
        idle_duration = (adjusted_end - adjusted_start).total_seconds()
        if idle_duration > 0:
            total_idle_seconds += idle_duration
    total_idle_time = round(total_idle_seconds) 

    total_call_data = frappe.db.sql(f"""
        SELECT 
            SUM(duration) AS total_duration
        FROM `tabEmployee Fincall`
        WHERE employee = '{user}' AND call_datetime > '{start_date_}' AND call_datetime < '{end_date_}'
    """, as_dict=True)
    total_meeting_data = frappe.db.sql(f"""
        SELECT 
            SUM(TIME_TO_SEC(TIMEDIFF(meeting_to, meeting_from))) AS total_duration  
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE mcr.employee = '{user}' and m.docstatus = 1 and m.meeting_from >= '{start_date_}' and m.meeting_to <= '{end_date_}'
    """, as_dict=True)

    list_data = []
    meeting_total_data = frappe.db.sql(f"""
        SELECT m.meeting_from as start_time, m.meeting_to as end_time
        FROM `tabMeeting` as m
        JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        WHERE mcr.employee ='{user}' and m.docstatus = 1 and m.meeting_from >= '{start_date_}' and m.meeting_to <= '{end_date_}'
    """, as_dict=True)
    calls_total_data = frappe.db.sql(f"""
        SELECT call_datetime as start_time, ADDTIME(call_datetime, SEC_TO_TIME(duration)) as end_time
        FROM `tabEmployee Fincall`
        WHERE employee = '{user}' and call_datetime >= '{start_date_}' and call_datetime <= '{end_date_}' and (calltype != 'Missed' and calltype != 'Rejected')
    """, as_dict=True)
    application_total_data = frappe.db.sql(f"""
        SELECT from_time as start_time, to_time as end_time
        FROM `tabApplication Usage log`
        WHERE employee = '{user}' and date >= '{start_date}' and date <= '{end_date}'
    """, as_dict=True)

    list_data.append(meeting_total_data)
    list_data.append(calls_total_data)
    list_data.append(application_total_data) 

    if list_data != [[], [], []]:

        # Flatten the list of intervals
        flat_intervals = [interval for sublist in list_data for interval in sublist]

        # Sort intervals by start time
        flat_intervals.sort(key=lambda x: x['start_time'])

        # Merge overlapping intervals
        merged_intervals = []
        current_interval = flat_intervals[0]

        for interval in flat_intervals[1:]:
            if interval['start_time'] and interval['end_time'] and current_interval['end_time']:
                if interval['start_time'] <= current_interval['end_time']:
                    # There is overlap, so merge the intervals
                    current_interval['end_time'] = max(current_interval['end_time'], interval['end_time'])
                else:
                    # No overlap, so add the current interval to the list and start a new one
                    merged_intervals.append(current_interval)
                    current_interval = interval
            elif interval['start_time']:
                # No overlap, so add the current interval to the list and start a new one
                merged_intervals.append(current_interval)
                current_interval = interval

        # Don't forget to add the last interval
        if current_interval:
            merged_intervals.append(current_interval)


        # Calculate the total time
        total_time = timedelta()
        for interval in merged_intervals:
            if interval['start_time'] and interval['end_time']:
                total_time += interval['end_time'] - interval['start_time']
   


        total_time = total_time.total_seconds()
    else:
        total_time = 0                              

    toal_hours_to_show = max(32400, total_time)
    total_active_hours = total_time - total_idle_time 
    return {
        "total_time": total_time,
        "total_idle_time": total_idle_time,
        "total_call_data": total_call_data[0].total_duration,
        "total_meeting_data": total_meeting_data[0].total_duration,
        "total_active_hours": total_active_hours,
        "total_inactive_hours": (toal_hours_to_show or 0) - ((total_active_hours or 0) + (total_idle_time or 0)),
        "total_hours": toal_hours_to_show,
    }


@frappe.whitelist()
def get_applicationTimeChart_data(user=None, start_date=None, end_date=None):
    if not user or user == None:
        return {
            "labels": [],
            "values": []
        }
    application_name = frappe.db.sql(f"""
        SELECT 
            LEFT(application_name, 25) AS application_name, 
            ROUND(SUM(duration) / 3600, 2) AS total_duration
        FROM `tabApplication Usage log`
        WHERE employee = '{user}' AND date >= '{start_date}' AND date <= '{end_date}'
        GROUP BY LEFT(application_name, 25)
        ORDER BY total_duration DESC
        LIMIT 10
    """, as_dict=True)

    labels = []
    values = []

    for app in application_name:
        labels.append(app['application_name'])
        values.append(app['total_duration'])

    return {
        "labels": labels,
        "values": values
    }

@frappe.whitelist()
def get_callsTimeChart_data(user = None, start_date=None, end_date=None):
    if not user or user == None:
        return {
            "labels": [],
            "values": []
        }
    start_date_,end_date_ = set_dates(start_date, end_date)
    caller_name = frappe.db.sql(f"""
        SELECT COALESCE(contact, client, customer_no) AS identifier, 
               round(SUM(duration)/60,2) AS total_duration,
               COUNT(*) AS call_count
        FROM `tabEmployee Fincall`
        Where employee = '{user}' AND call_datetime >= '{start_date_}' AND call_datetime <= '{end_date_}'
        GROUP BY COALESCE(contact, client, customer_no)
        ORDER BY total_duration DESC
        LIMIT 10
    """, as_dict=True)

    labels = []
    values = []

    for app in caller_name:
        labels.append(app['identifier'])
        values.append(app['total_duration'])

    return {
        "labels": labels,
        "values": values
    }

@frappe.whitelist()
def get_intensityChart_data(user = None,start_date=None,end_date=None):
    if not user or user == None:
        return {
            "labels": [],
            "values": []
        }
    start_date_, end_date_ = set_dates(start_date, end_date)
    intensity_data = frappe.db.sql(f"""
        SELECT SUM(total_keystrokes) as total_keystrokes, 
               sum(total_mouse_clicks) as total_mouse_clicks, 
               HOUR(date_time) as hour, 
               FLOOR(MINUTE(date_time) / 15) * 15 as minute_interval, 
               WEEKDAY(DATE(date_time)) as weekday
        FROM `tabWork Intensity`
        WHERE employee = '{user}' 
              AND date_time >= '{start_date_}' 
              AND date_time <= '{end_date_}'
              AND hour(date_time) between 7 and 23
        GROUP BY weekday, hour, minute_interval
    """, as_dict=True)
    
    labels = [[] for _ in range(7)]
    values = [[] for _ in range(7)]

    for entry in intensity_data:
        weekday = entry['weekday']
        hour = entry['hour']
        minute_interval = entry['minute_interval']
        keystrokes = entry['total_keystrokes']
        mouse_clicks = entry['total_mouse_clicks']
        label = f"{hour:02}:{minute_interval:02}"
        value = keystrokes + mouse_clicks
        
        labels[weekday].append(label)
        values[weekday].append(value)

    for weekday in range(7):
        for hour in range(7, 24):
            for minute_interval in range(0, 60, 15):
                label = f"{hour:02}:{minute_interval:02}"
                if label not in labels[weekday]:
                    labels[weekday].append(label)
                    values[weekday].append(0)

    for i in range(7):
        combined = sorted(zip(labels[i], values[i]))
        labels[i], values[i] = zip(*combined)
    return {
        "labels": labels,
        "values": values,
    }
@frappe.whitelist()
def get_callsTypeChart_data(user = None,start_date=None,end_date=None):
    if not user or user == None:
        return {
            "labels": [],
            "values": []
        }
    start_date_,end_date_ = set_dates(start_date, end_date)
    internal_fincall_data = frappe.db.sql(f"""
        SELECT 
            COUNT(*) AS fincall_count,
            round(SUM(duration)/60,2) as total_duration
        FROM `tabEmployee Fincall`
        Where employee = '{user}' and call_datetime >= '{start_date_}' and call_datetime <= '{end_date_}' and (link_to = 'Company' and link_to is not null)
    """, as_dict=True)

    external_fincall_data = frappe.db.sql(f"""
        SELECT 
            COUNT(*) AS fincall_count,
            round(SUM(duration)/60,2) as total_duration
        FROM `tabEmployee Fincall`
        Where employee = '{user}' and call_datetime >= '{start_date_}' and call_datetime <= '{end_date_}' and (link_to != 'Company' or link_to is null)
    """, as_dict=True)

    return{
        "labels":["Internal","External"],
        "values":[internal_fincall_data[0].fincall_count, external_fincall_data[0].fincall_count],
        "time":[(internal_fincall_data[0].total_duration or 0), (external_fincall_data[0].total_duration or 0)]
    }

@frappe.whitelist()
def get_domainTimeChart_data(user = None,start_date=None,end_date=None):
    if not user or user == None:
        return {
            "labels": [],
            "values": []
        }
    start_date_,end_date_ = set_dates(start_date, end_date)
    domain_data = frappe.db.sql(f"""
        SELECT domain, round(SUM(duration)/60,2) as total_duration
        FROM `tabURL Access Log`
        Where employee = '{user}' and from_time >= '{start_date_}' and to_time <= '{end_date_}' and domain != '' and domain is not null
        GROUP BY domain
        ORDER BY total_duration DESC
        LIMIT 10
    """, as_dict=True)

    labels = []
    values = []

    for app in domain_data:
        labels.append(app['domain'])
        values.append(app['total_duration'])

    return {
        "labels": labels,
        "values": values
    }
    
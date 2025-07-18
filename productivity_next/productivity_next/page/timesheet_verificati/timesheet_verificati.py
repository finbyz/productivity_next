import frappe
from frappe.utils import time_diff_in_seconds, flt
from datetime import datetime
from datetime import timedelta
from frappe.utils import today

def get_employee_and_date():
    employee = frappe.form_dict.get('employee')
    date = frappe.form_dict.get('date')
    if not date:
        date = frappe.utils.today()
    return employee, date

def secs_to_hhmm(secs):
    if not secs or secs <= 0:
        return "00:00"
    mins = int(secs // 60)
    hours = mins // 60
    mins = mins % 60
    return f"{hours:02d}:{mins:02d}"

@frappe.whitelist()
def get_summary_data():
    employee, date = get_employee_and_date()
    # Calls
    calls = frappe.db.get_all(
        'Employee Fincall',
        filters={
            'employee': employee,
            'date': date,
            'calltype': ["not in", ["Missed", "Rejected"]]
        },
        fields=['calltype', 'duration']
    )
    incoming = [c for c in calls if c['calltype'] == 'Incoming']
    outgoing = [c for c in calls if c['calltype'] == 'Outgoing']
    def sum_duration(lst):
        return sum([flt(c['duration'] or 0) for c in lst])
    incoming_dur = sum_duration(incoming)
    outgoing_dur = sum_duration(outgoing)
    total_dur = sum_duration(calls)
    # Meetings (use same SQL as details, include project)
    meetings = frappe.db.sql('''
        SELECT m.project, m.internal_meeting, m.meeting_from, m.meeting_to,
               TIMESTAMPDIFF(SECOND, m.meeting_from, m.meeting_to) as duration
        FROM `tabMeeting` m
        JOIN `tabMeeting Company Representative` mcr ON m.name = mcr.parent
        WHERE mcr.employee = %s AND m.docstatus = 1
          AND m.meeting_from >= %s AND m.meeting_to <= %s
    ''', (employee, f"{date} 00:00:00", f"{date} 23:59:59"), as_dict=True)
    internal = [m for m in meetings if m['internal_meeting']]
    external = [m for m in meetings if not m['internal_meeting']]
    def meeting_secs(lst):
        return sum([
            m['duration'] or 0
            for m in lst if m['meeting_from'] and m['meeting_to']
        ])
    internal_dur = meeting_secs(internal)
    external_dur = meeting_secs(external)
    total_meet = meeting_secs(meetings)
    # System Usage (segregate App/Web by url is null or not)
    total_web_data = frappe.db.sql(f'''
        SELECT sum(duration) as total_web_duration, count(*) as total_web_count
        FROM `tabApplication Usage log`
        WHERE date = '{date}' and employee = '{employee}' and url is not null
    ''', as_dict=True)[0]
    total_app_data = frappe.db.sql(f'''
        SELECT sum(duration) as total_app_duration, count(*) as total_app_count
        FROM `tabApplication Usage log`
        WHERE date = '{date}' and employee = '{employee}' and url is null
    ''', as_dict=True)[0]
    app_dur = flt(total_app_data["total_app_duration"] or 0)
    app_count = total_app_data["total_app_count"]
    web_dur = flt(total_web_data["total_web_duration"] or 0)
    web_count = total_web_data["total_web_count"]
    total_sys = app_dur + web_dur
    return {
        "calls": {
            "incoming": {"duration": secs_to_hhmm(incoming_dur), "count": len(incoming)},
            "outgoing": {"duration": secs_to_hhmm(outgoing_dur), "count": len(outgoing)},
            "total": secs_to_hhmm(total_dur)
        },
        "meetings": {
            "internal": {"duration": secs_to_hhmm(internal_dur), "count": len(internal)},
            "external": {"duration": secs_to_hhmm(external_dur), "count": len(external)},
            "total": secs_to_hhmm(total_meet)
        },
        "system": {
            "app": {"duration": secs_to_hhmm(app_dur), "count": app_count},
            "web": {"duration": secs_to_hhmm(web_dur), "count": web_count},
            "total": secs_to_hhmm(total_sys)
        }
    }

@frappe.whitelist()
def get_calls_details():
    employee, date = get_employee_and_date()
    calls = frappe.db.get_all(
        'Employee Fincall',
        filters={
            'employee': employee,
            'date': date,
            'calltype': ["not in", ["Missed", "Rejected"]]
        },
        fields=['name', 'client', 'duration', 'project', 'call_datetime', 'contact', 'link_name', 'calltype', 'customer_no']
    )
    details = [
        {
            'name': c['name'],
            'client': c['client'],
            'customer_no': c['customer_no'],
            'duration': secs_to_hhmm(flt(c['duration'])),
            'project': c['project'],
            'call_datetime': c['call_datetime'],
            'contact': c['contact'],
            'link_name': c['link_name'],
            'calltype': c['calltype']
        } for c in calls
    ]
    # Project-wise summary
    project_map = {}
    for c in calls:
        p = c['project'] or 'No Project'
        secs = flt(c['duration'])
        project_map.setdefault(p, 0)
        project_map[p] += secs
    project_summary = [
        {'project': p, 'total_time': secs_to_hhmm(secs)}
        for p, secs in project_map.items()
    ]
    return {
        'details': details,
        'project_summary': project_summary
    }

@frappe.whitelist()
def bulk_set_call_projects(call_projects):
    """
    call_projects: list of dicts {name: call_id, project: project_name}
    """
    import json
    call_projects = json.loads(call_projects) if isinstance(call_projects, str) else call_projects
    for row in call_projects:
        if row.get('project'):
            frappe.db.set_value("Employee Fincall", row['name'], "project", row['project'])
    frappe.db.commit()
    return True

@frappe.whitelist()
def set_call_project(call_id, project):
    frappe.db.set_value("Employee Fincall", call_id, "project", project)
    frappe.db.commit()

@frappe.whitelist()
def get_meetings_details():
    employee, date = get_employee_and_date()
    # Return project, discussion, arranged_by, company_representative, party_representative, duration
    meetings = frappe.db.sql('''
        SELECT m.project, m.discussion, m.meeting_arranged_by as arranged_by, 
               m.name as meeting_name, m.meeting_from, m.meeting_to, m.internal_meeting,
               TIMESTAMPDIFF(SECOND, m.meeting_from, m.meeting_to) as duration
        FROM `tabMeeting` m
        JOIN `tabMeeting Company Representative` mcr ON m.name = mcr.parent
        WHERE mcr.employee = %s AND m.docstatus = 1
          AND m.meeting_from >= %s AND m.meeting_to <= %s
    ''', (employee, f"{date} 00:00:00", f"{date} 23:59:59"), as_dict=True)
    for m in meetings:
        # Company reps (all employee_name from child table)
        company_reps = frappe.db.get_all(
            "Meeting Company Representative",
            filters={"parent": m["meeting_name"]},
            fields=["employee_name"]
        )
        m["company_representative"] = ", ".join([cr["employee_name"] for cr in company_reps if cr["employee_name"]])
        # Party reps (all contact from child table)
        party_reps = frappe.db.get_all(
            "Meeting Party Representative",
            filters={"parent": m["meeting_name"]},
            fields=["contact"]
        )
        m["party_representative"] = ", ".join([pr["contact"] for pr in party_reps if pr["contact"]])
        m['duration'] = secs_to_hhmm(m['duration']) if m['duration'] else "00:00"
    # Group by project for table summary
    project_map = {}
    for m in meetings:
        p = m['project'] or 'No Project'
        secs = m['duration']
        if isinstance(secs, str):
            # convert back to seconds for sum
            h, mi = [int(x) for x in secs.split(":")] if ":" in secs else (0, 0)
            secs = h * 3600 + mi * 60
        project_map.setdefault(p, 0)
        project_map[p] += secs
    project_summary = [
        {'project': p, 'total_time': secs_to_hhmm(secs)}
        for p, secs in project_map.items()
    ]
    return {
        'details': meetings,
        'project_summary': project_summary
    }
@frappe.whitelist()
def get_system_details():
    employee, date = get_employee_and_date()
    logs = frappe.db.get_all(
        'Application Usage log',
        filters={
            'date': date,
            'employee': employee
        },
        fields=['project', 'from_time', 'to_time']
    )
    project_map = {}
    for l in logs:
        if not l['project']:
            continue
        secs = time_diff_in_seconds(l['to_time'], l['from_time']) if l['from_time'] and l['to_time'] else 0
        project_map.setdefault(l['project'], 0)
        project_map[l['project']] += secs
    return [
        {'project': p, 'total_time': secs_to_hhmm(secs)}
        for p, secs in project_map.items()
    ]

@frappe.whitelist()
def preview_timesheet():
    employee, date = get_employee_and_date()
    # Find the draft or submitted timesheet created by productify for this employee and date
    timesheets = frappe.get_list(
        "Timesheet",
        filters={
            "employee": employee,
            "is_created_by_productify": 1,
            "start_date": date,
            "docstatus": ["in",[0,1]]
        },
        fields=["name", "docstatus"],
        limit=1
    )
    if not timesheets:
        return {"logs": [], "total_hours": 0, "project_summary": [], "docstatus": None, "timesheet_name": None}
    ts = frappe.get_doc("Timesheet", timesheets[0]["name"])
    logs = []
    total_hours = 0
    project_map = {}
    for row in ts.time_logs:
        logs.append({
            "activity_type": row.activity_type,
            "task": row.task,
            "project": row.project,
            "issue": row.issue,
            "hours": row.hours,
            "from_time": row.from_time,
            "to_time": row.to_time,
            "description": row.description
        })
        total_hours += row.hours or 0
        p = row.project or "No Project"
        project_map.setdefault(p, 0)
        project_map[p] += row.hours or 0
    project_summary = [
        {"project": p, "total_hours": round(h, 2)}
        for p, h in project_map.items()
    ]
    return {
        "logs": logs,
        "total_hours": round(total_hours, 2),
        "project_summary": project_summary,
        "docstatus": ts.docstatus,
        "timesheet_name": ts.name
    }

def get_employee_meetings(employee, date):
    data = frappe.db.sql(f"""
        SELECT m.name as meeting, m.meeting_from as from_time, m.meeting_to as to_time, 
           m.internal_meeting, m.project, m.task, m.meeting_arranged_by,
           mcr.employee as company_rep_employee, mcr.employee_name as company_rep_name,
            mpr.contact as party_rep_contact
        FROM `tabMeeting` as m
        LEFT JOIN `tabMeeting Company Representative` as mcr ON m.name = mcr.parent
        LEFT JOIN `tabMeeting Party Representative` as mpr ON m.name = mpr.parent
        WHERE mcr.employee = '{employee}' and m.docstatus = 1 and m.meeting_from >= '{date} 00:00:00' and m.meeting_to <= '{date} 23:59:59'
        """, as_dict=True)
    return data

@frappe.whitelist()
def create_timesheet_for_employee_date():
    employee, date = get_employee_and_date()
    # Get application logs for this employee and date
    applications = frappe.get_all(
        "Application Usage log",
        fields=["employee","from_time","to_time","task","issue","project"],
        filters={
            "employee": employee,
            "date": ["between", [date, date]],
        }
    )
    # Get call logs for this employee and date
    calls = frappe.get_all(
        "Employee Fincall",
        fields=["name as call_id","employee","call_datetime as from_time","ADDTIME(call_datetime, SEC_TO_TIME(duration)) as to_time", "issue", "task", "project"],
        filters={
            "employee": employee,
            "call_datetime": ["between", [f"{date} 00:00:00", f"{date} 23:59:59"]],
        }
    )
    # Get meeting logs for this employee and date
    meetings = get_employee_meetings(employee, date)
    # Group and merge logs for this employee
    merged_logs = {}
    applications = group_logs_by_employee(applications)
    calls = group_logs_by_employee(calls)
    merged_logs[employee] = merge_logs(applications.get(employee, []))
    merged_logs[employee] = merge_logs(merged_logs.get(employee, []) + calls.get(employee, []))
    merged_logs[employee] = split_logs(merged_logs.get(employee, []), meetings)
    merged_logs[employee] = split_logs(merged_logs.get(employee, []), calls.get(employee, []))
    # Create or update timesheet for this employee and date
    existing_timesheets = frappe.get_list(
        "Timesheet",
        filters={
            "employee": employee,
            "status": "Draft",
            "is_created_by_productify": 1,
            "start_date": date,
        },
        fields=["name"],
        limit=1
    )
    if existing_timesheets:
        timesheet = frappe.get_doc("Timesheet", existing_timesheets[0]["name"])
        timesheet.time_logs = []
    else:
        timesheet = frappe.new_doc("Timesheet")
        timesheet.employee = employee
    timesheet.is_created_by_productify = True
    timesheet.start_date = date
    employee_merged_logs = merged_logs.get(employee, [])
    if not employee_merged_logs:
        return {"success": False, "message": "No logs found for this employee and date."}
    for log in employee_merged_logs:
        log["to_time"] = log["to_time"] - timedelta(seconds=1)
        seconds = (log["to_time"] - log["from_time"]).total_seconds()
        hours = seconds / 3600
        if seconds <= 0:
            continue
        activity_type = ""
        if log.get("meeting"):
            activity_type = "Meeting"
        elif log.get("issue"):
            activity_type = "Issue"
        elif log.get("task"):
            activity_type = "Task"
        elif log.get("project"):
            activity_type = "Project"
        elif log.get("call_id"):
            activity_type = "Call"
        description = get_activity_description(log)
        timesheet.append("time_logs", {
            "activity_type": activity_type,
            "task": log.get("task"),
            "project": log.get("project"),
            "issue": log.get("issue"),
            "hours": hours,
            "from_time": log["from_time"],
            "to_time": log["to_time"],
            "description": description
        })
    try:
        if timesheet.time_logs:
            timesheet.save()
            return {"success": True, "timesheet": timesheet.name}
        else:
            return {"success": False, "message": "No logs found for this employee and date."}
    except Exception as e:
        frappe.log_error(f"Failed to create timesheet for {employee}",e)
        return {"success": False, "message": str(e)}


def group_logs_by_employee(logs):
    employee_logs = {}
    for log in logs:
        employee = log.get("employee")
        if employee not in employee_logs:
            employee_logs[employee] = []
        employee_logs[employee].append(log)
    return employee_logs


def merge_logs(logs):
    logs.sort(key=lambda x: x["from_time"])
    
    merged_logs = []
    
    for log in logs:
        if not merged_logs:
            merged_logs.append(log)
            continue
        
        last_log = merged_logs[-1]
        time_gap = (log["from_time"] - last_log["to_time"]).total_seconds()
        
        priority_keys = ["task", "issue", "project"]
        
        key_changed = any(
            log.get(key) and log[key] != last_log.get(key)
            for key in priority_keys
        )
        
        both_none = all(log.get(key) is None and last_log.get(key) is None for key in priority_keys)
        
        if time_gap <= 10 and not key_changed and (both_none or any(log.get(key) == last_log.get(key) for key in priority_keys)):
            last_log["to_time"] = max(last_log["to_time"], log["to_time"])
        
        elif log["from_time"] <= last_log["to_time"]:
            if log["to_time"] <= last_log["to_time"]:
                continue
            if log["from_time"] < last_log["to_time"]:
                last_log["to_time"] = log["from_time"]
            
            merged_logs.append(log)        
        else:
            log["from_time"] = max(log["from_time"], last_log["to_time"] + timedelta(seconds=1))
            merged_logs.append(log)
    
    return merged_logs

def split_logs(merged_logs, new_logs):
    updated_logs = []
    i, j = 0, 0

    while i < len(merged_logs) or j < len(new_logs):
        if j >= len(new_logs): 
            updated_logs.append(merged_logs[i])
            i += 1
            continue

        if i >= len(merged_logs): 
            updated_logs.append(new_logs[j])
            j += 1
            continue

        old_log = merged_logs[i]
        new_log = new_logs[j]

        if new_log["to_time"] <= old_log["from_time"]:
            updated_logs.append(new_log)
            j += 1
        elif new_log["from_time"] >= old_log["to_time"]:
            updated_logs.append(old_log)
            i += 1
        else:
            if old_log["from_time"] < new_log["from_time"]:
                updated_logs.append({
                    **old_log,
                    "to_time": new_log["from_time"]
                })
            updated_logs.append(new_log)
            j += 1
            
            if old_log["to_time"] > new_log["to_time"]:
                merged_logs[i]["from_time"] = new_log["to_time"]
            else:
                i += 1
    for k in range(1, len(updated_logs)):
        if updated_logs[k]["from_time"] < updated_logs[k - 1]["to_time"]:
            updated_logs[k]["from_time"] = updated_logs[k - 1]["to_time"]
    return updated_logs

def get_activity_description(activity):
    """Generate description using Task and Issue subject lines."""
    description_parts = []

    if activity.get('task'):
        task_subject = frappe.db.get_value("Task", activity['task'], "subject") or ""
        if task_subject:
            description_parts.append(f"Task - {task_subject}")

    if activity.get('issue'):
        issue_subject = frappe.db.get_value("Issue", activity['issue'], "subject") or ""
        if issue_subject:
            description_parts.append(f"Issue - {issue_subject}")

    return "\n".join(description_parts)

@frappe.whitelist()
def submit_timesheet(name):
    doc = frappe.get_doc("Timesheet", name)
    doc.submit()
    return {"success": True}
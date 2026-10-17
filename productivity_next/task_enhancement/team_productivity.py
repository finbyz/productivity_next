"""Team task totals and range-based activity for the signed-in reporting manager."""

import hashlib
import json
from collections import defaultdict
from datetime import datetime, time, timedelta

import frappe
from frappe.utils import get_datetime, nowdate


CACHE_SECONDS = 15 * 60
TEAM_CACHE_SECONDS = 2 * 60 * 60
CACHE_PREFIX = "productivity_next:team_productivity:v6"


def _date_range(from_date, to_date):
	try:
		start = datetime.strptime(str(from_date), "%Y-%m-%d").date()
		end = datetime.strptime(str(to_date), "%Y-%m-%d").date()
	except (TypeError, ValueError):
		frappe.throw("From Date and To Date must be valid YYYY-MM-DD dates.", frappe.ValidationError)
	if start > end:
		frappe.throw("From Date cannot be after To Date.", frappe.ValidationError)
	return start, end


def _manager_team():
	user = frappe.session.user
	if user == "Guest":
		frappe.throw("Login required", frappe.PermissionError)
	cache = frappe.cache()
	key = f"{CACHE_PREFIX}:team:{hashlib.sha256(user.encode()).hexdigest()}"
	team = cache.get_value(key)
	if team is not None:
		return team
	managers = frappe.get_all(
		"Employee", filters={"user_id": user, "status": "Active"}, pluck="name"
	)
	team = frappe.get_all(
		"Employee",
		filters={"reports_to": ["in", managers], "status": "Active", "user_id": ["is", "set"]},
		fields=["name", "employee_name", "user_id"],
		limit_page_length=0,
	) if managers else []
	cache.set_value(key, team, expires_in_sec=TEAM_CACHE_SECONDS)
	return team


def _task_counts(team, start, end):
	"""Count the same tasks returned by api.get_tasks for each team member."""
	users = sorted({row.user_id for row in team if row.user_id})
	counts = defaultdict(lambda: {"total": 0, "completed": 0, "pending": 0, "overdue": 0, "task_types": {}})
	if not users:
		return counts

	# Each user appears once, so a task assigned to several team members is
	# counted once for each member, exactly as separate get_tasks calls would.
	team_users = " UNION ALL ".join("SELECT %s AS user_id" for _ in users)
	today = datetime.strptime(nowdate(), "%Y-%m-%d").date()
	rows = frappe.db.sql(
		f"""
		SELECT team.user_id AS assignee, task.`type`, COUNT(*) AS total,
			SUM(task.status = 'Completed') AS completed,
			SUM(task.status != 'Completed'
				AND (task.status = 'Overdue' OR task.exp_end_date < %s)) AS overdue
		FROM ({team_users}) AS team
		JOIN `tabTask` AS task ON (
			(task.status NOT IN ('Unplanned', 'Template', 'Cancelled', 'Completed')
				AND task.exp_start_date <= %s
				AND (task._assign LIKE CONCAT('%%"', team.user_id, '"%%')
					OR task.assignee = team.user_id))
			OR (task.status = 'Completed'
				AND task.completed_on BETWEEN %s AND %s
				AND task.completed_by = team.user_id)
		)
		GROUP BY team.user_id, task.`type`
		""",
		(today, *users, end, start, end),
		as_dict=True,
	)
	for row in rows:
		count = int(row.total)
		completed = int(row.completed or 0)
		overdue = int(row.overdue or 0)
		item = counts[row.assignee]
		item["total"] += count
		task_type = row.type or "Unspecified"
		item["task_types"][task_type] = item["task_types"].get(task_type, 0) + count
		item["completed"] += completed
		item["overdue"] += overdue
		item["pending"] += count - completed - overdue
	return counts


def _merge_intervals(intervals):
	merged = []
	for start, end in sorted(intervals):
		if end <= start:
			continue
		if merged and start <= merged[-1][1]:
			merged[-1] = (merged[-1][0], max(merged[-1][1], end))
		else:
			merged.append((start, end))
	return merged


def _seconds(intervals):
	return sum((end - start).total_seconds() for start, end in intervals)


def _overlap_seconds(left, right):
	total = 0
	i = j = 0
	while i < len(left) and j < len(right):
		start = max(left[i][0], right[j][0])
		end = min(left[i][1], right[j][1])
		if end > start:
			total += (end - start).total_seconds()
		if left[i][1] < right[j][1]:
			i += 1
		else:
			j += 1
	return total


def _activity_times(team, start, end):
	employees = [row.name for row in team]
	placeholders = ", ".join(["%s"] * len(employees))
	start_at = datetime.combine(start, time.min)
	end_at = datetime.combine(end + timedelta(days=1), time.min)
	# A log starting just before midnight can overlap the selected first day.
	lookup_start = start - timedelta(days=1)
	queries = (
		("activity", f"""
			SELECT employee, from_time AS start_time, to_time AS end_time
			FROM `tabApplication Usage log`
			WHERE employee IN ({placeholders}) AND `date` BETWEEN %s AND %s
		""", (*employees, lookup_start, end)),
		("activity", f"""
			SELECT employee, call_datetime AS start_time,
				ADDTIME(call_datetime, SEC_TO_TIME(duration)) AS end_time
			FROM `tabEmployee Fincall`
			WHERE employee IN ({placeholders}) AND `date` BETWEEN %s AND %s
				AND calltype NOT IN ('Missed', 'Rejected')
		""", (*employees, lookup_start, end)),
		("activity", f"""
			SELECT mcr.employee, m.meeting_from AS start_time, m.meeting_to AS end_time
			FROM `tabMeeting` m
			JOIN `tabMeeting Company Representative` mcr ON mcr.parent = m.name
			WHERE mcr.employee IN ({placeholders}) AND m.docstatus = 1
				AND m.meeting_from < %s AND m.meeting_to > %s
		""", (*employees, end_at, start_at)),
		("idle", f"""
			SELECT employee, from_time AS start_time, to_time AS end_time
			FROM `tabEmployee Idle Time`
			WHERE employee IN ({placeholders}) AND `date` BETWEEN %s AND %s
		""", (*employees, lookup_start, end)),
	)
	activity = defaultdict(list)
	protected = defaultdict(list)
	idle = defaultdict(list)
	for index, (kind, query, params) in enumerate(queries):
		for row in frappe.db.sql(query, params, as_dict=True):
			if not row.start_time or not row.end_time:
				continue
			interval = (max(get_datetime(row.start_time), start_at), min(get_datetime(row.end_time), end_at))
			if interval[1] <= interval[0]:
				continue
			if kind == "idle":
				idle[row.employee].append(interval)
			else:
				activity[row.employee].append(interval)
				if index in (1, 2):
					protected[row.employee].append(interval)
	result = {}
	for employee in employees:
		active_intervals = _merge_intervals(activity[employee])
		idle_intervals = _merge_intervals(idle[employee])
		protected_intervals = _merge_intervals(protected[employee])
		total = _seconds(active_intervals)
		idle_seconds = max(0, _overlap_seconds(idle_intervals, active_intervals) - _overlap_seconds(idle_intervals, protected_intervals))
		idle_seconds = min(total, idle_seconds)
		result[employee] = {
			"active_seconds": round(total - idle_seconds),
			"idle_seconds": round(idle_seconds),
			"progress_percent": round(100 * (total - idle_seconds) / total, 1) if total else 0,
		}
	return result



def _cache_key(team, start, end):
	payload = json.dumps(
		{
			"manager": frappe.session.user,
			"team": sorted((row.name, row.user_id, row.employee_name) for row in team),
			"from_date": start.isoformat(),
			"to_date": end.isoformat(),
		},
		separators=(",", ":"),
	)
	return f"{CACHE_PREFIX}:{hashlib.sha256(payload.encode()).hexdigest()}"


def _build_rows(team, start, end):
	counts = _task_counts(team, start, end)
	activity = _activity_times(team, start, end)
	return [
		{
			"employee": row.name,
			"employee_name": row.employee_name,
			**counts[row.user_id],
			**activity[row.name],
		}
		for row in team
	]


@frappe.whitelist(methods=["GET"])
def get_team_productivity(from_date, to_date):
	"""Return direct reports' task totals and activity for the selected range."""
	start, end = _date_range(from_date, to_date)
	team = _manager_team()
	if not team:
		return {"is_team": False, "rows": []}
	key = _cache_key(team, start, end)
	cache = frappe.cache()
	rows = cache.get_value(key)
	if rows is None:
		rows = _build_rows(team, start, end)
		cache.set_value(key, rows, expires_in_sec=CACHE_SECONDS)
	return {"is_team": True, "rows": rows}

"""Track active Task.assignee values and alert managers when an employee has no tasks."""

import hashlib
import pickle
from collections import defaultdict
from uuid import uuid4

import frappe
from frappe.utils import escape_html, nowdate


TERMINAL_STATUSES = ("Completed", "Cancelled", "Closed")
PREFIX = "productivity_next:employee_active_tasks"
EMPLOYEES_KEY = f"{PREFIX}:employees"
OWNERS_KEY = f"{PREFIX}:task_owners"
READY_KEY = f"{PREFIX}:ready"
LOCK_KEY = f"{PREFIX}:lock"
PENDING_KEY = f"{PREFIX}:pending_notifications"
MORNING_PENDING_KEY = f"{PREFIX}:pending_morning_notifications"


def _task_key(employee):
	return f"{PREFIX}:employee:{employee}"


def _decoded(values):
	return {value.decode() if isinstance(value, bytes) else value for value in values}


def _employees():
	return frappe.get_all(
		"Employee",
		filters={"status": "Active", "user_id": ["is", "set"]},
		fields=["name", "employee_name", "user_id", "reports_to"],
		limit_page_length=0,
		order_by="",
	)


def _active_tasks():
	# This feature deliberately uses Task.assignee only, never ToDo assignments.
	return frappe.get_all(
		"Task",
		filters={"assignee": ["is", "set"], "status": ["not in", TERMINAL_STATUSES]},
		fields=["name", "assignee"],
		limit_page_length=0,
		order_by="",
	)


def _lock(cache):
	return cache.lock(cache.make_key(LOCK_KEY), timeout=600, blocking_timeout=120)


def warm_active_task_cache(notify=False):
	"""Rebuild every employee set from the database; the 06:00 job also alerts managers."""
	cache = frappe.cache()
	with _lock(cache):
		employees = _employees()
		user_to_employees = defaultdict(list)
		for employee in employees:
			user_to_employees[employee.user_id].append(employee.name)

		tasks_by_employee = defaultdict(set)
		owners = {}
		for task in _active_tasks():
			assigned_employees = tuple(user_to_employees.get(task.assignee, ()))
			for employee in assigned_employees:
				tasks_by_employee[employee].add(task.name)
			if assigned_employees:
				owners[task.name] = assigned_employees

		old_employees = _decoded(cache.smembers(EMPLOYEES_KEY))
		pipe = cache.pipeline(transaction=True)
		pipe.delete(cache.make_key(READY_KEY), cache.make_key(EMPLOYEES_KEY), cache.make_key(OWNERS_KEY))
		for employee in old_employees | {row.name for row in employees}:
			pipe.delete(cache.make_key(_task_key(employee)))
		if employees:
			pipe.sadd(cache.make_key(EMPLOYEES_KEY), *(row.name for row in employees))
		for employee, task_names in tasks_by_employee.items():
			pipe.sadd(cache.make_key(_task_key(employee)), *task_names)
		for task_name, assigned_employees in owners.items():
			pipe.hset(cache.make_key(OWNERS_KEY), task_name, pickle.dumps(assigned_employees))
		pipe.execute()
		cache.set_value(READY_KEY, True)
		zero_employees = [row for row in employees if not tasks_by_employee[row.name]]

	if notify:
		_notify_morning(zero_employees)
	return len(zero_employees)


def morning_warmup_and_notify():
	"""Registered at 06:00 in hooks.py (site timezone)."""
	warm_active_task_cache(notify=True)


def queue_task_sync(doc, method=None):
	"""on_change covers ordinary saves and Document.db_set updates."""
	if method != "after_delete" and not (
		doc.has_value_changed("assignee") or doc.has_value_changed("status")
	):
		return
	frappe.enqueue(sync_task, task_name=doc.name, queue="short", enqueue_after_commit=True)


def queue_employee_refresh(doc, method=None):
	if method != "after_delete" and not any(
		doc.has_value_changed(field) for field in ("user_id", "status", "reports_to")
	):
		return
	frappe.enqueue(warm_active_task_cache, queue="default", enqueue_after_commit=True)


def sync_task(task_name):
	"""Read the committed Task, then move its ID between employee sets exactly once."""
	cache = frappe.cache()
	if not cache.get_value(READY_KEY):
		# Redis may have been cleared after migration or the 06:00 warmup.
		# Rebuild outside the sync lock because warm_active_task_cache takes it.
		warm_active_task_cache(notify=False)
	zero_employees = []
	with _lock(cache):
		if not cache.get_value(READY_KEY):
			return
		old_employees = set(cache.hget(OWNERS_KEY, task_name) or ())
		task = frappe.db.get_value("Task", task_name, ["assignee", "status"], as_dict=True)
		new_employees = set()
		if task and task.assignee and task.status not in TERMINAL_STATUSES:
			new_employees = set(
				frappe.get_all(
					"Employee", filters={"user_id": task.assignee, "status": "Active"}, pluck="name"
				)
			)

		if old_employees == new_employees:
			return
		for employee in old_employees - new_employees:
			cache.srem(_task_key(employee), task_name)
			if not cache.scard(cache.make_key(_task_key(employee))):
				zero_employees.append(employee)
		for employee in new_employees - old_employees:
			cache.sadd(_task_key(employee), task_name)
		if new_employees:
			cache.hset(OWNERS_KEY, task_name, tuple(sorted(new_employees)))
		else:
			cache.hdel(OWNERS_KEY, task_name)
		# Redis counters can reset while old Notification Logs remain in the database.
		# Give each transition a unique ID and keep it in pending for stable retries.
		events = {employee: uuid4().hex for employee in zero_employees}
		for employee, event_id in events.items():
			cache.hset(PENDING_KEY, employee, {"event_id": event_id, "date": nowdate()})

	for employee in events:
		_deliver_pending_notification(employee)


def retry_pending_notifications():
	"""Retry alerts whose cache update succeeded but Notification Log insert failed."""
	for employee in _decoded(frappe.cache().hgetall(PENDING_KEY)):
		frappe.enqueue(
			_deliver_pending_notification,
			employee=employee,
			queue="short",
			job_id=f"employee-zero-task-alert:{employee}",
			deduplicate=True,
		)
	for manager in _decoded(frappe.cache().hgetall(MORNING_PENDING_KEY)):
		frappe.enqueue(
			_deliver_pending_morning_notification,
			manager=manager,
			queue="short",
			job_id=f"employee-morning-zero-task-alert:{manager}",
			deduplicate=True,
		)


def _deliver_pending_notification(employee):
	pending = frappe.cache().hget(PENDING_KEY, employee)
	if not pending:
		return
	_notify_transition(employee, pending.get("event_id", pending.get("episode")), pending["date"])
	# Clear only after the Notification Log transaction commits. If it rolls back,
	# the pending item remains for the retry job.
	frappe.db.after_commit.add(lambda: _clear_pending_notification(employee, pending))


def _clear_pending_notification(employee, expected):
	cache = frappe.cache()
	with _lock(cache):
		# hget can return a stale request-local value after another worker writes
		# a newer episode. hgetall reads the current Redis hash.
		pending = cache.hgetall(PENDING_KEY)
		if (pending.get(employee) or pending.get(employee.encode())) == expected:
			cache.hdel(PENDING_KEY, employee)


def _deliver_pending_morning_notification(manager):
	pending = frappe.cache().hget(MORNING_PENDING_KEY, manager)
	if not pending:
		return
	manager_user = _active_manager_user(manager)
	if manager_user:
		_create_notification(
			_notification_name("morning", manager, on_date=pending["date"]),
			manager_user,
			pending["subject"],
		)
	frappe.db.after_commit.add(
		lambda: _clear_pending_morning_notification(manager, pending)
	)


def _clear_pending_morning_notification(manager, expected):
	cache = frappe.cache()
	with _lock(cache):
		pending = cache.hgetall(MORNING_PENDING_KEY)
		if (pending.get(manager) or pending.get(manager.encode())) == expected:
			cache.hdel(MORNING_PENDING_KEY, manager)


def _still_without_tasks(users):
	if not users:
		return set()
	busy = set(
		frappe.get_all(
			"Task",
			filters={"assignee": ["in", list(users)], "status": ["not in", TERMINAL_STATUSES]},
			pluck="assignee",
			group_by="assignee",
			limit_page_length=0,
			order_by="",
		)
	)
	return set(users) - busy


def _notification_name(kind, *parts, on_date=None):
	payload = ":".join((PREFIX, kind, on_date or nowdate(), *(str(part) for part in parts)))
	return "PNT-" + hashlib.sha256(payload.encode()).hexdigest()[:32]


def _create_notification(name, user, subject, employee=None):
	if frappe.db.exists("Notification Log", name):
		return
	values = {
		"doctype": "Notification Log",
		"name": name,
		"for_user": user,
		"type": "Alert",
		"subject": subject,
		"from_user": "Administrator",
	}
	if employee:
		values.update(document_type="Employee", document_name=employee)
	try:
		frappe.get_doc(values).insert(ignore_permissions=True, set_name=name)
	except frappe.DuplicateEntryError:
		# A retry or concurrent worker already created the durable alert.
		pass


def _active_manager_user(manager):
	manager_employee = frappe.db.get_value(
		"Employee", manager, ["user_id", "status"], as_dict=True
	)
	if not manager_employee or manager_employee.status != "Active" or not manager_employee.user_id:
		return None
	if not frappe.db.get_value("User", manager_employee.user_id, "enabled"):
		return None
	return manager_employee.user_id


def _notify_morning(zero_employees):
	valid_users = _still_without_tasks({row.user_id for row in zero_employees})
	by_manager = defaultdict(list)
	for employee in zero_employees:
		if employee.user_id in valid_users and employee.reports_to:
			by_manager[employee.reports_to].append(employee)
	for manager, employees in by_manager.items():
		if not _active_manager_user(manager):
			continue
		names = ", ".join(escape_html(name) for name in sorted(row.employee_name or row.name for row in employees))
		frappe.cache().hset(
			MORNING_PENDING_KEY,
			manager,
			{"date": nowdate(), "subject": f"Employees with no active tasks: {names}"},
		)
		frappe.enqueue(
			_deliver_pending_morning_notification,
			manager=manager,
			queue="short",
			job_id=f"employee-morning-zero-task-alert:{manager}",
			deduplicate=True,
		)


def _notify_transition(employee_name, event_id, alert_date):
	employee = frappe.db.get_value(
		"Employee", employee_name, ["name", "employee_name", "user_id", "reports_to", "status"], as_dict=True
	)
	if not employee or employee.status != "Active" or not employee.user_id or not employee.reports_to:
		return
	if employee.user_id not in _still_without_tasks({employee.user_id}):
		return
	manager_user = _active_manager_user(employee.reports_to)
	if not manager_user:
		return
	_create_notification(
		_notification_name("transition", employee_name, event_id, on_date=alert_date),
		manager_user,
		f"{escape_html(employee.employee_name or employee.name)} has no active tasks",
		employee_name,
	)


@frappe.whitelist()
def get_team_task_status():
	"""Return cached Task IDs for the signed-in manager's direct reports only."""
	if frappe.session.user == "Guest":
		frappe.throw("Login required", frappe.PermissionError)
	cache = frappe.cache()
	if not cache.get_value(READY_KEY):
		warm_active_task_cache()
	manager_employees = frappe.get_all(
		"Employee", filters={"user_id": frappe.session.user, "status": "Active"}, pluck="name"
	)
	if not manager_employees:
		return []
	team = frappe.get_all(
		"Employee",
		filters={"reports_to": ["in", manager_employees], "status": "Active", "user_id": ["is", "set"]},
		fields=["name", "employee_name", "user_id"],
		limit_page_length=0,
	)
	return [
		{
			"employee": row.name,
			"employee_name": row.employee_name,
			"active_task_ids": sorted(_decoded(cache.smembers(_task_key(row.name)))),
		}
		for row in team
	]

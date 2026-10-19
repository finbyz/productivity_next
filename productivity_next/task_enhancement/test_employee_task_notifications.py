"""Behavioral tests for the employee Task.assignee cache."""

from collections import defaultdict
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
import pickle

from productivity_next.patches import warm_employee_task_cache
from productivity_next.task_enhancement import employee_task_notifications as alerts


class FakePipeline:
	def __init__(self, cache):
		self.cache = cache
		self.commands = []

	def __getattr__(self, command):
		def append(*args):
			self.commands.append((command, args))
			return self
		return append

	def execute(self):
		for command, args in self.commands:
			getattr(self.cache, command)(*args)


class FakeCache:
	def __init__(self):
		self.values = {}
		self.sets = defaultdict(set)
		self.hashes = defaultdict(dict)

	def make_key(self, key):
		return key

	def lock(self, *_args, **_kwargs):
		return nullcontext()

	def pipeline(self, **_kwargs):
		return FakePipeline(self)

	def get_value(self, key):
		return self.values.get(key)

	def set_value(self, key, value):
		self.values[key] = value

	def delete(self, *keys):
		for key in keys:
			self.values.pop(key, None)
			self.sets.pop(key, None)
			self.hashes.pop(key, None)

	def sadd(self, key, *values):
		self.sets[key].update(values)

	def srem(self, key, value):
		self.sets[key].discard(value)

	def smembers(self, key):
		return self.sets[key]

	def scard(self, key):
		return len(self.sets[key])

	def hset(self, key, field, value):
		self.hashes[key][field] = value

	def hget(self, key, field):
		value = self.hashes[key].get(field)
		return pickle.loads(value) if isinstance(value, bytes) else value

	def hgetall(self, key):
		return self.hashes[key].copy()

	def hdel(self, key, field):
		self.hashes[key].pop(field, None)

	def incr(self, key):
		self.values[key] = self.values.get(key, 0) + 1
		return self.values[key]


class TestEmployeeTaskNotifications(TestCase):
	def setUp(self):
		self.cache = FakeCache()
		self.employees = [
			SimpleNamespace(name="EMP-001", employee_name="Alice", user_id="alice@example.com", reports_to="MGR"),
			SimpleNamespace(name="EMP-002", employee_name="Bob", user_id="bob@example.com", reports_to="MGR"),
		]
		self.tasks = [SimpleNamespace(name="TASK-001", assignee="alice@example.com")]
		self.cache_patch = patch.object(alerts.frappe, "cache", return_value=self.cache)
		self.employees_patch = patch.object(alerts, "_employees", return_value=self.employees)
		self.tasks_patch = patch.object(alerts, "_active_tasks", return_value=self.tasks)
		self.date_patch = patch.object(alerts, "nowdate", return_value="2026-10-14")
		self.cache_patch.start()
		self.employees_patch.start()
		self.tasks_patch.start()
		self.date_patch.start()
		self.addCleanup(self.cache_patch.stop)
		self.addCleanup(self.employees_patch.stop)
		self.addCleanup(self.tasks_patch.stop)
		self.addCleanup(self.date_patch.stop)

	def test_migration_patch_warms_cache_without_notifications(self):
		with (
			patch.object(warm_employee_task_cache.frappe, "db", SimpleNamespace(has_column=lambda *_args: True)),
			patch.object(warm_employee_task_cache, "warm_active_task_cache") as warm,
		):
			warm_employee_task_cache.execute()
		warm.assert_called_once_with(notify=False)

	def test_team_status_uses_signed_in_manager(self):
		self.cache.set_value(alerts.READY_KEY, True)
		get_all = Mock(side_effect=[["MGR-001"], [self.employees[0]]])
		with (
			patch.object(alerts.frappe, "session", SimpleNamespace(user="manager@example.com")),
			patch.object(alerts.frappe, "get_all", get_all),
		):
			rows = alerts.get_team_task_status.__wrapped__()
		self.assertEqual(rows[0]["employee"], "EMP-001")
		self.assertEqual(get_all.call_args_list[0].kwargs["filters"]["user_id"], "manager@example.com")

	def test_morning_warmup_tracks_task_ids_and_alerts_zero_employees(self):
		with patch.object(alerts, "_notify_morning") as notify:
			zero_count = alerts.warm_active_task_cache(notify=True)
		self.assertEqual(zero_count, 1)
		self.assertEqual(self.cache.smembers(alerts._task_key("EMP-001")), {"TASK-001"})
		self.assertEqual(self.cache.smembers(alerts._task_key("EMP-002")), set())
		self.assertEqual([row.name for row in notify.call_args.args[0]], ["EMP-002"])

	def test_reassignment_moves_id_and_notifies_old_employee_once(self):
		with patch.object(alerts, "_notify_morning"):
			alerts.warm_active_task_cache(notify=True)
		with (
			patch.object(alerts.frappe, "db", SimpleNamespace(get_value=lambda *_args, **_kwargs: SimpleNamespace(assignee="bob@example.com", status="Open"))),
			patch.object(alerts.frappe, "get_all", return_value=["EMP-002"]),
			patch.object(alerts, "_deliver_pending_notification") as deliver,
		):
			alerts.sync_task("TASK-001")
			alerts.sync_task("TASK-001")
		self.assertEqual(self.cache.smembers(alerts._task_key("EMP-001")), set())
		self.assertEqual(self.cache.smembers(alerts._task_key("EMP-002")), {"TASK-001"})
		pending = self.cache.hget(alerts.PENDING_KEY, "EMP-001")
		self.assertEqual(pending["date"], "2026-10-14")
		self.assertEqual(len(pending["event_id"]), 32)
		deliver.assert_called_once_with("EMP-001")

	def test_sync_after_non_notifying_warmup_alerts_on_zero_transition(self):
		alerts.warm_active_task_cache()
		with (
			patch.object(alerts.frappe, "db", SimpleNamespace(get_value=lambda *_args, **_kwargs: None)),
			patch.object(alerts, "_deliver_pending_notification") as deliver,
		):
			alerts.sync_task("TASK-001")
		self.assertEqual(self.cache.smembers(alerts._task_key("EMP-001")), set())
		pending = self.cache.hget(alerts.PENDING_KEY, "EMP-001")
		self.assertEqual(pending["date"], "2026-10-14")
		self.assertEqual(len(pending["event_id"]), 32)
		deliver.assert_called_once_with("EMP-001")

	def test_sync_rebuilds_missing_cache(self):
		with (
			patch.object(alerts.frappe, "db", SimpleNamespace(get_value=lambda *_args, **_kwargs: SimpleNamespace(assignee="alice@example.com", status="Open"))),
			patch.object(alerts.frappe, "get_all", return_value=["EMP-001"]),
			patch.object(alerts, "warm_active_task_cache", wraps=alerts.warm_active_task_cache) as warm,
		):
			alerts.sync_task("TASK-001")
		warm.assert_called_once_with(notify=False)
		self.assertTrue(self.cache.get_value(alerts.READY_KEY))
		self.assertEqual(self.cache.smembers(alerts._task_key("EMP-001")), {"TASK-001"})

	def test_repeated_zero_transitions_get_distinct_ids_after_cache_rebuild(self):
		with (
			patch.object(alerts.frappe, "db", SimpleNamespace(get_value=lambda *_args, **_kwargs: None)),
			patch.object(alerts, "_deliver_pending_notification"),
		):
			alerts.warm_active_task_cache()
			alerts.sync_task("TASK-001")
			first = self.cache.hget(alerts.PENDING_KEY, "EMP-001")["event_id"]
			alerts.warm_active_task_cache()
			alerts.sync_task("TASK-001")
			second = self.cache.hget(alerts.PENDING_KEY, "EMP-001")["event_id"]
		self.assertNotEqual(first, second)

	def test_completion_removes_id_without_alert_if_another_task_remains(self):
		self.tasks.append(SimpleNamespace(name="TASK-002", assignee="alice@example.com"))
		alerts.warm_active_task_cache()
		with (
			patch.object(alerts.frappe, "db", SimpleNamespace(get_value=lambda *_args, **_kwargs: SimpleNamespace(assignee="alice@example.com", status="Completed"))),
			patch.object(alerts, "_deliver_pending_notification") as deliver,
		):
			alerts.sync_task("TASK-001")
		self.assertEqual(self.cache.smembers(alerts._task_key("EMP-001")), {"TASK-002"})
		deliver.assert_not_called()

	def test_failed_delivery_stays_pending_and_retry_clears_after_commit(self):
		pending = {"episode": 3, "date": "2026-10-14"}
		self.cache.hset(alerts.PENDING_KEY, "EMP-001", pending)
		callbacks = []
		db = SimpleNamespace(after_commit=SimpleNamespace(add=callbacks.append))
		with (
			patch.object(alerts.frappe, "db", db),
			patch.object(alerts, "_notify_transition", side_effect=RuntimeError("insert failed")),
		):
			with self.assertRaisesRegex(RuntimeError, "insert failed"):
				alerts._deliver_pending_notification("EMP-001")
		self.assertEqual(self.cache.hget(alerts.PENDING_KEY, "EMP-001"), pending)
		self.assertEqual(callbacks, [])
		with (
			patch.object(alerts.frappe, "db", db),
			patch.object(alerts, "_notify_transition") as notify,
		):
			alerts._deliver_pending_notification("EMP-001")
		notify.assert_called_once_with("EMP-001", 3, "2026-10-14")
		self.assertEqual(self.cache.hget(alerts.PENDING_KEY, "EMP-001"), pending)
		callbacks[0]()
		self.assertIsNone(self.cache.hget(alerts.PENDING_KEY, "EMP-001"))

	def test_retry_enqueues_each_pending_employee_independently(self):
		self.cache.hset(alerts.PENDING_KEY, "EMP-001", {"episode": 1, "date": "2026-10-14"})
		self.cache.hset(alerts.PENDING_KEY, "EMP-002", {"episode": 1, "date": "2026-10-14"})
		self.cache.hset(alerts.MORNING_PENDING_KEY, "MGR", {"date": "2026-10-14", "subject": "Alert"})
		with patch.object(alerts.frappe, "enqueue") as enqueue:
			alerts.retry_pending_notifications()
		self.assertEqual(enqueue.call_count, 3)
		self.assertEqual(
			{call.kwargs["employee"] for call in enqueue.call_args_list if "employee" in call.kwargs},
			{"EMP-001", "EMP-002"},
		)
		self.assertEqual(enqueue.call_args_list[-1].kwargs["manager"], "MGR")

	def test_old_delivery_cannot_erase_newer_zero_transition(self):
		newer = {"episode": 2, "date": "2026-10-14"}
		self.cache.hset(alerts.PENDING_KEY, "EMP-001", newer)
		with patch.object(self.cache, "hget", return_value={"episode": 1, "date": "2026-10-14"}):
			alerts._clear_pending_notification("EMP-001", {"episode": 1, "date": "2026-10-14"})
		self.assertEqual(self.cache.hget(alerts.PENDING_KEY, "EMP-001"), newer)

	def test_inactive_manager_does_not_receive_morning_alert(self):
		self.tasks.clear()

		def get_value(doctype, name, field, as_dict=False):
			if doctype == "Employee" and name == "MGR":
				return SimpleNamespace(user_id="manager@example.com", status="Left")
			return None

		with (
			patch.object(alerts.frappe, "db", SimpleNamespace(get_value=get_value)),
			patch.object(alerts, "_still_without_tasks", return_value={"alice@example.com", "bob@example.com"}),
			patch.object(alerts.frappe, "enqueue") as enqueue,
		):
			alerts.warm_active_task_cache(notify=True)
		enqueue.assert_not_called()

	def test_morning_alert_groups_zero_task_employees_by_reporting_manager(self):
		self.tasks.clear()

		def get_value(doctype, name, field, as_dict=False):
			if doctype == "Employee" and name == "MGR":
				return SimpleNamespace(user_id="manager@example.com", status="Active")
			if doctype == "User" and name == "manager@example.com" and field == "enabled":
				return 1
			return None
		with (
			patch.object(alerts.frappe, "db", SimpleNamespace(get_value=get_value)),
			patch.object(alerts, "_still_without_tasks", return_value={"alice@example.com", "bob@example.com"}),
			patch.object(alerts.frappe, "enqueue") as enqueue,
		):
			alerts.warm_active_task_cache(notify=True)
		self.assertEqual(
			self.cache.hget(alerts.MORNING_PENDING_KEY, "MGR"),
			{"date": "2026-10-14", "subject": "Employees with no active tasks: Alice, Bob"},
		)
		enqueue.assert_called_once()
		self.assertEqual(enqueue.call_args.kwargs["manager"], "MGR")

	def test_morning_delivery_remains_pending_until_commit(self):
		pending = {"date": "2026-10-14", "subject": "Employees with no active tasks: Alice"}
		self.cache.hset(alerts.MORNING_PENDING_KEY, "MGR", pending)
		callbacks = []
		db = SimpleNamespace(after_commit=SimpleNamespace(add=callbacks.append))
		with (
			patch.object(alerts.frappe, "db", db),
			patch.object(alerts, "_active_manager_user", return_value="manager@example.com"),
			patch.object(alerts, "_create_notification", side_effect=RuntimeError("insert failed")),
		):
			with self.assertRaisesRegex(RuntimeError, "insert failed"):
				alerts._deliver_pending_morning_notification("MGR")
		self.assertEqual(callbacks, [])
		self.assertEqual(self.cache.hget(alerts.MORNING_PENDING_KEY, "MGR"), pending)
		with (
			patch.object(alerts.frappe, "db", db),
			patch.object(alerts, "_active_manager_user", return_value="manager@example.com"),
			patch.object(alerts, "_create_notification") as create,
		):
			alerts._deliver_pending_morning_notification("MGR")
		create.assert_called_once_with(
			alerts._notification_name("morning", "MGR", on_date="2026-10-14"),
			"manager@example.com",
			pending["subject"],
		)
		self.assertEqual(self.cache.hget(alerts.MORNING_PENDING_KEY, "MGR"), pending)
		callbacks[0]()
		self.assertIsNone(self.cache.hget(alerts.MORNING_PENDING_KEY, "MGR"))

	def test_notification_log_has_stable_id_for_retry_deduplication(self):
		notification = Mock()
		with (
			patch.object(alerts.frappe, "db", SimpleNamespace(exists=lambda *_args: False)),
			patch.object(alerts.frappe, "get_doc", return_value=notification) as get_doc,
		):
			alerts._create_notification("alert-id", "manager@example.com", "Alice has no active tasks", "EMP-001")
		values = get_doc.call_args.args[0]
		self.assertEqual(values["doctype"], "Notification Log")
		self.assertEqual(values["type"], "Alert")
		self.assertEqual(values["for_user"], "manager@example.com")
		self.assertEqual(values["document_name"], "EMP-001")
		notification.insert.assert_called_once_with(ignore_permissions=True, set_name="alert-id")

"""Range-based manager chart tests."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from productivity_next.task_enhancement import team_productivity as chart


class FakeCache:
	def __init__(self):
		self.values = {}
		self.ttls = {}

	def get_value(self, key, **kwargs):
		return self.values.get(key)

	def set_value(self, key, value, expires_in_sec=None):
		self.values[key] = value
		self.ttls[key] = expires_in_sec


class TestTeamProductivity(TestCase):
	def setUp(self):
		self.team = [
			SimpleNamespace(name="EMP-001", employee_name="Alice", user_id="alice@example.com", image="/alice.png"),
			SimpleNamespace(name="EMP-002", employee_name="Bob", user_id="bob@example.com", image=None),
		]

	def test_task_counts_match_get_tasks_selection_and_date_range(self):
		rows = [
			SimpleNamespace(assignee="alice@example.com", type="Bug", total=3, completed=2, overdue=1),
			SimpleNamespace(assignee="alice@example.com", type="Feature", total=3, completed=0, overdue=0),
		]
		calls = []

		def sql(query, params, as_dict):
			calls.append((query, params))
			return rows

		start, end = date(2026, 10, 11), date(2026, 10, 17)
		with (
			patch.object(chart.frappe, "db", SimpleNamespace(sql=sql)),
			patch.object(chart, "nowdate", return_value="2026-10-14"),
		):
			counts = chart._task_counts(self.team, start, end)

		self.assertEqual(counts["alice@example.com"], {
			"total": 6, "completed": 2, "pending": 3, "overdue": 1,
			"task_types": {"Bug": 3, "Feature": 3},
		})
		self.assertEqual(len(calls), 1)
		query, params = calls[0]
		self.assertIn("task._assign LIKE CONCAT", query)
		self.assertIn("task.assignee = team.user_id", query)
		self.assertIn("task.completed_by = team.user_id", query)
		self.assertIn("task.exp_start_date <= %s", query)
		self.assertIn("task.completed_on BETWEEN %s AND %s", query)
		self.assertIn("'Unplanned', 'Template', 'Cancelled', 'Completed'", query)
		self.assertEqual(params, (date(2026, 10, 14), "alice@example.com", "bob@example.com",
			end, start, end))

	def test_empty_team_task_counts_do_not_query_database(self):
		with patch.object(chart.frappe, "db", SimpleNamespace(sql=Mock())) as database:
			counts = chart._task_counts([], date(2026, 10, 11), date(2026, 10, 17))
		self.assertEqual(dict(counts), {})
		database.sql.assert_not_called()

	def test_activity_merges_overlaps_and_excludes_meeting_from_idle(self):
		base = datetime(2026, 10, 14)
		def row(employee, start_hour, end_hour):
			return SimpleNamespace(
				employee=employee,
				start_time=base.replace(hour=start_hour),
				end_time=base.replace(hour=end_hour),
			)

		results = [
			[row("EMP-001", 9, 12)],
			[row("EMP-001", 10, 11)],
			[row("EMP-001", 11, 12)],
			[row("EMP-001", 10, 12)],
		]
		queries = []
		def sql(query, params, as_dict):
			queries.append((query, params))
			return results[len(queries) - 1]

		with patch.object(chart.frappe, "db", SimpleNamespace(sql=sql)):
			activity = chart._activity_times(self.team, date(2026, 10, 14), date(2026, 10, 14))

		self.assertEqual(len(queries), 4)
		self.assertEqual(activity["EMP-001"], {
			"active_seconds": 10800, "idle_seconds": 0, "progress_percent": 100.0,
		})
		self.assertEqual(activity["EMP-002"], {
			"active_seconds": 0, "idle_seconds": 0, "progress_percent": 0,
		})

	def test_idle_time_reduces_progress_within_selected_range(self):
		base = datetime(2026, 10, 14)
		results = [
			[SimpleNamespace(employee="EMP-001", start_time=base.replace(hour=9), end_time=base.replace(hour=12))],
			[],
			[],
			[SimpleNamespace(employee="EMP-001", start_time=base.replace(hour=10), end_time=base.replace(hour=11))],
		]
		with patch.object(chart.frappe, "db", SimpleNamespace(sql=lambda *_args, **_kwargs: results.pop(0))):
			activity = chart._activity_times(self.team, date(2026, 10, 14), date(2026, 10, 14))
		self.assertEqual(activity["EMP-001"], {
			"active_seconds": 7200, "idle_seconds": 3600, "progress_percent": 66.7,
		})

	def test_manager_team_rechecks_direct_reports_on_every_request(self):
		with (
			patch.object(chart.frappe, "session", SimpleNamespace(user="manager@example.com")),
			patch.object(chart.frappe, "get_all", side_effect=[["MGR-001"], self.team, ["MGR-001"], []]) as get_all,
		):
			self.assertEqual(chart._manager_team(), self.team)
			self.assertEqual(chart._manager_team(), [])
		self.assertEqual(get_all.call_count, 4)
		self.assertEqual(get_all.call_args_list[1].kwargs["filters"]["reports_to"], ["in", ["MGR-001"]])

	def test_reassigned_employee_cannot_receive_cached_rows(self):
		cache = FakeCache()
		with (
			patch.object(chart.frappe, "session", SimpleNamespace(user="manager@example.com")),
			patch.object(chart.frappe, "cache", return_value=cache),
			patch.object(chart, "_manager_team", side_effect=[self.team, []]),
			patch.object(chart, "_build_rows", return_value=[{"employee": "EMP-001"}]) as build,
		):
			self.assertTrue(chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14")["is_team"])
			self.assertEqual(chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14"),
				{"is_team": False, "rows": []})
		build.assert_called_once()

	def test_api_returns_only_reporting_managers_team(self):
		cache = FakeCache()
		with (
			patch.object(chart.frappe, "session", SimpleNamespace(user="manager@example.com")),
			patch.object(chart.frappe, "cache", return_value=cache),
			patch.object(chart, "_manager_team", return_value=self.team),
			patch.object(chart, "_task_counts", return_value={
				"alice@example.com": {"total": 1, "completed": 0, "pending": 1, "overdue": 0, "task_types": {"Bug": 1}},
				"bob@example.com": {"total": 0, "completed": 0, "pending": 0, "overdue": 0, "task_types": {}},
			}) as task_counts,
			patch.object(chart, "_activity_times", return_value={
				"EMP-001": {"active_seconds": 3600, "idle_seconds": 1800, "progress_percent": 66.7},
				"EMP-002": {"active_seconds": 0, "idle_seconds": 0, "progress_percent": 0},
			}),
		):
			result = chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14")
		task_counts.assert_called_once_with(self.team, date(2026, 10, 14), date(2026, 10, 14))
		self.assertEqual(set(result), {"is_team", "rows"})
		self.assertTrue(result["is_team"])
		self.assertEqual(len(result["rows"]), 2)
		self.assertEqual(result["rows"][0]["employee"], "EMP-001")
		self.assertEqual(result["rows"][0]["image"], "/alice.png")
		self.assertEqual(result["rows"][0]["progress_percent"], 66.7)
		self.assertEqual(result["rows"][1]["total"], 0)

	def test_cache_hit_reuses_rows_and_miss_rebuilds_after_expiry(self):
		cache = FakeCache()
		with (
			patch.object(chart.frappe, "session", SimpleNamespace(user="manager@example.com")),
			patch.object(chart.frappe, "cache", return_value=cache),
			patch.object(chart, "_manager_team", return_value=self.team),
			patch.object(chart, "_build_rows", return_value=[{"employee": "EMP-001", "total": 1}]) as build,
		):
			first = chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14")
			build.assert_called_once()
			key = chart._cache_key(self.team, date(2026, 10, 14), date(2026, 10, 14))
			self.assertEqual(cache.ttls[key], 900)
			cached = chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14")
			self.assertEqual(cached, first)
			build.assert_called_once()
			cache.values.pop(key)
			chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14")
			self.assertEqual(build.call_count, 2)

	def test_cache_key_changes_when_overdue_reference_day_changes(self):
		with patch.object(chart.frappe, "session", SimpleNamespace(user="manager@example.com")):
			with patch.object(chart, "nowdate", return_value="2026-10-14"):
				first = chart._cache_key(self.team, date(2026, 10, 1), date(2026, 10, 14))
			with patch.object(chart, "nowdate", return_value="2026-10-15"):
				second = chart._cache_key(self.team, date(2026, 10, 1), date(2026, 10, 14))
		self.assertNotEqual(first, second)

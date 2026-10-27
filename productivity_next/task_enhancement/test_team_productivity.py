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
			SimpleNamespace(
				name="EMP-001", employee_name="Alice", user_id="alice@example.com",
				image="/alice.png", reports_to="MGR-001",
			),
			SimpleNamespace(
				name="EMP-002", employee_name="Bob", user_id="bob@example.com",
				image=None, reports_to="EMP-001",
			),
		]

	def test_task_counts_use_assignee_and_get_tasks_date_filters(self):
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
		self.assertIn("task.assignee IN", query)
		self.assertNotIn("task._assign", query)
		self.assertNotIn("task.completed_by", query)
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

	def test_manager_team_includes_manager_and_recursive_reports(self):
		cache = FakeCache()
		manager = SimpleNamespace(
			name="MGR-001", employee_name="Manager", user_id="manager@example.com",
			image=None, reports_to=None,
		)
		with (
			patch.object(chart.frappe, "session", SimpleNamespace(user="manager@example.com")),
			patch.object(chart.frappe, "cache", return_value=cache),
			patch.object(chart.frappe, "get_all", return_value=[manager, *self.team]) as get_all,
		):
			team = chart._manager_team()
			self.assertEqual(chart._manager_team(), team)
		self.assertEqual([row.name for row in team], ["MGR-001", "EMP-001", "EMP-002"])
		self.assertEqual(get_all.call_count, 1)
		self.assertEqual(list(cache.ttls.values()), [3 * 60 * 60])

	def test_roles_do_not_expand_employee_hierarchy(self):
		cache = FakeCache()
		user_employee = SimpleNamespace(
			name="EMP-CEO", employee_name="CEO", user_id="ceo@example.com",
			image=None, reports_to=None,
		)
		with (
			patch.object(chart.frappe, "session", SimpleNamespace(user="ceo@example.com")),
			patch.object(chart.frappe, "cache", return_value=cache),
			patch.object(chart.frappe, "get_roles") as get_roles,
			patch.object(chart.frappe, "get_all", return_value=[user_employee, *self.team]),
		):
			team = chart._manager_team()

		self.assertEqual(team, [])
		get_roles.assert_not_called()

	def test_empty_team_response_is_cached(self):
		cache = FakeCache()
		with (
			patch.object(chart.frappe, "session", SimpleNamespace(user="manager@example.com")),
			patch.object(chart.frappe, "cache", return_value=cache),
			patch.object(chart, "_manager_team", return_value=[]) as manager_team,
		):
			first = chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14")
			cached = chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14")
		self.assertEqual(first, {"is_team": False, "rows": []})
		self.assertEqual(cached, first)
		manager_team.assert_called_once()
		self.assertEqual(list(cache.ttls.values()), [60 * 60])

	def test_api_returns_team_as_hierarchy(self):
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
		self.assertEqual(len(result["rows"]), 1)
		self.assertEqual(result["rows"][0]["employee"], "EMP-001")
		self.assertEqual(result["rows"][0]["image"], "/alice.png")
		self.assertEqual(result["rows"][0]["progress_percent"], 66.7)
		self.assertEqual(result["rows"][0]["reports_to"], "MGR-001")
		self.assertEqual(len(result["rows"][0]["children"]), 1)
		self.assertEqual(result["rows"][0]["children"][0]["employee"], "EMP-002")
		self.assertEqual(result["rows"][0]["children"][0]["total"], 0)

	def test_response_cache_hit_reuses_whole_response_and_miss_rebuilds(self):
		cache = FakeCache()
		with (
			patch.object(chart.frappe, "session", SimpleNamespace(user="manager@example.com")),
			patch.object(chart.frappe, "cache", return_value=cache),
			patch.object(chart, "_manager_team", return_value=self.team),
			patch.object(chart, "_build_rows", return_value=[{"employee": "EMP-001", "total": 1}]) as build,
		):
			first = chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14")
			build.assert_called_once()
			key = chart._response_cache_key(date(2026, 10, 14), date(2026, 10, 14))
			self.assertEqual(cache.ttls[key], 60 * 60)
			self.assertEqual(cache.values[key], first)
			cached = chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14")
			self.assertEqual(cached, first)
			build.assert_called_once()
			cache.values.pop(key)
			chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14")
			self.assertEqual(build.call_count, 2)

	def test_without_cache_refreshes_and_replaces_cached_response(self):
		cache = FakeCache()
		first_rows = [{"employee": "EMP-001", "total": 1}]
		fresh_rows = [{"employee": "EMP-001", "total": 2}]
		with (
			patch.object(chart.frappe, "session", SimpleNamespace(user="manager@example.com")),
			patch.object(chart.frappe, "cache", return_value=cache),
			patch.object(chart, "_manager_team", return_value=self.team),
			patch.object(chart, "_build_rows", side_effect=[first_rows, fresh_rows]) as build,
		):
			first = chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14")
			cached = chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14")
			fresh = chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14", "1")
			cached_fresh = chart.get_team_productivity.__wrapped__("2026-10-14", "2026-10-14")
			key = chart._response_cache_key(date(2026, 10, 14), date(2026, 10, 14))

		self.assertEqual(cached, first)
		self.assertEqual(fresh["rows"], fresh_rows)
		self.assertEqual(cached_fresh, fresh)
		self.assertEqual(build.call_count, 2)
		self.assertEqual(cache.values[key], fresh)
		self.assertEqual(cache.ttls[key], 60 * 60)

	def test_response_cache_key_changes_when_overdue_reference_day_changes(self):
		with patch.object(chart.frappe, "session", SimpleNamespace(user="manager@example.com")):
			with patch.object(chart, "nowdate", return_value="2026-10-14"):
				first = chart._response_cache_key(date(2026, 10, 1), date(2026, 10, 14))
			with patch.object(chart, "nowdate", return_value="2026-10-15"):
				second = chart._response_cache_key(date(2026, 10, 1), date(2026, 10, 14))
		self.assertNotEqual(first, second)

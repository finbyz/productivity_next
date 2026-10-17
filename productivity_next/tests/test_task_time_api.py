"""Task time API combines cached submitted history with live current-day logs."""

from datetime import date
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from productivity_next import api


class FakeCache:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def get_value(self, key):
        return self.values.get(key)

    def set_value(self, key, value, expires_in_sec=None):
        self.values[key] = value
        self.ttls[key] = expires_in_sec


class TestTaskTimeAPI(TestCase):
    def setUp(self):
        self.cache = FakeCache()
        self.queries = []
        self.history = [SimpleNamespace(task="TASK-1", employee="EMP-001", total_hours=2)]
        self.live = [SimpleNamespace(task="TASK-1", employee="EMP-001", total_duration=300)]
        self.employees = [SimpleNamespace(name="EMP-001", employee_name="Alice")]

    def sql(self, query, params, as_dict=True):
        self.queries.append((query, params))
        if "`tabTimesheet Detail`" in query:
            return self.history
        if "`tabApplication Usage log`" in query:
            return self.live
        raise AssertionError("Unexpected query")

    def test_history_is_cached_but_today_is_live_and_missing_tasks_are_zero(self):
        with (
            patch.object(api, "today", return_value="2026-10-15"),
            patch.object(api.frappe, "cache", return_value=self.cache),
            patch.object(api.frappe, "get_list", return_value=["TASK-1", "TASK-2"]),
            patch.object(api.frappe, "get_all", return_value=self.employees) as employees,
            patch.object(api.frappe.db, "sql", side_effect=self.sql),
        ):
            first = api.get_all_employee_time_on_tasks('["TASK-1", "TASK-2"]', "2026-10-01", "2026-10-15")
            self.live = [SimpleNamespace(task="TASK-1", employee="EMP-001", total_duration=600)]
            second = api.get_all_employee_time_on_tasks('["TASK-1", "TASK-2"]', "2026-10-01", "2026-10-15")

        self.assertEqual([row.task for row in first], ["TASK-1", "TASK-2"])
        self.assertEqual([row.total_duration for row in first], [7500, 0])
        self.assertEqual([row.total_duration for row in second], [7800, 0])
        self.assertEqual(first[0].employee_time[0].employee_name, "Alice")
        self.assertEqual(first[0].employee_time[0].total_duration, 7500)
        self.assertEqual(first[1].employee_time, [])
        self.assertEqual(second[0].employee_time[0].total_duration, 7800)
        self.assertEqual(sum("`tabTimesheet Detail`" in q for q, _ in self.queries), 1)
        self.assertEqual(sum("`tabApplication Usage log`" in q for q, _ in self.queries), 2)
        self.assertIn("GROUP BY tsd.task, ts.employee", self.queries[0][0])
        self.assertIn("GROUP BY task, employee", self.queries[1][0])
        self.assertEqual(list(self.cache.ttls.values()), [4 * 60 * 60])
        self.assertEqual(self.queries[0][1]["end_exclusive"], date(2026, 10, 15))
        self.assertEqual(employees.call_args.kwargs["filters"], {"name": ["in", ["EMP-001"]]})

    def test_multiple_employees_keep_separate_named_durations(self):
        self.history = [
            SimpleNamespace(task="TASK-1", employee="EMP-001", total_hours=1),
            SimpleNamespace(task="TASK-1", employee="EMP-002", total_hours=2),
        ]
        self.live = [
            SimpleNamespace(task="TASK-1", employee="EMP-001", total_duration=30),
            SimpleNamespace(task="TASK-1", employee="EMP-003", total_duration=90),
        ]
        self.employees = [
            SimpleNamespace(name="EMP-001", employee_name="Alice"),
            SimpleNamespace(name="EMP-002", employee_name="Bob"),
            SimpleNamespace(name="EMP-003", employee_name="Alice"),
        ]
        with (
            patch.object(api, "today", return_value="2026-10-15"),
            patch.object(api.frappe, "cache", return_value=self.cache),
            patch.object(api.frappe, "get_list", return_value=["TASK-1"]),
            patch.object(api.frappe, "get_all", return_value=self.employees),
            patch.object(api.frappe.db, "sql", side_effect=self.sql),
        ):
            result = api.get_all_employee_time_on_tasks(
                '["TASK-1"]', "2026-10-14", "2026-10-15"
            )[0]

        self.assertEqual(
            [(row.employee_name, row.total_duration) for row in result.employee_time],
            [("Alice", 3630), ("Bob", 7200), ("Alice", 90)],
        )
        self.assertEqual(result.total_duration, 10920)
        self.assertEqual(result.total_hours, 3.03)

    def test_past_range_excludes_live_logs(self):
        with (
            patch.object(api, "today", return_value="2026-10-15"),
            patch.object(api.frappe, "cache", return_value=self.cache),
            patch.object(api.frappe, "get_list", return_value=["TASK-1"]),
            patch.object(api.frappe, "get_all", return_value=self.employees),
            patch.object(api.frappe.db, "sql", side_effect=self.sql),
        ):
            result = api.get_all_employee_time_on_tasks(["TASK-1"], "2026-10-10", "2026-10-14")

        self.assertEqual(result[0].total_duration, 7200)
        self.assertEqual(len(self.queries), 1)
        self.assertIn("`tabTimesheet Detail`", self.queries[0][0])

    def test_future_range_returns_zero_without_time_queries(self):
        with (
            patch.object(api, "today", return_value="2026-10-15"),
            patch.object(api.frappe, "get_list", return_value=["TASK-1"]),
            patch.object(api.frappe, "get_all") as employees,
            patch.object(api.frappe.db, "sql", side_effect=self.sql),
        ):
            result = api.get_all_employee_time_on_tasks(["TASK-1"], "2026-10-16", "2026-10-20")

        self.assertEqual(result[0].total_duration, 0)
        self.assertEqual(result[0].employee_time, [])
        self.assertFalse(self.queries)
        employees.assert_not_called()

    def test_unreadable_task_cannot_use_cached_totals(self):
        with (
            patch.object(api, "today", return_value="2026-10-15"),
            patch.object(api.frappe, "get_list", return_value=[]),
            patch.object(api.frappe.db, "sql", side_effect=self.sql),
        ):
            with self.assertRaises(api.frappe.PermissionError):
                api.get_all_employee_time_on_tasks(["TASK-1"], "2026-10-01", "2026-10-15")

        self.assertFalse(self.queries)

    def test_existing_employee_endpoint_keeps_its_signature_and_filter(self):
        rows = [SimpleNamespace(task="TASK-1", total_duration=90)]
        with patch.object(api.frappe.db, "get_all", return_value=rows) as get_all:
            result = api.get_user_time_on_tasks(
                "EMP-001", '["TASK-1"]', "2026-10-15", "2026-10-15"
            )

        self.assertEqual(result, rows)
        self.assertEqual(get_all.call_args.kwargs["filters"], {
            "employee": "EMP-001",
            "task": ["in", ["TASK-1"]],
            "date": ["between", ("2026-10-15", "2026-10-15")],
        })

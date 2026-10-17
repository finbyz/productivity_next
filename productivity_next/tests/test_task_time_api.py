"""Task authorization and submitted-history reconciliation without a database."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from productivity_next import api
from productivity_next.task_enhancement import task_time


def raise_error(message, exception=frappe.ValidationError):
    raise exception(message)


def moment(value):
    return datetime.fromisoformat(value)


def activity(start, end, employee="EMP-001", task="TASK-1"):
    return frappe._dict(task=task, employee=employee, start_time=moment(start), end_time=moment(end))


class TestTaskTimeAPI(TestCase):
    def setUp(self):
        self.fake = SimpleNamespace(
            get_list=Mock(return_value=["TASK-1"]),
            get_all=Mock(return_value=[frappe._dict(name="EMP-001", employee_name="Alice")]),
            parse_json=frappe.parse_json, _dict=frappe._dict, throw=raise_error,
            ValidationError=frappe.ValidationError, PermissionError=frappe.PermissionError,
        )
        self.enterContext(patch.object(api, "frappe", self.fake))
        self.enterContext(patch.object(api, "_", lambda text: text))
        self.enterContext(patch.object(api, "today", return_value="2026-10-15"))
        self.totals = self.enterContext(patch.object(task_time, "get_task_totals", return_value={
            "TASK-1": {"EMP-001": 7500, "EMP-002": 300}
        }))

    def call(self, tasks='["TASK-1"]', **kwargs):
        return api.get_all_employee_time_on_tasks.__wrapped__(tasks, **kwargs)

    def test_named_contributors_include_stable_ids_and_seconds(self):
        self.fake.get_list.return_value = ["TASK-1", "TASK-2"]
        rows = self.call('["TASK-1", "TASK-2", "TASK-1"]', from_date="2026-10-01", to_date="2026-10-15")
        self.assertEqual([row.task for row in rows], ["TASK-1", "TASK-2"])
        self.assertEqual([row.total_duration for row in rows], [7800, 0])
        self.assertEqual(rows[0].employee_time[0].employee, "EMP-001")
        self.assertEqual(rows[0].employee_time[0].employee_name, "Alice")
        self.assertEqual(rows[0].total_hours, 2.17)
        self.assertEqual(rows[1].employee_time, [])
        self.totals.assert_called_once_with(["TASK-1", "TASK-2"], date(2026, 10, 1), date(2026, 10, 15), date(2026, 10, 15))

    def test_existing_unreadable_task_is_denied_before_loading_totals(self):
        # get_all can find the Task; get_list denies the current user access.
        self.fake.get_all.return_value = ["TASK-1"]
        self.fake.get_list.return_value = []
        with self.assertRaises(frappe.PermissionError):
            self.call()
        self.totals.assert_not_called()
        self.fake.get_all.assert_not_called()

    def test_invalid_inputs_and_large_batches_are_rejected(self):
        for tasks in ('{"name":"TASK-1"}', '[null]', '[1]', 'invalid', '[""]', [str(i) for i in range(101)]):
            with self.subTest(tasks=tasks), self.assertRaises(frappe.ValidationError):
                self.call(tasks)
        for invalid_date in ("", "0000-00-00", "2026-02-31", ["2026-10-14"]):
            with self.subTest(date=invalid_date), self.assertRaises(frappe.ValidationError):
                self.call(from_date=invalid_date)
        with self.assertRaises(frappe.ValidationError):
            self.call(from_date="2026-10-16", to_date="2026-10-15")
        self.totals.assert_not_called()


class TestTaskTimeAccounting(TestCase):
    def setUp(self):
        self.applications = []
        self.calls = []
        self.meetings = []
        self.details = []
        self.sheets = []
        self.queries = []
        self.fake = SimpleNamespace(db=SimpleNamespace(sql=Mock(side_effect=self.sql)))
        self.enterContext(patch.object(task_time, "frappe", self.fake))

    def sql(self, query, params, **kwargs):
        self.queries.append((query, params))
        if "`tabTimesheet Detail`" in query:
            return self.details + self.sheets
        if "FROM `tabTimesheet`" in query:
            return self.sheets
        if "`tabApplication Usage log`" in query:
            return self.applications
        if "`tabEmployee Fincall`" in query:
            return self.calls
        if "`tabMeeting`" in query:
            return self.meetings
        raise AssertionError(query)

    def total(self, day="2026-10-15", start="2026-10-14", end="2026-10-14"):
        return task_time.get_task_totals(["TASK-1"], date.fromisoformat(start),
            date.fromisoformat(end), date.fromisoformat(day)).get("TASK-1", {}).get("EMP-001", 0)

    def submit(self, day="2026-10-14", start="2026-10-14 09:00", end="2026-10-14 11:00", hours=2):
        self.sheets = [frappe._dict(employee="EMP-001", start_date=date.fromisoformat(day), end_date=date.fromisoformat(day))]
        self.details = [frappe._dict(task="TASK-1", employee="EMP-001", from_time=moment(start), to_time=moment(end), hours=hours)]

    def test_activity_survives_midnight_before_submission(self):
        self.applications = [activity("2026-10-14 09:00", "2026-10-14 10:00")]
        self.assertEqual(self.total(day="2026-10-14"), 3600)
        self.assertEqual(self.total(day="2026-10-15"), 3600)

    def test_submission_replaces_fallback_without_double_count_or_stale_cache(self):
        self.applications = [activity("2026-10-14 09:00", "2026-10-14 10:00")]
        self.assertEqual(self.total(), 3600)
        self.submit()
        self.assertEqual(self.total(), 7200)
        self.details = []
        self.sheets = []
        self.assertEqual(self.total(), 3600)

    def test_app_calls_and_meetings_merge_overlapping_time(self):
        self.applications = [activity("2026-10-14 09:00", "2026-10-14 10:00")]
        self.calls = [activity("2026-10-14 09:30", "2026-10-14 10:30")]
        self.meetings = [activity("2026-10-14 10:00", "2026-10-14 11:00")]
        self.assertEqual(self.total(), 7200)
        self.assertEqual(self.total(day="2026-10-14"), 7200)

    def test_submitted_cross_midnight_detail_is_clipped_proportionally(self):
        self.submit(start="2026-10-13 23:00", end="2026-10-14 01:00", hours=2)
        self.assertEqual(self.total(), 3600)

    def test_fallback_cross_midnight_keeps_only_unsubmitted_day(self):
        self.applications = [activity("2026-10-13 23:00", "2026-10-14 01:00")]
        self.submit(day="2026-10-13", start="2026-10-13 23:00", end="2026-10-14 01:00")
        self.details = []
        self.assertEqual(self.total(start="2026-10-13", end="2026-10-14"), 3600)

    def test_submitted_day_without_task_is_authoritative(self):
        self.applications = [activity("2026-10-14 09:00", "2026-10-14 10:00")]
        self.submit()
        self.details = []
        self.assertEqual(self.total(), 0)

    def test_future_range_does_not_query_time(self):
        self.assertEqual(self.total(day="2026-10-13"), 0)
        self.assertEqual(self.queries, [])

    def test_days_outside_submitted_coverage_keep_fallback(self):
        self.submit(day="2026-10-13", start="2026-10-13 09:00", end="2026-10-13 10:00", hours=1)
        self.applications = [activity("2026-10-14 09:00", "2026-10-14 10:00")]
        self.assertEqual(self.total(start="2026-10-13", end="2026-10-14"), 7200)

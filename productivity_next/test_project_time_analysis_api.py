"""Project cache isolation, current permissions, and refresh coordination."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from productivity_next import api


def raise_error(message, exception=frappe.ValidationError):
    raise exception(message)


class FakeCache:
    def __init__(self):
        self.values = {}
        self.guard = Mock()
        self.guard.acquire.return_value = True
        self.guard.owned.return_value = True

    def get_value(self, key, **kwargs):
        return self.values.get(key)

    def set_value(self, key, value, **kwargs):
        self.values[key] = value

    def make_key(self, key):
        return key

    def lock(self, *args, **kwargs):
        return self.guard


class TestProjectTimeAnalysisAPI(TestCase):
    def setUp(self):
        self.cache = FakeCache()
        self.fake = SimpleNamespace(
            session=SimpleNamespace(user="alice@example.com"), cache=Mock(return_value=self.cache),
            get_list=Mock(side_effect=lambda doctype, **kwargs: ["EMP-001"] if doctype == "Employee" else ["PROJECT"]),
            throw=raise_error, ValidationError=frappe.ValidationError, PermissionError=frappe.PermissionError,
        )
        self.rows = [{"employee": "EMP-001", "project": "PROJECT", "total_hours": "2.00", "internal_task": 0}]
        self.enterContext(patch.object(api, "frappe", self.fake))
        self.enterContext(patch.object(api, "_", lambda text: text))
        self.permission = self.enterContext(patch("frappe.desk.query_report.get_report_doc"))
        self.row_permissions = self.enterContext(patch(
            "frappe.desk.query_report.get_filtered_data", side_effect=lambda doctype, columns, rows, user: rows
        ))

    def call(self, **kwargs):
        return api.get_project_time_analysis.__wrapped__("2026-10-01", "2026-10-14", "EMP-001", **kwargs)

    def key(self):
        return api._get_project_time_analysis_cache_key("2026-10-01", "2026-10-14", "EMP-001")

    def test_report_runs_both_categories_for_requested_employee(self):
        def report_result(*, filters, **kwargs):
            return {"result": [dict(employee_id="EMP-001", project="PROJECT", total_hours=2),
                               dict(employee_id="OTHER", project="PRIVATE", total_hours=4)]}
        with patch("frappe.desk.query_report.run", side_effect=report_result) as run:
            rows = api._run_project_time_analysis("2026-10-01", "2026-10-14", "EMP-001")
        self.assertEqual([row["internal_task"] for row in rows], [0, 1])
        self.assertEqual([call.kwargs["filters"]["employee"] for call in run.call_args_list], ["EMP-001"] * 2)
        self.assertEqual({row["employee"] for row in rows}, {"EMP-001"})

    def test_cache_is_scoped_to_user_and_employee(self):
        first = self.key()
        self.fake.session.user = "bob@example.com"
        self.assertNotEqual(first, self.key())
        self.assertNotEqual(self.key(), api._get_project_time_analysis_cache_key("2026-10-01", "2026-10-14", "EMP-002"))

    def test_cache_hit_still_checks_employee_and_report_row_permissions(self):
        self.cache.values[self.key()] = {"generation": "one", "rows": self.rows}
        self.assertEqual(self.call(), [{"project": "PROJECT", "total_hours": "2.00", "internal_task": 0}])
        self.row_permissions.side_effect = None
        self.row_permissions.return_value = []
        self.assertEqual(self.call(), [])
        self.fake.get_list.side_effect = None
        self.fake.get_list.return_value = []
        with self.assertRaises(frappe.PermissionError):
            self.call()
        self.assertEqual(self.permission.call_count, 3)

    def test_report_totals_do_not_require_project_document_read(self):
        self.cache.values[self.key()] = {"generation": "one", "rows": self.rows}
        self.fake.get_list.side_effect = lambda doctype, **kwargs: ["EMP-001"] if doctype == "Employee" else []
        self.assertEqual(self.call(), [{"project": "PROJECT", "total_hours": "2.00", "internal_task": 0}])
        self.assertEqual([call.args[0] for call in self.fake.get_list.call_args_list], ["Employee"])
        self.row_permissions.assert_called_once_with(
            "Application Usage log",
            [{"fieldname": "project", "fieldtype": "Link", "options": "Project"}],
            self.rows,
            "alice@example.com",
        )

    def test_refresh_replaces_cache_under_the_same_lock(self):
        self.cache.values[self.key()] = {"generation": "old", "rows": []}
        with patch.object(api, "_run_project_time_analysis", return_value=self.rows) as run:
            result = self.call(without_cache="1")
        run.assert_called_once_with("2026-10-01", "2026-10-14", "EMP-001")
        self.assertEqual(result[0]["total_hours"], "2.00")
        self.assertEqual(self.cache.values[self.key()]["rows"], self.rows)
        self.cache.guard.acquire.assert_called_once()
        self.cache.guard.release.assert_called_once()

    def test_waiting_refresh_reuses_new_generation(self):
        self.cache.values[self.key()] = {"generation": "old", "rows": []}
        def acquire():
            self.cache.values[self.key()] = {"generation": "new", "rows": self.rows}
            return True
        self.cache.guard.acquire.side_effect = acquire
        with patch.object(api, "_run_project_time_analysis") as run:
            self.assertEqual(self.call(without_cache=1)[0]["total_hours"], "2.00")
        run.assert_not_called()

    def test_lock_contention_does_not_start_duplicate_report(self):
        self.cache.guard.acquire.return_value = False
        with patch.object(api, "_run_project_time_analysis") as run:
            with self.assertRaises(frappe.ValidationError):
                self.call(without_cache=1)
        run.assert_not_called()

    def test_expired_lock_cannot_overwrite_cache(self):
        previous = {"generation": "old", "rows": []}
        self.cache.values[self.key()] = previous
        self.cache.guard.owned.return_value = False
        with patch.object(api, "_run_project_time_analysis", return_value=self.rows):
            with self.assertRaises(frappe.ValidationError):
                self.call(without_cache=1)
        self.assertEqual(self.cache.values[self.key()], previous)

import datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe

from productivity_next.productivity_next.report.project_time_analysis import (
    project_time_analysis,
)


class TestProjectTimeAnalysisFilters(TestCase):
    def test_issue_hours_use_selected_projects_and_employee(self):
        sql = Mock(return_value=[])
        with patch.object(project_time_analysis.frappe, "db", SimpleNamespace(sql=sql)):
            project_time_analysis._get_issue_hours(
                {"from_date": "2026-10-01", "to_date": "2026-10-14", "employee": "EMP-001"},
                ["INTERNAL-PROJECT"],
            )
        query, params = sql.call_args.args
        self.assertIn("i.project IN %(projects)s", query)
        self.assertIn("e.name IN %(employees)s", query)
        self.assertEqual(params["projects"], ("INTERNAL-PROJECT",))
        self.assertEqual(params["employees"], ("EMP-001",))

    def test_issue_only_employee_appears_without_per_row_queries(self):
        row = frappe._dict(employee_id="EMP-001", employee_name="Alice", project="INTERNAL", issue_hours=2)
        fake = SimpleNamespace(
            utils=SimpleNamespace(now_datetime=datetime.datetime.now), logger=Mock(),
            db=SimpleNamespace(sql=Mock(side_effect=AssertionError("Unexpected per-row query"))),
        )
        with (
            patch.object(project_time_analysis, "frappe", fake),
            patch.object(project_time_analysis, "_get_issue_hours", return_value=[row]) as issues,
        ):
            result = project_time_analysis.calculate_time_aggregates(
                [], [], [], ["employee_id", "project"], {}, ["INTERNAL"],
            )
        issues.assert_called_once_with({}, ["INTERNAL"])
        self.assertEqual(result[0]["issue_hours"], 2)
        self.assertEqual(result[0]["employee_id"], "EMP-001")
        self.assertEqual(result[0]["project"], "INTERNAL")

    def test_normalises_iso_date_range(self):
        filters = project_time_analysis._normalise_date_filters(
            {
                "from_date": "2026-08-03",
                "to_date": "2026-08-04",
            }
        )

        self.assertEqual(filters["from_date"], datetime.date(2026, 8, 3))
        self.assertEqual(filters["to_date"], datetime.date(2026, 8, 4))

    def test_rejects_sql_in_date_filter(self):
        with patch.object(
            project_time_analysis.frappe,
            "throw",
            side_effect=frappe.ValidationError,
        ), self.assertRaises(frappe.ValidationError):
            project_time_analysis._normalise_date_filters(
                {
                    "from_date": "2026-08-03' OR 1=1 --",
                    "to_date": "2026-08-04",
                }
            )

    def test_sql_in_list_escapes_names(self):
        escaped = Mock(side_effect=lambda value: "'" + value.replace("'", "''") + "'")
        fake_frappe = SimpleNamespace(db=SimpleNamespace(escape=escaped))

        with patch.object(project_time_analysis, "frappe", fake_frappe):
            self.assertEqual(
                project_time_analysis._sql_in_list(["O'Brien", "Plain"]),
                "('O''Brien', 'Plain')",
            )
            self.assertEqual(project_time_analysis._sql_in_list([]), "(NULL)")

        self.assertEqual(escaped.call_count, 2)

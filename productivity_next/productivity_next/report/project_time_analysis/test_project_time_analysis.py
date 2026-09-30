import datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe

from productivity_next.productivity_next.report.project_time_analysis import (
    project_time_analysis,
)


class TestProjectTimeAnalysisFilters(TestCase):
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

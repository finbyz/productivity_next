from datetime import date, datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe

from productivity_next import api
from productivity_next.productivity_next.report.productify_activity_summary import (
    productify_activity_summary as report,
)


class TestProductifyWorkingHours(TestCase):
    def calculate(self, start, end, leaves=(), holidays=(), has_leave_application=True):
        def query(sql, values, as_dict):
            self.assertTrue(as_dict)
            if 'tabHoliday' in sql:
                return [frappe._dict(holiday_date=day) for day in holidays]
            self.assertIn("status = 'Approved'", sql)
            self.assertIn('docstatus = 1', sql)
            self.assertIn('from_date <= %s AND to_date >= %s', sql)
            self.assertEqual(values, ('EMP-001', frappe.utils.getdate(end), frappe.utils.getdate(start)))
            return [frappe._dict(leave) for leave in leaves]

        db = SimpleNamespace(
            sql=Mock(side_effect=query), exists=Mock(return_value=has_leave_application)
        )
        with patch.object(api.frappe, 'db', db, create=True), \
                patch.object(frappe.local, 'flags', frappe._dict(in_test=False), create=True):
            result = api.calculate_total_working_hours('EMP-001', start, end, 8, 4)
        return result, db

    def leave(self, start, end=None, half_day=False, half_day_date=None):
        return dict(
            from_date=date.fromisoformat(start),
            to_date=date.fromisoformat(end or start),
            half_day=half_day,
            half_day_date=date.fromisoformat(half_day_date) if half_day_date else None,
        )

    def test_full_day_leave(self):
        hours, _ = self.calculate('2026-10-05', '2026-10-05', [self.leave('2026-10-05')])
        self.assertEqual(hours, 0)

    def test_half_day_leave(self):
        hours, _ = self.calculate(
            '2026-10-05', '2026-10-05',
            [self.leave('2026-10-05', half_day=True, half_day_date='2026-10-05')],
        )
        self.assertEqual(hours, 4)

    def test_range_has_only_one_half_day(self):
        hours, _ = self.calculate(
            '2026-10-05', '2026-10-09',
            [self.leave('2026-10-05', '2026-10-07', True, '2026-10-06')],
        )
        self.assertEqual(hours, 20)

    def test_leave_range_clipped_to_report(self):
        for start, end in [('2026-10-01', '2026-10-06'),
                           ('2026-10-06', '2026-10-15'),
                           ('2026-10-01', '2026-10-15')]:
            with self.subTest(start=start, end=end):
                hours, _ = self.calculate('2026-10-05', '2026-10-07', [self.leave(start, end)])
                self.assertEqual(hours, 8 if start == '2026-10-06' or end == '2026-10-06' else 0)

    def test_half_day_outside_report_does_not_reduce_full_leave_days(self):
        hours, _ = self.calculate(
            '2026-10-06', '2026-10-07',
            [self.leave('2026-10-05', '2026-10-07', True, '2026-10-05')],
        )
        self.assertEqual(hours, 0)

    def test_two_half_days_cover_full_day(self):
        half_day = self.leave('2026-10-05', half_day=True, half_day_date='2026-10-05')
        hours, _ = self.calculate('2026-10-05', '2026-10-05', [half_day, half_day])
        self.assertEqual(hours, 0)

    def test_overlapping_leaves_do_not_create_negative_hours(self):
        full_day = self.leave('2026-10-05')
        half_day = self.leave('2026-10-05', half_day=True, half_day_date='2026-10-05')
        for leaves in ([full_day, half_day], [half_day, full_day]):
            with self.subTest(leaves=leaves):
                hours, _ = self.calculate('2026-10-05', '2026-10-05', leaves)
                self.assertEqual(hours, 0)

    def test_legacy_single_half_day_without_date(self):
        hours, _ = self.calculate(
            '2026-10-05', '2026-10-05', [self.leave('2026-10-05', half_day=True)]
        )
        self.assertEqual(hours, 4)

    def test_half_day_uses_saturday_hours(self):
        hours, _ = self.calculate(
            '2026-10-10', '2026-10-10',
            [self.leave('2026-10-10', half_day=True, half_day_date='2026-10-10')],
        )
        self.assertEqual(hours, 2)

    def test_holidays_and_sundays_are_not_deducted_twice(self):
        hours, _ = self.calculate(
            '2026-10-09', '2026-10-12', [self.leave('2026-10-10', '2026-10-12')],
            holidays=[date(2026, 10, 12)],
        )
        self.assertEqual(hours, 8)

    def test_leave_doctype_optional(self):
        hours, db = self.calculate('2026-10-05', '2026-10-11', has_leave_application=False)
        self.assertEqual(hours, 44)
        self.assertEqual(db.sql.call_count, 1)

    def test_date_and_datetime_inputs(self):
        hours, _ = self.calculate(date(2026, 10, 5), datetime(2026, 10, 6))
        self.assertEqual(hours, 16)


class TestActivitySummaryPeriods(TestCase):
    def test_monthly_period_starts_at_selected_date(self):
        with patch('builtins.print'):
            periods = report.monthly_ranges(datetime(2026, 10, 6), datetime(2026, 11, 3))
        self.assertEqual(periods, [
            (datetime(2026, 10, 6), datetime(2026, 10, 31)),
            (datetime(2026, 11, 1), datetime(2026, 11, 3)),
        ])

    def test_leave_adjusted_hours_used_in_report_score(self):
        expected_hours = 4
        analysis = dict(
            productivity_score={'EMP-001': expected_hours},
            total_hours_per_employee={'EMP-001': 4 * 3600},
            total_days={'EMP-001': 1},
        )
        db = SimpleNamespace(sql=Mock(return_value=[]), get_value=Mock(return_value=None),
                             exists=Mock(return_value=False))
        with patch.object(report.frappe, 'db', db, create=True), \
                patch.object(report.frappe, 'get_value', return_value='EMP-001'), \
                patch.object(report, 'user_analysis_data', return_value=analysis), \
                patch.object(report, '_', side_effect=lambda label: label):
            rows, _ = report.get_data(dict(from_date='2026-10-05', to_date='2026-10-05'))
        self.assertEqual(rows[0]['productivity_score'], 100)


class TestActivitySummaryLeave(TestCase):
    def test_leave_column_displays_labels(self):
        with patch.object(report, "_", side_effect=lambda label: label):
            column = next(column for column in report.get_columns() if column["fieldname"] == "leave")
        self.assertEqual(column["fieldtype"], "Data")

    def test_leave_values_and_ranges(self):
        leaves = [frappe._dict(
            employee="EMP-001", from_date="2026-10-04", to_date="2026-10-06",
            half_day=1, half_day_date="2026-10-05",
        )]
        filters = dict(from_date="2026-10-05", to_date="2026-10-07", employee="EMP-001")
        db = SimpleNamespace(exists=Mock(return_value=True))
        with patch.object(report.frappe, "db", db, create=True), \
                patch.object(report.frappe, "get_all", return_value=leaves) as get_all:
            days = report.get_leave_days(filters)
        self.assertEqual(days.get(("EMP-001", date(2026, 10, 5)), 0), 0.5)
        self.assertEqual(days.get(("EMP-001", date(2026, 10, 6)), 0), 1)
        self.assertEqual(days.get(("EMP-001", date(2026, 10, 7)), 0), 0)
        self.assertNotIn(("EMP-001", date(2026, 10, 4)), days)
        self.assertEqual(get_all.call_args.kwargs["filters"]["docstatus"], 1)
        self.assertEqual(get_all.call_args.kwargs["filters"]["status"], "Approved")
        self.assertEqual(get_all.call_args.kwargs["filters"]["employee"], "EMP-001")

    def test_leave_is_in_report_rows_and_period_totals(self):
        for frequency, expected in [("Daily", ["Half Day", "Full Day", "No Leave"]),
                                    ("Weekly", ["1.5 Days"]), ("Monthly", ["1.5 Days"])]:
            with self.subTest(frequency=frequency):
                analysis = dict(productivity_score={"EMP-001": 8})
                days = {("EMP-001", date(2026, 10, 5)): 0.5,
                        ("EMP-001", date(2026, 10, 6)): 1}
                db = SimpleNamespace(sql=Mock(return_value=[]), get_value=Mock(return_value=None))
                with patch.object(report.frappe, "db", db, create=True), \
                        patch.object(report.frappe, "get_value", return_value="EMP-001"), \
                        patch.object(report, "user_analysis_data", return_value=analysis), \
                        patch.object(report, "get_leave_days", return_value=days), \
                        patch.object(report, "_", side_effect=lambda label: label), \
                        patch("builtins.print"):
                    rows, totals = report.get_data(dict(
                        from_date="2026-10-05", to_date="2026-10-07", frequency=frequency,
                    ))
                self.assertEqual([row["leave"] for row in rows], expected)
                self.assertEqual([total["leave"] for total in totals], expected)

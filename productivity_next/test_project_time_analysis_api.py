from unittest import TestCase
from unittest.mock import patch

from productivity_next import api


class TestProjectTimeAnalysisAPI(TestCase):
    def test_report_runs_for_both_project_types_and_returns_internal_task_flag(self):
        def report_result(*, filters, **_kwargs):
            internal = filters["is_internal_project"]
            return {
                "result": [
                    {
                        "employee_id": "EMP-001",
                        "project": "INTERNAL" if internal else "CUSTOMER",
                        "total_hours": 1.5 if internal else 2.75,
                    },
                    {
                        "employee_id": "EMP-002",
                        "project": "OTHER",
                        "total_hours": 4,
                    },
                ]
            }

        with patch("frappe.desk.query_report.run", side_effect=report_result) as run:
            all_rows = api._run_project_time_analysis("2026-10-01", "2026-10-14")

        self.assertEqual(
            [call.kwargs["filters"]["is_internal_project"] for call in run.call_args_list],
            [0, 1],
        )
        self.assertEqual(
            api._filter_project_time_analysis_for_employee(all_rows, "EMP-001"),
            [
                {"project": "CUSTOMER", "total_hours": "2.75", "internal_task": 0},
                {"project": "INTERNAL", "total_hours": "1.50", "internal_task": 1},
            ],
        )

    def test_cache_key_is_versioned_for_new_response_shape(self):
        self.assertTrue(
            api._get_project_time_analysis_cache_key("2026-10-01", "2026-10-14").startswith(
                "project_time_analysis:v9:"
            )
        )

    def test_api_returns_flag_for_requested_employee_only(self):
        cached_rows = [
            {"employee": "EMP-001", "project": "CUSTOMER", "total_hours": "2.75", "internal_task": 0},
            {"employee": "EMP-001", "project": "INTERNAL", "total_hours": "1.50", "internal_task": 1},
            {"employee": "EMP-002", "project": "OTHER", "total_hours": "4.00", "internal_task": 1},
        ]
        with (
            patch("frappe.desk.query_report.get_report_doc"),
            patch.object(api, "_get_cached_project_time_analysis", return_value=cached_rows) as cached,
        ):
            result = api.get_project_time_analysis.__wrapped__(
                "2026-10-01", "2026-10-14", "EMP-001"
            )

        self.assertEqual(
            result,
            [
                {"project": "CUSTOMER", "total_hours": "2.75", "internal_task": 0},
                {"project": "INTERNAL", "total_hours": "1.50", "internal_task": 1},
            ],
        )
        cached.assert_called_once_with("2026-10-01", "2026-10-14")

    def test_without_cache_refreshes_shared_cache_and_filters_employee(self):
        report_rows = [
            {"employee": "EMP-001", "project": "FRESH", "total_hours": "3.00", "internal_task": 0},
            {"employee": "EMP-002", "project": "OTHER", "total_hours": "5.00", "internal_task": 1},
        ]
        for without_cache in (1, "1", "true"):
            with self.subTest(without_cache=without_cache):
                with (
                    patch("frappe.desk.query_report.get_report_doc") as permission_check,
                    patch.object(api, "_run_project_time_analysis", return_value=report_rows) as run,
                    patch.object(api, "_get_cached_project_time_analysis") as cached,
                    patch.object(api.frappe, "cache") as cache,
                ):
                    result = api.get_project_time_analysis.__wrapped__(
                        "2026-10-01", "2026-10-14", "EMP-001", without_cache
                    )

                permission_check.assert_called_once_with(api.PROJECT_TIME_ANALYSIS_REPORT)
                run.assert_called_once_with("2026-10-01", "2026-10-14")
                cached.assert_not_called()
                cache.set_value.assert_called_once_with(
                    api._get_project_time_analysis_cache_key("2026-10-01", "2026-10-14"),
                    report_rows,
                    expires_in_sec=api.PROJECT_TIME_ANALYSIS_CACHE_TTL,
                )
                self.assertEqual(
                    result,
                    [{"project": "FRESH", "total_hours": "3.00", "internal_task": 0}],
                )

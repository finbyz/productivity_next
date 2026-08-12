"""Tests for timesheet log generation using real seed data patterns.

Seed data characteristics (from Application Usage log.json & meetings.json):
  - 1170 app logs for EMP/00095 on 2026-08-11, ~10s each, boundary-equal (log[n].to_time == log[n+1].from_time)
  - 1012 logs without task, 158 with task (TASK36628, TASK36629, TASK36712)
  - 6 meetings overlapping different task blocks
  - No calls
"""
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_datetime, today

from productivity_next.schedule import (
    create_timesheet_logs,
    get_employee_meetings,
    merge_logs,
    normalize_non_overlapping_logs,
    split_logs,
)


# ---------------------------------------------------------------------------
# Seed data helpers — load the user's real JSON files
# ---------------------------------------------------------------------------

class SeedDataDriver:
    """Load user-supplied JSON files and adapt them for test builds."""

    SEED_DIR = Path(__file__).resolve().parent.parent / "seeds"

    def load_application_logs(self) -> list[dict]:
        path = self.SEED_DIR / "Application Usage log.json"
        with open(path) as fh:
            return json.load(fh)["data"]

    def load_meetings(self) -> list[dict]:
        path = self.SEED_DIR / "meetings.json"
        with open(path) as fh:
            return json.load(fh)["message"]


def _fuel(seed_driver=None):
    """Return the seed driver; populate a small helper dict lazily."""
    if seed_driver is None:
        seed_driver = SeedDataDriver()
    return seed_driver


# ---------------------------------------------------------------------------
# Unit tests — pure functions, no DB
# ---------------------------------------------------------------------------

class TestMergeLogs(FrappeTestCase):
    """merge_logs receives application logs grouped per employee."""

    def setUp(self):
        from datetime import datetime as dt

        self.today_str = today()
        self.marker = dt.fromisoformat

    def _app_log(self, employee, from_time, to_time, task=None, issue=None, project=None):
        return {
            "employee": employee,
            "from_time": from_time,
            "to_time": to_time,
            "task": task,
            "issue": issue,
            "project": project,
        }

    def test_boundary_equal_adjacent_logs_merge_when_same_task(self):
        """Adjacent logs with 0s gap and same task merge into one block."""
        base = get_datetime(f"{self.today_str} 09:30:00")
        logs = [
            self._app_log("E1", base, base + timedelta(seconds=10), task="T1"),
            self._app_log("E1", base + timedelta(seconds=10), base + timedelta(seconds=20), task="T1"),
            self._app_log("E1", base + timedelta(seconds=20), base + timedelta(seconds=30), task="T1"),
        ]
        merged = merge_logs(logs)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["to_time"], base + timedelta(seconds=30))

    def test_boundary_equal_adjacent_logs_split_when_different_task(self):
        """Adjacent logs with 0s gap but different task stay separate."""
        base = get_datetime(f"{self.today_str} 09:30:00")
        logs = [
            self._app_log("E1", base, base + timedelta(seconds=10), task="T1"),
            self._app_log("E1", base + timedelta(seconds=10), base + timedelta(seconds=20), task="T2"),
        ]
        merged = merge_logs(logs)
        self.assertEqual(len(merged), 2)
        # last_log.to_time is truncated to log.from_time when overlap & different assignment
        self.assertEqual(merged[0]["to_time"], base + timedelta(seconds=10))
        self.assertEqual(merged[1]["from_time"], base + timedelta(seconds=10))

    def test_small_gap_with_same_task_merges(self):
        """Logs with gap ≤10s and same task merge."""
        base = get_datetime(f"{self.today_str} 09:30:00")
        logs = [
            self._app_log("E1", base, base + timedelta(seconds=10), task="T1"),
            self._app_log("E1", base + timedelta(seconds=20), base + timedelta(seconds=30), task="T1"),
        ]
        merged = merge_logs(logs)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["to_time"], base + timedelta(seconds=30))

    def test_larger_gap_keeps_logs_separate(self):
        """Logs with gap >10s stay separate even with same task."""
        base = get_datetime(f"{self.today_str} 09:30:00")
        logs = [
            self._app_log("E1", base, base + timedelta(seconds=10), task="T1"),
            self._app_log("E1", base + timedelta(seconds=21), base + timedelta(seconds=31), task="T1"),
        ]
        merged = merge_logs(logs)
        self.assertEqual(len(merged), 2)

    def test_no_task_logs_merge(self):
        """Logs with both task=None should merge (same_assignment = all None == None)."""
        base = get_datetime(f"{self.today_str} 09:30:00")
        logs = [
            self._app_log("E1", base, base + timedelta(seconds=10)),
            self._app_log("E1", base + timedelta(seconds=10), base + timedelta(seconds=20)),
            self._app_log("E1", base + timedelta(seconds=20), base + timedelta(seconds=30)),
        ]
        merged = merge_logs(logs)
        self.assertEqual(len(merged), 1)

    def test_no_task_then_task_split(self):
        """No-task logs followed by task logs should not merge."""
        base = get_datetime(f"{self.today_str} 09:30:00")
        logs = [
            self._app_log("E1", base, base + timedelta(seconds=10)),
            self._app_log("E1", base + timedelta(seconds=10), base + timedelta(seconds=20), task="T1"),
        ]
        merged = merge_logs(logs)
        self.assertEqual(len(merged), 2)

    def test_enclosed_log_dropped(self):
        """If a log is entirely inside the previous log, it's skipped regardless of task."""
        base = get_datetime(f"{self.today_str} 09:30:00")
        # Different task, fully enclosed → dropped
        logs = [
            self._app_log("E1", base, base + timedelta(seconds=100)),
            self._app_log("E1", base + timedelta(seconds=10), base + timedelta(seconds=20), task="T1"),
        ]
        merged = merge_logs(logs)
        self.assertEqual(len(merged), 1, "Enclosed with different task is dropped")
        self.assertEqual(merged[0]["to_time"], base + timedelta(seconds=100))

        # Same task, fully enclosed → merged into the larger block
        logs2 = [
            self._app_log("E1", base, base + timedelta(seconds=100), task="T1"),
            self._app_log("E1", base + timedelta(seconds=10), base + timedelta(seconds=20), task="T1"),
        ]
        merged2 = merge_logs(logs2)
        self.assertEqual(len(merged2), 1)  # merged into first
        self.assertEqual(merged2[0]["to_time"], base + timedelta(seconds=100))

        # Different task, partially overlapping → truncated
        logs3 = [
            self._app_log("E1", base, base + timedelta(seconds=100), task="T1"),
            self._app_log("E1", base + timedelta(seconds=50), base + timedelta(seconds=150), task="T2"),
        ]
        merged3 = merge_logs(logs3)
        self.assertEqual(len(merged3), 2)
        self.assertEqual(merged3[0]["to_time"], base + timedelta(seconds=50))

    def test_non_overlapping_logs_preserve_order(self):
        """Logs that don't overlap remain in original order."""
        base = get_datetime(f"{self.today_str} 09:30:00")
        logs = [
            self._app_log("E1", base, base + timedelta(minutes=10)),
            self._app_log("E1", base + timedelta(minutes=20), base + timedelta(minutes=30)),
            self._app_log("E1", base + timedelta(minutes=40), base + timedelta(minutes=50)),
        ]
        merged = merge_logs(logs)
        self.assertEqual(len(merged), 3)


class TestSplitLogs(FrappeTestCase):
    """split_logs splices meetings or calls into existing merged application blocks."""

    def setUp(self):
        self.today_str = today()

    def test_new_log_before_all_old(self):
        base = get_datetime(f"{self.today_str} 09:00:00")
        merged = [
            {"from_time": base + timedelta(minutes=30), "to_time": base + timedelta(minutes=60), "task": "T1"},
        ]
        new = [
            {"from_time": base, "to_time": base + timedelta(minutes=20), "meeting": "M1"},
        ]
        result = split_logs(merged, new)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["from_time"], base)

    def test_new_log_after_all_old(self):
        base = get_datetime(f"{self.today_str} 09:00:00")
        merged = [
            {"from_time": base, "to_time": base + timedelta(minutes=30), "task": "T1"},
        ]
        new = [
            {"from_time": base + timedelta(minutes=40), "to_time": base + timedelta(minutes=60), "meeting": "M1"},
        ]
        result = split_logs(merged, new)
        self.assertEqual(len(result), 2)

    def test_meeting_splits_app_block_in_two(self):
        """Meeting in the middle of an app block splits it into before + meeting + after."""
        base = get_datetime(f"{self.today_str} 09:00:00")
        merged = [
            {"from_time": base, "to_time": base + timedelta(minutes=60), "task": "T1"},
        ]
        new = [
            {"from_time": base + timedelta(minutes=20), "to_time": base + timedelta(minutes=40), "meeting": "M1"},
        ]
        result = split_logs(merged, new)
        self.assertEqual(len(result), 3)
        # Before meeting
        self.assertEqual(result[0]["from_time"], base)
        self.assertEqual(result[0]["to_time"], base + timedelta(minutes=20))
        # Meeting
        self.assertEqual(result[1]["meeting"], "M1")
        # After meeting
        self.assertEqual(result[2]["from_time"], base + timedelta(minutes=40))
        self.assertEqual(result[2]["to_time"], base + timedelta(minutes=60))

    def test_meeting_fully_contained_in_app(self):
        """Meeting completely inside an app block — app split into before + meeting."""
        base = get_datetime(f"{self.today_str} 09:00:00")
        merged = [
            {"from_time": base, "to_time": base + timedelta(minutes=60), "task": "T1"},
        ]
        new = [
            {"from_time": base + timedelta(minutes=15), "to_time": base + timedelta(minutes=25), "meeting": "M1"},
        ]
        result = split_logs(merged, new)
        self.assertEqual(len(result), 3)
        # After meeting, remaining app block
        self.assertEqual(result[2]["from_time"], base + timedelta(minutes=25))
        self.assertEqual(result[2]["to_time"], base + timedelta(minutes=60))

    def test_multiple_meetings_interleaved(self):
        base = get_datetime(f"{self.today_str} 09:00:00")
        merged = [
            {"from_time": base, "to_time": base + timedelta(hours=6), "task": "T1"},
        ]
        new = [
            {"from_time": base + timedelta(hours=1), "to_time": base + timedelta(hours=1, minutes=20), "meeting": "M1"},
            {"from_time": base + timedelta(hours=3), "to_time": base + timedelta(hours=3, minutes=20), "meeting": "M2"},
        ]
        result = split_logs(merged, new)
        meetings = [r for r in result if r.get("meeting")]
        self.assertEqual(len(meetings), 2)

    def test_cleanup_loop_fixes_overlaps(self):
        """The final correction loop pushes overlapping from_time forward."""
        base = get_datetime(f"{self.today_str} 09:00:00")
        merged = [
            {"from_time": base, "to_time": base + timedelta(minutes=60), "task": "T1"},
        ]
        # This new log starts at minute 10 with to_time beyond old's end
        new = [
            {"from_time": base + timedelta(minutes=10), "to_time": base + timedelta(minutes=90), "meeting": "M1"},
        ]
        result = split_logs(merged, new)
        for i in range(1, len(result)):
            self.assertLessEqual(
                get_datetime(result[i - 1]["to_time"]),
                get_datetime(result[i]["from_time"]),
            )


class TestNormalizeNonOverlappingLogs(FrappeTestCase):
    """normalize_non_overlapping_logs — final pass before save."""

    def setUp(self):
        self.today_str = today()

    def test_clips_partial_overlap(self):
        base = get_datetime(f"{self.today_str} 09:00:00")
        logs = [
            {"from_time": base, "to_time": base + timedelta(hours=1)},
            {"from_time": base + timedelta(minutes=15), "to_time": base + timedelta(minutes=30)},
            {"from_time": base + timedelta(minutes=45), "to_time": base + timedelta(minutes=75)},
        ]
        normalized = normalize_non_overlapping_logs(logs)
        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[1]["from_time"], base + timedelta(hours=1))

    def test_boundary_equality_creates_1s_gap(self):
        """When a log starts exactly where the previous ends, subtract 1s from previous to_time."""
        base = get_datetime(f"{self.today_str} 09:00:00")
        logs = [
            {"from_time": base, "to_time": base + timedelta(minutes=10)},
            {"from_time": base + timedelta(minutes=10), "to_time": base + timedelta(minutes=20)},
        ]
        normalized = normalize_non_overlapping_logs(logs)
        self.assertLess(
            normalized[0]["to_time"],
            get_datetime(base + timedelta(minutes=10)),
        )

    def test_fully_contained_overlap_skipped(self):
        base = get_datetime(f"{self.today_str} 09:00:00")
        logs = [
            {"from_time": base, "to_time": base + timedelta(hours=2)},
            {"from_time": base + timedelta(minutes=30), "to_time": base + timedelta(minutes=60)},
        ]
        normalized = normalize_non_overlapping_logs(logs)
        self.assertEqual(len(normalized), 1)


# ---------------------------------------------------------------------------
# Integration test — feeds seed data through the full pipeline
# ---------------------------------------------------------------------------

class TestTimesheetLogGenerationWithSeedData(FrappeTestCase):
    """End-to-end test using the user's real Application Usage log.json and meetings.json.

    The test injects exactly the records found in the seed files, runs
    create_timesheet_logs, and asserts the resulting timesheet is valid and
    passable through ERPNext's save validation.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.seed = SeedDataDriver()
        cls.app_logs = cls.seed.load_application_logs()
        cls.meetings_data = cls.seed.load_meetings()

    def setUp(self):
        self.suffix = uuid4().hex[:8]
        company = frappe.db.get_value("Company", {}, "name")
        self.assertTrue(company, "Need at least one Company in the test site")

        # Create employee matching seed data pattern
        self.employee = frappe.get_doc({
            "doctype": "Employee",
            "first_name": f"SeedTest {self.suffix}",
            "company": company,
            "gender": "Male",
            "date_of_birth": "1990-01-01",
            "date_of_joining": today(),
            "status": "Active",
        }).insert(ignore_permissions=True)

        # Ensure Activity Types exist
        for at in ("No Task", "Task", "Meeting", "Call", "Issue", "Project"):
            if not frappe.db.exists("Activity Type", at):
                frappe.get_doc({"doctype": "Activity Type", "activity_type": at}).insert(
                    ignore_permissions=True
                )

        # List of User is a child table (istable:1) — mock frappe.get_all instead.
        # Create seed tasks — from both app logs and meetings
        self.tasks = {}
        unique_tasks = {r.get("task") for r in self.app_logs if r.get("task")}
        unique_tasks |= {m.get("task") for m in self.meetings_data if m.get("task")}
        for tname in unique_tasks:
            task = frappe.get_doc({
                "doctype": "Task",
                "subject": f"Seed Task {tname}",
                "status": "Open",
                "company": company,
                "assignee": "Administrator",
            }).insert(ignore_permissions=True)
            self.tasks[tname] = task.name

        # Create seed projects — project_name has a unique index, use suffix to avoid collisions.
        # Store the actual doc name (autoname) for link field remapping, not project_name.
        unique_projects = {r.get("project") for r in self.app_logs if r.get("project")}
        unique_projects |= {m.get("project") for m in self.meetings_data if m.get("project")}
        self.project_map = {}
        for pname in unique_projects:
            test_pname = f"{pname} ({self.suffix})"
            existing = frappe.db.exists("Project", {"project_name": test_pname})
            if existing:
                self.project_map[pname] = existing
                continue
            proj = frappe.get_doc({
                "doctype": "Project",
                "project_name": test_pname,
                "company": company,
                "status": "Open",
                "project_allowance_start_date": today(),
            }).insert(ignore_permissions=True)
            self.project_map[pname] = proj.name  # doc name for link fields

        # Create Meeting Purpose if needed
        purposes = {m.get("purpose") for m in self.meetings_data if m.get("purpose")}
        for purpose in purposes:
            if not frappe.db.exists("Meeting Purpose", purpose):
                frappe.get_doc({
                    "doctype": "Meeting Purpose",
                    "purpose": purpose,
                    "internal_meeting": 1,
                }).insert(ignore_permissions=True)

        # Prepare a second employee for meeting company reps
        self.second_employee = frappe.get_doc({
            "doctype": "Employee",
            "first_name": f"SeedTest2 {self.suffix}",
            "company": company,
            "gender": "Female",
            "date_of_birth": "1990-06-01",
            "date_of_joining": today(),
            "status": "Active",
        }).insert(ignore_permissions=True)

        # Contacts for meetings
        self.contacts = []
        for i in range(2):
            contact = frappe.get_doc({
                "doctype": "Contact",
                "first_name": f"SeedContact{i} {self.suffix}",
            }).insert(ignore_permissions=True)
            self.contacts.append(contact)

        # Seed data dates are 2026-08-11; shift everything to today()
        from datetime import datetime as _dt
        # Pick the dominant seed date (most records, not alphabetically last)
        date_counts = Counter(r.get("date") for r in self.app_logs if r.get("date"))
        seed_date_str = date_counts.most_common(1)[0][0]  # "2026-08-11"
        seed_date = _dt.strptime(seed_date_str, "%Y-%m-%d").date()
        today_date = _dt.strptime(today(), "%Y-%m-%d").date()
        self._date_shift = (today_date - seed_date).days  # usually 1

        def _shift(ts_str: str) -> str:
            """Shift a datetime string from seed date to today."""
            if not ts_str:
                return ts_str
            parsed = _dt.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            shifted = parsed + timedelta(days=self._date_shift)
            return shifted.strftime("%Y-%m-%d %H:%M:%S")

        # --- Insert seed application logs ---
        # Remap employee, task, project to test equivalents; drop proxy_employee link
        for rec in self.app_logs:
            log = rec.copy()
            log["employee"] = self.employee.name
            log["from_time"] = _shift(log.get("from_time"))
            log["to_time"] = _shift(log.get("to_time"))
            log["date"] = _shift(log.get("date", "") + " 00:00:00")[:10] if log.get("date") else today()
            if log.get("task") and log["task"] in self.tasks:
                log["task"] = self.tasks[log["task"]]
            if log.get("project") and log["project"] in self.project_map:
                log["project"] = self.project_map[log["project"]]
            # Drop proxy_employee (link to EMP/00095 which doesn't exist)
            log.pop("proxy_employee", None)
            frappe.get_doc({"doctype": "Application Usage log", **log}).insert(
                ignore_permissions=True
            )

        # --- Insert seed meetings ---
        for m in self.meetings_data:
            meeting = frappe.get_doc({
                "doctype": "Meeting",
                "internal_meeting": m.get("internal_meeting", 1),
                "purpose": m.get("purpose", "Issue Discussion"),
                "discussion": m.get("discussion", "Seed meeting"),
                "meeting_from": _shift(m["meeting_from"]),
                "meeting_to": _shift(m["meeting_to"]),
                "posting_date": today_date.strftime("%Y-%m-%d"),
                "meeting_arranged_by": "Administrator",
                "organization": "Internal Meeting",
                "project": self.project_map.get(m.get("project"), m.get("project")),
                "task": self.tasks.get(m.get("task")) if m.get("task") and m["task"] in self.tasks else m.get("task"),
                "issue": m.get("issue"),
                "meeting_company_representative": [
                    {"employee": self.employee.name},
                    {"employee": self.second_employee.name},
                ],
                "meeting_party_representative": [
                    {"contact": c.name} for c in self.contacts
                ],
            }).insert(ignore_permissions=True)
            try:
                frappe.db.set_value("Meeting", meeting.name, "docstatus", 1)
            except Exception:
                pass  # Meeting may have been rejected by validate; still inserted

    def test_full_pipeline_with_seed_data(self):
        """Run the full pipeline against seed data and verify the timesheet."""
        original_get_all = frappe.get_all

        def single_employee_only(doctype, *args, **kwargs):
            if doctype == "List of User":
                return [self.employee.name]
            return original_get_all(doctype, *args, **kwargs)

        with patch(
            "productivity_next.schedule.frappe.get_all",
            single_employee_only,
        ):
            create_timesheet_logs()

        timesheet_name = frappe.db.get_value(
            "Timesheet",
            {
                "employee": self.employee.name,
                "start_date": today(),
                "docstatus": 0,
                "is_created_by_productify": 1,
            },
        )
        self.assertTrue(
            timesheet_name,
            "A timesheet should have been created for the test employee",
        )

        timesheet = frappe.get_doc("Timesheet", timesheet_name)
        logs = sorted(timesheet.time_logs, key=lambda row: row.from_time)

        self.assertGreater(
            len(logs), 2, "Seed data should produce multiple time log entries"
        )

        # Activity type coverage
        activity_types = {row.activity_type for row in logs}
        self.assertIn("Meeting", activity_types, "Seed data has meetings")
        self.assertIn("Task", activity_types, "Seed data has task-assigned app logs")
        self.assertIn("No Task", activity_types, "Seed data has no-task app logs")

        # Verify no overlaps in the saved timesheet
        self._assert_no_boundary_equality(logs)

    def _assert_no_boundary_equality(self, time_logs):
        """ERPNext's timesheet.save() must pass — no boundary adjacency allowed after the 1s-gap fix."""
        for prev, curr in zip(time_logs, time_logs[1:]):
            self.assertLess(
                get_datetime(prev.to_time),
                get_datetime(curr.from_time),
                f"Boundary equality or overlap at {prev.to_time} -> {curr.from_time}",
            )

    def test_timesheet_passes_erpnext_save(self):
        """Smoke test: create_timesheet_logs output must survive timesheet.save()."""
        original_get_all = frappe.get_all

        def single_employee_only(doctype, *args, **kwargs):
            if doctype == "List of User":
                return [self.employee.name]
            return original_get_all(doctype, *args, **kwargs)

        with patch(
            "productivity_next.schedule.frappe.get_all",
            single_employee_only,
        ):
            create_timesheet_logs()

        timesheet_name = frappe.db.get_value(
            "Timesheet",
            {
                "employee": self.employee.name,
                "start_date": today(),
                "docstatus": 0,
                "is_created_by_productify": 1,
            },
        )
        self.assertTrue(timesheet_name)

        # This save must not raise OverlapError
        doc = frappe.get_doc("Timesheet", timesheet_name)
        doc.save()

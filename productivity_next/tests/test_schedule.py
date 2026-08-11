from datetime import timedelta
from random import Random
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_datetime, today

from productivity_next.schedule import (
    create_timesheet_logs,
    get_employee_meetings,
    normalize_non_overlapping_logs,
)


class TestTimesheetLogGeneration(FrappeTestCase):
    def test_normalizer_clips_and_discards_overlaps(self):
        start = get_datetime(f"{today()} 09:00:00")
        logs = [
            {"from_time": start, "to_time": start + timedelta(hours=1)},
            {"from_time": start + timedelta(minutes=15), "to_time": start + timedelta(minutes=30)},
            {"from_time": start + timedelta(minutes=45), "to_time": start + timedelta(minutes=75)},
        ]

        normalized = normalize_non_overlapping_logs(logs)

        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[1]["from_time"], start + timedelta(hours=1))
        self.assert_non_overlapping(normalized)

    def test_create_timesheet_logs_end_to_end(self):
        fixture = self.create_fixture()
        self.assertEqual(
            frappe.db.count(
                "Application Usage log",
                {"employee": fixture["employee"], "date": today()},
            ),
            400,
        )
        self.assertEqual(
            frappe.db.count("Employee Fincall", {"employee": fixture["employee"]}),
            3,
        )
        self.assertEqual(len(get_employee_meetings(fixture["employee"], today())), 2)
        original_get_all = frappe.get_all

        def fixture_employee_only(doctype, *args, **kwargs):
            if doctype == "List of User":
                return [fixture["employee"]]
            return original_get_all(doctype, *args, **kwargs)

        with patch("productivity_next.schedule.frappe.get_all", fixture_employee_only):
            create_timesheet_logs()

        timesheet_name = frappe.db.get_value(
            "Timesheet",
            {
                "employee": fixture["employee"],
                "start_date": today(),
                "docstatus": 0,
                "is_created_by_productify": 1,
            },
        )
        self.assertTrue(timesheet_name)
        logs = sorted(
            frappe.get_doc("Timesheet", timesheet_name).time_logs,
            key=lambda row: row.from_time,
        )
        self.assertGreaterEqual(len(logs), 9)
        self.assertIn("Task", {row.activity_type for row in logs})
        self.assertIn("Meeting", {row.activity_type for row in logs})
        self.assertIn("Call", {row.activity_type for row in logs})
        self.assert_non_overlapping(logs)

    def create_fixture(self):
        suffix = uuid4().hex[:8]
        company = frappe.db.get_value("Company", {}, "name")
        self.assertTrue(company, "The test site must have a Company")
        employee = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": f"Timesheet E2E {suffix}",
                "company": company,
                "gender": "Male",
                "date_of_birth": "1990-01-01",
                "date_of_joining": today(),
                "status": "Active",
            }
        ).insert(ignore_permissions=True)

        second_employee = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": f"Timesheet E2E Participant {suffix}",
                "company": company,
                "gender": "Male",
                "date_of_birth": "1990-01-01",
                "date_of_joining": today(),
                "status": "Active",
            }
        ).insert(ignore_permissions=True)

        for activity_type in ("No Task", "Task", "Meeting", "Call"):
            if not frappe.db.exists("Activity Type", activity_type):
                frappe.get_doc(
                    {"doctype": "Activity Type", "activity_type": activity_type}
                ).insert(ignore_permissions=True)

        task = frappe.get_doc(
            {
                "doctype": "Task",
                "subject": f"Timesheet E2E Task {suffix}",
                "status": "Open",
                "company": company,
                "assignee": "Administrator",
            }
        ).insert(ignore_permissions=True)

        start = get_datetime(f"{today()} 09:00:00")
        random = Random(20260811)
        for index in range(400):
            start_offset = random.randint(0, (8 * 60 * 60) - 300)
            duration = random.randint(10, 300)
            log_start = start + timedelta(seconds=start_offset)
            frappe.get_doc(
                {
                    "doctype": "Application Usage log",
                    "employee": employee.name,
                    "date": today(),
                    "from_time": log_start,
                    "to_time": log_start + timedelta(seconds=duration),
                    "application_title": f"Task application {index}",
                    "application_name": "Timesheet E2E",
                    "process_name": "timesheet-e2e",
                    "ip_address": "127.0.0.1",
                    "task": task.name,
                }
            ).insert(ignore_permissions=True)

        contacts = [
            frappe.get_doc(
                {"doctype": "Contact", "first_name": f"E2E Contact {i} {suffix}"}
            ).insert(ignore_permissions=True).name
            for i in range(2)
        ]
        purpose = f"Timesheet E2E {suffix}"
        frappe.get_doc(
            {"doctype": "Meeting Purpose", "purpose": purpose, "internal_meeting": 1}
        ).insert(ignore_permissions=True)

        for meeting_index, (from_minute, to_minute) in enumerate(
            ((60, 120), (240, 300))
        ):
            meeting = frappe.get_doc(
                {
                    "doctype": "Meeting",
                    "internal_meeting": 1,
                    "purpose": purpose,
                    "discussion": f"Overlap meeting {meeting_index}",
                    "meeting_from": start + timedelta(minutes=from_minute),
                    "meeting_to": start + timedelta(minutes=to_minute),
                    "meeting_company_representative": [
                        {"employee": employee.name},
                        {"employee": second_employee.name},
                    ],
                    "meeting_party_representative": [
                        {"contact": contact} for contact in contacts
                    ],
                }
            ).insert(ignore_permissions=True)
            frappe.db.set_value("Meeting", meeting.name, "docstatus", 1)

        for call_index, (from_minute, duration_minutes) in enumerate(
            ((75, 15), (270, 20), (370, 10))
        ):
            frappe.get_doc(
                {
                    "doctype": "Employee Fincall",
                    "employee": employee.name,
                    "employee_mobile": "9000000000",
                    "customer_no": f"91111111{call_index:02d}",
                    "call_datetime": start + timedelta(minutes=from_minute),
                    "duration": duration_minutes * 60,
                    "date": today(),
                    "calltype": "Incoming",
                    "contact": contacts[0],
                }
            ).insert(ignore_permissions=True)
        return {"employee": employee.name}

    def assert_non_overlapping(self, logs):
        def value(log, field):
            return getattr(log, field) if hasattr(log, field) else log[field]

        for previous, current in zip(logs, logs[1:]):
            self.assertLessEqual(
                get_datetime(value(previous, "to_time")),
                get_datetime(value(current, "from_time")),
            )

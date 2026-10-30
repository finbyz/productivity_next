from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from productivity_next.task_enhancement.overrides.doctype import task as task_module


class TestTask(FrappeTestCase):
	def test_cancelled_leaf_does_not_reopen_completed_parent(self):
		root = create_task("Root", is_group=True)
		parent = create_task("Parent", is_group=True, parent_task=root.name)
		completed_child = create_task("Completed child", parent_task=parent.name)
		cancelled_child = create_task("Cancelled child", parent_task=parent.name)

		completed_child.status = "Completed"
		completed_child.save()
		cancelled_child.status = "Cancelled"
		cancelled_child.save()

		parent.reload()
		parent.status = "Completed"
		parent.save()

		self.assertEqual(parent.status, "Completed")
		self.assertEqual(frappe.db.get_value("Task", parent.name, "status"), "Completed")
		self.assertEqual(frappe.db.get_value("Task", root.name, "status"), "Completed")


def create_task(label, *, is_group=False, parent_task=None):
	return frappe.get_doc(
		{
			"doctype": "Task",
			"subject": f"Parent status test {label} {frappe.generate_hash(length=8)}",
			"status": "Open",
			"is_group": is_group,
			"parent_task": parent_task,
			"assignee": "Administrator",
		}
	).insert()


class TestAssignmentCompletion(TestCase):
	def test_repeated_completion_notifies_each_open_assignee_once(self):
		assignments = [
			frappe._dict(name="open-one", allocated_to="one@example.com", status="Open"),
			frappe._dict(name="open-two", allocated_to="two@example.com", status="Open"),
			frappe._dict(name="completed", allocated_to="three@example.com", status="Completed"),
			frappe._dict(name="closed", allocated_to="four@example.com", status="Closed"),
			frappe._dict(name="cancelled", allocated_to="five@example.com", status="Cancelled"),
		]
		notifications = []

		def get_assignments(doctype, *, fields, filters):
			status_filter = filters["status"]
			if isinstance(status_filter, tuple):
				return [row for row in assignments if row.status != status_filter[1]]
			return [row for row in assignments if row.status == status_filter]

		def complete_assignment(doctype, name, *, todo, assign_to, status, ignore_permissions):
			row = next(row for row in assignments if row.name == todo)
			row.status = status
			notifications.append(assign_to)

		with (
			patch.object(task_module.frappe, "get_all", side_effect=get_assignments),
			patch.object(task_module, "set_status", side_effect=complete_assignment),
		):
			self.assertTrue(task_module.clomplete_all_assignments("Task", "TASK-TEST"))
			self.assertFalse(task_module.clomplete_all_assignments("Task", "TASK-TEST"))
			self.assertFalse(task_module.clomplete_all_assignments("Task", "TASK-TEST"))

		self.assertEqual(notifications, ["one@example.com", "two@example.com"])
		self.assertEqual([row.status for row in assignments], [
			"Completed", "Completed", "Completed", "Closed", "Cancelled",
		])

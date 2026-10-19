import frappe
from frappe.tests.utils import FrappeTestCase


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

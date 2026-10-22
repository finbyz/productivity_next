import json
import frappe
from frappe.utils import nowdate, add_days, add_months, add_years
from jinja2 import Template
from frappe.desk.form import assign_to


class Notification:
	"""Mixin for extend_doctype_class — adds Task channel support to Notification."""

	def send(self, doc):
		"""Build recipients and send Notification"""

		context = {"doc": doc, "alert": self, "comments": None}
		if doc.get("_comments"):
			context["comments"] = json.loads(doc.get("_comments"))

		if self.is_standard:
			self.load_standard_properties(context)

		try:
			if self.channel == "Email":
				self.send_an_email(doc, context)

			if self.channel == "Slack":
				self.send_a_slack_msg(doc, context)

			if self.channel == "SMS":
				self.send_sms(doc, context)

			if self.channel == "System Notification" or self.send_system_notification:
				self.create_system_notification(doc, context)

			if self.channel == "Task":
				self.create_task(doc, context)
		except Exception as e:
			self.log_error(f"Failed to send Notification: {str(e)}")

	def get_assign_to_user(self, doc, context):
		assign_to_users = []

		for recipient in self.recipients:
			if recipient.condition:
				if not frappe.safe_eval(recipient.condition, None, context):
					continue
			if recipient.receiver_by_document_field:
				fields = recipient.receiver_by_document_field.split(",")
				# fields from child table
				if len(fields) > 1:
					for d in doc.get(fields[1]):
						assign_to_users.append(d.get(fields[0]))
				# field from parent doc
				else:
					assign_to_users.append(doc.get(fields[0]))

		return set(assign_to_users)

	def create_task(self, doc, context):
		"""Create Task from Notification"""
		assign_to_users = self.get_assign_to_user(doc, context)
		try:
			# Render subject and message using templates
			task_subject_template = Template(self.subject)
			formatted_subject = task_subject_template.render(doc=doc)
			task_description_template = Template(self.message)
			formatted_message = task_description_template.render(doc=doc)

			# Calculate end date based on frequency
			days_to_add = int(self.exp_end_date_after) if self.exp_end_date_after else 0
			exp_end_date = nowdate()
			if self.frequency == "Day":
				exp_end_date = add_days(exp_end_date, days_to_add)
			elif self.frequency == "Month":
				exp_end_date = add_months(exp_end_date, days_to_add)
			elif self.frequency == "Year":
				exp_end_date = add_years(exp_end_date, days_to_add)

			# Create new Task document
			task = frappe.new_doc("Task")
			task.subject = formatted_subject
			task.exp_start_date = nowdate()
			task.description = formatted_message
			task.exp_end_date = exp_end_date
			task.type = self.type
			task.project = self.project
			task.priority = self.priority
			task.flags.ignore_mandatory = True
			if self.assignee and doc.get(self.assignee):
				task.assignee = doc.get(self.assignee)
			task.save(ignore_permissions=True)

			for assignment in self.assignment:
				assign_to.add(
					dict(
						assign_to=[assignment.assignment],
						doctype="Task",
						name=task.name,
						description=formatted_message,
						priority=self.priority,
						notify=True,
					),
					ignore_permissions=True,
				)
			for assign_to_user in assign_to_users:
				if assign_to_user == "Guest" or not assign_to_user:
					continue

				assign_to.add(
					dict(
						assign_to=[assign_to_user],
						doctype="Task",
						name=task.name,
						description=formatted_message,
						priority=self.priority,
						notify=True,
					),
					ignore_permissions=True,
				)
			frappe.msgprint("Task Created and Assigned Successfully")
			return task
		except Exception as e:
			frappe.log_error(f"Error in creating task: {str(e)}", "Notification Task Creation Error")
			frappe.msgprint("Failed to create task.", alert=True)

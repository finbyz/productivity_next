import frappe
from frappe import _
import frappe.utils
from frappe.desk.form.assign_to import set_status

from erpnext.projects.doctype.task.task import Task as _Task

from frappe.model.workflow import set_workflow_state_on_action, WorkflowPermissionError, get_workflow, get_transitions


class Task(_Task):

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		approver: DF.Link
		assignee: DF.Link
		process_flow = DF.Link
	
	def validate_workflow(self):
		"""Validate if the workflow transition is valid"""
		if frappe.flags.in_install == "frappe":
			return
		workflow = self.meta.get_workflow()
		if workflow:
			validate_workflow(self)
			if not self._action == "save":
				set_workflow_state_on_action(self, workflow, self._action)
	
	def before_validate(self):
		self.set_completed_on_and_completed_by()
		self.set_color()

	def validate_status(self):
		if self.is_template and self.status != "Template":
			self.status = "Template"
		if self.status != self.get_db_value("status") and self.status == "Completed":
			for d in self.depends_on:
				if frappe.db.get_value("Task", d.task, "status") not in ("Completed", "Cancelled"):
					frappe.throw(
						_(
							"Cannot complete task {0} as its dependant task {1} are not completed / cancelled."
						).format(frappe.bold(self.name), frappe.bold(d.task))
					)

			clomplete_all_assignments(self.doctype, self.name)
	
	def validate(self):
		super().validate()
		self.validate_status()
	
	def on_update(self):
		self.assign_to_assignee_and_task_approver()
	
	def validate_status(self):
		if self.status == "Scheduled" and (not self.exp_start_date or not self.exp_end_date):
			frappe.throw("Expected Start Date and Expected End Date are required to set this task's status to Scheduled.")
		
		if self.exp_start_date and self.exp_end_date and self.status in ["Unplanned", "Open"]:
			self.workflow_state = "Scheduled"
			self.status = "Scheduled"
	
	def assign_to_assignee_and_task_approver(self):
		if self.assignee and not frappe.get_value("ToDo", filters={'reference_type': "Task", 'reference_name': self.name, 'allocated_to': self.assignee, 'status': ['!=', 'Cancelled']}):
			frappe.desk.form.assign_to.add({
				'assign_to': [self.assignee],
				'doctype': "Task",
				'name': self.name,
				'description': f"Task assigned to {self.assignee}",
				'assign_by': frappe.session.user  # Correct user session reference
			})
		
		for row in self.approver:
			if not frappe.get_value("ToDo", filters={'reference_type': "Task", 'reference_name': self.name, 'allocated_to': row.user, 'status': ['!=', 'Cancelled']}):
				frappe.desk.form.assign_to.add({
				'assign_to': [row.user],
				'doctype': "Task",
				'name': self.name,
				'description': f"Task Approver assigned to {row.user}",
				'assign_by': frappe.session.user  # Correct user session reference
			})
		
	
	def set_completed_on_and_completed_by(self):
		if self.status == "Completed":
			if not self.completed_on:
				self.completed_on = frappe.utils.nowdate()
			if not self.completed_by and frappe.session.user != "Administrator":
				self.completed_by = frappe.session.user
		else:
			self.completed_on = None
			self.completed_by = None
	
	def set_color(self):
		match self.status:
			case "Completed":
				self.color = "#e4f5e9"
			case "Cancelled":
				self.color = "#f3f3f3"
			case "Open":
				self.color = "#fff1e7"
			case "Overdue":
				self.color = "#fff0f0"
			case "Working":
				self.color = "#fff7d3"
			case "Pending Review":
				self.color = "#fcd4fc"
			case _:
				self.color = None

	@frappe.whitelist()
	def fetch_process_flow_steps(self):
		return frappe.get_all(
			"Process Flow Step", 
			filters={"parenttype": "Process Flow", "parent": self.process_flow}, 
			order_by="idx", 
			fields=['process_step', 'description', 'document_url']
		)

	@frappe.whitelist()
	def fetch_process_flow_checks(self):
		return frappe.get_all(
			"Process Flow Check", 
			filters={"parenttype": "Process Flow", "parent": self.process_flow}, 
			order_by="idx", 
			fields=['required_check']
		)


def clomplete_all_assignments(doctype, name, ignore_permissions=False):
	assignments = frappe.get_all(
		"ToDo",
		fields=["allocated_to", "name"],
		filters=dict(reference_type=doctype, reference_name=name, status=("!=", "Cancelled")),
	)
	if not assignments:
		return False

	for assign_to in assignments:
		set_status(
			doctype,
			name,
			todo=assign_to.name,
			assign_to=assign_to.allocated_to,
			status="Completed",
			ignore_permissions=ignore_permissions,
		)

	return True

def validate_workflow(doc):
	"""Validate Workflow State and Transition for the current user.

	- Check if user is allowed to edit in current state
	- Check if user is allowed to transition to the next state (if changed)
	"""
	workflow = get_workflow(doc.doctype)

	current_state = None
	if getattr(doc, "_doc_before_save", None):
		current_state = doc._doc_before_save.get(workflow.workflow_state_field)
	next_state = doc.get(workflow.workflow_state_field)

	if not next_state:
		next_state = workflow.states[0].state
		doc.set(workflow.workflow_state_field, next_state)

	if not current_state:
		current_state = workflow.states[0].state

	state_row = [d for d in workflow.states if d.state == current_state]
	if not state_row:
		frappe.throw(
			_("{0} is not a valid Workflow State. Please update your Workflow and try again.").format(
				frappe.bold(current_state)
			)
		)
	state_row = state_row[0]

	# if transitioning, check if user is allowed to transition
	if current_state != next_state:
		bold_current = frappe.bold(current_state)
		bold_next = frappe.bold(next_state)

		if not doc._doc_before_save:
			# transitioning directly to a state other than the first
			# e.g from data import
			return
			# frappe.throw(
			# 	_("Workflow State transition not allowed from {0} to {1}").format(bold_current, bold_next),
			# 	WorkflowPermissionError,
			# )

		transitions = get_transitions(doc._doc_before_save)
		transition = [d for d in transitions if d.next_state == next_state]
		if not transition:
			frappe.throw(
				_("Workflow State transition not allowed from {0} to {1}").format(bold_current, bold_next),
				WorkflowPermissionError,
			)
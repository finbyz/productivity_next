import frappe
from frappe import _
import frappe.utils
from frappe.desk.form.assign_to import set_status
from frappe.desk.form.assign_to import clear
from frappe.utils import flt

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
		self.validate_parent_task()

	def validate_parent_task(self):
		"""
		Validate parent task to ensure that a task is not made a child of itself
		
		Args:
			self (Document): Task document being saved
		"""
		
		if self.name == self.parent_task:
			frappe.throw(_("Task cannot be a child of itself"))
		
		if self.parent_task and not frappe.get_cached_value('Task', self.parent_task, 'is_group'):
			frappe.throw(_("Is Group must be checked for parent task"))
		
		if self.parent_task and frappe.get_cached_value("Task", self.parent_task, "project") != self.project:
			frappe.throw(_("Parent Task must belong to the same project"))

	def validate_status(self):
		# Added this code
		if self.status == "Scheduled" and (not self.exp_start_date or not self.exp_end_date):
			frappe.throw("Expected Start Date and Expected End Date are required to set this task's status to Scheduled.")
		
		if self.exp_start_date and self.exp_end_date and self.status in ["Unplanned", "Open"]:
			self.workflow_state = "Scheduled"
			self.status = "Scheduled"

		if self.is_group and self.status not in ["Open", "Completed", "Cancelled"]:
			self.status = "Open"
		# Code ended here
		
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

			clomplete_all_assignments(self.doctype, self.name) # Instead of closing all assignments, we will complete them
	
	def validate(self):
		super().validate()
		self.validate_status()
	
	def on_update(self):
		super().on_update()
		self.assign_to_assignee_and_task_approver()
		self.update_if_is_group()
		self.update_parent_task()
   
	# def update_parent_task(self):
	# 	if self.parent_task:
	# 		parent_tasks = frappe.db.sql(f"""
	# 			WITH RECURSIVE parent_task AS (
	# 				SELECT * FROM `tabTask` WHERE name = '{self.name}'
	# 				UNION ALL
	# 				SELECT t.* FROM `tabTask` t
	# 				INNER JOIN parent_task pt ON t.name = pt.parent_task
	# 			)
	# 			SELECT distinct name FROM parent_task WHERE is_group = 1
	# 		""", pluck='name')
			
	# 		for parent_task in parent_tasks:
	# 			sum_child_task = frappe.db.sql(f"""
	# 				WITH RECURSIVE `task_tree` AS (
	# 					SELECT * FROM `tabTask` WHERE name = '{parent_task}'
	# 					UNION ALL
	# 					SELECT t.* FROM `tabTask` t
	# 					INNER JOIN task_tree tt ON t.parent_task = tt.name
	# 				)
	# 				SELECT SUM(expected_time) AS total_expected_time
	# 				FROM (
	# 					SELECT DISTINCT name, expected_time FROM task_tree WHERE is_group != 1
	# 				) AS unique_tasks
	# 			""")
				
				
	# 			if sum_child_task:
	# 				expected_time = flt(sum_child_task[0][0] or 0)
	# 			else:
	# 				expected_time = 0
				
	# 			frappe.db.set_value("Task", parent_task, "expected_time", expected_time, update_modified=False)
	def update_parent_task(self):
		if self.parent_task:
			parent_tasks = frappe.db.sql(f"""
				WITH RECURSIVE parent_task AS (
					SELECT * FROM `tabTask` WHERE name = '{self.name}'
					UNION ALL
					SELECT t.* FROM `tabTask` t
					INNER JOIN parent_task pt ON t.name = pt.parent_task
				)
				SELECT DISTINCT name FROM parent_task WHERE is_group = 1
			""", pluck='name')
			
			for parent_task in parent_tasks:
				# Expected time
				sum_child_task = frappe.db.sql(f"""
					WITH RECURSIVE task_tree AS (
						SELECT * FROM `tabTask` WHERE name = '{parent_task}'
						UNION ALL
						SELECT t.* FROM `tabTask` t
						INNER JOIN task_tree tt ON t.parent_task = tt.name
					)
					SELECT SUM(expected_time) AS total_expected_time
					FROM (
						SELECT DISTINCT name, expected_time FROM task_tree WHERE is_group != 1
					) AS unique_tasks
				""")

				# Date range
				date_range = frappe.db.sql(f"""
					WITH RECURSIVE task_tree AS (
						SELECT * FROM `tabTask` WHERE name = '{parent_task}'
						UNION ALL
						SELECT t.* FROM `tabTask` t
						INNER JOIN task_tree tt ON t.parent_task = tt.name
					)
					SELECT 
						MIN(exp_start_date) AS min_start,
						MAX(exp_end_date) AS max_end
					FROM (
						SELECT DISTINCT name, exp_start_date, exp_end_date FROM task_tree WHERE is_group != 1
					) AS unique_tasks
				""", as_dict=True)

				# Check if all are completed
				all_completed = frappe.db.sql(f"""
					WITH RECURSIVE task_tree AS (
						SELECT * FROM `tabTask` WHERE name = '{parent_task}'
						UNION ALL
						SELECT t.* FROM `tabTask` t
						INNER JOIN task_tree tt ON t.parent_task = tt.name
					)
					SELECT COUNT(*) 
					FROM (
						SELECT DISTINCT name, status FROM task_tree WHERE is_group != 1
					) AS leaf_tasks
					WHERE status != 'Completed'
				""")[0][0] == 0

				# Latest completed_on & completed_by
				latest_completed = frappe.db.sql(f"""
					WITH RECURSIVE task_tree AS (
						SELECT * FROM `tabTask` WHERE name = '{parent_task}'
						UNION ALL
						SELECT t.* FROM `tabTask` t
						INNER JOIN task_tree tt ON t.parent_task = tt.name
					)
					SELECT completed_on, completed_by FROM (
						SELECT DISTINCT name, completed_on, completed_by FROM task_tree 
						WHERE is_group != 1 AND status = 'Completed'
					) AS completed_tasks
					ORDER BY completed_on DESC
					LIMIT 1
				""", as_dict=True)

				expected_time = flt(sum_child_task[0][0] or 0) if sum_child_task else 0
				exp_start_date = date_range[0]["min_start"] if date_range else None
				exp_end_date = date_range[0]["max_end"] if date_range else None
				status = "Completed" if all_completed else "Open"
				completed_on = latest_completed[0]["completed_on"] if (all_completed and latest_completed) else None
				completed_by = latest_completed[0]["completed_by"] if (all_completed and latest_completed) else None

				# Update parent task
				frappe.db.set_value("Task", parent_task, {
					"expected_time": expected_time,
					"exp_start_date": exp_start_date,
					"exp_end_date": exp_end_date,
					"status": status,
					"completed_on": completed_on,
					"completed_by": completed_by
				}, update_modified=False)



	def update_if_is_group(self):
		if self.is_group:
			self.status = "Open"
			
			sum_child_task = frappe.db.sql(f"""
				WITH RECURSIVE `task_tree` AS (
					SELECT * FROM `tabTask` WHERE name = '{self.name}'
					UNION ALL
					SELECT t.* FROM `tabTask` t
					INNER JOIN task_tree tt ON t.parent_task = tt.name
				)
				SELECT SUM(expected_time) AS total_expected_time
				FROM (
					SELECT DISTINCT name, expected_time FROM task_tree WHERE is_group != 1
				) AS unique_tasks
			""")
			
			if sum_child_task:
				self.db_set('expected_time', flt(sum_child_task[0][0]))
			else:
				self.db_set('expected_time', 0)
			
	def unassign_todo(self):
		if self.status == "Completed":
			clomplete_all_assignments(self.doctype, self.name)
		if self.status == "Cancelled":
			clear(self.doctype, self.name)

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
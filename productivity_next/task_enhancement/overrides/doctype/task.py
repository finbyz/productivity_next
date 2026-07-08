import frappe
from frappe import _
import frappe.utils
from frappe.desk.form.assign_to import set_status
from frappe.desk.form.assign_to import clear
from frappe.utils import flt
from datetime import date
from erpnext.projects.doctype.task.task import Task as _Task

from frappe.model.workflow import set_workflow_state_on_action, WorkflowPermissionError, get_workflow, get_transitions


class Task(_Task):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.projects.doctype.task_depends_on.task_depends_on import TaskDependsOn
		from frappe.types import DF

		act_end_date: DF.Date | None
		act_start_date: DF.Date | None
		actual_time: DF.Float
		closing_date: DF.Date | None
		color: DF.Color | None
		company: DF.Link | None
		completed_by: DF.Link | None
		completed_on: DF.Date | None
		department: DF.Link | None
		depends_on: DF.Table[TaskDependsOn]
		depends_on_tasks: DF.Code | None
		description: DF.TextEditor | None
		duration: DF.Int
		exp_end_date: DF.Date | None
		exp_start_date: DF.Date | None
		expected_time: DF.Float
		is_group: DF.Check
		is_milestone: DF.Check
		is_template: DF.Check
		issue: DF.Link | None
		lft: DF.Int
		old_parent: DF.Data | None
		parent_task: DF.Link | None
		priority: DF.Literal["Low", "Medium", "High", "Urgent"]
		progress: DF.Percent
		project: DF.Link | None
		review_date: DF.Date | None
		rgt: DF.Int
		start: DF.Int
		status: DF.Literal["Open", "Working", "Pending Review", "Overdue", "Template", "Completed", "Cancelled"]
		subject: DF.Data
		task_weight: DF.Float
		template_task: DF.Data | None
		total_billing_amount: DF.Currency
		total_costing_amount: DF.Currency
		type: DF.Link | None
	# end: auto-generated types
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
		if self.status == "Scheduled" and (
			not self.exp_start_date or not self.exp_end_date
		):
			frappe.throw(
				_(
					"Expected Start Date and Expected End Date are required to set this task's status to Scheduled."
				)
			)

		if (
			self.exp_start_date
			and self.exp_end_date
			and self.status in {"Unplanned", "Open"}
		):
			self.workflow_state = "Scheduled"
			self.status = "Scheduled"

		if self.is_group and self.status not in {"Open", "Completed", "Cancelled"}:
			self.status = "Open"

		if self.is_template and self.status != "Template":
			self.status = "Template"

		# Only validate dependencies when transitioning to Completed
		if self.status != "Completed" or not self.has_value_changed("status"):
			return

		dependency_tasks = [d.task for d in self.depends_on]

		if dependency_tasks:
			incomplete_task = frappe.get_all(
				"Task",
				filters={
					"name": ["in", dependency_tasks],
					"status": ["not in", ["Completed", "Cancelled"]],
				},
				pluck="name",
				limit_page_length=1,
			)

			if incomplete_task:
				frappe.throw(
					_(
						"Cannot complete task {0} as its dependant task {1} is not completed / cancelled."
					).format(
						frappe.bold(self.name),
						frappe.bold(incomplete_task[0]),
					)
				)

		clomplete_all_assignments(self.doctype, self.name)
	def validate(self):
		super().validate()
		self.validate_status()
		self.validate_parent_expected_end_date()
	
	def on_update(self):
		super().on_update()
		self.assign_to_assignee_and_task_approver()
		self.update_if_is_group()
		self.update_parent_task()
		self.check_employee_fincall_for_lead()
		
	def validate_parent_expected_end_date(self):
		if not self.parent_task or not self.exp_end_date:
			return

		parent_exp_end_date = frappe.db.get_value("Task", self.parent_task, "exp_end_date")
		if not parent_exp_end_date:
			return

		# if getdate(self.exp_end_date) > getdate(parent_exp_end_date):
		# 	frappe.throw(
		# 		_(
		# 			"Expected End Date should be less than or equal to parent task's Expected End Date {0}."
		# 		).format(format_date(parent_exp_end_date)),
		# 		frappe.exceptions.InvalidDates,
		# 	)
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
		if not self.parent_task:
			return

		# Skip expensive recursive update when nothing relevant has changed.
		# This is the primary performance guard — without it every save
		# triggers multiple recursive CTEs for every ancestor group.
		_watched = (
			"status",
			"expected_time",
			"exp_start_date",
			"exp_end_date",
			"completed_on",
			"completed_by",
		)
		if not self.is_new() and not any(self.has_value_changed(f) for f in _watched):
			return

		# Walk upward once to collect all ancestor group tasks.
		parent_tasks = frappe.db.sql(
			"""
			WITH RECURSIVE parent_task AS (
				SELECT name, parent_task, is_group
				FROM `tabTask`
				WHERE name = %(name)s
				UNION ALL
				SELECT t.name, t.parent_task, t.is_group
				FROM `tabTask` t
				INNER JOIN parent_task pt ON t.name = pt.parent_task
			)
			SELECT DISTINCT name FROM parent_task WHERE is_group = 1
			""",
			{"name": self.name},
			pluck="name",
		)

		for parent_task in parent_tasks:
			# Single combined CTE: replaces 5 separate recursive queries.
			# The tree is walked only once per parent; all aggregates are
			# computed in a single pass over the leaf-task result set.
			result = frappe.db.sql(
				"""
				WITH RECURSIVE task_tree AS (
					SELECT name, parent_task, is_group,
						   expected_time, exp_start_date, exp_end_date,
						   status, completed_on, completed_by
					FROM `tabTask`
					WHERE name = %(parent)s
					UNION ALL
					SELECT t.name, t.parent_task, t.is_group,
						   t.expected_time, t.exp_start_date, t.exp_end_date,
						   t.status, t.completed_on, t.completed_by
					FROM `tabTask` t
					INNER JOIN task_tree tt ON t.parent_task = tt.name
				),
				leaf_tasks AS (
					SELECT DISTINCT name, expected_time, exp_start_date,
						   exp_end_date, status, completed_on, completed_by
					FROM task_tree
					WHERE is_group != 1
				)
				SELECT
					SUM(expected_time)                                         AS total_expected_time,
					MIN(exp_start_date)                                        AS min_start,
					MAX(exp_end_date)                                          AS max_end,
					SUM(CASE WHEN status != 'Completed' THEN 1 ELSE 0 END)     AS incomplete_count,
					MAX(CASE WHEN status = 'Completed' THEN completed_on END)  AS latest_completed_on,
					(SELECT completed_by
					 FROM leaf_tasks
					 WHERE status = 'Completed'
					 ORDER BY completed_on DESC
					 LIMIT 1)                                                  AS latest_completed_by
				FROM leaf_tasks
				""",
				{"parent": parent_task},
				as_dict=True,
			)

			if not result:
				continue

			row = result[0]
			all_completed = row.incomplete_count == 0

			frappe.db.set_value(
				"Task",
				parent_task,
				{
					"expected_time": flt(row.total_expected_time or 0),
					"exp_start_date": row.min_start,
					"exp_end_date": row.max_end,
					"status": "Completed" if all_completed else "Open",
					"completed_on": row.latest_completed_on if all_completed else None,
					"completed_by": row.latest_completed_by if all_completed else None,
				},
				update_modified=False,
			)

	def update_if_is_group(self):
		if self.is_group:
			self.status = "Open"

			sum_child_task = frappe.db.sql(
				f"""
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
			"""
			)

			if sum_child_task:
				self.db_set("expected_time", flt(sum_child_task[0][0]))
			else:
				self.db_set("expected_time", 0)

	def unassign_todo(self):
		if self.status == "Completed":
			clomplete_all_assignments(self.doctype, self.name)
		if self.status == "Cancelled":
			clear(self.doctype, self.name)

	def assign_to_assignee_and_task_approver(self):
		# Only run on first save or when assignee / approver list has changed
		# to avoid redundant ToDo lookups on every unrelated save.
		assignee_changed = self.is_new() or self.has_value_changed("assignee")
		approver_changed = self.is_new() or self.has_value_changed("approver")

		if assignee_changed and self.assignee:
			if not frappe.get_value(
				"ToDo",
				filters={
					"reference_type": "Task",
					"reference_name": self.name,
					"allocated_to": self.assignee,
					"status": ["!=", "Cancelled"],
				},
			):
				frappe.desk.form.assign_to.add(
					{
						"assign_to": [self.assignee],
						"doctype": "Task",
						"name": self.name,
						"description": f"Task assigned to {self.assignee}",
						"assign_by": frappe.session.user,
					}
				)

		if approver_changed:
			for row in self.approver:
				if not frappe.get_value(
					"ToDo",
					filters={
						"reference_type": "Task",
						"reference_name": self.name,
						"allocated_to": row.user,
						"status": ["!=", "Cancelled"],
					},
				):
					frappe.desk.form.assign_to.add(
						{
							"assign_to": [row.user],
							"doctype": "Task",
							"name": self.name,
							"description": f"Task Approver assigned to {row.user}",
							"assign_by": frappe.session.user,
						}
					)

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

	def check_employee_fincall_for_lead(self):
		# Guard 1: Only relevant when the task is being marked Completed.
		# Skip the DB config query entirely on every other save.
		if self.status != "Completed" or not self.has_value_changed("status"):
			return

		# Guard 2: Needs a linked lead and a start date to validate.
		if not self.lead or not self.exp_start_date:
			return

		config = frappe.db.sql(
			"""
			SELECT 
				MAX(CASE WHEN field = 'validate_marketing_follow_up_with_calls' THEN value END) AS validate_marketing_follow_up_with_calls,
				MAX(CASE WHEN field = 'default_marketing_project' THEN value END) AS default_marketing_project,
				MAX(CASE WHEN field = 'task_type' THEN value END) AS task_type
			FROM `tabSingles`
			WHERE doctype = 'Productify Configuration'
		""",
			as_dict=True,
		)

		if not config or not frappe.utils.cint(
			config[0].validate_marketing_follow_up_with_calls
		):
			return

		if (
			self.project != config[0].default_marketing_project
			or config[0].task_type != self.type
		):
			return

		today = date.today()
		fincall_exists = frappe.db.exists(
			"Employee Fincall",
			{"link_name": self.lead, "date": ["between", [self.exp_start_date, today]]},
		)

		communication_exists = frappe.db.sql(
			"""
			SELECT 1
			FROM `tabCommunication`
			WHERE reference_name = %s
			AND communication_date >= %s
			LIMIT 1
			""",
			(self.lead, self.exp_start_date),
		)

		has_attachment = frappe.db.exists(
			"File", {"attached_to_doctype": self.doctype, "attached_to_name": self.name}
		)

		if not fincall_exists and not has_attachment and not communication_exists:
			frappe.throw(
				_(
					"No follow-up found for this Lead. Please attach a screenshot of the follow-up on Email or WhatsApp as evidence for closure of this task."
				)
			)

	@frappe.whitelist()
	def fetch_process_flow_steps(self):
		return frappe.get_all(
			"Process Flow Step",
			filters={"parenttype": "Process Flow", "parent": self.process_flow},
			order_by="idx",
			fields=["process_step", "description", "document_url"],
		)

	@frappe.whitelist()
	def fetch_process_flow_checks(self):
		return frappe.get_all(
			"Process Flow Check",
			filters={"parenttype": "Process Flow", "parent": self.process_flow},
			order_by="idx",
			fields=["required_check"],
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

	
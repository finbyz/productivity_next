# -*- coding: utf-8 -*-
# Copyright (c) 2017, FinByz Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import msgprint, db, _
import json
from frappe.utils import cint, getdate, get_fullname, get_url_to_form,now_datetime, get_datetime
# from erpnext.accounts.party import get_party_details
from productivity_next.productivity_next.doctype.meeting_schedule.meeting_schedule import get_party_details

class Meeting(Document):
	def before_submit(self):
		if not self.subject:
			frappe.throw(_("Subject is mandatory before submit"))

	def validate(self):
		# The Task made on submit needs an assignee ("Pending On"); manual meetings may
		# leave the organizer empty, so it defaults to whoever enters the meeting.
		if not self.meeting_arranged_by and frappe.session.user not in ("Guest", "Administrator"):
			self.meeting_arranged_by = frappe.session.user
		if self.internal_meeting :
			self.organization = "Internal Meeting"
		if self.party_type and self.party:
			data = get_party_details(party_type=self.party_type,party=self.party)
			if data:
				self.contact_person = data.contact_person
				self.email_id = data.contact_email
				self.mobile_no = data.contact_mobile
				self.contact = data.contact_dispaly
				self.address = data.customer_address
				self.address_display = data.address_display
				self.organization = data.organisation

		if self.meeting_from and self.meeting_to:
			if self.meeting_from > self.meeting_to:
				frappe.throw(_("Meeting To Date must be after Meeting From Date"))
		
		self.check_min_participants()
		# Convert meeting_from and meeting_to to datetime objects
		meeting_from = get_datetime(self.meeting_from)
		meeting_to = get_datetime(self.meeting_to)
		# Check employee duplication in the 'meeting_company_representative' child table
		employee_list = []
		for representative in self.meeting_company_representative:
			if representative.employee in employee_list:
				frappe.throw(_("Employee {0} ({1}) is already in this meeting.").format(representative.employee, representative.employee_name))
			employee_list.append(representative.employee)
		# Check overlapping meetings for each representative in the 'meeting_company_representative' child table
			overlapping_employee_meetings = frappe.db.sql("""
				SELECT
					m.name, m.meeting_from, m.meeting_to
				FROM
					`tabMeeting` m
				JOIN
					`tabMeeting Company Representative` cr ON cr.parent = m.name
				WHERE
					cr.employee = %(employee)s
					AND (m.meeting_from <= %(meeting_to)s AND m.meeting_to >= %(meeting_from)s)
					AND m.name != %(name)s
					AND m.docstatus = 1
			""", {
				'meeting_from': meeting_from,
				'meeting_to': meeting_to,
				'employee': representative.employee,
				'name': self.name
			})
			
			# If there are overlapping meetings for the representative, throw a validation error
			if overlapping_employee_meetings:
				employee_meeting_links = "\n".join(
					[f'<a href="/app/meeting/{meeting[0]}">{meeting[0]}</a>' for meeting in overlapping_employee_meetings]
				)
				frappe.throw(f"Employee {representative.employee} already has a meeting during this time period:\n{employee_meeting_links}")

		if self.party_type == "Lead":
			customer = frappe.db.sql("""select lead_name, name from `tabCustomer` where lead_name = %s""", self.party, as_dict=1)
			if customer:
				self.party = customer[0].name
				self.party_type = "Customer"
				frappe.msgprint("This Lead was already converted to Customer. Now the Party Type is changed to Customer")
			else:
				pass

	def on_submit(self):
		user_name = frappe.db.get_value("Employee",{"user_id":frappe.session.user},"employee_name")
		url = get_url_to_form("Meeting", self.name)
		# url = "http://erp.finbyz.in/desk#Form/Lead%20Meeting/" + self.name
		if user_name:
			discussed = "<strong><a href="+url+">"+self.name+"</a>: </strong>"+ user_name + " Met "+ str(self.contact_person) + " On "+ str(self.meeting_from) +"<br>" + (self.discussion or "").replace('\n', "<br>")
		else:
			discussed = "<strong><a href="+url+">"+self.name+"</a>: </strong>"+ frappe.session.user + " Met "+ str(self.contact_person)+ " On "+ str(self.meeting_from) +"<br>" + (self.discussion or "").replace('\n', "<br>")

		cm = frappe.new_doc("Comment")
		cm.subject = self.name
		cm.comment_type = "Comment"
		cm.content = discussed
		cm.reference_doctype = self.party_type
		cm.reference_name = self.party
		cm.comment_email = frappe.session.user
		cm.comment_by = user_name
		cm.save(ignore_permissions=True)
		if self.party_type == "Lead":
			target_lead = frappe.get_doc("Lead", self.party)
			target_lead.status = "Meeting Done"
			target_lead.contact_by = self.contact_by
			target_lead.contact_date = self.contact_date
			if not target_lead.email_id:
				target_lead.email_id = self.email_id
			if not target_lead.lead_name:
				target_lead.lead_name = self.contact_person
			if not target_lead.mobile_no:
				target_lead.mobile_no = self.mobile_no
			target_lead.save(ignore_permissions=True)
		
		# When submit the Meeting then will create the Event
		for d in self.get('actionables'):
			if d.expected_completion_date:
				date_obj = get_datetime(d.expected_completion_date)
				starts_on = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
				ends_on = date_obj.replace(hour=23, minute=59, second=59, microsecond=999999)
				new_event = frappe.get_doc(dict(
					doctype = 'Event',
					subject = " - ".join(filter(None, [d.actionable, d.responsible])),
					event_category = "Meeting",
					# mandatory on Event; AI-created actionables leave it empty
					event_type = d.event_type or "Private",
					starts_on = starts_on,
					ends_on = ends_on,
					description = self.discussion
				))
				new_event.append('event_participants', {
					'reference_doctype': "Meeting", 'reference_docname': self.name
					})
				new_event.save(ignore_permissions=True)
		self.check_min_participants()
  
		if self.longitude and self.latitude and self.address:
			frappe.db.set_value("Address",self.address,"latitude",self.latitude)
			frappe.db.set_value("Address",self.address,"longitude",self.longitude)

		# --- Create Task on Submit ---
		# Prepare subject
		company_reps = ', '.join([rep.employee_name or rep.employee for rep in self.meeting_company_representative])
		party_reps = ', '.join([rep.contact for rep in self.meeting_party_representative])
		project_name = frappe.db.get_value("Project", self.project, "project_name")
		subject = f"Meeting by {self.meeting_arranged_by} for {project_name or ''} with {company_reps} and {party_reps}"

		# Create Task
		if not self.task:
			task = frappe.new_doc("Task")
			task.subject = self.subject
			task.description = subject
			task.project = self.project
			task.type = "Internal Meeting" if self.organization == "Internal Meeting" else "External Meeting"
			task.status = "Completed"
			task.completed_by = self.meeting_arranged_by or frappe.session.user
			task.completed_on = self.meeting_to
			task.exp_start_date = self.meeting_from
			task.exp_end_date = self.meeting_to
			task.reference_type = "Meeting"
			task.reference_name = self.name
			task.assignee = self.meeting_arranged_by or frappe.session.user
			task.save(ignore_permissions=True)
			# Link Task to Meeting
			self.db_set("task", task.name)


	def check_min_participants(self):
		if self.internal_meeting == 1:
			if len(self.get('meeting_company_representative')) < 2:
				frappe.throw(_("Please add atleast two Participants"))

@frappe.whitelist()
def get_events(start, end, filters=None):
	"""Returns events for Gantt / Calendar view rendering.
	:param start: Start date-time.
	:param end: End date-time.
	:param filters: Filters (JSON).
	"""
	#filters = json.loads(filters)
	from frappe.desk.calendar import get_event_conditions
	conditions = get_event_conditions("Meeting", filters)

	data = frappe.db.sql("""
			select 
				name, meeting_from, meeting_to, organization, party
			from 
				`tabMeeting`
			where
				(meeting_from <= %(end)s and meeting_to >= %(start)s) {conditions}
			""".format(conditions=conditions),
				{
					"start": start,
					"end": end
				}, as_dict=True, update={"allDay": 0})

	if not data:
		return []
		
	data = [x.name for x in data]

	return frappe.db.get_list("Meeting",
		{ "name": ("in", data), "docstatus":1 },
		["name", "meeting_from", "meeting_to", "organization", "party"]
	)


# ---------------------------------------------------------------------------
# Visibility: a Meeting is visible only to the people involved in it — its creator,
# its organizer (meeting_arranged_by; Teams meetings are created by the webhook as
# Guest) and its internal participants (Company Representatives) — and to their
# managers: anyone above them in the Employee "Reports To" tree, at any depth (the same
# hierarchy User Permissions on Employee follow). Roles in MEETING_SEE_ALL_ROLES and
# Administrator see every Meeting.
# Wired in hooks.py: permission_query_conditions covers list/report view, search and
# link fields; has_permission covers opening, editing, printing and the API.
# User Permissions do not narrow this: Meeting's link fields set ignore_user_permissions.
# ---------------------------------------------------------------------------

MEETING_SEE_ALL_ROLES = {"System Manager"}


def _sees_all_meetings(user):
	return user == "Administrator" or bool(MEETING_SEE_ALL_ROLES & set(frappe.get_roles(user)))


def _meeting_team(user):
	"""Employees and users whose meetings `user` may see: the user's own Employee
	records plus everyone reporting to them, directly or indirectly. Cached per request."""
	cache = getattr(frappe.local, "meeting_visibility_team", None)
	if cache is None:
		cache = frappe.local.meeting_visibility_team = {}
	if user not in cache:
		employees = set(frappe.get_all("Employee", filters={"user_id": user}, pluck="name"))
		frontier = list(employees)
		while frontier:
			juniors = frappe.get_all("Employee", filters={"reports_to": ["in", frontier]}, pluck="name")
			frontier = [e for e in juniors if e not in employees]
			employees.update(frontier)

		users = {user}
		if employees:
			users.update(
				u for u in frappe.get_all(
					"Employee", filters={"name": ["in", list(employees)]}, pluck="user_id"
				) if u
			)
		cache[user] = (employees, users)
	return cache[user]


def get_permission_query_conditions(user=None):
	user = user or frappe.session.user
	if _sees_all_meetings(user):
		return ""

	employees, users = _meeting_team(user)
	in_users = ", ".join(frappe.db.escape(u) for u in users)
	# emp_user_id is copied onto the row from the Employee; also match on the Employee
	# itself so a row with an empty or stale emp_user_id still counts
	participant = f"rep.emp_user_id IN ({in_users})"
	if employees:
		participant += " OR rep.employee IN ({})".format(", ".join(frappe.db.escape(e) for e in employees))

	return f"""(`tabMeeting`.owner = {frappe.db.escape(user)}
		OR `tabMeeting`.meeting_arranged_by IN ({in_users})
		OR EXISTS (
			SELECT 1 FROM `tabMeeting Company Representative` rep
			WHERE rep.parent = `tabMeeting`.name AND rep.parenttype = 'Meeting'
			  AND ({participant})
		))"""


def has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if _sees_all_meetings(user):
		return True

	if doc.is_new() or doc.owner == user:
		return True

	employees, users = _meeting_team(user)
	if doc.get("meeting_arranged_by") in users:
		return True
	for rep in doc.get("meeting_company_representative") or []:
		if rep.get("emp_user_id") in users or rep.get("employee") in employees:
			return True

	return False

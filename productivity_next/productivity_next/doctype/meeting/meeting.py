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
	def validate(self):
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
			discussed = "<strong><a href="+url+">"+self.name+"</a>: </strong>"+ user_name + " Met "+ str(self.contact_person) + " On "+ self.meeting_from +"<br>" + self.discussion.replace('\n', "<br>")
		else:
			discussed = "<strong><a href="+url+">"+self.name+"</a>: </strong>"+ frappe.session.user + " Met "+ str(self.contact_person)+ " On "+ self.meeting_from +"<br>" + self.discussion.replace('\n', "<br>")

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
			target_lead.turnover = self.turnover
			target_lead.business_specifics = self.business_specifics
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
					subject = d.actionable +' - '+ d.responsible,
					event_category = "Meeting",
					event_type = d.event_type,
					starts_on = starts_on,
					ends_on = ends_on,
					description = self.discussion
				))
				new_event.append('event_participants', {
					'reference_doctype': "Meeting", 'reference_docname': self.name
					})
				new_event.save(ignore_permissions=True)
		self.check_min_participants()


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
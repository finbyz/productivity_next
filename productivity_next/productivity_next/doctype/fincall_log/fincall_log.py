# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import datetime
from datetime import datetime


class FincallLog(Document):
	def save_fincall_log(self):
		if not self.employee_fincall_generated:
			doctype = None
			docname = None
			
			if contact := (
				frappe.db.get_value(
					"Contact Phone",
					{"phone": ["like", f"%{self.customer_no}%"], "parenttype": "Contact"},
					"parent",
				)
			):
				doctype = "Contact"
				docname = contact
			
			elif lead := (
				frappe.db.get_value("Lead", {"mobile_no": ["like", f"%{self.customer_no}%"]}, "name")
			):
				doctype = "Lead"
				docname = lead
			
			if doctype and docname:
				frappe.enqueue(
					self.create_employee_log,
					doctype=doctype,
					docname=docname,
					job_name="Employee FinCall Generation",
					enqueue_after_commit=True
				)
				self.create_employee_log("Contact", contact)
	
	def validate(self):
		set_date(self)
		if not self.get("__islocal"):
			self.save_fincall_log()

	def after_insert(self):
		self.save_fincall_log()

	def create_employee_log(self, doctype, docname, party_type=None, party=None):
		employee_details = frappe.db.get_value(
			"Employee",
			self.employee,
			["name", "employee_name"],
			as_dict=1,
		)
		if employee_details:
			ec_doc = frappe.new_doc("Employee Fincall")
			ec_doc.employee = employee_details.name
			ec_doc.employee_name = employee_details.employee_name
			ec_doc.mobile_no = self.employee_mobile
			ec_doc.receiver_number = self.customer_no
			ec_doc.link_to = doctype
			ec_doc.contact = docname
			if doctype == "Contact" and not (party_type and party):
				dynamic_data = frappe.db.get_value(
					"Dynamic Link",
					{"parent": docname, "parenttype": doctype},
					["link_doctype", "link_name"],
					order_by="idx desc",
					as_dict=1,
				)
				if dynamic_data:
					ec_doc.attach_to_doctype = dynamic_data.link_doctype
					ec_doc.attach_to_docname = dynamic_data.link_name

			elif party_type and party:
				ec_doc.attach_to_doctype = party_type
				ec_doc.attach_to_docname = party

			ec_doc.call_datetime = self.call_datetime
			# ec_doc.time = self.time
			ec_doc.call_duration = self.duration
			ec_doc.call_type = self.calltype
			ec_doc.fincall_log_ref = self.name
			try:
				ec_doc.phone_contact_name = self.client.split("(")[0]
			except:
				pass

			ec_doc.flags.ignore_permissions = True
			ec_doc.save()
			self.db_set("employee_fincall_generated", 1)

def set_date(self):
	datetime_str=frappe.db.get_value("Fincall Log",self.name,"call_datetime")
	datetime_obj = datetime.strptime(datetime_str, "%d%b%Y%H%M%S")
	date = datetime_obj.date()

@frappe.whitelist()
def bg_employee_log_generation():
	call_logs = frappe.db.get_all(
		"Fincall Log", {"employee_fincall_generated": 0, "ignore_contact": 0}
	)
	if call_logs:
		frappe.enqueue(
			enqueue_logs,
			call_logs=call_logs,
			queue="long",
			job_name="Employee Log Generation",
		)
		frappe.msgprint("Log generation has started in Background")


def enqueue_logs(call_logs):
	for row in call_logs:
		if not frappe.db.exists("Employee Fincall", {"fincall_log_ref": row.name}):
			call_doc = frappe.get_doc("FinCall Log", row.name)
			call_doc.save()
		elif frappe.db.exists("Employee Fincall", {"fincall_log_ref": row.name}):
			frappe.db.set_value(
				" FinCall Log", row.name, "employee_fincall_generated", 1
			)


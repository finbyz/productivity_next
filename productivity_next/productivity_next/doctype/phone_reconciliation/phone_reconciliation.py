# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PhoneReconciliation(Document):
	@frappe.whitelist()
	def get_unreconciled_numbers(self):
		self.call_details = []

		condition = ""
		if self.employee:
			employee = frappe.db.get_value(
				"Employee",
				self.employee,
				["custom_company_mobile", "employee_name"],
				as_dict=1,
			)

			if not employee.custom_company_mobile:
				frappe.throw("Please mention company number in Employee")

			condition += f"AND employee_mobile = '{employee.custom_company_mobile}'"

		if self.from_date:
			condition += f"AND creation >= '{self.from_date}'"

		if self.to_date:
			condition += f"AND creation <= '{self.to_date}'"

		call_data = frappe.db.sql(
			f"""
				SELECT DISTINCT employee_mobile, customer_no, client
				FROM `tabFincall Log`
				WHERE employee_fincall_generated = 0 and ignore_contact = 0 and contact_created = 0 {condition}
			""",
			as_dict=1,
		)

		for row in call_data:
			if not self.employee:
				employee = frappe.db.get_value(
					"Employee",
					# {"custom_company_mobile": row.employee_mobile},
					self.employee,
					["name", "employee_name"],
					as_dict=1,
				)
			if not employee:
				employee = {}
			self.append(
				"call_details",
				{
					"employee": self.employee or employee.get("name"),
					"employee_name": employee.get("employee_name"),
					"mobile_no": row.customer_no,
					"client_details": row.client,
				},
			)

	@frappe.whitelist()
	def allocate_phone_numbers(self):
		remove_rows = []
		for row in self.call_details:
			update_row = False
			contact = None
			if row.contact and not row.ignore_contact and not row.contact_created:
				contact_doc = frappe.get_doc("Contact", row.contact)
				if row.salutation:
					contact_doc.salutation = row.salutation
				existing_links = {
					i.link_name: i.link_doctype for i in contact_doc.links
				}
				existing_numbers = [i.phone for i in contact_doc.phone_nos]
				if row.mobile_no not in existing_numbers:
					contact_doc.append("phone_nos", {"phone": row.mobile_no})
				if row.party and not existing_links.get(row.party):
					contact_doc.append(
						"links",
						{"link_doctype": row.party_type, "link_name": row.party},
					)
				contact_doc.flags.ignore_permissions = True
				contact_doc.save()
				contact = row.contact
				update_row = True

			elif (
				row.party_type
				and row.party
				and row.first_name
				and not row.ignore_contact
				and not row.contact_created
			):
				contact = create_contact(
					row.mobile_no,
					row.first_name,
					row.party_type,
					row.party,
					row.last_name,
					row.salutation,
				)
				update_row = True
			if update_row:
				self.append(
					"allocation_logs",
					{
						"employee": row.employee,
						"employee_name": row.employee_name,
						"client_details": row.client_details,
						"mobile_no": row.mobile_no,
						"contact": contact,
						"employee": row.employee,
						"party_type": row.party_type,
						"party": row.party,
						"first_name": row.first_name,
						"last_name": row.last_name,
					},
				)

				remove_rows.append(row.idx - 1)
				frappe.enqueue(
					create_emp_logs,
					contact=contact,
					client_no=row.mobile_no,
					party_type=row.party_type,
					party=row.party,
					queue="long",
				)
		return sorted(remove_rows)


@frappe.whitelist()
def create_contact(
	client_no, first_name, party_type, party, last_name=None, salutation=None
):
	contact_doc = frappe.new_doc("Contact")
	contact_doc.salutation = salutation
	contact_doc.first_name = first_name
	contact_doc.last_name = last_name
	contact_doc.append("links", {"link_doctype": party_type, "link_name": party})
	contact_doc.append("phone_nos", {"phone": client_no})
	contact_doc.flags.ignore_permissions = True
	contact_doc.save()

	return contact_doc.name


@frappe.whitelist()
def ignore_contact(client_no):
	ign_doc = frappe.new_doc("Ignored Contact")
	ign_doc.customer_contact = client_no
	ign_doc.ignored_by = frappe.session.user
	ign_doc.flags.ignore_permissions = True
	ign_doc.save()

	frappe.db.sql(
		f"""
		UPDATE `tabFincall Log`
		SET ignore_contact = 1
		WHERE customer_no = '{client_no}'
	"""
	)


def create_emp_logs(contact, client_no, party_type, party):
	Fincall_logs = frappe.db.get_all(
		"Fincall Log", {"customer_no": client_no}
	)
	for row in Fincall_logs:
		call_doc = frappe.get_doc("Fincall Log", row.name)
		call_doc.create_employee_log("Contact", contact, party_type, party)
		call_doc.contact_created = 1
		call_doc.flags.ignore_permissions = 1
		call_doc.save()


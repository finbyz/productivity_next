# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime
from frappe.utils import get_datetime
from frappe.utils import cint


class PhoneReconciliation(Document):
    @frappe.whitelist()
    def get_unreconciled_numbers(self):
        self.phone_reconciliation_call = []

        condition = ""
        if self.employee:
            # employee = frappe.db.get_value(
            # 	"Employee",
            # 	self.employee,
            # 	["custom_company_mobile", "employee_name"],
            # 	as_dict=1,
            # )

            # if not employee.custom_company_mobile:
            # 	frappe.throw("Please mention company number in Employee")

            condition += f"AND employee = '{self.employee}'"

        if self.from_date and self.to_date :
            condition += f"AND call_datetime BETWEEN '{get_datetime(self.from_date)}' AND '{get_datetime(self.to_date)}'"

        call_data = frappe.db.sql(
            f"""
                SELECT DISTINCT employee_mobile, customer_no, client
                FROM `tabFincall Log`
                WHERE employee_fincall_generated = 0 and ignore_contact = 0 and contact_created = 0 {condition}
            """,
            as_dict=1,
        )
        if call_data:
            for row in call_data:
                # frappe.throw(str(row))
                if self.employee:
                    employee = frappe.db.get_value(
                        "Employee",
                        self.employee,
                        "employee_name",
                        as_dict=1,
                    )
                    self.append(
                        "phone_reconciliation_call",
                        {
                            "employee": self.employee,
                            "employee_name": employee.get("employee_name"),
                            "client_details": row.client,
                            "client_no": row.customer_no,
                        },
                    )
        else:
            frappe.msgprint("No Unreconciled Numbers Found")
    @frappe.whitelist()
    def allocate_phone_numbers(self):
        remove_rows = []
        for row in self.phone_reconciliation_call:
            update_row = False
            contact = None
            if row.contact and not row.ignore_contact and not row.contact_created:
                contact_doc = frappe.get_doc("Contact", row.contact)
                frappe.throw(str(contact_doc))
                if row.salutation:
                    contact_doc.salutation = row.salutation
                existing_links = {
                    i.link_name: i.link_doctype for i in contact_doc.links
                }
                existing_numbers = [i.phone for i in contact_doc.phone_nos]
                if row.client_no not in existing_numbers:
                    contact_doc.append("phone_nos", {"phone": row.client_no})
                if row.party and not existing_links.get(row.party):
                    contact_doc.append(
                        "links",
                        {"link_doctype": row.party_type, "link_name": row.party},
                    )
                contact_doc.flags.ignore_permissions = True
                contact_doc.save()
                contact = row.contact
                frappe.throw("update_row")

                update_row = True
            elif (
                row.party_type
                and row.party
                and row.first_name
                and not row.ignore_contact
                and not row.contact_created
            ):
                contact = create_contact(
                    row.client_no,
                    row.first_name,
                    row.party_type,
                    row.party,
                    row.last_name,
                    row.salutation,
                    row.is_primary_mobile_no,
                    row.is_primary_phone,
                    row.client_email,
                    row.is_primary_email,
                )
                update_row = True
                frappe.throw(update_row)
            if update_row:
                self.append(
                    "allocation_logs",
                    {
                        "employee": row.employee,
                        "employee_name": row.employee_name,
                        "client_details": row.client_details,
                        "client_no": row.client_no,
                        "contact": contact,
                        "employee": row.employee,
                        "party_type": row.party_type,
                        "party": row.party,
                        "first_name": row.first_name,
                        "last_name": row.last_name,
                    },
                )
                frappe.throw("MAI YAHAN HUN")
                remove_rows.append(row.idx - 1)
                frappe.enqueue(
                    create_emp_logs,
                    contact=contact,
                    client_no=row.client_no,
                    party_type=row.party_type,
                    party=row.party,
                    queue="long",
                )
        return sorted(remove_rows)

@frappe.whitelist()
def update_contact(client_email, client_no, update_client, is_primary_phone, is_primary_email, is_primary_mobile_no,party_type, party):
    contact_doc = frappe.get_doc("Contact", update_client)
    
    is_primary_phone = True if is_primary_phone == "1" else False
    is_primary_email = True if is_primary_email == "1" else False
    is_primary_mobile_no = True if is_primary_mobile_no == "1" else False
    
    if client_no != "0" and not client_no in [row.phone for row in contact_doc.phone_nos]:
        if is_primary_phone or is_primary_mobile_no:
            for row in contact_doc.phone_nos:
                row.is_primary_phone = 0
                row.is_primary_mobile_no = 0
        
        contact_doc.append("phone_nos", {
            "phone": client_no, 
            "is_primary_phone": 1 if is_primary_phone else 0, 
            "is_primary_mobile_no": 1 if is_primary_mobile_no else 0
        })

    if party_type and party and not party in [row.link_name for row in contact_doc.links]:
        contact_doc.append("links", {"link_doctype": party_type, "link_name": party})



    if client_email != "0" and not client_email in [row.email_id for row in contact_doc.email_ids]:
        if is_primary_email:
            for row in contact_doc.email_ids:
                row.is_primary = 0
                
        contact_doc.append("email_ids", {
            "email_id": client_email, 
            "is_primary": 1 if is_primary_email else 0
        })

    contact_doc.flags.ignore_permissions = True
    contact_doc.save()
    frappe.msgprint("Contact has been updated.")
    # fincall_log = frappe.db.get_all("Fincall Log", {"customer_no": client_no})
    # for row in fincall_log:
    #     call_doc = frappe.get_doc("Fincall Log", row.name)
    #     call_doc.create_employee_log("Contact", contact_doc.name)
    #     call_doc.contact_created = 1
    #     call_doc.flags.ignore_permissions = 1
    #     call_doc.save()



@frappe.whitelist()
def create_contact(is_primary_mobile_no, is_primary_phone, is_primary_email, client_email, client_no, first_name, party_type, party, last_name=None, salutation=None):	
    contact_doc = frappe.new_doc("Contact")
    contact_doc.salutation = salutation
    contact_doc.first_name = first_name
    contact_doc.last_name = last_name
    contact_doc.append("links", {"link_doctype": party_type, "link_name": party})
    if client_no != "0":
        contact_doc.append("phone_nos", {"phone": client_no, "is_primary_mobile_no": is_primary_mobile_no, "is_primary_phone": is_primary_phone})
        
    if client_email != "0":
        contact_doc.append("email_ids", {"email_id": client_email, "is_primary": is_primary_email})
    
    contact_doc.flags.ignore_permissions = True
    contact_doc.save()  
    contact_doc_resave = frappe.get_doc("Contact", contact_doc.name)
    contact_doc_resave.flags.ignore_permissions = True
    contact_doc_resave.save()
    frappe.msgprint("Contact has been created.")
    # fincall_log = frappe.db.get_all("Fincall Log", {"customer_no": client_no})
    # for row in fincall_log:
    #     call_doc = frappe.get_doc("Fincall Log", row.name)
    #     call_doc.create_employee_log("Contact", contact_doc.name, party_type, party)
    #     call_doc.contact_created = 1
    #     call_doc.flags.ignore_permissions = 1
    #     call_doc.save()


@frappe.whitelist()
def ignore_contact(client_no):
    ign_doc = frappe.new_doc("Fincall Ignored Contact")
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

# def create_emp_logs(contact, client_no, party_type, party):
#     Fincall_logs = frappe.db.get_all(
#         "Fincall Log", {"customer_no": client_no}
#     )
#     for row in Fincall_logs:
#         call_doc = frappe.get_doc("Fincall Log", row.name)
#         call_doc.create_employee_log("Contact", contact, party_type, party)
#         call_doc.contact_created = 1
#         call_doc.flags.ignore_permissions = 1
#         call_doc.save()
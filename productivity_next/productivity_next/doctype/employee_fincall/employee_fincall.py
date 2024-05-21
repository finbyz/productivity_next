# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

class EmployeeFincall(Document):
    def validate(self):
        if not self.contact or self.contact == "" or self.contact == None:
            self.create_notification_log()
    def create_notification_log(self):
        doc = frappe.new_doc("Notification Log")
        doc.subject = "You need to create contact for {}".format(self.client)
        doc.for_user = frappe.db.get_value("Employee", self.employee, "user_id")
        doc.type = "Alert"
        doc.document_type = "Employee Fincall"
        doc.document_name = self.name
        doc.from_user = frappe.db.get_value("Employee", self.employee, "user_id")
        doc.flags.ignore_permissions = True
        doc.save()

@frappe.whitelist()
def update_contact( client_no, update_client, is_primary_phone, is_primary_mobile_no,party_type, party):
    contact_doc = frappe.get_doc("Contact", update_client)
    is_primary_phone = True if is_primary_phone == "1" else False
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


    contact_doc.flags.ignore_permissions = True
    contact_doc.save()
    frappe.msgprint("Contact has been updated.")
    fincall_log = frappe.db.get_all("Fincall Log", {"customer_no": client_no})
    for row in fincall_log:
        call_doc = frappe.get_doc("Fincall Log", row.name)
        call_doc.contact_created = 1
        call_doc.flags.ignore_permissions = 1
        call_doc.save()
        employee_fincall = frappe.db.get_all("Employee Fincall", {"customer_no": client_no})
    for row in employee_fincall:
        emp_call_doc = frappe.get_doc("Employee Fincall", row.name)
        emp_call_doc.contact = contact_doc.name
        emp_call_doc.link_to = party_type
        emp_call_doc.link_name = party
        emp_call_doc.flags.ignore_permissions = 1
        emp_call_doc.save()
            
@frappe.whitelist()
def create_contact(is_primary_mobile_no, is_primary_phone, client_no, first_name, party_type, party, last_name=None, salutation=None):	
    contact_doc = frappe.new_doc("Contact")
    contact_doc.salutation = salutation
    contact_doc.first_name = first_name
    contact_doc.last_name = last_name
    contact_doc.append("links", {"link_doctype": party_type, "link_name": party})
    if client_no != "0":
        contact_doc.append("phone_nos", {"phone": client_no, "is_primary_mobile_no": is_primary_mobile_no, "is_primary_phone": is_primary_phone})
    
    contact_doc.flags.ignore_permissions = True
    contact_doc.save()  
    contact_doc_resave = frappe.get_doc("Contact", contact_doc.name)
    contact_doc_resave.flags.ignore_permissions = True
    contact_doc_resave.save()
    frappe.msgprint("Contact has been created.")
    fincall_log = frappe.db.get_all("Fincall Log", {"customer_no": client_no})
    for row in fincall_log:
        call_doc = frappe.get_doc("Fincall Log", row.name)
        call_doc.contact_created = 1
        call_doc.flags.ignore_permissions = 1
        call_doc.save()
    employee_fincall = frappe.db.get_all("Employee Fincall", {"customer_no": client_no})
    for row in employee_fincall:
        emp_call_doc = frappe.get_doc("Employee Fincall", row.name)
        emp_call_doc.contact = contact_doc.name
        emp_call_doc.link_to = party_type
        emp_call_doc.link_name = party
        emp_call_doc.flags.ignore_permissions = 1
        emp_call_doc.save()
    

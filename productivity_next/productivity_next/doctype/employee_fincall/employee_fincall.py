# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

class EmployeeFincall(Document):
    def validate(self):
        if not self.contact or self.contact == "" or self.contact is None:
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
        
    @property
    def get_contact_name(self):
        contact = frappe.get_doc('Contact',self.contact,fields=["first_name+ ' ' +last_name as full_name"])
        return contact.first_name
    

    @property
    def get_svg(self) -> str:
        call_type = self.calltype.lower()
        if call_type == 'incoming':
            return '<img src="/assets/productivity_next/calltype/svg/outgoing.png">'
        elif call_type == 'outgoing':
            return '<img src="/assets/productivity_next/calltype/svg/incoming.png">'
        elif call_type == 'missed':
            return '<img src="/assets/productivity_next/calltype/svg/missed.png">'
        elif call_type == 'rejected':
            return '<img src="/assets/productivity_next/calltype/svg/rejected.png">'
        return ''
        
    def before_save(self):
        time_minutes = self.duration / 60
        comment = frappe.get_doc({
            'doctype': 'Comment',
            'comment_type': 'Comment',
            'reference_doctype': 'Customer',
            'reference_name': self.link_name,
            'comment_by':self.employee_name,
            'content': f"{ self.employee_name } {self.get_svg} call  { self.get_contact_name } at { self.call_datetime } for {time_minutes:.1f} minutes", # TODO : ADD - { if remarks } and discussed { remarks }
        }).insert()
        comment.save()
        print('Comment created',self.link_name)
        

@frappe.whitelist()
def update_contact(client_no, update_client, is_primary_phone, is_primary_mobile_no,party_type, party):
    frappe.enqueue(
                enqueue_update_contact,
                client_no=client_no,
                update_client=update_client,
                is_primary_phone=is_primary_phone,
                is_primary_mobile_no=is_primary_mobile_no,
                party_type=party_type,
                party=party,
                queue="long",
                job_name="Contact Updation",
            )
def enqueue_update_contact(client_no, update_client, is_primary_phone, is_primary_mobile_no,party_type, party):
    contact_doc = frappe.get_doc("Contact", update_client)
    is_primary_phone = True if is_primary_phone == "1" else False
    is_primary_mobile_no = True if is_primary_mobile_no == "1" else False
    
    if client_no != "0" and client_no not in [row.phone for row in contact_doc.phone_nos]:
        if is_primary_phone or is_primary_mobile_no:
            for row in contact_doc.phone_nos:
                row.is_primary_phone = 0
                row.is_primary_mobile_no = 0
        
        contact_doc.append("phone_nos", {
            "phone": client_no, 
            "is_primary_phone": 1 if is_primary_phone else 0, 
            "is_primary_mobile_no": 1 if is_primary_mobile_no else 0
        })

    if party_type and party and party not in [row.link_name for row in contact_doc.links]:
        contact_doc.append("links", {"link_doctype": party_type, "link_name": party})


    contact_doc.flags.ignore_permissions = True
    contact_doc.save()
    frappe.msgprint("Contact has been updated.")
            
@frappe.whitelist()
def create_contact(is_primary_mobile_no, is_primary_phone, client_no, first_name, party_type, party, last_name=None, salutation=None):
    frappe.enqueue(
                enqueue_create_contact,
                is_primary_mobile_no=is_primary_mobile_no,
                is_primary_phone=is_primary_phone,
                client_no=client_no,
                first_name=first_name,
                party_type=party_type,
                party=party,
                last_name=last_name,
                salutation=salutation,
                queue="long",
                job_name="Contact Creation",
            )	
    
def enqueue_create_contact(is_primary_mobile_no, is_primary_phone, client_no, first_name, party_type, party, last_name=None, salutation=None):
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
    

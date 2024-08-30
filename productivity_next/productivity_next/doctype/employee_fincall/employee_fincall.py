# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
from frappe.utils.data import format_datetime
from frappe.utils import format_duration


class EmployeeFincall(Document):
    def validate(self):
        if not self.contact or self.contact == "" or self.contact is None:
            self.create_notification_log()

    def create_notification_log(self):
        doc = frappe.new_doc("Notification Log")
        if self.client and self.client != "":
            subject_text = "You need to create contact for {}".format(self.client)
        else:
            subject_text = "You need to create contact for {}".format(self.customer_no)

        doc.subject = subject_text
        doc.for_user = frappe.db.get_value("Employee", self.employee, "user_id")
        doc.type = "Alert"
        doc.document_type = "Employee Fincall"
        doc.document_name = self.name
        doc.from_user = frappe.db.get_value("Employee", self.employee, "user_id")
        doc.flags.ignore_permissions = True
        doc.save()


    @property
    def get_contact_name(self):
        if frappe.db.exists("Contact", self.contact):
            contact = frappe.get_doc("Contact", self.contact)
            return f"{contact.first_name or ''} {contact.last_name if contact.last_name else ''}"
        return None

    def get_comment(self):
        if frappe.db.exists("Comment", self.comment):
            comment = frappe.get_doc("Comment", self.comment)
            return comment
        return None

    @property
    def get_svg(self) -> str:
        call_type = self.calltype.lower()
        if call_type == "incoming":
            return '<img src="/assets/productivity_next/calltype/svg/incomming.png">'
        elif call_type == "outgoing":
            return '<img src="/assets/productivity_next/calltype/svg/outgoing.png">'
        elif call_type == "missed":
            return '<img src="/assets/productivity_next/calltype/svg/missed.png">'
        elif call_type == "rejected":
            return '<img src="/assets/productivity_next/calltype/svg/rejected.png">'
        return ""

    def get_comment_text(self, employee_fincall_url) -> str:
        if self.get_contact_name is None:
            return ""
        call_time = format_duration(self.duration)
        formatted_datetime = format_datetime(self.call_datetime, "dd-MM-yyyy HH:mm:ss")
        spoken_about = f"<br><b>Discussed: </b><p>{self.spoke_about}</p>" if self.spoke_about else ""
        TEXT = (
            f"<b>{self.employee_name}</b> <a href='{employee_fincall_url}'>{self.get_svg}</a> "
            f"<b>{self.get_contact_name}</b> at {formatted_datetime} "
            f"for {call_time} {spoken_about}"
        )
        return TEXT

    def before_save(self):
        comment = self.get_comment()
        if not comment:
            return

        comment.update(
            {
                "content": self.get_comment_text(self.get_url()),
            }
        )
        comment.save()


@frappe.whitelist()
def update_contact(
    client_no, update_client, is_primary_phone, is_primary_mobile_no, party_type, party
):
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


def enqueue_update_contact(
    client_no, update_client, is_primary_phone, is_primary_mobile_no, party_type, party
):
    contact_doc = frappe.get_doc("Contact", update_client)
    is_primary_phone = True if is_primary_phone == "1" else False
    is_primary_mobile_no = True if is_primary_mobile_no == "1" else False

    if client_no != "0" and client_no not in [
        row.phone for row in contact_doc.phone_nos
    ]:
        if is_primary_phone or is_primary_mobile_no:
            for row in contact_doc.phone_nos:
                row.is_primary_phone = 0
                row.is_primary_mobile_no = 0

        contact_doc.append(
            "phone_nos",
            {
                "phone": client_no,
                "is_primary_phone": 1 if is_primary_phone else 0,
                "is_primary_mobile_no": 1 if is_primary_mobile_no else 0,
            },
        )

    if (
        party_type
        and party
        and party not in [row.link_name for row in contact_doc.links]
    ):
        contact_doc.append("links", {"link_doctype": party_type, "link_name": party})

    contact_doc.flags.ignore_permissions = True
    contact_doc.save()
    frappe.msgprint("Contact has been updated.")


@frappe.whitelist()
def create_contact(
    is_primary_mobile_no,
    is_primary_phone,
    client_no,
    first_name,
    party_type,
    party,
    last_name=None,
    salutation=None,
):
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


def enqueue_create_contact(
    is_primary_mobile_no,
    is_primary_phone,
    client_no,
    first_name,
    party_type,
    party,
    last_name=None,
    salutation=None,
):
    contact_doc = frappe.new_doc("Contact")
    contact_doc.salutation = salutation
    contact_doc.first_name = first_name
    contact_doc.last_name = last_name
    contact_doc.append("links", {"link_doctype": party_type, "link_name": party})
    if client_no != "0":
        contact_doc.append(
            "phone_nos",
            {
                "phone": client_no,
                "is_primary_mobile_no": is_primary_mobile_no,
                "is_primary_phone": is_primary_phone,
            },
        )

    contact_doc.flags.ignore_permissions = True
    contact_doc.save()
    contact_doc_resave = frappe.get_doc("Contact", contact_doc.name)
    contact_doc_resave.flags.ignore_permissions = True
    contact_doc_resave.save()
    frappe.msgprint("Contact has been created.")
    
def on_doctype_update():
    frappe.db.add_unique("Employee Fincall", ["date", "employee", "call_datetime","customer_no"])
    frappe.db.add_index("Employee Fincall", ["date", "employee", "calltype"])

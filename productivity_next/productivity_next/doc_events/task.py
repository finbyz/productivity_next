from frappe.model.document import Document
from frappe.utils import nowdate
import frappe
import json
def before_save(self, method):
    if self.status == "Completed":
        self.completed_on = nowdate()
        self.completed_by = frappe.session.user

    if self.status == "Completed":
        self.color = "#e4f5e9"
    elif self.status == "Cancelled":
        self.color = "#f3f3f3"
    elif self.status == "Open":
        self.color = "#fff1e7"
    elif self.status == "Overdue":
        self.color = "#fff0f0"
    elif self.status == "Working":
        self.color = "#fff7d3"
    elif self.status == "Pending Review":
        self.color = "#e3a3ff"

    # first_name = self.task_owner_.split('@')[0].split('.')[0].capitalize()
    # self.calendar_title = f'{self.subject} ({first_name})'

@frappe.whitelist()
def validate(self, method): 
    existing_assignment = frappe.get_all(
        'ToDo',
        filters={   
            'reference_type': "Task",
            'reference_name': self.name,
            'allocated_to': self.task_owner_
        }
    )

    if not existing_assignment:
        frappe.desk.form.assign_to.add({
            'assign_to': [self.task_owner_],
            'doctype': "Task",
            'name': self.name,
            'description': f"Task assigned to {self.task_owner_}",
            'assign_by': frappe.session.user  # Correct user session reference
        })

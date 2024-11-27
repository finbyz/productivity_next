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
        self.color = "#f7fbfd"

import json
import json

@frappe.whitelist()
def validate(doc): 
    # If `doc` is not already a dictionary, convert it from JSON string
    if isinstance(doc, str):
        doc_json = json.loads(doc)
    else:
        doc_json = doc

    # Check if `doc_json` is now a dictionary
    if not isinstance(doc_json, dict):
        frappe.throw("Invalid document format!")

    
    existing_assignment = frappe.get_all(
        'ToDo',
        filters={   
            'reference_type': "Task",
            'reference_name': doc_json["name"],  # Use the `name` field from JSON
            'allocated_to': doc_json["task_owner_"]  # Use the `task_owner_` field from JSON
        }
    )

    if not existing_assignment:
        frappe.desk.form.assign_to.add({
            'assign_to': [doc_json["task_owner_"]],
            'doctype': "Task",
            'name': doc_json["name"],
            'description': f"Task assigned to {doc_json['task_owner_']}",
            'assign_by': frappe.session.user  # Correct user session reference
        })

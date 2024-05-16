from __future__ import unicode_literals
import frappe

def execute():
    # List of indexes to create
    indexes = [
        {"doctype": "Application Usage log", "fields": ["employee", "date", "domain"]},
        {"doctype": "Fincall Log", "fields": ["employee", "date"]},
        {"doctype": "Meeting Company Representative", "fields": ["parent", "employee"]},
        {"doctype": "Meeting", "fields": ["meeting_from", "meeting_to"]},
        {"doctype": "Application Checkin Checkout", "fields": ["employee", "time"]},
        {"doctype": "Screen Screenshot Log", "fields": ["employee", "datetime"]},
        {"doctype": "Version", "fields": ["owner", "creation", "ref_doctype", "docname"]},
        {"doctype": "Version", "fields": ["creation", "ref_doctype", "docname"]},
        {"doctype": "Idle Time Log", "fields": ["employee", "time", "status"]}
    ]

    # Attempt to create each index, handling exceptions if index already exists
    for index in indexes:
        try:
            frappe.db.add_index(index["doctype"], index["fields"])
            print(f"Index added to {index['doctype']} on fields {index['fields']}")
        except Exception as e:
            print(f"Failed to add index to {index['doctype']} on fields {index['fields']}: {e}")

from __future__ import unicode_literals
import frappe

def execute():
    # List of indexes to create
    indexes = [
        {"doctype": "Fincall Log", "fields": ["employee", "date"]},
        {"doctype": "Meeting Company Representative", "fields": ["parent", "employee"]},
        {"doctype": "Meeting", "fields": ["meeting_from", "meeting_to"]},
        {"doctype": "Version", "fields": ["owner", "creation", "ref_doctype", "docname"]},
        {"doctype": "Version", "fields": ["creation", "ref_doctype", "docname"]},
        {"doctype": "Employee Fincall", "fields": ["employee", "customer_no", "calltype", "call_datetime"]},
        {"doctype": "URL Access Log", "fields": ["employee", "from_time", "to_time","domain"]}
    ]

    # Attempt to create each index, handling exceptions if index already exists
    for index in indexes:
        try:
            import frappe
            frappe.db.add_index(index["doctype"], index["fields"])
            print(f"Index added to {index['doctype']} on fields {index['fields']}")
        except Exception as e:
            print(f"Failed to add index to {index['doctype']} on fields {index['fields']}: {e}")
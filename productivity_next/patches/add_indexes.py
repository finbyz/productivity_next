from __future__ import unicode_literals
import frappe

def execute():
    # List of indexes to create
    indexes = [
        {"doctype": "Fincall Log", "fields": ["employee", "date"]},
        {"doctype": "Meeting Company Representative", "fields": ["parent", "employee"]},
        {"doctype": "Meeting", "fields": ["meeting_from", "meeting_to"]},
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

frappe.db.add_index("Version", ["modified_by","creation", "ref_doctype"])
frappe.db.add_index("Employee Fincall", ["date", "employee", "calltype"])
frappe.db.add_index("Application Usage log", ["date", "employee", "domain"])
frappe.db.add_index("Employee Idle Time",["date","employee"])
frappe.db.add_index("Productify Work Summary",["date","employee"])
frappe.db.add_index("Work Intensity",["employee","time"])
frappe.db.add_index("Screen Screenshot Log",["employee","time"])
frappe.db.add_index("Meeting",["meeting_from","meeting_to","docstatus"])
frappe.db.add_index("Meeting Company Representative",["employee"])
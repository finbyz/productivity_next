from __future__ import unicode_literals
import frappe

def execute():
    frappe.db.add_index("Application Usage log", ["employee", "date", "domain"])
    frappe.db.add_index("Fincall Log", ["employee", "date"])
    frappe.db.add_index("Meeting Company Representative", ["parent","employee"])
    frappe.db.add_index("Meeting", ["meeting_from","meeting_to"])
    frappe.db.add_index("Application Checkin Checkout", ["employee", "time"])
    frappe.db.add_index("Screen Screenshot Log", ["employee", "datetime"])
    frappe.db.add_index("Version", ["owner", "creation","ref_doctype","docname"])
    frappe.db.add_index("Idle Time Log", ["employee", "time","status"])
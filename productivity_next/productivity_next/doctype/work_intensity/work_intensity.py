# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WorkIntensity(Document):
    pass

def on_doctype_update():
    frappe.db.add_unique("Work Intensity", ["employee", "time"])
    frappe.db.add_index("Work Intensity",["employee","time"])
# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LocationLogs(Document):
	pass


# def on_doctype_update():
#     frappe.db.add_unique("Location Logs", ["employee", "date", "uuid"])
#     frappe.db.add_index("Location Logs", ["employee", "date", "time"])

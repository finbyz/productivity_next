# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

class ProductifyWorkSummary(Document):
	pass


def on_doctype_update():
	frappe.db.add_index("Productify Work Summary",["date","employee"])

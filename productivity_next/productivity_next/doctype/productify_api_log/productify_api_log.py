# Copyright (c) 2025, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ProductifyAPILog(Document):
	def validate(self):
		self.total_api_calls = sum(acf.frequency for acf in self.productify_api_call_frequency)

# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import time_diff_in_seconds


class EmployeeIdleTime(Document):
	def validate(self):
		self.duration = time_diff_in_seconds(self.to_time, self.from_time)

def on_doc_update(self):
	frappe.db.add_unique("Application Usage log", ["employee", "from_time", "to_time"])
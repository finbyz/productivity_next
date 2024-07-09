# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from frappe.utils import time_diff_in_seconds


class EmployeeIdleTime(Document):
	def validate(self):
		self.duration = time_diff_in_seconds(self.end_time, self.start_time)

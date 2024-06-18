# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from frappe.utils import time_diff_in_seconds
import frappe


class URLAccessLog(Document):
	def validate(self):
		self.domain=self.url.split('/')[2]
		self.duration = time_diff_in_seconds(self.to_time, self.from_time)
		if self.duration <=0:
		    raise frappe.ValidationError("To time should be greater than from time")

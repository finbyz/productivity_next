# Copyright (c) 2023, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import time_diff_in_seconds

import re

class ApplicationUsagelog(Document):
	def validate(self):
		if not self.ip_address:
			x_forwarded_for = frappe.get_request_header("X-Forwarded-For", str(frappe.request.headers))
			self.ip_address = re.search(r"^(.+)", x_forwarded_for).group(1)
		
		if not self.application_name and self.application_title:
			self.application_name = self.application_title.split("-")[-1].strip()
		
		self.duration = time_diff_in_seconds(self.to_time, self.from_time)

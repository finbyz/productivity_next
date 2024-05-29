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
		application_names = {"code.exe":"Visual Studio Code","chrome.exe":"Google Chrome","explorer.exe":"File Explorer"}
		if self.process_id:
			application_name = application_names.get(self.process_id, self.process_id)
			if application_name:
				self.application_name = application_name
			else:
				self.application_name = self.process_id.split(".exe")[0]
		
		self.duration = time_diff_in_seconds(self.to_time, self.from_time)

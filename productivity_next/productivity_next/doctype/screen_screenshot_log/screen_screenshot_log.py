# Copyright (c) 2023, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document

class ScreenScreenshotLog(Document):
	def validate(self):
		if not self.ip_address:
			x_forwarded_for = frappe.get_request_header("X-Forwarded-For", str(frappe.request.headers))
			self.ip_address = re.search(r"^(.+)", x_forwarded_for).group(1)
	
	def after_insert(self):
		if self.screenshot and self.name:
			if frappe.db.exists("File", {"file_url": self.screenshot}):
				frappe.db.set_value("File", self.screenshot, "attached_to_doctype", "Screen Screenshot Log", update_modified=False)
				frappe.db.set_value("File", self.screenshot, "attached_to_field", "screenshot", update_modified=False)
				frappe.db.set_value("File", self.screenshot, "attached_to_name", self.name, update_modified=False)


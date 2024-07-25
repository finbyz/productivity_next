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
	
	def on_update(self):
		if self.screenshot and self.name:
			if name:= frappe.db.get_value("File", filters={"folder": "Home/screenshots", "file_url": self.screenshot}, fieldname="name"):
				frappe.db.set_value("File", name, "attached_to_doctype", "Screen Screenshot Log", update_modified=False)
				frappe.db.set_value("File", name, "attached_to_field", "screenshot", update_modified=False)
				frappe.db.set_value("File", name, "attached_to_name", self.name, update_modified=False)


def on_doctype_update():
	frappe.db.add_unique("Screen Screenshot Log", ["employee", "time"])
	frappe.db.add_index("Screen Screenshot Log",["employee","time"])
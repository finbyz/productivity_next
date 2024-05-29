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
		application_names = {"code.exe":"Visual Studio Code","chrome.exe":"Google Chrome","explorer.exe":"File Explorer","ApplicationFrameHost.exe":"Whatsapp","Skype.exe":"Skype","notepad++.exe":"Notepad++","Notepad.exe":"Notepad",
		"msedge.exe":"Microsoft Edge","firefox.exe":"Mozilla Firefox","AnyDesk.exe":"Any Desk","python.exe":"Python","powershell.exe":"Powershell","cmd.exe":"Command Prompt","devenv.exe":"Visual Studio","outlook.exe":"Outlook","excel.exe":"Excel","winword.exe":"Word","powerpnt.exe":"Powerpoint",}
		if self.process_id:
			application_name = application_names.get(self.process_id)
			if application_name:
				self.application_name = application_name
			else:
				self.application_name = (self.process_id).split(".exe")[0].capitalize()
		if not self.process_id:
			if not self.application_name and self.application_title:
				self.application_name = self.application_title.split("-")[-1].strip()
		
		self.duration = time_diff_in_seconds(self.to_time, self.from_time)
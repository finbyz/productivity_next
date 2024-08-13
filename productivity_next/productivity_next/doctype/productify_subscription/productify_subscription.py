# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests
import json


class ProductifySubscription(Document):
	def validate(self):
		if not self.site_url:
			self.site_url = frappe.utils.get_url()
		
		frappe.enqueue(self.update_application_usage_log, enqueue_after_commit=True)
		frappe.enqueue(self.update_fincall_log, enqueue_after_commit=True)

		
	def update_application_usage_log(self):
		if self.application_usage:
			url = "https://productivity.finbyz.tech/api/method/productivity_backend.api.organization_signup"

			list_of_users = [{
				"employee_id": row.employee,
				"email": row.user_id,
				"full_name": row.employee_name,
				"status": row.status,
			} for row in self.list_of_users if row.application_usage]

			data = {
				"domain": self.site_url,
				"organization_name": self.organization_name,
				"contact_person_name": self.name,
				"contact_person_email": self.email,
				"contact_person_phone": self.mobile_no,
				"list_of_users": list_of_users,
				"plan": "Application Usage",
			}

			response = requests.post(url, json=data)

			return response.json()
	
	def update_fincall_log(self):
		if self.fincall:
			url = "https://productivity.finbyz.tech/api/method/productivity_backend.api.organization_signup"

			list_of_users = [{
				"employee_id": row.employee,
				"email": row.user_id,
				"full_name": row.employee_name,
				"status": row.status,
			} for row in self.list_of_users if row.fincall]

			data = {
				"domain": self.site_url,
				"organization_name": self.organization_name,
				"contact_person_name": self.name,
				"contact_person_email": self.email,
				"contact_person_phone": self.mobile_no,
				"list_of_users": list_of_users,
				"plan": "Call Usage",
			}

			response = requests.post(url, json=data)

			return response.json()

# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests
import json


BASE_URL = "https://productivity.finbyz.tech"
CALL_LOG_URL = f"{BASE_URL}/api/resource/Productivity Call log Organization"
APPLICATION_ORG_URL = f"{BASE_URL}/api/resource/Productivity Application Organization"
class ProductifySubscription(Document):
    def validate(self):
        if not self.site_url:
            self.site_url = frappe.utils.get_url()
        self.remove_duplicate_users()
        frappe.enqueue(self.update_subscription, enqueue_after_commit=True)
        frappe.enqueue(self.update_application_list_of_users, enqueue_after_commit=True)
        frappe.enqueue(self.update_fincall_list_of_users, enqueue_after_commit=True)

    def remove_duplicate_users(self):
        users = set()
        self.list_of_users = [ row for row in self.list_of_users if row.user_id not in users and not users.add(row.user_id) ]
    
    def update_application_list_of_users(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"token {self.api_key}:{self.get_password('api_secret')}",
        }
        list_of_users = [
            {
                "employee_id": row.employee,
                "email": row.user_id,
                "full_name": row.employee_name,
                "status": row.status,
                "fincall": row.fincall,
                "application_usage": row.application_usage,
            }
            for row in self.list_of_users
        ]
        requests.put(
            f"{APPLICATION_ORG_URL}/{self.organization_name}",
            json={
                "list_of_users": list_of_users,
            },
            headers=headers,
        )
    
    def update_fincall_list_of_users(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"token {self.api_key}:{self.get_password('api_secret')}",
        }
        list_of_users = [
            {
                "employee_id": row.employee,
                "email": row.user_id,
                "full_name": row.employee_name,
                "status": row.status,
                "fincall": row.fincall,
                "application_usage": row.application_usage,
            }
            for row in self.list_of_users
        ]
        return requests.put(
            f"{CALL_LOG_URL}/{self.organization_name}",
            json={
                "list_of_users": list_of_users,
            },
            headers=headers,
        )

    def update_subscription(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"token {self.api_key}:{self.get_password('api_secret')}",
        }
        return requests.put(
            f"{APPLICATION_ORG_URL}/{self.organization_name}",
            json={
                "project_subscription": self.project,
                "issue_subscription": self.issue,
                "task_subscription": self.task,
                "sales_person_subscription": self.sales_person,
                "application_usage_subscription": self.application_usage,
                "fincall_subscription": self.fincall,
            },
            headers=headers,
        )

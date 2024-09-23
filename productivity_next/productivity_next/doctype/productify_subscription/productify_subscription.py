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
        if self.is_subscription_expired(type="application"):
            frappe.throw("Your Subscription is expired")
        if not self.site_url:
            self.site_url = frappe.utils.get_url()
        self.remove_duplicate_users()
        self.validate_fincall()
        self.validate_application_usage()
        frappe.enqueue(self.update_subscription, enqueue_after_commit=True)
        frappe.enqueue(self.update_application_list_of_users, enqueue_after_commit=True)
        frappe.enqueue(self.update_fincall_list_of_users, enqueue_after_commit=True)

    def validate_fincall(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"token {self.api_key}:{self.get_password('api_secret')}",
        }
        resp = requests.get(f"{CALL_LOG_URL}/{self.call_organization_name}", headers=headers)
        if resp.status_code == 200:
            resp = resp.json()["data"]
            no_users = resp.get("no_of_users",10)
            no_of_fincall_user = len([row for row in self.list_of_users if row.fincall])
            if no_users and no_of_fincall_user > no_users:
                frappe.msgprint(
                    f"You have taken Fincall subscription for {no_users} users while you have selected {no_of_fincall_user} users, please speak to your service provider to increase the number of subscription"
                )
    def validate_application_usage(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"token {self.api_key}:{self.get_password('api_secret')}",
        }
        resp = requests.get(f'{APPLICATION_ORG_URL}/{self.application_organization_name}?fields=["no_of_users"]', headers=headers)
        if resp.status_code == 200:
            resp = resp.json()["data"]
            no_users = resp.get("no_of_users",10)
            no_of_application_user = len([row for row in self.list_of_users if row.application_usage])
            if no_users and no_of_application_user > no_users:
                frappe.msgprint(
                    f"You have taken Application Usage subscription for {no_users} users while you have selected {no_of_application_user} users, please speak to your service provider to increase the number of subscription"
                )
                
    def remove_duplicate_users(self):
        users = set()
        self.list_of_users = [
            row
            for row in self.list_of_users
            if row.employee not in users and not users.add(row.employee)

        ]

    def update_application_list_of_users(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"token {self.api_key}:{self.get_password('api_secret')}",
        }
        response = requests.get(
            f"{APPLICATION_ORG_URL}/{self.application_organization_name}",
            params={"fields": ["list_of_users"]},
            headers=headers
        )
        if response.status_code == 200:
            existing_records = response.json().get('data',{}).get('list_of_users', [])
        else:
            frappe.log_error("Upadating productify user",response.text)

        record_dict = {record["employee_id"]: [record["name"],record['email_sent']] for record in existing_records}
        
        list_of_users = [
            {
                "name": record_dict.get(row.employee,["",False])[0],
                "email_sent": record_dict.get(row.employee,["",False])[1],
                "employee_id": row.employee,
                "email": row.user_id,
                "full_name": row.employee_name,
                "status": row.status,
                "fincall": row.fincall,
                "application_usage": row.application_usage,
                "parent": self.application_organization_name,
                "parentfield": "list_of_users",
                "parenttype": "Productivity Application Organization",
            }
            for row in self.list_of_users
        ]
        requests.put(
            f"{APPLICATION_ORG_URL}/{self.application_organization_name}",
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
        response = requests.get(
            f"{CALL_LOG_URL}/{self.call_organization_name}",
            params={"fields": ["list_of_users"]},
            headers=headers
        )
        if response.status_code == 200:
            existing_records = response.json().get('data',{}).get('list_of_users', [])
        else:
            frappe.log_error("Upadating productify user",response.text)

        record_dict = {record["employee_id"]: record["name"] for record in existing_records}
        
        list_of_users = [
            {
                "name": record_dict.get(row.employee),
                "employee_id": row.employee,
                "email": row.user_id,
                "full_name": row.employee_name,
                "status": row.status,
                "fincall": row.fincall,
                "application_usage": row.application_usage,
                "parent": self.call_organization_name,
                "parentfield": "list_of_users",
                "parenttype": "Productivity Call log Organization",
            }
            for row in self.list_of_users
        ]
        return requests.put(
            f"{CALL_LOG_URL}/{self.call_organization_name}",
            json={
                "list_of_users": list_of_users,
            },
            headers=headers,
        )

    def is_subscription_expired(self,type:str=None):
        URL = f"{APPLICATION_ORG_URL}/{self.application_organization_name}"
        if type == "fincall":
            URL = f"{CALL_LOG_URL}/{self.application_organization_name}"
        elif type == "application":
            URL = f"{APPLICATION_ORG_URL}/{self.application_organization_name}"
        else:
            URL = f"{APPLICATION_ORG_URL}/{self.application_organization_name}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"token {self.api_key}:{self.get_password('api_secret')}",
        }
        resp = requests.get(
            f"{URL}", headers=headers
        )
        if resp.status_code == 200:
            data = resp.json()["data"]
            valid_upto = data.get("valid_upto")
            return valid_upto and valid_upto < frappe.utils.nowdate()

        return False

    def update_subscription(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"token {self.api_key}:{self.get_password('api_secret')}",
        }
        return requests.put(
            f"{APPLICATION_ORG_URL}/{self.application_organization_name}",
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

# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from frappe.utils import time_diff_in_seconds,get_datetime
import frappe
import datetime


class URLAccessLog(Document):
    def validate(self):
        from_time = get_datetime(self.from_time)
        to_time = get_datetime(self.to_time)
        if frappe.db.exists("URL Access Log",{"employee":self.employee,"from_time":from_time,"to_time":to_time,"url":self.url}) or frappe.db.exists("URL Access Log",{"employee":self.employee,"from_time":from_time,"to_time":to_time-datetime.timedelta(seconds=1),"url":self.url}):
            frappe.throw("URL Access Log already exists for this time period.")
        if frappe.db.exists("URL Access Log",{"employee":self.employee,"from_time":from_time,"to_time":to_time+datetime.timedelta(seconds=1),"url":self.url}):
            name=frappe.get_doc("URL Access Log",{"employee":self.employee,"from_time":from_time,"to_time":to_time+datetime.timedelta(seconds=1),"url":self.url},pluck="name")
            frappe.delete_doc("URL Access Log",name)
        self.url = self.url or ''
        url_split = self.url.split('/')
        if len(url_split) > 3:
            self.domain=self.url.split('/')[2]
        self.duration = time_diff_in_seconds(to_time, from_time)
        if self.duration <=9:
            raise frappe.ValidationError("To time should be greater than from time and diffrance should be greater than equal 10 seconds.")

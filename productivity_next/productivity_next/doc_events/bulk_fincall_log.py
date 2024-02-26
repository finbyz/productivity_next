import frappe
import json

def validate(self, method):
    update_fincall_call(self)

def update_fincall_call(self):
    data = json.loads(self.fincall_logs)
    for i in str(data):
        doc = frappe.new_doc('Fincall Log')
        doc.employee_mobile = i["employee_mobile"]
        doc.customer_no = i["customer_no"]
        doc.employee = i["employee"]
        doc.client = i["client"]
        doc.calltype = i["calltype"]
        doc.employee_fincall_generated = i["employee_fincall_generated"]
        doc.contact_created = i["contact_created"]
        doc.duration = i["duration"]
        doc.note = i["note"]
        doc.raw_log = i["raw_log"]
        doc.call_datetime = i["call_datetime"]
        doc.insert()
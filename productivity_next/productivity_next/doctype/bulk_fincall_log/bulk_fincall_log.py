# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import json
import frappe
from datetime import datetime

class BulkFincallLog(Document):
	def validate(self):
		data = json.loads(self.fincall_logs)
		if data:
			frappe.enqueue(
			self.generate_fincall_log,
			bulk_fincall_log=data,
			queue="long",
			job_name="Fincall Log Generation",
			enqueue_after_commit=True,
			)
			frappe.msgprint("Fincall Log generation has started in Background")
	
	def generate_fincall_log(self, bulk_fincall_log):
		for i in bulk_fincall_log:
			doc = frappe.new_doc('Fincall Log')
			doc.employee_mobile = i["employee_mobile"]
			doc.customer_no = i["customer_no"]
			doc.employee = i["employee"]
			doc.client = i["client"]
			doc.calltype = i["calltype"].split(".")[1].capitalize()
			doc.employee_fincall_generated = i["employee_fincall_generated"]
			doc.contact_created = i["contact_created"]
			doc.duration = i["duration"]
			doc.note = i["note"]
			doc.raw_log = i["raw_log"]
			doc.call_datetime = datetime.utcfromtimestamp(int(i["call_datetime"]) / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')
			doc.insert()

# da = """[{"employee_mobile":"00820826","customer_no":"+917021735435","employee":"HR-EMP-00014","client":"Manoj Sharma Yogesh","calltype":"CallType.incoming","employee_fincall_generated":0,"contact_created":0,"duration":"57","note":"test3","raw_log":"code","call_datetime":"1709974110571"},{"employee_mobile":"00820826","customer_no":"7021735435","employee":"HR-EMP-00014","client":"Manoj Sharma Yogesh","calltype":"CallType.outgoing","employee_fincall_generated":0,"contact_created":0,"duration":"0","note":"test3","raw_log":"code","call_datetime":"1709973930008"},{"employee_mobile":"00820826","customer_no":"7021735435","employee":"HR-EMP-00014","client":"Manoj Sharma Yogesh","calltype":"CallType.outgoing","employee_fincall_generated":0,"contact_created":0,"duration":"0","note":"test3","raw_log":"code","call_datetime":"1709973858223"},{"employee_mobile":"00820826","customer_no":"7021735435","employee":"HR-EMP-00014","client":"Manoj Sharma Yogesh","calltype":"CallType.outgoing","employee_fincall_generated":0,"contact_created":0,"duration":"11","note":"test3","raw_log":"code","call_datetime":"1709971936102"},{"employee_mobile":"00820826","customer_no":"+919773267141","employee":"HR-EMP-00014","client":"null","calltype":"CallType.incoming","employee_fincall_generated":0,"contact_created":0,"duration":"73","note":"test3","raw_log":"code","call_datetime":"1709969461870"},{"employee_mobile":"00820826","customer_no":"9537499772","employee":"HR-EMP-00014","client":"Dhruvin Finbyz","calltype":"CallType.outgoing","employee_fincall_generated":0,"contact_created":0,"duration":"43","note":"test3","raw_log":"code","call_datetime":"1709957285829"},{"employee_mobile":"00820826","customer_no":"+917800863268","employee":"HR-EMP-00014","client":"Shiva B","calltype":"CallType.outgoing","employee_fincall_generated":0,"contact_created":0,"duration":"0","note":"test3","raw_log":"code","call_datetime":"1709956035985"},{"employee_mobile":"00820826","customer_no":"+918382087095","employee":"HR-EMP-00014","client":"null","calltype":"CallType.outgoing","employee_fincall_generated":0,"contact_created":0,"duration":"66","note":"test3","raw_log":"code","call_datetime":"1709954732980"}]"""
# data = json.loads(da)
# for i in data:
# 	doc = frappe.new_doc('Fincall Log')
# 	doc.employee_mobile = i["employee_mobile"]
# 	doc.customer_no = i["customer_no"]
# 	doc.employee = i["employee"]
# 	doc.client = i["client"]
# 	doc.calltype = i["calltype"].split(".")[1].capitalize()
# 	doc.employee_fincall_generated = i["employee_fincall_generated"]
# 	doc.contact_created = i["contact_created"]
# 	doc.duration = i["duration"]
# 	doc.note = i["note"]
# 	doc.raw_log = i["raw_log"]
# 	doc.call_datetime = datetime.utcfromtimestamp(int(i["call_datetime"]) / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')
# 	doc.insert()

# da = """[{"employee_mobile":"00820826","customer_no":"+917021735435","employee":"HR-EMP-00014","client":"Manoj Sharma Yogesh","calltype":"CallType.incoming","employee_fincall_generated":0,"contact_created":0,"duration":"57","note":"test3","raw_log":"code","call_datetime":"1709974110571"},{"employee_mobile":"00820826","customer_no":"7021735435","employee":"HR-EMP-00014","client":"Manoj Sharma Yogesh","calltype":"CallType.outgoing","employee_fincall_generated":0,"contact_created":0,"duration":"0","note":"test3","raw_log":"code","call_datetime":"1709973930008"},{"employee_mobile":"00820826","customer_no":"7021735435","employee":"HR-EMP-00014","client":"Manoj Sharma Yogesh","calltype":"CallType.outgoing","employee_fincall_generated":0,"contact_created":0,"duration":"0","note":"test3","raw_log":"code","call_datetime":"1709973858223"},{"employee_mobile":"00820826","customer_no":"7021735435","employee":"HR-EMP-00014","client":"Manoj Sharma Yogesh","calltype":"CallType.outgoing","employee_fincall_generated":0,"contact_created":0,"duration":"11","note":"test3","raw_log":"code","call_datetime":"1709971936102"},{"employee_mobile":"00820826","customer_no":"+919773267141","employee":"HR-EMP-00014","client":"null","calltype":"CallType.incoming","employee_fincall_generated":0,"contact_created":0,"duration":"73","note":"test3","raw_log":"code","call_datetime":"1709969461870"},{"employee_mobile":"00820826","customer_no":"9537499772","employee":"HR-EMP-00014","client":"Dhruvin Finbyz","calltype":"CallType.outgoing","employee_fincall_generated":0,"contact_created":0,"duration":"43","note":"test3","raw_log":"code","call_datetime":"1709957285829"},{"employee_mobile":"00820826","customer_no":"+917800863268","employee":"HR-EMP-00014","client":"Shiva B","calltype":"CallType.outgoing","employee_fincall_generated":0,"contact_created":0,"duration":"0","note":"test3","raw_log":"code","call_datetime":"1709956035985"},{"employee_mobile":"00820826","customer_no":"+918382087095","employee":"HR-EMP-00014","client":"null","calltype":"CallType.outgoing","employee_fincall_generated":0,"contact_created":0,"duration":"66","note":"test3","raw_log":"code","call_datetime":"1709954732980"}]"""
# data = json.loads(da)
# for i in data:
# 	call_datetime = datetime.utcfromtimestamp(int(i["call_datetime"]) / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')
# 	print(call_datetime)
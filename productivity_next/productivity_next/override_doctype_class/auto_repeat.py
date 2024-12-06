import frappe
from frappe.automation.doctype.auto_repeat.auto_repeat import AutoRepeat as _AutoRepeat
from frappe.utils import date_diff, nowdate, add_days, add_months, add_years


class AutoRepeat(_AutoRepeat):
	def update_doc(self, new_doc, reference_doc):
		new_doc.docstatus = 0
		if new_doc.meta.get_field("set_posting_time"):
			new_doc.set("set_posting_time", 1)

		if new_doc.meta.get_field("auto_repeat"):
			new_doc.set("auto_repeat", self.name)

		for fieldname in [
			"naming_series",
			"ignore_pricing_rule",
			"posting_time",
			"select_print_heading",
			"user_remark",
			"remarks",
			"owner",
		]:
			if new_doc.meta.get_field(fieldname):
				new_doc.set(fieldname, reference_doc.get(fieldname))

		for data in new_doc.meta.fields:
			if data.fieldtype == "Date" and data.reqd:
				new_doc.set(data.fieldname, self.next_schedule_date)

		self.set_auto_repeat_period(new_doc)
		self.set_start_and_end_date(new_doc, reference_doc)

		auto_repeat_doc = frappe.get_doc("Auto Repeat", self.name)

		# for any action that needs to take place after the recurring document creation
		# on recurring method of that doctype is triggered
		new_doc.run_method("on_recurring", reference_doc=reference_doc, auto_repeat_doc=auto_repeat_doc)
	
	def set_start_and_end_date(self, new_doc, reference_doc):
		for row in self.task_due_date or []:
			if row.date_field:
				if row.frequency == "Day":
					new_doc.set(row.date_field ,add_days(nowdate(), row.end_date_after))
				elif row.frequency == "Month":
					new_doc.set(row.date_field ,add_months(nowdate(), row.end_date_after))
				elif row.frequency == "Year":
					new_doc.set(row.date_field ,add_years(nowdate(), row.end_date_after))

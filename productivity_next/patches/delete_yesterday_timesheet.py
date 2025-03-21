import frappe
from frappe.utils import nowdate, add_days

def execute():
    yesterday = add_days(nowdate(), -1)
    timesheets = frappe.get_all("Timesheet", filters={"creation": [">=", yesterday], "creation": ["<", nowdate()]}, pluck="name")
    for ts in timesheets:
        doc = frappe.get_doc("Timehsheet", ts)
        doc.cancel()
        frappe.delete_doc("Timesheet", ts, force=True)
    frappe.db.commit()

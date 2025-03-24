import frappe
from frappe.utils import nowdate, add_days

def execute():
    yesterday = add_days(nowdate(), -1)
    timesheets = frappe.get_all(
        "Timesheet", 
        filters={
            "creation": ["between", [yesterday, yesterday]],
            "docstatus": 1
        },
        pluck="name"
    )
    for ts in timesheets:
        doc = frappe.get_doc("Timesheet", ts)
        doc.cancel()
        frappe.delete_doc("Timesheet", ts, force=True)

# NewV16: wrapped in execute() so that importing this module (e.g. via /api/method/<module>.x,
# which imports before the whitelist check) no longer runs it. Run on purpose with:
#   bench --site <site> execute productivity_next.Update_enable_productify_analysis_employee.execute
import frappe


def execute():
	frappe.db.sql("""UPDATE `tabEmployee` set enable_productify_analysis = 1 Where enable_productify_analysis = 0 and status = 'Active'""")
	frappe.db.sql("""UPDATE `tabMeeting` set organization = 'Internal Meeting' Where internal_meeting = 1""")

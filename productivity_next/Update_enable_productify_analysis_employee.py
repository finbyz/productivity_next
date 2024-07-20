import frappe
frappe.db.sql("""UPDATE `tabEmployee` set enable_productify_analysis = 1 Where enable_productify_analysis = 0 and status = 'Active'""")
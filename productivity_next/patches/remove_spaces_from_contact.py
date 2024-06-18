from __future__ import unicode_literals
import frappe

def execute():
    frappe.db.sql("""UPDATE `tabContact Phone` SET phone = REPLACE(phone, ' ', '')""")
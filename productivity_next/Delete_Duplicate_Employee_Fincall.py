# If same employee fincall log are created multiple times then delete all duplicates
import frappe


duplicate_employee_fincalls = frappe.db.sql("""
select min(name) as name_to_keep, call_datetime, customer_no, employee, count(*) as count
from `tabEmployee Fincall`
group by call_datetime, customer_no, employee
having count(*) > 1
""", as_dict=True)

names_to_keep = [row['name_to_keep'] for row in duplicate_employee_fincalls]
names_to_delete = frappe.db.sql("""
select name
from `tabEmployee Fincall`
where (call_datetime, customer_no, employee) in (
    select call_datetime, customer_no, employee
    from `tabEmployee Fincall`
    group by call_datetime, customer_no, employee
    having count(*) > 1
) and name not in ({names})
""".format(names=", ".join(["%s"] * len(names_to_keep))), names_to_keep, as_dict=True)

for doc in names_to_delete:
    frappe.delete_doc('Employee Fincall', doc['name'])
    print(doc.name)
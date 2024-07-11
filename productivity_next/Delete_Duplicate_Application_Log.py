# If same application usage log are created multiple times then delete all duplicates
import frappe


duplicate_application_usage_logs = frappe.db.sql("""
select min(name) as name_to_keep,employee, CAST(from_time AS DATETIME), CAST(to_time AS DATETIME), count(*) as count
from `tabApplication Usage log`
group by employee, CAST(from_time AS DATETIME), CAST(to_time AS DATETIME)
having count(*) > 1
""", as_dict=True)

names_to_keep = [row['name_to_keep'] for row in duplicate_application_usage_logs]
names_to_delete = frappe.db.sql("""
select name
from `tabApplication Usage log`
where (employee, CAST(from_time AS DATETIME), CAST(to_time AS DATETIME)) in (
    select employee, CAST(from_time AS DATETIME), CAST(to_time AS DATETIME)
    from `tabApplication Usage log`
    group by employee, CAST(from_time AS DATETIME), CAST(to_time AS DATETIME)
    having count(*) > 1
) and name not in ({names})
""".format(names=", ".join(["%s"] * len(names_to_keep))), names_to_keep, as_dict=True)

for doc in names_to_delete:
    frappe.delete_doc('Application Usage log', doc['name'])
    print(doc.name)
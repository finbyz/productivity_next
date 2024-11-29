# If same Location Logs are created multiple times then delete all duplicates
import frappe


duplicate_application_location_logs = frappe.db.sql("""
select min(name) as name_to_keep,employee, uuid, count(*) as count
from `tabLocation Logs`
group by employee, uuid
having count(*) > 1
""", as_dict=True)

names_to_keep = [row['name_to_keep'] for row in duplicate_application_location_logs]
names_to_delete = frappe.db.sql("""
select name
from `tabLocation Logs`
where (employee, uuid) in (
    select employee, uuid
    from `tabLocation Logs`
    group by employee, uuid
    having count(*) > 1
) and name not in ({names})
""".format(names=", ".join(["%s"] * len(names_to_keep))), names_to_keep, as_dict=True)

batch_size = 100
for i in range(0, len(names_to_delete), batch_size):
    batch = names_to_delete[i:i + batch_size]
    for doc in batch:
        frappe.delete_doc('Location Logs', doc['name'])
        print(f"Deleted: {doc['name']}")
    frappe.db.commit()
    print(f"Committed batch {i // batch_size + 1}")
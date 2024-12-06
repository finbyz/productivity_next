import frappe

# Find duplicate logs
duplicate_application_location_logs = frappe.db.sql("""
    SELECT min(name) as name_to_keep, employee, timestamp, count(*) as count 
    FROM `tabLocation Logs` 
    GROUP BY employee, timestamp 
    HAVING count(*) > 1
""", as_dict=True)

# Get names to keep
names_to_keep = [row['name_to_keep'] for row in duplicate_application_location_logs]

# Find and delete duplicate logs
names_to_delete = frappe.db.sql("""
    SELECT name 
    FROM `tabLocation Logs` 
    WHERE (employee, timestamp) IN (
        SELECT employee, timestamp 
        FROM `tabLocation Logs` 
        GROUP BY employee, timestamp 
        HAVING count(*) > 1
    ) AND name NOT IN ({names})
""".format(names=", ".join(["%s"] * len(names_to_keep))), names_to_keep, as_dict=True)

frappe.db.sql("""
    DELETE FROM `tabLocation Logs` 
    WHERE name IN ({placeholders})
""".format(placeholders=", ".join(["%s"] * len(names_to_delete))), 
[doc['name'] for doc in names_to_delete])
frappe.db.commit()
print(f"Deleted {len(names_to_delete)} duplicate records")
import frappe
delete_query = """
DELETE FROM `tabComment`
WHERE name IN (
    SELECT name FROM (
        SELECT c.name
        FROM `tabComment` c
        LEFT JOIN `tabEmployee Fincall` ef ON c.name = ef.comment
        WHERE c.comment_type = 'Info'
        AND c.subject IN ('Incoming', 'Outgoing', 'Missed', 'Rejected')
        AND ef.name IS NULL
    ) AS comments_to_delete
)
"""

result = frappe.db.sql(delete_query)

deleted_count = frappe.db.sql("SELECT ROW_COUNT()", as_list=True)[0][0]

frappe.db.commit()

print(f"Deleted {deleted_count} comments.")
# NewV16: wrapped in execute() so that importing this module (e.g. via /api/method/<module>.x,
# which imports before the whitelist check) no longer runs it. Run on purpose with:
#   bench --site <site> execute productivity_next.delete_duplicate_comments.execute
import frappe


def execute():
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

import frappe


def execute():
	"""Make the creator the approver of every task that has no approver yet."""
	frappe.db.sql(
		"""
		INSERT INTO `tabTask Approver`
			(name, parent, parenttype, parentfield, idx, user, owner, modified_by, creation, modified, docstatus)
		SELECT CONCAT('apr-', t.name), t.name, 'Task', 'approver', 1, t.owner,
			'Administrator', 'Administrator', NOW(6), NOW(6), 0
		FROM `tabTask` t
		WHERE t.owner NOT IN ('Administrator', 'Guest')
			AND NOT EXISTS (
				SELECT 1 FROM `tabTask Approver` a
				WHERE a.parent = t.name AND a.parenttype = 'Task' AND a.parentfield = 'approver'
			)
		"""
	)

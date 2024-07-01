import frappe


def execute():
    employee_fincalls = frappe.get_all(
        "Employee Fincall",
        filters={"comment": ["is", "set"]},
        fields=["name", "comment"],
    )
    for employee_fincall in employee_fincalls:
        frappe.db.set_value("Employee Fincall", employee_fincall.name, "comment", None)
        frappe.delete_doc("Comment", employee_fincall.comment)
        print(f"Deleted comment for Employee Fincall {employee_fincall.name}")

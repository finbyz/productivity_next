import frappe

def execute():
    # Get all draft timesheets
    timesheets = frappe.get_all(
        "Timesheet",
        filters={"docstatus": 0},   # draft status
        fields=["name"]
    )

    for t in timesheets:
        try:
            doc = frappe.get_doc("Timesheet", t.name)
            doc.submit()
        except Exception as e:
            frappe.log_error(
                title="Draft Timesheet Auto-Submit Failed",
                message=f"Timesheet: {t.name}\nError: {e}"
            )
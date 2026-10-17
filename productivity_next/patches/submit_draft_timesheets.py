import frappe

def execute():
    
    timesheets = frappe.get_all(
        "Timesheet",
        filters={"docstatus": 0},  # draft
        pluck="name"
    )
    
    total = len(timesheets)

    for i in range(0, total, 50):
        batch = timesheets[i : i + 50]
        
        for ts in batch:
            try:
                doc = frappe.get_doc("Timesheet", ts)
                doc.submit()
            except Exception as exc:
                frappe.log_error(
                    title="Draft Timesheet Auto-Submit Failed",
                    message=f"Timesheet: {ts}\nError: {exc}"
                )
        frappe.db.commit()
    
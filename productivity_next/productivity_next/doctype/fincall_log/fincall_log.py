import frappe
from frappe.model.document import Document
from datetime import timedelta
from dateutil.parser import parse

class FincallLog(Document):
    def save_fincall_log(self):
        if not self.employee_fincall_generated:
            self.create_employee_log()
    
    def validate(self):
        self.set_date()
        if not self.get("__islocal"):
            self.save_fincall_log()

    def after_insert(self):
        self.save_fincall_log()

    def create_employee_log(self):
        # Retrieve employee details
        employee_details = frappe.db.get_value(
            "Employee",
            self.employee,
            ["name", "employee_name"],
            as_dict=True,
        )

        if employee_details:
            # Convert call_datetime to datetime object
            call_datetime = parse(str(self.call_datetime))
            
            # Calculate the date 15 days ago
            fifteen_days_ago = call_datetime - timedelta(days=15)

            # Check if an Employee Fincall document with the same data exists in the last 15 days
            existing_fincall = frappe.db.sql("""
                SELECT name 
                FROM `tabEmployee Fincall` 
                WHERE employee = %(employee)s
                AND customer_no = %(customer_no)s
                AND calltype = %(calltype)s
                AND call_datetime BETWEEN %(fifteen_days_ago)s AND %(call_datetime)s
            """, {
                "employee": employee_details['name'],
                "customer_no": self.customer_no,
                "calltype": self.calltype,
                "fifteen_days_ago": fifteen_days_ago,
                "call_datetime": call_datetime,
            })

            if not existing_fincall:
                # Create new Employee Fincall document
                ec_doc = frappe.new_doc("Employee Fincall")
                ec_doc.employee = employee_details['name']
                ec_doc.employee_name = employee_details['employee_name']
                ec_doc.employee_mobile = self.employee_mobile
                ec_doc.client = self.client
                ec_doc.customer_no = self.customer_no
                ec_doc.call_datetime = call_datetime
                ec_doc.duration = self.duration
                ec_doc.date = call_datetime.date()
                ec_doc.calltype = self.calltype
                ec_doc.fincall_log_ref = self.name

                # Try to get contact details
                try:
                    contact_query = """
                        SELECT c.name, dl.link_doctype, dl.link_name 
                        FROM `tabContact` AS c 
                        JOIN `tabContact Phone` AS cp ON cp.parent = c.name 
                        JOIN `tabDynamic Link` AS dl ON dl.parent = c.name 
                        WHERE cp.phone LIKE %s
                        LIMIT 1
                    """
                    contact_details = frappe.db.sql(contact_query, ("%{}%".format(self.customer_no),), as_dict=True)

                    if contact_details:
                        contact = contact_details[0]
                        ec_doc.link_to = contact.get('link_doctype', '')
                        ec_doc.contact = contact.get('name', '')
                        ec_doc.link_name = contact.get('link_name', '')
                except Exception as e:
                    pass  # Handle case where contact is not found

                ec_doc.flags.ignore_permissions = True
                ec_doc.save()

                # Update flag indicating that employee fincall is generated
                self.db_set("employee_fincall_generated", 1)

    def set_date(self):
        self.date = parse(self.call_datetime).date()


@frappe.whitelist()
def bg_employee_log_generation():
    call_logs = frappe.db.get_all(
        "Fincall Log", {"employee_fincall_generated": 0, "ignore_contact": 0}
    )
    if call_logs:
        frappe.enqueue(
            enqueue_logs,
            call_logs=call_logs,
            queue="long",
            job_name="Employee Log Generation",
        )
        frappe.msgprint("Log generation has started in Background")


def enqueue_logs(call_logs):
    for row in call_logs:
        if not frappe.db.exists("Employee Fincall", {"fincall_log_ref": row.name}):
            call_doc = frappe.get_doc("Fincall Log", row.name)
            call_doc.save()
        elif frappe.db.exists("Employee Fincall", {"fincall_log_ref": row.name}):
            frappe.db.set_value(
                "Fincall Log", row.name, "employee_fincall_generated", 1
            )

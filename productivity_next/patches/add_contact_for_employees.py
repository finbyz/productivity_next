import frappe

def execute():
    data = frappe.db.sql("""
        select name 
        from `tabEmployee` 
        where cell_number is not null 
        and cell_number != '' 
        and status = 'Active'
    """, as_dict=1)
    for d in data:
        try:
            employee_doc = frappe.get_doc("Employee", d['name'])
            contact_doc = frappe.new_doc("Contact")
            contact_doc.first_name = employee_doc.first_name
            contact_doc.last_name = employee_doc.last_name
            if employee_doc.gender:
                if employee_doc.gender == 'Male':
                    contact_doc.salutation = 'Mr'
                else:
                    contact_doc.salutation = 'Ms'
            if employee_doc.company_email:
                contact_doc.append("email_ids", {
                    "email_id": employee_doc.company_email,
                    "is_primary": 1
                })
            if employee_doc.personal_email:
                contact_doc.append("email_ids", {
                    "email_id": employee_doc.personal_email,
                })
            contact_doc.append("phone_nos", {
                "phone": employee_doc.cell_number,
                "is_primary_phone": 1
            })
            contact_doc.append("links", {
                "link_doctype": "Company",
                "link_name": employee_doc.company,
            })
            contact_doc.save(ignore_permissions=True)
            print("Contact created for Employee: " + d['name'])
        except Exception as e:
            print("FAILED")

import frappe

def execute():
    frappe.db.sql("""INSERT INTO `tabDocField` 
    (`name`, `parent`, `parentfield`, `parenttype`, `fieldname`, `label`, `fieldtype`,`idx`,`modified_by`, `creation`, `modified`, `owner`, `docstatus`, `collapsible`, `in_list_view`, `in_standard_filter`, `in_global_search`)
    VALUES
    (UUID(), 'Employee', 'fields', 'DocType', 'company_description', 'Company Description', 'Text Editor',109, 'Administrator', NOW(), NOW(), 'Administrator', 0, 0, 0, 0, 0);
    """)
    print("ADDED SUCCESSFULLY!")
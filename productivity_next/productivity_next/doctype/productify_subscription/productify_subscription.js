// Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Productify Subscription", {
    refresh(frm) {
        if (frm.doc.__islocal) {
            frm.set_value('email', frappe.session.user_email);
            frm.set_value('erpnext_url', window.location.origin);
            frm.set_value('organization_name', frappe.defaults.get_user_default('company') || '');

            frappe.db.get_value('User', { 'name': frappe.session.user }, 'mobile_no').then((value) => {
                frm.set_value('mobile_no', value.mobile_no);
            });

            if (frm.doc.list_of_users.length === 0) {
                frappe.db.get_list('Employee', {
                    fields: ['name'],
                    filters: {
                        'status': 'Active'
                    },
                    order_by: 'name'
                }).then((employees) => {
                    let table_data = [];
                    employees.forEach((employee) => {
                        table_data.push({
                            'employee': employee.name,
                            'fincall': 1,
                            'application_usage': 1,
                            'sales_person': 1
                        });
                    });
                    frm.set_value('list_of_users', table_data);
                });
            }
        }
    },
});

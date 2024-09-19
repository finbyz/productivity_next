// Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Productify Subscription", {
    refresh(frm) {
        frm.set_query('employee', 'list_of_users', function (doc, cdt, cdn) {
            return {
                filters: {
                    'status': 'Active'
                }
            }
        });
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
                        'status': 'Active',
                        "user_id": ["is", "set"]
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
        frm.trigger('issue');
        frm.trigger('task');
    },
    
    project(frm) {
        frm.trigger('task');
    },
   
    task(frm) {
        if (frm.doc.project) {
            frm.toggle_display('task', true);
        }
        else {
            frm.toggle_display('task', false);
            frm.set_value('task', 0);
        }
        frm.trigger('issue');
    },
    issue(frm) {
        if (frm.doc.project && frm.doc.task) {
            frm.toggle_display('issue', true);
        }
        else {
            frm.toggle_display('issue', false);
            frm.set_value('issue', 0);
        }
    },
    get_users(frm) {
        frappe.db.get_list('Employee', {
            fields: ['name', 'user_id', 'first_name',"middle_name","last_name"],
            filters: {
                'status': 'Active',
                "user_id": ["is", "set"]
            },
            order_by: 'name'
        }).then((employees) => {
            let table_data = [];
            employees.forEach((employee) => {
                if (frm.doc.list_of_users.find((user) => user.employee === employee.name)) {
                    return;
                }
                table_data.push({
                    'employee': employee.name,
                    'fincall': 1,
                    'application_usage': 1,
                    'sales_person': 1,
                    'user_id': employee.user_id,
                }); 
            });
            frm.set_value('list_of_users', [...frm.doc.list_of_users, ...table_data]);
        });
    },
});

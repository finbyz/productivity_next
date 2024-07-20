const { error } = require("echarts/types/src/util/log.js");

document.addEventListener("DOMContentLoaded", function () {
    let data = {
        'domain': window.origin || '',
        'organization_name': frappe.defaults.get_user_default('company') || '',
        'contact_person': frappe.boot.user.first_name || '' + ' ' + frappe.boot.user.last_name || '',
        'email_id': frappe.boot.user.email || '',
        'mobile_no': '',
    }

    let dialog = new frappe.ui.Dialog({
        title: 'Table-Test',
        size: "extra-large",
        fields: [
            {
                label: 'Table',
                fieldname: 'table',
                fieldtype: 'Table',
                cannot_add_rows: true,
                in_place_edit: false,
                data: [],
                fields: [
                    { fieldname: 'employee', fieldtype: 'Data', in_list_view: 1, label: 'Employee' },
                    { fieldname: 'user_id', fieldtype: 'Data', in_list_view: 1, label: 'User ID' },
                    { fieldname: 'cell_number', fieldtype: 'Data', in_list_view: 1, label: 'Phone No' },
                    { fieldname: 'call_sub', fieldtype: 'Check', in_list_view: 1, label: 'Call' },
                    { fieldname: 'application_sub', fieldtype: 'Check', in_list_view: 1, label: 'Application Usage' },
                    { fieldname: 'sales_person_sub', fieldtype: 'Check', in_list_view: 1, label: 'Sales Person' },
                ],
            }
        ],

    });
    

    frappe.db.get_list('Employee', {
        fields: ['employee_name', 'user_id', 'cell_number'],
        filters: {
            'status': 'Active'
        }
    }).then((employees) => {
        let table_data = [];
        employees.forEach((employee) => {
            table_data.push({
                'employee': employee.employee_name,
                'user_id': employee.user_id,
                'cell_number': employee.cell_number,
                'call_sub': 1,
                'application_sub': 1,
                'sales_person_sub': 1
            });
        });
        dialog.fields_dict.table.df.data = table_data;
        dialog.fields_dict.table.refresh();
    });
    let d = new frappe.ui.Dialog({
        title: 'Organization Signup for Productivity Next',
        fields: [
            {
                label: 'Domain',
                fieldname: 'domain',
                fieldtype: 'Data',
                reqd: 1,
                default: window.origin
            },
            {
                label: 'Organization Name',
                fieldname: 'organization_name',
                fieldtype: 'Data',
                reqd: 1,
                default: data.organization_name
            },
            {
                label: 'Contact Person',
                fieldname: 'contact_person',
                fieldtype: 'Data',
                default: data.contact_person
            },
            {
                label: 'Email ID',
                fieldname: 'email_id',
                fieldtype: 'Data',
                reqd: 1, // Required field
                options: 'Email',
                default: data.email_id
            },
            {
                label: 'Mobile No',
                fieldname: 'mobile_no',
                fieldtype: 'Data',
                reqd: 1, // Required field
                default: data.mobile_no
            },
            {
                label: 'Subscription for Call',
                fieldname: 'subscription_call',
                fieldtype: 'Check'
            },
            {
                label: 'Application Usage',
                fieldname: 'application_sub',
                fieldtype: 'Check'
            },
            {
                label: 'Sales Person',
                fieldname: 'sales_person_sub',
                fieldtype: 'Check'
            }
        ],
        size: 'small',
        primary_action_label: 'Submit',
        primary_action(values) {
            let subscription_plan = [];
            if (values.subscription_call) {
                subscription_plan.push('Call');
            }
            if (values.application_sub) {
                subscription_plan.push('Application Usage');
            }
            if (values.sales_person_sub) {
                subscription_plan.push('Sales Person');
            }
            frappe.call({
                method: 'productivity_next.api.organization_signup',
                type: 'POST',
                args: {
                    domain: values.domain,
                    organization_name: values.organization_name,
                    contact_person: values.contact_person,
                    email: values.email_id,
                    mobile_no: values.mobile_no,
                    subscription_plan: subscription_plan.join(', '),
                    application: values.application_sub,
                    sales_person: values.sales_person_sub
                },
                success: (r) => {
                    console.log(r);
                    dialog.show();
                },
                error: (r) => {
                    frappe.errprint(r.message);
                }
            });
        }
    });

    d.show(); // Show 'd' dialog initially

});

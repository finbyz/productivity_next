frappe.require('assets/productivity_next/productivity_next/party.min.js');

document.addEventListener("DOMContentLoaded", function () {
    function hasrole(rl) {
		if (typeof rl == "string") rl = [rl];
		for (var i in rl) {
			if ((frappe.boot ? frappe.boot.user.roles : ["Guest"]).indexOf(rl[i]) != -1)
				return true;
		}
	}
    if (!hasrole('System Manager')) {
        console.log('User is not System Manager');
        return;
    }
    let subscription;
    frappe.db.get_doc('Productify Subscription')
        .then(doc => {
            subscription = doc;
            window.subscription = doc;
            if (doc.docstatus === 1 && doc.list_of_users.length > 0) {
                return;
            }
        }
    )

    let data = {
        'domain': window.origin || '',
        'organization_name': frappe.defaults.get_user_default('company') || '',
        'contact_person': frappe.boot.user.first_name || '' + ' ' + frappe.boot.user.last_name || '',
        'email_id': frappe.boot.user.email || '',
        'mobile_no': '',
    }

    let dialog = new frappe.ui.Dialog({
        title: 'Organization Signup for Productivity Next',
        size: "extra-large",
        fields: [
            {
                label: 'Employees',
                fieldname: 'table',
                fieldtype: 'Table',
                cannot_add_rows: true,
                in_place_edit: false,
                data: [],
                fields: [
                    { fieldname: 'employee', fieldtype: 'Data', in_list_view: 1, label: 'Employee', read_only: 1 },
                    { fieldname: 'user_id', fieldtype: 'Data', in_list_view: 1, label: 'User ID', read_only: 1 },
                    { fieldname: 'cell_number', fieldtype: 'Data', in_list_view: 1, label: 'Phone No' },
                    { fieldname: 'fincall', fieldtype: 'Check', in_list_view: 1, label: 'Fin Call' },
                    { fieldname: 'application_usage', fieldtype: 'Check', in_list_view: 1, label: 'Application Usage' },
                    { fieldname: 'sales_person', fieldtype: 'Check', in_list_view: 1, label: 'Sales Person' },
                    { fieldname: 'project', fieldtype: 'Check', in_list_view: 1, label: 'Project Tracking' },
                    { fieldname: 'issue', fieldtype: 'Check', in_list_view: 1, label: 'Issue Tracking' },
                ],
            },
        ],
        primary_action_label: 'Submit',
        primary_action(values) {
            frappe.confirm('This detail will be shared with Finbyz. Do you want to submit?', () => {
                frappe.call({
                    method: "productivity_next.api.send_user_list",
                    type: 'POST',
                    args: {
                        user_list: values.table
                    },
                    callback: function (r) {
                        if (r.message) {
                            frappe.msgprint(`You have successfully registered for Productify. Please ask your Users to download <a target="_blank" href='https://productivity.finbyz.tech/files/Productify.exe'>Productify App</a> and <a target="_blank" href="https://play.google.com/store/apps/details?id=com.finbyzfincall.productify&pcampaignid=web_share">Fincall App</a>  to start activity analysis.\nLogin on both places will be through their own ERP email id and password`);
                            party.confetti(document.body, {
                                count: party.variation.range(200, 300),
                            });
                            dialog.hide();
                            frappe.db.get_doc('Productify Subscription')
                                .then(doc => {
                                    subscription = doc;
                                    window.subscription = doc;
                                    if (doc.docstatus === 1 && doc.list_of_users.length > 0) {
                                        return;
                                    }
                                }
                                )
                        }
                    }
                });
            });

        }

    });

    let organization_fields = [
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
            fieldtype: 'Link',
            options: 'Company',
            reqd: 1,
            default: data.organization_name
        },
        {
            label: 'Contact Person',
            fieldname: 'contact_person',
            fieldtype: 'Data',
            default: frappe.boot.user.name == 'Administrator' ? '' : data.contact_person
        },
        {
            label: 'Email ID',
            fieldname: 'email_id',
            fieldtype: 'Data',
            reqd: 1, // Required field
            options: 'Email',
            default: frappe.boot.user.name == 'Administrator' ? '' : data.email_id
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
    ]
    frappe.db.get_list('Employee', {
        fields: ['employee_name', 'name', 'user_id', 'cell_number'],
        filters: {
            'status': 'Active',
            'user_id': ['is', 'set']
        },
        limit: 500000
    }).then((employees) => {
        let table_data = [];
        employees.forEach((employee) => {
            table_data.push({
                'employee': employee.employee_name,
                'user_id': employee.user_id,
                'cell_number': employee.cell_number,
                'fincall': 1,
                'application_usage': 1,
                'sales_person': 0,
                'name': employee.name
            });
        });
        dialog.fields_dict.table.df.data = table_data;
        dialog.fields_dict.table.refresh();
    });
    let d = new frappe.ui.Dialog({
        title: 'Organization Signup for Productivity Next',
        fields: organization_fields,
        size: 'small',
        primary_action_label: 'Submit',
        primary_action(values) {
            frappe.call({
                method: 'productivity_next.api.organization_signup',
                type: 'POST',
                args: {
                    domain: values.domain,
                    organization_name: values.organization_name,
                    contact_person: values.contact_person,
                    email: values.email_id,
                    mobile_no: values.mobile_no,
                    application: values.application_sub,
                    fincall: values.fincall ? 1 : 0,
                    application_usage: values.application_usage ? 1 : 0,
                    sales_person: values.sales_person ? 1 : 0,
                    project: values.project ? 1 : 0,
                    issue: values.issue ? 1 : 0,
                },
                callback: function (r) {
                    if (r.status === 400) {
                        frappe.msgprint(r.message);
                        return;
                    }

                    d.hide();
                    dialog.show();

                    frappe.db.get_doc('Productify Subscription')
                        .then(doc => {
                            subscription = doc;
                            window.subscription = doc;
                            if (doc.docstatus === 1 && doc.list_of_users.length > 0) {
                                return;
                            }
                        }
                        )
                }
            });
            d.hide();
        }
    });
    if (window.location.pathname === '/app' || window.location.pathname === '/app/home') {
        if (subscription && !subscription.organization_name) {
            d.show();
            console.log('Subscription not done');
        }
    }
    setInterval(() => {
        if (window.location.pathname === '/app' || window.location.pathname === '/app/home') {
            if (subscription && !subscription.organization_name && !d.display) {
                d.show();
                console.log('Subscription not done');
                return;
            }
            if (subscription && subscription.organization_name && subscription.list_of_users.length === 0 && !dialog.display) {
                dialog.show();
                console.log('Subscription done but no users');
            }
        }

    }, 30000);

});


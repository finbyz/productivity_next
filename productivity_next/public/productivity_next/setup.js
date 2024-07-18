let d = new frappe.ui.Dialog({
    title: 'Organization Signup for Productivity Next',
    fields: [
        {
            label: 'Domain',
            fieldname: 'domain',
            fieldtype: 'Data',
            default: window.location.origin,
            reqd: 1
        },
        {
            label: 'Organization Name',
            fieldname: 'organization_name',
            fieldtype: 'Data',
            reqd: 1,

        },
        {
            label: 'Contact Person',
            fieldname: 'contact_person',
            fieldtype: 'Data'
        },
        {
            label: 'Email ID',
            fieldname: 'email_id',
            fieldtype: 'Data',
            reqd: 1, // Required field
            options: 'Email'
        },
        {
            label: 'Mobile No',
            fieldname: 'mobile_no',
            fieldtype: 'Data',
            reqd: 1 // Required field
        },
        {
            label: 'Subscription for Call',
            fieldname: 'subscription_call',
            fieldtype: 'Check'
        },
        {
            label: 'Application',
            fieldname: 'application',
            fieldtype: 'Check'
        },
        {
            label: 'Sales Person',
            fieldname: 'sales_person',
            fieldtype: 'Check'
        }
    ],
    size: 'small', // small, large, extra-large 
    primary_action_label: 'Submit',
    primary_action(values) {
        console.log(values);

        subscription_plan = [];
        if (values.subscription_call) {
            subscription_plan.push('Call');
        }
        if (values.application) {
            subscription_plan.push('Application');
        }
        if (values.sales_person) {
            subscription_plan.push('Sales Person');
        }
        frappe.call({
            method: 'productivity_next.api.organization_signup',
            args: {
                domain: values.domain,
                organization_name: values.organization_name,
                contact_person: values.contact_person,
                email: values.email_id,
                mobile_no: values.mobile_no,
                subscription_plan: subscription_plan.join(', '),
                application: values.application,
                sales_person: values.sales_person
            },
            success: function (r) { 
                if (r.message) {
                    frappe.msgprint('Organization has been successfully registered.');
                }
            },
            error: function (err) {
                console.error(err);
                frappe.throw('An error occurred: ' + (err.message || 'Please try again later.'));
            }
        });

        d.hide();
        // Additional logic can be added here
    }
});

window.onload = function () {
    host = window.location.host;
    app_url = window.location.origin + '/app';
    if (window.location.href === app_url || window.location.href === app_url + '/home') {
        d.show();
    }
}

// Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Fincall", {
	create_contact(frm) {
        let d = frm.doc;

        let fields = [
            {
                label: __("Contact No"),
                fieldtype: 'Data',
                fieldname: 'client_no',
                default: frm.doc.customer_no
            },
            {
                label: __("Is Primary Mobile"),
                fieldtype: 'Check',
                fieldname: 'is_primary_mobile_no',
                default: 1,
            },
            {
                label: __("Is Primary Phone"),
                fieldtype: 'Check',
                fieldname: 'is_primary_phone',
            },
            {fieldtype: 'Section Break'},
            {
                label: __("Update Existing Contact"),
                fieldtype: 'Check',
                fieldname: 'update_existing_client',
                default: 1,
            },
            {
                label: __("Update Contact"),
                fieldtype: 'Link',
                options: "Contact",
                depends_on: 'eval:doc.update_existing_client',
                fieldname: 'update_client',
                change: function(){
					let merge = this.get_value();
					let contact = this.layout.get_value('update_client');
                    if(contact){
                        console.log(contact)
                        frappe.db.get_doc("Contact", contact).then(doc => {
                            console.log(doc);
                            this.layout.get_field('party_type').set_input(doc.links[0].link_doctype);
                            this.layout.get_field('party').set_input(doc.links[0].link_name);
                        }).catch(err => {
                            console.error("Error fetching document:", err);
                        });
                    }
				},
                mandatory_depends_on: 'eval:doc.update_existing_client'
            },
            {fieldtype: 'Section Break'},
            {
                label: __("Party Type"),
                fieldtype: 'Link',
                options: "DocType",
                fieldname: 'party_type',
                get_query: function() {
                    return {
                        filters: {
                            "name": ["in", ["Customer", "Supplier", "Lead","Company"]]
                        }
                    };
                },
                reqd: 1,
            },
            {
                label: __("First Name"),
                fieldtype: 'Data',
                fieldname: 'first_name',
                reqd: 1,
                default: frm.doc.client,
                depends_on: 'eval:!doc.update_existing_client',
                mandatory_depends_on: 'eval:!doc.update_existing_client'
            },
            {
                label: __("Salutation"),
                fieldtype: 'Link',
                fieldname: 'salutation',
                options: "Salutation",
                depends_on: 'eval:!doc.update_existing_client',
                reqd: 1,
                mandatory_depends_on: 'eval:!doc.update_existing_client'
            },
            {fieldtype: 'Column Break'},
            {
                label: __("Party"),
                fieldtype: 'Dynamic Link',
                options: "party_type",
                fieldname: 'party',
                reqd: 1,
            },
            {
                label: __("Last Name"),
                fieldtype: 'Data',
                fieldname: 'last_name',
                depends_on: 'eval:!doc.update_existing_client',
            }
        ];

        let dialog = new frappe.ui.Dialog({
            title: __("Create Contact"),
            fields: fields,
            primary_action_label: __("Create"),
            primary_action: function(values) {
                console.log(values.client_no);
                if (values.update_existing_client){
                    frappe.call({
                        method: 'productivity_next.productivity_next.doctype.employee_fincall.employee_fincall.update_contact',
                        args: {
                            client_no: values.client_no || 0,
                            update_client: values.update_client,
                            is_primary_phone: values.is_primary_phone,
                            is_primary_mobile_no: values.is_primary_mobile_no,
                            party_type: values.party_type,
                            party: values.party,
                        },
                        callback: (r) => {
                            dialog.hide();
                            frm.refresh();
                        }
                    });
                }
                else{
                frappe.call({
                    method: 'productivity_next.productivity_next.doctype.employee_fincall.employee_fincall.create_contact',
                    args: {
                        is_primary_mobile_no: values.is_primary_mobile_no,
                        client_no: values.client_no || 0,
                        first_name: values.first_name,
                        party_type: values.party_type,
                        party: values.party,
                        last_name: values.last_name,
                        is_primary_phone: values.is_primary_phone,
                        salutation: values.salutation
                    },
                    callback: (r) => {
                        dialog.hide();
                        frm.refresh();
                    }
                });
                }
            }
        });

        dialog.show();
        console.log("BUTTON DAB GAYA");
    },
});

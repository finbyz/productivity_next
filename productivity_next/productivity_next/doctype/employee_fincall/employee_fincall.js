// Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Fincall", {
	refresh(frm) {
		frm.add_custom_button(__("Create Task"), () => {
			frm.events.open_create_task_dialog(frm);
		});
	},

	open_create_task_dialog(frm) {
		let dialog = new frappe.ui.Dialog({
			title: __("Create Task"),
			fields: [
				{
					label: __("Subject"),
					fieldtype: 'Data',
					fieldname: 'subject',
					reqd: 1,
					default: frm.doc.client ? __("Follow-up {0}", [frm.doc.client]) : undefined,
				},
				{
					label: __("Assignee"),
					fieldtype: 'Link',
					options: "User",
					fieldname: 'assignee',
					reqd: 1,
				},
				{
					label: __("Expected Date"),
					fieldtype: 'Date',
					fieldname: 'exp_end_date',
					reqd: 1,
					default: frappe.datetime.get_today(),
				},
				{
					label: __("Project"),
					fieldtype: 'Link',
					options: "Project",
					fieldname: 'project',
					default: frm.doc.project,
				},
				{
					label: __("Type"),
					fieldtype: 'Link',
					options: "Task Type",
					fieldname: 'type',
					reqd: 1,
				},
			],
			primary_action_label: __("Create"),
			primary_action: function(values) {
				dialog.disable_primary_action();
				frappe.db.insert({
					doctype: "Task",
					subject: values.subject,
					assignee: values.assignee,
					exp_start_date: values.exp_end_date,
                    exp_end_date: values.exp_end_date,
					project: values.project || null,
					type: values.type,
				}).then((doc) => {
					dialog.hide();
					frappe.show_alert({
						message: __("Task {0} created", [
							`<a href="/app/task/${encodeURIComponent(doc.name)}">${frappe.utils.escape_html(values.subject)}</a>`,
						]),
						indicator: "green",
					});
					// Link the new task back onto this Fincall record.
					frm.set_value("task", doc.name);
					if (!frm.is_new()) frm.save();
				}).catch(() => {
					dialog.enable_primary_action();
				});
			}
		});

		// Default the assignee to the linked employee's user, if available.
		if (frm.doc.employee) {
			frappe.db.get_value("Employee", frm.doc.employee, "user_id").then((r) => {
				const user_id = r && r.message && r.message.user_id;
				if (user_id && !dialog.get_value("assignee")) {
					dialog.set_value("assignee", user_id);
				}
			});
		}

		dialog.show();
	},

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

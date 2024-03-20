// Copyright (c) 2023, Finbyz Tech Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Phone Reconciliation', {
	refresh: function(frm) {
		frm.disable_save();
		frm.set_df_property('phone_reconciliation_call', 'cannot_delete_rows', true);
		frm.set_df_property('phone_reconciliation_call', 'cannot_add_rows', true);
		if (frm.doc.from_date || frm.doc.employee) {
			frm.add_custom_button(__('Get Unreconciled Numbers'), () =>
				frm.trigger("get_unreconciled_entries")
			);
			frm.change_custom_button_type('Get Unreconciled Numbers', null, 'primary');
		}
		if (frm.doc.phone_reconciliation_call[0]){
			frm.add_custom_button(__('Allocate'), () =>
				frm.trigger("allocate_phones")
			);
		}
	},
	get_unreconciled_entries:function(frm){
		frm.clear_table("phone_reconciliation_call");
		frm.clear_table("phone_reconciliation_allocation");
		frm.call({
			doc: frm.doc,
			method: 'get_unreconciled_numbers',
			callback: () => {
				frm.refresh();
			}
		});
	},
	allocate_phones: function(frm){
		frm.call({
			doc: frm.doc,
			method: 'allocate_phone_numbers',
			callback: (r) => {
				r.message.reverse()
				r.message.forEach(function(i){
					cur_frm.get_field("phone_reconciliation_call").grid.grid_rows[parseInt(i)].remove()
				})
				// frappe.msgprint("Contact has been allocated.")
				cur_frm.refresh_fields("phone_reconciliation_call");
				cur_frm.refresh_fields("phone_reconciliation_allocation");
				frm.refresh();
			}
		})
	},
	employee: function(frm) {
		frm.refresh();
	},
	from_date: function(frm) {
		frm.refresh();
	}
});
if (cur_frm && cur_frm.fields_dict['phone_reconciliation_call'] && cur_frm.fields_dict['phone_reconciliation_call'].grid) {
    cur_frm.fields_dict['phone_reconciliation_call'].grid.get_field("party_type").get_query = function(doc) {
        return {
            filters: {
                "name": ["in", ["Customer", "Supplier", "Lead"]]
            }
        };
    };
} else {
    console.log("The field 'phone_reconciliation_call' is not initialized yet.");
}

frappe.ui.form.on('Phone Reconciliation Call', {
	contact: function(frm) {
		frm.refresh();
	},
	create_contact: function(frm, cdt, cdn){
		let d = locals[cdt][cdn]

		let fields = [
            {
                label: __("Contact No"),
                fieldtype: 'Data',
                fieldname: 'client_no',
				default: d.client_no,
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
            {
                label: __("Client Email"),
                fieldtype: 'Data',
                fieldname: 'client_email',
            },
            {
                label: __("Is primary Email"),
                fieldtype: 'Check',
                fieldname: 'is_primary_email',
                default: 1,
            },
            {fieldtype: 'Section Break'},
            {
                label: __("Update Existing Contact"),
                fieldtype: 'Check',
                fieldname: 'update_existing_client',
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
				}
            },
            {
                label: __("Update Contact"),
                fieldtype: 'Link',
                options: "Contact",
                depends_on: 'eval:doc.update_existing_client',
                fieldname: 'update_client',
				default: d.contact,
            },
            {fieldtype: 'Section Break'},
            {
                label: __("Party Type"),
                fieldtype: 'Link',
                options: "DocType",
                fieldname: 'party_type',
                default: d.party_type,
                get_query: function() {
                    return {
                        filters: {
                            "name": ["in", ["Customer", "Supplier", "Lead"]]
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
                depends_on: 'eval:!doc.update_existing_client',
                mandatory_depends_on: 'eval:!doc.update_existing_client'
            },
            {
                label: __("Salutation"),
                fieldtype: 'Link',
                fieldname: 'salutation',
                options: "Salutation",
                depends_on: 'eval:!doc.update_existing_client',
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

		if (!d.contact_created && !d.ignore_contact){
			d.dialog = new frappe.ui.Dialog({
				title: __("Create Contact"),
				fields: fields
			});
			d.dialog.set_primary_action(__("Create"), function(){
				d.values = d.dialog.get_values();
				if (d.values.update_existing_client){
                    frappe.call({
                        method: 'productivity_next.productivity_next.doctype.phone_reconciliation.phone_reconciliation.update_contact',
                        args: {
                            client_email: d.values.client_email || 0,
                            client_no: d.values.client_no || 0,
                            update_client: d.values.update_client,
                            is_primary_phone: d.values.is_primary_phone,
                            is_primary_email: d.values.is_primary_email,
                            is_primary_mobile_no: d.values.is_primary_mobile_no,
							party_type: d.values.party_type,
                            party: d.values.party,
                        },
                        callback: (r) => {
							var allocation_table = cur_frm.add_child("phone_reconciliation_allocation");
							allocation_table.employee=d.employee
							allocation_table.employee_name = d.employee_name
							allocation_table.client_details = d.values.client
							allocation_table.client_no = d.client_no
							allocation_table.contact = d.values.update_client
							allocation_table.employee=d.employee
							allocation_table.party_type = d.values.party_type
							allocation_table.party = d.values.party

							cur_frm.get_field("phone_reconciliation_call").grid.grid_rows[parseInt(d.idx - 1)].remove()
							cur_frm.refresh_fields("phone_reconciliation_call");
							cur_frm.refresh_fields("phone_reconciliation_allocation");
							d.dialog.hide();
							frappe.msgprint("Contact has been updated.")
							frm.refresh();
						}
                    });
				}
				else{
				frappe.call({ 
					method: 'productivity_next.productivity_next.doctype.phone_reconciliation.phone_reconciliation.create_contact',
					args: {
						client_email: d.values.client_email || 0,
						is_primary_email: d.values.is_primary_email,
						client_no: d.client_no || 0,
						first_name : d.values.first_name,
						party_type: d.values.party_type,
						party: d.values.party,
						last_name: d.values.last_name,
						is_primary_mobile_no: d.values.is_primary_mobile_no,
						is_primary_phone: d.values.is_primary_phone,
						salutation: d.values.salutation
					},
					callback: (r) => {
						console.log(r.message)
						var allocation_table = cur_frm.add_child("phone_reconciliation_allocation");
						console.log(allocation_table)
						// allocation_table.employee=d.employee
						allocation_table.employee_name = d.employee_name
						allocation_table.client_details = d.values.client
						allocation_table.client_no = d.client_no
						allocation_table.contact = r.message
						allocation_table.employee=d.employee
						allocation_table.party_type = d.values.party_type
						allocation_table.party = d.values.party
						allocation_table.first_name = d.values.first_name
						allocation_table.last_name = d.values.last_name

						cur_frm.get_field("phone_reconciliation_call").grid.grid_rows[parseInt(d.idx - 1)].remove()
						cur_frm.refresh_fields("phone_reconciliation_call");
						cur_frm.refresh_fields("phone_reconciliation_allocation");
						d.dialog.hide();
						frappe.msgprint("Contact has been created.")
						frm.refresh();
					}
				})
			}
			});
			d.dialog.show();
		}
	},
	ignore_contact: function(frm, cdt, cdn){
		let d = locals[cdt][cdn]
		if (d.ignore_contact){
			frappe.confirm(
				__('Do you want to ignore contact from sync?'),
				function() {
					frappe.call({
						method:
						"productivity_next.productivity_next.doctype.phone_reconciliation.phone_reconciliation.ignore_contact",
						args: {client_no: d.client_no},
						callback: function(data){
							if(!data.exc){
								var allocation_table = cur_frm.add_child("phone_reconciliation_allocation");
								allocation_table.employee=d.employee
								allocation_table.employee_name = d.employee_name
								allocation_table.client_details = d.client_details
								allocation_table.client_no = d.client_no
								allocation_table.employee=d.employee
								allocation_table.ignore_contact = d.ignore_contact
								
								cur_frm.get_field("phone_reconciliation_call").grid.grid_rows[parseInt(d.idx - 1)].remove()
								cur_frm.refresh_fields("phone_reconciliation_call");
								cur_frm.refresh_fields("phone_reconciliation_allocation");
								frappe.msgprint("Given Contact is ignored from Contact creation.")
							}
							
						}
					});
				}
			);
		}
	}
})
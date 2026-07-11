// Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Fincall", {


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
			primary_action: function (values) {
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

	refresh(frm) {
		frm.add_custom_button(__("Create Task"), function () {
			frm.events.open_create_task_dialog(frm);
		});
		frm.add_custom_button(__("Relink Call"), function () {
			// First, fetch available suggestions using the same phone-number lookup
			// logic as create_fincall in api.py, then open the dialog pre-populated.
			frappe.call({
				method: "productivity_next.productivity_next.doctype.employee_fincall.employee_fincall.get_relink_suggestions",
				args: { docname: frm.doc.name },
				callback: function (r) {
					let suggestions = r.message || [];
					let best = suggestions[0] || null;

					// Build select options from all returned suggestions
					let suggestion_options = suggestions.map((s) =>
						`${s.link_doctype}: ${s.link_name}${s.name ? " [" + s.name + "]" : ""}`
					);

					let dialog;
					let fields = [
						{
							label: __("Available Matches (from phone number lookup)"),
							fieldtype: "Select",
							fieldname: "suggestion",
							options: ["-- select a match or fill manually below --", ...suggestion_options],
							default: best
								? `${best.link_doctype}: ${best.link_name}${best.name ? " [" + best.name + "]" : ""}`
								: "-- select a match or fill manually below --",
							change: function () {
								let val = this.get_value();
								if (!val || val.startsWith("--")) return;
								// Parse "DocType: link_name [contact_name]"
								let match = val.match(/^(.+?):\s*(.+?)(?:\s*\[(.+)\])?$/);
								if (match) {
									dialog.set_value("party_type", match[1].trim());
									dialog.set_value("party", match[2].trim());
									if (match[3]) {
										dialog.set_value("contact", match[3].trim());
									}
								}
							},
						},
						{ fieldtype: "Section Break", label: __("Or specify manually") },
						{
							label: __("Party Type"),
							fieldtype: "Link",
							options: "DocType",
							fieldname: "party_type",
							reqd: 1,
							default: best ? best.link_doctype : frm.doc.link_to,
							get_query: function () {
								return {
									filters: {
										name: ["in", ["Customer", "Supplier", "Lead", "Company", "Job Applicant"]],
									},
								};
							},
							change: function () {
								let party_field = dialog.get_field("party");
								party_field.df.options = this.get_value();
								party_field.set_value("");
								party_field.refresh();
							},
						},
						{
							label: __("Party"),
							fieldtype: "Dynamic Link",
							options: "party_type",
							fieldname: "party",
							reqd: 1,
							default: best ? best.link_name : frm.doc.link_name,
						},
						{ fieldtype: "Column Break" },
						{
							label: __("Contact"),
							fieldtype: "Link",
							options: "Contact",
							fieldname: "contact",
							default: best ? (best.name || "") : (frm.doc.contact || ""),
							get_query: function () {
								let party_type = dialog.get_value("party_type");
								let party = dialog.get_value("party");
								return {
									query: 'frappe.contacts.doctype.contact.contact.contact_query',
									filters: {
										link_doctype: party_type,
										link_name: party
									}
								};
							},
						},
					];

					dialog = new frappe.ui.Dialog({
						title: __("Relink Call"),
						fields: fields,
						primary_action_label: __("Relink"),
						primary_action: function (values) {
							if (!values.party_type || !values.party) {
								frappe.msgprint(__("Please select a Party Type and Party."));
								return;
							}
							frappe.call({
								method: "productivity_next.productivity_next.doctype.employee_fincall.employee_fincall.relink_call",
								args: {
									docname: frm.doc.name,
									link_to: values.party_type,
									link_name: values.party,
									contact: values.contact || "",
								},
								callback: function (r) {
									if (!r.exc) {
										frappe.show_alert(
											{ message: __("Call relinked successfully."), indicator: "green" },
											3
										);
										dialog.hide();
										frm.reload_doc();
									}
								},
							});
						},
					});

					if (!best) {
						frappe.show_alert(
							{
								message: __("No automatic match found for {0}. Please fill in manually.", [frm.doc.customer_no]),
								indicator: "orange",
							},
							5
						);
					}

					dialog.show();
				},
			});
		});
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
			{ fieldtype: 'Section Break' },
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
				change: function () {
					let contact = this.get_value();
					if (contact) {
						console.log(contact)
						frappe.db.get_doc("Contact", contact).then(doc => {
							console.log(doc);
							dialog.set_value('party_type', doc.links[0].link_doctype);
							dialog.set_value('party', doc.links[0].link_name);
						}).catch(err => {
							console.error("Error fetching document:", err);
						});
					}
				},
				mandatory_depends_on: 'eval:doc.update_existing_client'
			},
			{ fieldtype: 'Section Break' },
			{
				label: __("Party Type"),
				fieldtype: 'Link',
				options: "DocType",
				fieldname: 'party_type',
				get_query: function () {
					return {
						filters: {
							"name": ["in", ["Customer", "Supplier", "Lead", "Company"]]
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
			{ fieldtype: 'Column Break' },
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

		let dialog = new frappe.ui.Dialog({ // dialog is declared here, fields above reference it via closure in create_contact
			title: __("Create Contact"),
			fields: fields,
			primary_action_label: __("Create"),
			primary_action: function (values) {
				console.log(values.client_no);
				if (values.update_existing_client) {
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
				else {
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
		dialog.fields_dict.contact_person.get_query = function (doc) {
			return {
				query: 'frappe.contacts.doctype.contact.contact.contact_query',
				filters: {
					link_doctype: frm.doc.party_type,
					link_name: frm.doc.party
				}
			}
		};
		dialog.show();
		console.log("BUTTON DAB GAYA");
	},
});

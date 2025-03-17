frappe.ui.form.on('Lead', {
	refresh: function(frm) {
		if(!frm.doc.__islocal){
			frm.add_custom_button(__("Meeting Schedule"), function() {
				return frappe.call({
					method : "productivity_next.api.make_meetings",
					args: {
						"source_name": frm.doc.name,
						"doctype": 'Lead',
						"ref_doctype": 'Meeting Schedule'
					},
					callback: function(r) {
						if(!r.exc) {
							var doc = frappe.model.sync(r.message);
							frappe.set_route("Form", r.message.doctype, r.message.name);
						}
					}
				})
			}, __("Create"));
			
			frm.add_custom_button(__("Meeting"), function() {
				return frappe.call({
					method : "productivity_next.api.make_meetings",
					args: {
						"source_name": frm.doc.name,
						"doctype": 'Lead',
						"ref_doctype": 'Meeting'
					},
					callback: function(r) {
						if(!r.exc) {
							var doc = frappe.model.sync(r.message);
							frappe.set_route("Form", r.message.doctype, r.message.name);
						}
					}
				})
			}, __("Create"));
		};

        if (erpnext.utils.CRMActivities) {
            class CustomCRMActivities extends erpnext.utils.CRMActivities {
                async create_task() {
                    let me = this;

                    let default_project = await frappe.db.get_single_value('Productify Subscription', 'default_marketing_project');
                    let default_task_type = await frappe.db.get_single_value('Productify Subscription', 'task_type') || 'Lead Follow Up';


                    let _create_task = () => {
                        frappe.prompt([
                            {
                                label: 'Subject',
                                fieldname: 'subject',
                                fieldtype: 'Data',
                                default: `Follow-up ${me.frm.doc.lead_name}`,
                                reqd: 1
                            },
                            {
                                label: 'Assignee',
                                fieldname: 'assignee',
                                fieldtype: 'Link',
                                options: 'User',
                                default: frappe.session.user,
                                reqd: 1
                            },
                            {
                                label: 'Expected Date',
                                fieldname: 'expected_date',
                                fieldtype: 'Date',
                                reqd: 1
                            },
                            {
                                label: 'Project', // ✅ New Field
                                fieldname: 'project',
                                fieldtype: 'Link',
                                options: 'Project', // Links to Project Doctype
                                default: default_project || '',
                                reqd: 0 // Not mandatory
                            },
                            {
                                label: 'Type', // ✅ New Field
                                fieldname: 'task_type',
                                fieldtype: 'Link',
                                default: default_task_type,
                                reqd: 1
                            }
                        ],
                        (values) => {
                            frappe.call({
                                method: 'frappe.client.insert',
                                args: {
                                    doc: {
                                        doctype: 'Task',
                                        subject: values.subject,
                                        assignee: values.assignee,
                                        exp_start_date: values.expected_date,
                                        exp_end_date: values.expected_date,
                                        expected_time: 0.25,
                                        status: 'Open',
                                        lead: me.frm.doc.name,
                                        project: values.project || null, // ✅ Save Project (if selected)
                                        type: values.task_type ,// ✅ Save Task Type,
                                        description : ''
                                    }
                                },
                                callback: function(response) {
                                    if (response.message) {
                                        frappe.msgprint(__('Task created successfully'));
                                        setTimeout(() => {
                                            me.load_tasks(); // ✅ Reload tasks after creation
                                        }, 300);
                                    }
                                }
                            });
                        },
                        __('Create Task'),
                        __('Create'));
                    };

                    $(".new-task-btn").off("click").on("click", _create_task);
                }

                load_tasks() {
                    let me = this;
                    frappe.call({
                        method: 'frappe.client.get_list',
                        args: {
                            doctype: 'Task',
                            filters: [
                                ['lead', '=', me.frm.doc.name],
                                ['status', '!=', 'Completed'],
                                ['status', '!=', 'Cancelled'],
                            ],
                            fields: ['name', 'subject', 'assignee', 'exp_start_date', 'expected_time', 'status'],
                            order_by: 'creation desc'
                        },
                        callback: function(task_response) {
                            if (task_response.message) {
                                let html = '';
                                task_response.message.forEach((task,index) => {
                                    html += `
                                        <div class="task-item" data-task-name="${task.name}" 
                                            style="width: 50%; margin-bottom: 10px; padding: 10px; border: 1px solid #ddd; border-radius: 5px; display: inline-block; margin-right: 2%; box-sizing: border-box;">
                                            <div>
                                                <b>📝 Subject:</b> ${task.subject} <br>
                                                <b>👤 Assignee:</b> ${task.assignee || 'Not Assigned'} <br>
                                                <b>📅 Start Date:</b> ${task.exp_start_date || 'N/A'} <br>
                                                <b>⏳ Expected Time:</b> ${task.expected_time || 0} hrs
                                            </div>
                                        </div>
                                    `;
                                });

                                me.frm.fields_dict['task_detail'].$wrapper.html(html);

                                // $(".task-checkbox").off("change").on("change", function() {
                                //     let task_name = $(this).data("task-name");
                                //     let status = $(this).is(":checked") ? 'Completed' : 'Open';
                                //     frappe.db.set_value('Task', task_name, 'status', status)
                                //         .then(() => {
                                //             frappe.msgprint(__('Task status updated'));
                                //             me.load_tasks(); // ✅ Reload after status update
                                //         });
                                // });
                            }
                        }
                    });
                }
            }

            erpnext.utils.CRMActivities = CustomCRMActivities;

            // ✅ Initialize and load tasks on form load/refresh
            let crmActivities = new erpnext.utils.CRMActivities({
                frm: frm,
                open_activities_wrapper: frm.custom_open_activities_wrapper,
                all_activities_wrapper: frm.custom_all_activities_wrapper,
                form_wrapper: frm.wrapper
            });

            frm.fields_dict['task_detail'].$wrapper.empty(); // ✅ Clear existing tasks
            crmActivities.load_tasks(); // ✅ Load existing tasks on form load/refresh
        }
		
    } 
});


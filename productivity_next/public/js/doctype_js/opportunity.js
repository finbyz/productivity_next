
frappe.ui.form.on('Opportunity', {
    refresh: function(frm) {
        frappe.call({
            method: 'productivity_next.api.get_defaults_productivity',
            callback: (response) => {
                if (response.message) {
                    frm.default_project = response.message.default_marketing_project || '';
                    frm.default_task_type = response.message.task_type || 'Lead Follow-up';
                    frm.allow_task_creation_for_opportunty = Number(response.message.create_task_instead_of_todo_for_opportunity_follow_up) === 1;

                    console.log("Allow Task Creation for Opportunity:", frm.allow_task_creation_for_opportunty);

                    // ✅ Only enable task creation if checkbox is checked
                    if (frm.allow_task_creation_for_opportunty) {
                        if (erpnext.utils.CRMActivities) {
                            class CustomCRMActivities extends erpnext.utils.CRMActivities {
                                async create_task() {
                                    let me = this;

                                    let { message } = await frappe.call({
                                        method: 'productivity_next.api.get_defaults_productivity'
                                    });

                                    let default_project = message.default_marketing_project || '';
                                    let default_task_type = message.task_type || 'Lead Follow-up';

                                    let _create_task = () => {
                                        frappe.prompt([
                                            {
                                                label: 'Subject',
                                                fieldname: 'subject',
                                                fieldtype: 'Data',
                                                default: `Follow-up ${me.frm.doc.title}`,
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
                                                label: 'Project', 
                                                fieldname: 'project',
                                                fieldtype: 'Link',
                                                options: 'Project', 
                                                default: default_project || '',
                                                reqd: 0 
                                            },
                                            {
                                                label: 'Type',
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
                                                        opportunity: me.frm.doc.name,
                                                        project: values.project || null,
                                                        type: values.task_type,
                                                        description : ''
                                                    }
                                                },
                                                callback: function(response) {
                                                    if (response.message) {
                                                        frappe.msgprint(__('Task created successfully'));
                                                        setTimeout(() => {
                                                            me.load_tasks(); 
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
                                                ['opportunity', '=', me.frm.doc.name],
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

                            frm.fields_dict['task_detail'].$wrapper.empty(); 
                            crmActivities.load_tasks(); 
                        }
                    }
                }
            }
        });
    },

    status: function(frm) {
        if (frm.doc.status == "Not Interested" || frm.doc.status == "Do Not Contact") {
            frm.set_value("contact_by", "");
            frm.set_value("contact_date", "");
        }
    }
});


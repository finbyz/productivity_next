// Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Task Management Tree"] = {
	"filters": [
        {
            fieldname: "project",
            label: __("Project"),
            fieldtype: "Link",
            options: "Project"
        },
        {
            fieldname: "task",
            label: __("Task"),
            fieldtype: "Link",
            options: "Task"
        },
        {
            fieldname: "task_owner",
            label: __("Task Owner"),
            fieldtype: "Link",
            options: "User",
            default: frappe.session.user
        },
        {
            fieldname: "show_completed_tasks",
            label: __("Show Completed Tasks"),
            fieldtype: "Check",
        }
    ],

    
    onload: function(report) {
        // Add refresh button
        report.page.add_inner_button(__('Refresh'), () => {
            report.refresh();
        });

        // Ensure event handlers are added after page is fully loaded
        $(document).ready(function() {
            // Remove existing event handlers
            $(document)
                .off('click', '.edit-task-btn')
                .off('click', '.copy-task-btn')
                .off('click', '.delete-task-btn')
                .off('click', '.add-subtask-btn')
                .off('click', '.goto-task-btn');

            // Add new event handlers using document-level delegation
            $(document).on('click', '.edit-task-btn', function(e) {
                try {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('Edit Task Button Clicked');
                    
                    let taskDataEncoded = $(this).attr('data-task');
                    if (!taskDataEncoded) {
                        console.error('No task data found');
                        return;
                    }
                    console.log("task encoded",$(this).attr('data-task'))
                    let taskData = JSON.parse(decodeURIComponent(taskDataEncoded));
                    console.log('Task Data:', taskData);
                    
                    showEditDialog(taskData, report);
                } catch (error) {
                    console.error('Error in edit task handler:', error);
                }
            });

            $(document).on('click', '.copy-task-btn', function(e) {
                try {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('Copy Task Button Clicked');
                    
                    let taskDataEncoded = $(this).attr('data-task');
                    if (!taskDataEncoded) {
                        console.error('No task data found');
                        return;
                    }
                    
                    let taskData = JSON.parse(decodeURIComponent(taskDataEncoded));
                    console.log('Task Data:', taskData);
                    
                    showCopyDialog(taskData, report);
                } catch (error) {
                    console.error('Error in copy task handler:', error);
                }
            });

            $(document).on('click', '.delete-task-btn', function(e) {
                try {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('Delete Task Button Clicked');
                    
                    let taskDataEncoded = $(this).attr('data-task');
                    if (!taskDataEncoded) {
                        console.error('No task data found');
                        return;
                    }
                    
                    let taskData = JSON.parse(decodeURIComponent(taskDataEncoded));
                    console.log('Task Data:', taskData);
                    
                    showDeleteDialog(taskData, report);
                } catch (error) {
                    console.error('Error in delete task handler:', error);
                }
            });

            $(document).on('click', '.add-subtask-btn', function(e) {
                try {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('Add Subtask Button Clicked');
                    
                    let taskDataEncoded = $(this).attr('data-task');
                    if (!taskDataEncoded) {
                        console.error('No task data found');
                        return;
                    }
                    
                    let taskData = JSON.parse(decodeURIComponent(taskDataEncoded));
                    console.log('Task Data:', taskData);
                    
                    showAddSubtaskDialog(taskData, report);
                } catch (error) {
                    console.error('Error in add subtask handler:', error);
                }
            });

            $(document).on('click', '.goto-task-btn', function(e) {
                try {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('Go to Task Button Clicked');
                    
                    let taskId = $(this).attr('data-task-id');
                    if (taskId) {
                        window.open(`/app/task/${taskId}`, '_blank');
                    } else {
                        console.error('No task ID found');
                    }
                } catch (error) {
                    console.error('Error in go to task handler:', error);
                }
            });
        });
    },

    "formatter": function(value, row, column, data, default_formatter) {
        console.log(data)
        if (column.fieldname === "edit_task" && !data.is_project) {
            // Create a copy of data and remove progress field
            const dataWithoutProgress = {...data};
            delete dataWithoutProgress.progress;

            // Safely handle potential undefined or null values
            const safeTaskData = JSON.stringify({
                task_id: dataWithoutProgress.task_id || '',
                task: dataWithoutProgress.task ? dataWithoutProgress.task.toString().trim().split(' - <span')[0].trim() : '',
                description: dataWithoutProgress.description ? dataWithoutProgress.description.toString().trim() : '',
                // Add other relevant fields as needed
                ...dataWithoutProgress
            });
            console.log("safe",safeTaskData)

            return `
                <div class="btn-group">
                    <button class="btn btn-xs btn-primary goto-task-btn" 
                        data-task-id='${dataWithoutProgress.task_id || ''}'>
                        <i class="fa fa-external-link"></i>
                    </button>
                    <button class="btn btn-xs btn-warning edit-task-btn" 
                        data-task='${encodeURIComponent(safeTaskData)}'>
                        <i class="fa fa-pencil"></i>
                    </button>
                    <button class="btn btn-xs btn-info copy-task-btn" 
                        data-task='${encodeURIComponent(safeTaskData)}'>
                        <i class="fa fa-copy"></i>
                    </button>
                    <button class="btn btn-xs btn-danger delete-task-btn" 
                        data-task='${encodeURIComponent(safeTaskData)}'>
                        <i class="fa fa-trash"></i>
                    </button>
                    <button class="btn btn-xs btn-success add-subtask-btn" 
                        data-task='${encodeURIComponent(safeTaskData)}'>
                        <i class="fa fa-plus"></i>
                    </button>
                </div>`;
        }
        return default_formatter(value, row, column, data);
    }
}

// Function to show edit dialog
function showEditDialog(taskData, report) {
    // Create a copy of taskData and remove progress field
    const taskDataWithoutProgress = {...taskData};
    delete taskDataWithoutProgress.progress;

    let d = new frappe.ui.Dialog({
        title: __('Edit Task'),
        fields: [
            {
                label: __('Task Name'),
                fieldname: 'task',
                fieldtype: 'Data',
                read_only: 1,
                default: taskDataWithoutProgress.task.trim()
            },
            {
                label: __('Task Owner'),
                fieldname: 'task_owner',
                fieldtype: 'Link',
                options: 'User',
                default: taskDataWithoutProgress.task_owner
            },
            {
                label: __('Status'),
                fieldname: 'status',
                fieldtype: 'Select',
                read_only:1,
                options: 'Open\nWorking\nPending Review\nCompleted\nCancelled',
                default: taskDataWithoutProgress.status
            },
            {
                label: __('Priority'),
                fieldname: 'priority',
                fieldtype: 'Select',
                options: 'Low\nMedium\nHigh',
                default: taskDataWithoutProgress.priority
            },
            {
                label: __('Expected Start Date'),
                fieldname: 'exp_start_date',
                fieldtype: 'Date',
                default: taskDataWithoutProgress.exp_start_date
            },
            {
                label: __('Expected End Date'),
                fieldname: 'exp_end_date',
                fieldtype: 'Date',
                default: taskDataWithoutProgress.exp_end_date
            },
            {
                label: __('Description'),
                fieldname: 'description',
                fieldtype: 'Text Editor',
                default: taskDataWithoutProgress.description
            }
        ],
        primary_action_label: __('Update Task'),
        secondary_action_label: taskDataWithoutProgress.is_group ? __('Update All Child Tasks') : null,
        
        primary_action: function() {
            updateTask(d, taskDataWithoutProgress, report, 'single');
        }
    });

    // Add secondary action for parent tasks
    if (taskDataWithoutProgress.is_group) {
        d.set_secondary_action(() => {
            updateTask(d, taskDataWithoutProgress, report, 'all');
        });
    }

    d.show();
}

// Function to show copy dialog
function showCopyDialog(taskData, report) {
    // Create a copy of taskData and remove progress field
    const taskDataWithoutProgress = {...taskData};
    delete taskDataWithoutProgress.progress;

    let d = new frappe.ui.Dialog({
        title: __('Copy Task Hierarchy'),
        fields: [
            {
                label: __('Original Task'),
                fieldname: 'task',
                fieldtype: 'Data',
                read_only: 1,
                default: taskDataWithoutProgress.task.trim()
            },
            {
                label: __('New Project'),
                fieldname: 'new_project',
                fieldtype: 'Link',
                options: 'Project',
                description: __('Leave empty to copy without project assignment')
            },
            {
                label: __('New Task Owner'),
                fieldname: 'new_task_owner',
                fieldtype: 'Link',
                options: 'User',
                description: __('Leave empty to keep original task owners')
            },
            {
                fieldname: 'copy_info',
                fieldtype: 'HTML',
                options: `
                    <div class="alert alert-info">
                        <p><strong>${__('Note')}:</strong></p>
                        <ul>
                            <li>${__('This will copy the entire task hierarchy including:')}</li>
                            <li>${__('- All child tasks')}</li>
                            <li>${__('- Descriptions')}</li>
                            <li>${__('- Attachments')}</li>
                            ${!taskDataWithoutProgress.is_project ? 
                                `<li>${__('If no project is selected, the project name will be included in the task subject')}</li>` 
                                : ''}
                        </ul>
                    </div>`
            }
        ],
        primary_action_label: __('Copy'),
        primary_action: function() {
            copyTaskHierarchy(d, taskDataWithoutProgress, report);
        }
    });

    d.show();
}

// Function to show delete dialog
function showDeleteDialog(taskData, report) {
    // Create a copy of taskData and remove progress field
    const taskDataWithoutProgress = {...taskData};
    delete taskDataWithoutProgress.progress;

    let d = new frappe.ui.Dialog({
        title: __('Delete Task'),
        fields: [
            {
                label: __('Task Name'),
                fieldname: 'task',
                fieldtype: 'Data',
                read_only: 1,
                default: taskDataWithoutProgress.task.trim()
            },
            {
                label: __('Delete Mode'),
                fieldname: 'delete_mode',
                fieldtype: 'Select',
                options: [
                    {label: __('Delete Single Task'), value: 'single'},
                    {label: __('Delete Task with Children'), value: 'all'}
                ],
                default: 'single',
                depends_on: `eval:${taskDataWithoutProgress.is_group}`,
                mandatory: 1
            },
            {
                fieldname: 'warning',
                fieldtype: 'HTML',
                options: `
                    <div class="alert alert-warning">
                        <p><strong>${__('Warning')}:</strong> ${__('This action cannot be undone.')}</p>
                        ${taskDataWithoutProgress.is_group ? 
                            `<p>${__('This task has child tasks. Selecting "Delete Task with Children" will delete all child tasks as well.')}</p>` 
                            : ''}
                    </div>`
            },
            {
                label: __('Confirmation'),
                fieldname: 'confirmation',
                fieldtype: 'Check',
                label: __('I understand this action cannot be undone'),
                reqd: 1
            }
        ],
        primary_action_label: __('Delete Task'),
        primary_action: function() {
            deleteTask(d, taskDataWithoutProgress, report);
        }
    });

    d.show();
}


// Function to handle task update
function updateTask(dialog, taskData, report, update_mode) {
    let values = dialog.get_values();
    
    if (!values) return;

    // Validate dates
    if (values.exp_start_date && values.exp_end_date && 
        frappe.datetime.str_to_obj(values.exp_start_date) > frappe.datetime.str_to_obj(values.exp_end_date)) {
        frappe.throw(__("Expected End Date cannot be before Expected Start Date"));
        return;
    }

    frappe.call({
        method: 'task_management.task_management.report.task_analysis.task_analysis.update_task',
        args: {
            task_data: values,
            update_mode: update_mode
        },
        freeze: true,
        freeze_message: update_mode === 'single' ? 
            __('Updating Task...') : 
            __('Updating Task and Child Tasks...'),
        callback: function(r) {
            if (!r.exc) {
                frappe.show_alert({
                    message: update_mode === 'single' ? 
                        __('Task updated successfully') : 
                        __('Task and child tasks updated successfully'),
                    indicator: 'green'
                });
                dialog.hide();
                report.refresh();
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    indicator: 'red',
                    message: r.exc
                });
            }
        }
    });
}

// Function to handle task deletion
function deleteTask(dialog, taskData, report) {
    let values = dialog.get_values();
    
    if (!values.confirmation) {
        frappe.throw(__('Please confirm deletion'));
        return;
    }

    frappe.call({
        method: 'task_management.task_management.report.task_analysis.task_analysis.delete_task',
        args: {
            task_data: values,
            delete_mode: values.delete_mode || 'single'
        },
        freeze: true,
        freeze_message: values.delete_mode === 'single' ? 
            __('Deleting Task...') : 
            __('Deleting Task and Child Tasks...'),
        callback: function(r) {
            if (!r.exc) {
                frappe.show_alert({
                    message: values.delete_mode === 'single' ? 
                        __('Task deleted successfully') : 
                        __('Task and child tasks deleted successfully'),
                    indicator: 'green'
                });
                dialog.hide();
                report.refresh();
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    indicator: 'red',
                    message: r.exc
                });
            }
        }
    });
}

// Function to handle task hierarchy copying
function copyTaskHierarchy(dialog, taskData, report) {
    let values = dialog.get_values();
    
    frappe.call({
        method: 'task_management.task_management.report.task_analysis.task_analysis.copy_task_hierarchy',
        args: {
            task_data: taskData,
            new_project: values.new_project,
            new_task_owner: values.new_task_owner
        },
        freeze: true,
        freeze_message: __('Copying Task Hierarchy...'),
        callback: function(r) {
            if (!r.exc) {
                frappe.show_alert({
                    message: __('Task hierarchy copied successfully'),
                    indicator: 'green'
                });
                dialog.hide();
                report.refresh();
                
                // Open the new task in a new tab
                // if (r.message && r.message.new_task_id) {
                //     frappe.set_route('Form', 'Task', r.message.new_task_id);
                // }
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    indicator: 'red',
                    message: r.exc
                });
            }
        }
    });
}

function showAddSubtaskDialog(taskData, report) {
    console.log(taskData)
    let d = new frappe.ui.Dialog({
        title: __('Add Subtask'),
        fields: [
            {
                label: __('Parent Task'),
                fieldname: 'parent_task',
                fieldtype: 'Data',
                read_only: 1,
                default: taskData.task_id.trim()
            },
            {
                label: __('Project'),
                fieldname: 'project',
                fieldtype : 'Data',
                read_only: 1,
                default: taskData.project
            },
            {
                label: __('Task Subject'),
                fieldname: 'subject',
                fieldtype: 'Data',
                reqd: 1
            },
            {
                label: __('Task Owner'),
                fieldname: 'task_owner',
                fieldtype: 'Link',
                options: 'User',
                default: frappe.session.user
            },
            {
                label: __('Status'),
                fieldname: 'status',
                fieldtype: 'Select',
                read_only: 1,
                options: 'Open\nWorking\nPending Review\nCompleted\nCancelled',
                default: 'Open'
            },
            {
                label: __('Priority'),
                fieldname: 'priority',
                fieldtype: 'Select',
                options: 'Low\nMedium\nHigh',
                default: taskData.priority || 'Medium'
            },
            {
                label: __('Expected Start Date'),
                fieldname: 'exp_start_date',
                fieldtype: 'Date',
                default: taskData.exp_end_date
            },
            {
                label: __('Expected End Date'),
                fieldname: 'exp_end_date',
                fieldtype: 'Date'
            },
            {
                label: __('Description'),
                fieldname: 'description',
                fieldtype: 'Text Editor'
            }
        ],
        primary_action_label: __('Create Subtask'),
        primary_action: function() {
            addSubtask(d, taskData, report);
        }
    });

    d.show();
}

// Function to handle adding a subtask
function addSubtask(dialog, parentTaskData, report) {
    let values = dialog.get_values();
    
    if (!values) return;

    // Validate dates
    if (values.exp_start_date && values.exp_end_date && 
        frappe.datetime.str_to_obj(values.exp_start_date) > frappe.datetime.str_to_obj(values.exp_end_date)) {
        frappe.throw(__("Expected End Date cannot be before Expected Start Date"));
        return;
    }

    // Add parent task information
    values.parent_task = parentTaskData.task_id.trim();
    values.project = parentTaskData.project || null;
    frappe.call({
        method: 'frappe.client.insert',
        args: {
            doc: {
                doctype: 'Task',
                subject: values.subject,
                parent_task: values.parent_task,
                project: values.project,
                task_owner_: values.task_owner,
                status: values.status,
                priority: values.priority,
                exp_start_date: values.exp_start_date,
                exp_end_date: values.exp_end_date,
                description: values.description
            }
        },
        freeze: true,
        freeze_message: __('Creating Subtask...'),
        callback: function(r) {
            if (!r.exc) {
                frappe.show_alert({
                    message: __('Subtask created successfully'),
                    indicator: 'green'
                });
                dialog.hide();
                report.refresh();
                
                // Optionally, open the new subtask in a form view
                // if (r.message) {
                //     frappe.set_route('Form', 'Task', r.message.name);
                // }
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    indicator: 'red',
                    message: r.exc
                });
            }
        }
    });
}
frappe.pages['timesheet-verificati'].on_page_load = function(wrapper) {
    frappe.require("assets/productivity_next/css/timesheet_verificati.css");
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Timesheet Verification',
        single_column: true
    });

    // Render HTML
    $(frappe.render_template("timesheet_verificati", {})).appendTo(page.body);

    // Helper to get filter values
    function get_filters() {
        return {
            employee: $("#employee_select").val(),
            date: $("#date_select").val()
        };
    }

    // Fetch and render summary cards
    function fetch_and_render_summary() {
        frappe.call({
            method: "productivity_next.productivity_next.page.timesheet_verificati.timesheet_verificati.get_summary_data",
            args: get_filters(),
            callback: function(r) {
                let d = r.message;
                // Calls
                $("#calls-incoming-duration").text(d.calls.incoming.duration);
                $("#calls-incoming-count").text(d.calls.incoming.count);
                $("#calls-outgoing-duration").text(d.calls.outgoing.duration);
                $("#calls-outgoing-count").text(d.calls.outgoing.count);
                $("#calls-total").text(d.calls.total);

                // Meetings
                $("#meetings-internal-duration").text(d.meetings.internal.duration);
                $("#meetings-internal-count").text(d.meetings.internal.count);
                $("#meetings-external-duration").text(d.meetings.external.duration);
                $("#meetings-external-count").text(d.meetings.external.count);
                $("#meetings-total").text(d.meetings.total);

                // System
                $("#system-app-duration").text(d.system.app.duration);
                $("#system-app-count").text(d.system.app.count);
                $("#system-web-duration").text(d.system.web.duration);
                $("#system-web-count").text(d.system.web.count);
                $("#system-total").text(d.system.total);
            }
        });
    }

    // Fetch employees for filter
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Employee",
            fields: ["name", "employee_name"],
            limit_page_length: 1000
        },
        callback: function(r) {
            let opts = r.message.map(e => `<option value="${e.name}">${e.employee_name || e.name}</option>`).join("");
            $("#employee_select").html(opts);
            // Set default to current user if possible
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Employee",
                    filters: { user_id: frappe.session.user },
                    fieldname: "name"
                },
                callback: function(res) {
                    if(res.message && res.message.name) {
                        $("#employee_select").val(res.message.name);
                    }
                    // Set date to today
                    $("#date_select").val(frappe.datetime.get_today());
                    fetch_and_render_summary();
                }
            });
        }
    });

    // Fetch button handler
    $(document).on("click", "#fetch_btn", function() {
    fetch_and_render_summary();
        $("#details-section").hide();
    });

    // Remove dynamic button insertion, only keep click handlers
    // Preview Timesheet handler
    $(document).on("click", "#preview_timesheet_btn", function() {
        $("#timesheet-preview-section").remove();
        frappe.call({
            method: "productivity_next.productivity_next.page.timesheet_verificati.timesheet_verificati.preview_timesheet",
            args: get_filters(),
            callback: function(r) {
                let logs = r.message.logs || [];
                let total_hours = r.message.total_hours || 0;
                let project_summary = r.message.project_summary || [];
				console.log("meg",r.message)
                let docstatus = r.message.docstatus;
                let timesheet_name = r.message.timesheet_name;
                let action_btn = "";
                if (timesheet_name) {
                    if (docstatus == 0) {
                        action_btn = `<button class='btn btn-success btn-sm me-2' id='submit_timesheet_btn' data-name='${timesheet_name}'>Submit Timesheet</button>`;
                    } else if (docstatus == 1) {
                        action_btn = `<button class='btn btn-danger btn-sm me-2' id='cancel_timesheet_btn' data-name='${timesheet_name}'>Cancel Timesheet</button>`;
                    }
                }
                let html = `<div id=\"timesheet-preview-section\" class=\"card p-4 mt-4\">
                    <div class=\"d-flex justify-content-between align-items-center mb-2\">
                        <h4 class=\"mb-0\">Timesheet Preview</h4>
                        <div>${action_btn}</div>
                    </div>
                    <div class=\"table-responsive\">
                        <table class=\"table table-bordered table-hover\">
                            <thead>
                                <tr>
                                    <th>Activity Type</th>
                                    <th>Task</th>
                                    <th>Project</th>
                                    <th>Issue</th>
                                    <th>Hours</th>
                                    <th>From Time</th>
                                    <th>To Time</th>
                                    <th>Description</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${logs.map(row => `
                                    <tr>
                                        <td>${row.activity_type || ""}</td>
                                        <td>${row.task || ""}</td>
                                        <td>${row.project || ""}</td>
                                        <td>${row.issue || ""}</td>
                                        <td>${row.hours || ""}</td>
                                        <td>${row.from_time || ""}</td>
                                        <td>${row.to_time || ""}</td>
                                        <td>${row.description || ""}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                    <div class=\"mt-3\"><strong>Total Time:</strong> ${total_hours} hours</div>
                    <div class=\"mt-3\">
                        <h5>Project-wise Time Segregation</h5>
                        <div class=\"table-responsive\">
                            <table class=\"table table-bordered table-hover\">
                                <thead>
                                    <tr>
                                        <th>Project</th>
                                        <th>Total Hours</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${project_summary.map(row => `
                                        <tr>
                                            <td>${row.project}</td>
                                            <td>${row.total_hours}</td>
                                        </tr>
                                    `).join("")}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>`;
                $(".timesheet-verificati-filters").after(html);
            }
        });
    });

    // Submit Timesheet handler
    $(document).on("click", "#submit_timesheet_btn", function() {
        let name = $(this).data("name");
		console.log("me",name)
        frappe.call({
            method: "productivity_next.productivity_next.page.timesheet_verificati.timesheet_verificati.submit_timesheet",
            args: {name},
            callback: function() {
                frappe.msgprint("Timesheet submitted.");
                $("#preview_timesheet_btn").click();
            }
        });
    });
    // Cancel Timesheet handler
    $(document).on("click", "#cancel_timesheet_btn", function() {
        let name = $(this).data("name");
        frappe.call({
            method: "frappe.client.cancel",
            args: {doctype: "Timesheet", name},
            callback: function() {
                frappe.msgprint("Timesheet cancelled.");
                $("#preview_timesheet_btn").click();
            }
        });
    });

    // Create Timesheet handler
    $(document).on("click", "#create_timesheet_btn", function() {
        frappe.call({
            method: "productivity_next.productivity_next.page.timesheet_verificati.timesheet_verificati.create_timesheet_for_employee_date",
            args: get_filters(),
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.msgprint("Timesheet created: " + r.message.timesheet);
                    $("#preview_timesheet_btn").click(); // Refresh preview
                } else {
                    frappe.msgprint(r.message && r.message.message ? r.message.message : "Failed to create timesheet.");
                }
            }
        });
    });

    // Card click handlers
    $("#card-calls").on("click", function() {
        // Fetch all projects first
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Project",
                fields: ["name", "project_name"],
                limit_page_length: 1000
            },
            callback: function(projects_res) {
                let projects = projects_res.message || [];
                frappe.call({
                    method: "productivity_next.productivity_next.page.timesheet_verificati.timesheet_verificati.get_calls_details",
                    args: get_filters(),
                    callback: function(r) {
                        let d = r.message.details;
                        let project_summary = r.message.project_summary;
						d = d.slice().sort((a, b) => {
							if (a.project && !b.project) return -1;
							if (!a.project && b.project) return 1;
							return 0;
						});
                        let html = `
                        <div class="card p-4">
                            <h4>Calls Details</h4>
                            <div class="table-responsive mb-4">
                                <table class="table table-bordered table-hover">
                                    <thead>
                                        <tr>
                                            <th>Call DateTime</th>
                                            <th>Contact</th>
                                            <th>Link Name</th>
											<th>Client</th>
											<th>Customer No.</th>
                                            <th>Type</th>
                                            <th>Duration</th>
                                            <th style="min-width:120px">Project</th>
                                        </tr>
                                    </thead>
                                    <tbody>
									${d.map((call, idx) => {
										let projectCell = "";
										if (call.project) {
											projectCell = `<span>${call.project}</span>`;
										} else {
											let opts = `<option value=''>No Project</option>` + projects.map(p => `<option value='${p.name}' ${call.project === p.name ? 'selected' : ''}>${p.project_name || p.name}</option>`).join("");
											projectCell = `<select class=\"form-select project-select\" data-idx=\"${idx}\">${opts}</select>`;
										}
										return `
										<tr>
											<td>${call.call_datetime || ""}</td>
											<td>${call.contact || ""}</td>
											<td>${call.link_name || ""}</td>
											<td>${call.client || ""}</td>
											<td>${call.customer_no || ""}</td>
											<td>${call.calltype || ""}</td>
											<td>${call.duration || ""}</td>
											<td style=\"min-width:220px\">${projectCell}</td>
										</tr>
										`;
									}).join("")}
                                    </tbody>
                                </table>
                            </div>
                            <div class="d-flex justify-content-center mt-2">
                                <button class="btn btn-sm btn-dark" id="bulk-update-projects">Bulk Update Projects</button>
                            </div>
                            <h5 class="mt-4">Project-wise Call Time</h5>
                            <div class="table-responsive">
                                <table class="table table-bordered table-hover">
                                    <thead>
                                        <tr>
                                            <th>Project</th>
                                            <th>Total Time</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${project_summary.map(row => `
                                            <tr>
                                                <td>${row.project}</td>
                                                <td>${row.total_time}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </div>
                `;
                $("#details-section").html(html).show();

                        // Initialize Select2 for all project dropdowns
                        setTimeout(function() {
                            $(".project-select").select2({
                                width: '100%',
                                dropdownParent: $("#details-section")
                            });
                        }, 0);

                        // Bulk update handler
                        $("#bulk-update-projects").on("click", function() {
                            let call_projects = d.map((call, idx) => {
                                return {
                                    name: call.name,
                                    project: $(".project-select[data-idx='"+idx+"']").val()
                                };
                            });
                    frappe.call({
                                method: "productivity_next.productivity_next.page.timesheet_verificati.timesheet_verificati.bulk_set_call_projects",
                                args: { call_projects: JSON.stringify(call_projects) },
                        callback: function() {
                                    frappe.msgprint("Projects updated for all calls.");
                            fetch_and_render_summary();
                                    $("#details-section").hide();
                        }
                    });
                        });
                    }
                });
            }
        });
    });

    $("#card-meetings").on("click", function() {
        frappe.call({
            method: "productivity_next.productivity_next.page.timesheet_verificati.timesheet_verificati.get_meetings_details",
            args: get_filters(),
            callback: function(r) {
                let d = r.message.details;
                let project_summary = r.message.project_summary;
                let html = `
                <div class="card p-4">
                    <h4>Meetings Details</h4>
                    <div class="table-responsive mb-4">
                        <table class="table table-bordered table-hover">
                            <thead>
                                <tr>
                                    <th>Project</th>
                                    <th>Discussion</th>
                                    <th>Arranged By</th>
                                    <th>Company Rep</th>
                                    <th>Party Rep</th>
                                    <th>Duration</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${d.map(m => `
                                    <tr>
                                        <td>${m.project || "No Project"}</td>
                                        <td>${m.discussion || ""}</td>
                                        <td>${m.arranged_by || ""}</td>
                                        <td>${m.company_representative || ""}</td>
                                        <td>${m.party_representative || ""}</td>
                                        <td>${m.duration || ""}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                    <h5>Project-wise Meeting Time</h5>
                    <div class="table-responsive">
                        <table class="table table-bordered table-hover">
                            <thead>
                                <tr>
                                    <th>Project</th>
                                    <th>Total Time</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${project_summary.map(row => `
                                    <tr>
                                        <td>${row.project}</td>
                                        <td>${row.total_time}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </div>
                `;
                $("#details-section").html(html).show();
            }
        });
    });

    $("#card-system").on("click", function() {
        frappe.call({
            method: "productivity_next.productivity_next.page.timesheet_verificati.timesheet_verificati.get_system_details",
            args: get_filters(),
            callback: function(r) {
                let d = r.message;
                let html = `
                <div class="card p-4">
                    <h4>System Usage Project-wise</h4>
                    <div class="table-responsive">
                        <table class="table table-bordered table-hover">
                            <thead>
                                <tr>
                                    <th>Project</th>
                                    <th>Total Time</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${d.map(row => `
                                    <tr>
                                        <td>${row.project || "No Project"}</td>
                                        <td>${row.total_time || "00:00"}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </div>
                `;
                $("#details-section").html(html).show();
            }
        });
    });

    // Hide details on card click elsewhere
    $(document).on("click", function(e) {
        if (!$(e.target).closest('.summary-card, #details-section').length) {
            $("#details-section").hide();
        }
    });
};
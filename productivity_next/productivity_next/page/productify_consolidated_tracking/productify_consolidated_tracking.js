frappe.pages['Productify Consolidated Tracking'].on_page_load = function (wrapper) {
    new UserProfile(wrapper);
}


UserProfile = class UserProfile {
    constructor(wrapper) {
        this.wrapper = $(wrapper);
        this.page = frappe.ui.make_app_page({
            parent: wrapper,
        });
        this.sidebar = this.wrapper.find(".layout-side-section");
        this.toggle_button = this.wrapper.find(".sidebar-toggle-placeholder");
        this.main_section = this.wrapper.find(".layout-main-section");
        this.buttonsInitialized = false;
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('start_date') == null && urlParams.get('end_date') == null) {
            var currentDate = new Date();
            currentDate.setDate(currentDate.getDate() - 1); // Set to one day before today
            var day = currentDate.getDate().toString().padStart(2, '0');
            var month = (currentDate.getMonth() + 1).toString().padStart(2, '0');
            var year = currentDate.getFullYear();
            this.selected_start_date = year + '-' + month + '-' + day;
            this.selected_end_date = year + '-' + month + '-' + day; // End date also one day before today
        }
        else {
            this.selected_start_date = urlParams.get('start_date');
            this.selected_end_date = urlParams.get('end_date');
        }
        if (urlParams.get('employee') != null && urlParams.get('employee') != 'undefined') {
            this.selected_employee = urlParams.get('employee');
        }
        else {
            this.selected_employee = null;
        }
        this.hide_sidebar_and_toggle();
        this.wrapper.bind("show", () => {
            this.show();
        });
    }

    hide_sidebar_and_toggle() {
        this.sidebar.hide();
        // this.toggle_button.hide();
        this.main_section.css('width', '100%');
    }

    show() {
        this.user_id = frappe.session.user;
        frappe.dom.freeze(__("Loading user profile") + "...");
        frappe.db.exists("User", this.user_id).then((exists) => {
            frappe.dom.unfreeze();
            if (exists) {
                this.make_user_profile();
            } else {
                frappe.msgprint(__("User does not exist"));
            }
        });
    }

    
	finish_user_profile_setup() {
		this.setup_user_search();
		this.setup_timespan();
		this.main_section.empty().append(frappe.render_template("productify_consolidated_tracking"));
		this.fetch_and_render_admin_data();	
		this.render_bar_chart();
		// this.render_client_time_chart();
		// this.fetch_and_render_user_data();
		this.render_line_chart();	
		this.update_client_calls_chart_data();
	}
	setup_timespan() {
        this.$user_search_button = this.page.set_primary_action(
            __("Select Timespan"),
            () => this.setup_timespan_dialog(),
        );
    }

    setup_timespan_dialog() {
		let dialog = new frappe.ui.Dialog({
			title: __("Select Timespan"),
			fields: [
				{
					fieldtype: "DateRange",
					fieldname: "timespan_range",
					label: __("Timespan Range"),
					description: __("Select a start and end date"),
				},
			],
			primary_action_label: __("Go"),
			primary_action: (data) => {
				let startDate, endDate;
				if (data.timespan_range) {
					[startDate, endDate] = data.timespan_range;
				} else {
					const today = new Date();
					endDate = today.toISOString().split('T')[0];
	
					const oneYearAgo = new Date(new Date().setFullYear(today.getFullYear() - 1));
					startDate = oneYearAgo.toISOString().split('T')[0];
				}
	
				dialog.hide();
				const newUrl = new URL(window.location.href);
				newUrl.searchParams.set('start_date', startDate);
				newUrl.searchParams.set('end_date', endDate);
				window.history.pushState({ path: newUrl.toString() }, '', newUrl.toString());
				const urlParams = new URLSearchParams(window.location.search);
				this.selected_start_date = urlParams.get('start_date');
				this.selected_end_date = urlParams.get('end_date');			
				this.make_user_profile();
			},
		});
		dialog.show();
	}
	make_user_profile() {
		this.user = frappe.user_info(this.user_id);
		if (!this.selected_employee) { 
			this.page.set_title("All Employees" + " ( FROM " + this.selected_start_date + " TO " + this.selected_end_date + " )");
		} else {
			frappe.db.get_doc("Employee", this.selected_employee)
				.then(employee => {
					this.page.set_title("All Employees" + " ( FROM " + this.selected_start_date + " TO " + this.selected_end_date + " )"); 
					this.finish_user_profile_setup();
				})
				.catch(error => {
					console.error("Failed to get employee details:", error);
                    frappe.msgprint(__("Failed to load employee details"));
				});
		}
		if (!this.selected_employee) { 
			this.finish_user_profile_setup();
		}
	}
    setup_user_search() {
        if (!this.buttonsInitialized) {  // Check if buttons have already been initialized
            // Add a refresh button with an icon
            this.page.add_action_icon("refresh", () => {
                window.location.reload();
            });

            this.buttonsInitialized = true;  // Set the flag to true after adding buttons
        }
    }

    show_user_search_dialog() {
        let dialog = new frappe.ui.Dialog({
            title: __("Change Employee"),
            fields: [
                {
                    fieldtype: "Link",
                    fieldname: "employee",
                    options: "Employee",
                    label: __("Employee"),
                },
            ],
            primary_action_label: __("Go"),
            primary_action: ({ employee }) => {
                dialog.hide();
                this.selected_employee = employee;
				this.make_user_profile()
				const newUrl = new URL(window.location.href);
				newUrl.searchParams.set('employee', employee);
				window.history.pushState({ path: newUrl.toString() }, '', newUrl.toString());
            },
        });
        dialog.show();

    }
	render_bar_chart() {
		this.barchart = new frappe.Chart(".performance-bar-chart", {
			type: "bar",
			height: 250,
			width: 400,
			colors: ["#00A6E0"],
			tooltipOptions: {
				formatTooltipX: d => (d + '').toUpperCase(),
				formatTooltipY: d => d + ' CHANGES',
			},
			data: {labels: [],
				datasets: [
					{
						values: [] 
					}
				]},
				isNavigable: true,
			});
			this.update_bar_chart_data();	
	};
	update_bar_chart_data() {
		frappe
			.xcall("productivity_next.productivity_next.page.productify_consolidated_tracking.productify_consolidated_tracking.get_barchart_data", {
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {	
				} else {
					this.barchart.update(r);
				}
			});
	};
	// fetch_and_render_user_data() {	
	//	  frappe.call({
	//	  	method: "productivity_next.productivity_next.page.productify_consolidated_tracking.productify_consolidated_tracking.get_admin_data",
	//	  	args: {
	//	  		user: "Administrator",
	//	  		start_date: this.selected_start_date,
	//	  		end_date: this.selected_end_date,
	//	  	},
	//	 	callback: (r) => {
	//	 		if (r.message) {
	//	 			this.render_user_data(r.message);
	//	 			$(document).ready(function() {
	//	 				$('#logCountModalTrigger').click(function() {
	//	 					$('#logCountModal').modal('show');
	//	 				});
	//	 			});					
	//	 		}
	//	 	}
	//	 });
	// };
	render_user_data(data) {
		let start_date_ = this.selected_start_date;
		let end_date_ = this.selected_end_date;
		console.log('Data received:', data);
	
		let total_hours = 0;
		let total_idle_hours = 0;
		let total_meeting_hours = 0;
		let total_meeting_count = 0;
		let total_incoming_fincall_hours = 0;
		let total_outgoing_fincall_hours = 0;
		let total_unique_doc = 0;
		let total_application_usage = 0;
		let total_version_count = 0;
		let total_incoming_fincall_count = 0;
		let total_outgoing_fincall_count = 0;
		let total_missed_fincall_count = 0;
		let total_rejected_fincall_count = 0;
		let internal_incoming_fincall_count = 0;
		let internal_outgoing_fincall_count = 0;
		let internal_missed_fincall_count = 0;
		let internal_rejected_fincall_count = 0;
		let internal_total_incoming_fincall_hours = 0;
		let internal_total_outgoing_fincall_hours = 0;
		let total_days = 1;
		let internal_meeting_hours = 0;
		let internal_meeting_count = 0;
		let domain_usage = 0;
	
		for (let i in data.combined_employee_data) {
			const employee = data.combined_employee_data[i];
			total_hours += employee.total_hours || 0;
			total_idle_hours += employee.total_idle_time || 0;
			total_incoming_fincall_hours += employee.total_incoming_fincall_count || 0;
			total_outgoing_fincall_hours += employee.total_outgoing_fincall_count || 0;
			total_unique_doc += employee.total_unique_doc || 0;
			total_application_usage += employee.application_usage || 0;
			total_version_count += employee.version_count || 0;
			total_incoming_fincall_count += employee.incoming_fincall_count || 0;
			total_outgoing_fincall_count += employee.outgoing_fincall_count || 0;
			total_missed_fincall_count += employee.missed_fincall_count || 0;
			total_rejected_fincall_count += employee.rejected_fincall_count || 0;
			internal_incoming_fincall_count += employee.internal_incoming_fincall_count || 0;
			internal_outgoing_fincall_count += employee.internal_outgoing_fincall_count || 0;
			internal_missed_fincall_count += employee.internal_missed_fincall_count || 0;
			internal_rejected_fincall_count += employee.internal_rejected_fincall_count || 0;
			internal_total_incoming_fincall_hours += employee.internal_total_incoming_fincall_count || 0;
			internal_total_outgoing_fincall_hours += employee.internal_total_outgoing_fincall_count || 0;
			total_days += employee.total_days || 1;
			domain_usage += employee.domain_used || 0;
		}
		console.log('Total hours:', domain_usage);
		total_meeting_hours = data.combined_employee_data[0].meeting_admin_data[0].total_meeting_duration || 0;
		total_meeting_count = data.combined_employee_data[0].meeting_admin_data[0].meeting_count || 0;
		internal_meeting_hours = data.combined_employee_data[0].meetings_admin_data_internal[0].total_meeting_duration || 0;
		internal_meeting_count = data.combined_employee_data[0].meetings_admin_data_internal[0].meeting_count || 0;
		let employee_data = this.selected_employee || this.user_id;
	
		const container = this.main_section.find("#user-data-cards");
		container.empty();
	
		let wholedata = `
			<div class="title-area">
				<h4 class="card-title">Productify Data</h4>
			</div>
			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Total Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;">${this.convertSecondsToTime(total_hours)}</div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Total Active Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;">${this.convertSecondsToTime((total_hours - total_idle_hours))}</div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Total Idle Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;">${this.convertSecondsToTime(total_idle_hours)}</div>
					</div>
				</div>
			</div>
			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Average Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;">${this.convertSecondsToTime(total_hours / total_days)}</div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Average Active Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;">${this.convertSecondsToTime((total_hours - total_idle_hours) / total_days)}</div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Average Idle Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;">${this.convertSecondsToTime(total_idle_hours / total_days)}</div>
					</div>
				</div>
			</div>
			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Meetings<span style="font-size:12px"> (External | Internal)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;"><b>${total_meeting_count}</b><span style="font-size:12px"> Meet - </span>${this.convertSecondsToTime(total_meeting_hours)} | <b>${internal_meeting_count}</b><span style="font-size:12px"> Meet - </span>${this.convertSecondsToTime(internal_meeting_hours)}</div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Time On Calls <span style="font-size:11px">(In Hours)(External)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${this.convertSecondsToTime_(total_incoming_fincall_hours)}</b><span style="font-size:12px"> Inc </span> | <b>${this.convertSecondsToTime_(total_outgoing_fincall_hours)}</b><span style="font-size:12px"> Out </span></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Fincall Log Call Count<span style="font-size:11px">(External)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${total_incoming_fincall_count}</b><span style="font-size:12px"> Inc </span>|<b> ${total_outgoing_fincall_count}</b><span style="font-size:12px"> Out</span> |<b> ${total_missed_fincall_count}</b><span style="font-size:12px"> Miss</span> |<b> ${total_rejected_fincall_count}</b> <span style="font-size:12px"> Rej</span></div>
					</div>
				</div>
			</div>
			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Application Usage Log Count</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;">
							<b>${total_application_usage}</b><span style="font-size:12px"> Applications Used</span>
						</div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Time On Calls <span style="font-size:11px">(In Hours)(Internal)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${this.convertSecondsToTime_(internal_total_incoming_fincall_hours)}</b><span style="font-size:12px"> Inc </span> | <b>${this.convertSecondsToTime_(internal_total_outgoing_fincall_hours)}</b><span style="font-size:12px"> Out </span></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Fincall Log Call Count<span style="font-size:11px">(Internal)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${internal_incoming_fincall_count}</b><span style="font-size:12px"> Inc </span>|<b> ${internal_outgoing_fincall_count}</b><span style="font-size:12px"> Out</span> |<b> ${internal_missed_fincall_count}</b><span style="font-size:12px"> Miss</span> |<b> ${internal_rejected_fincall_count}</b> <span style="font-size:12px"> Rej</span></div>
					</div>
				</div>
			</div>
			<div class="row mt-3">
			<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Domain Usage Count</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;">
							<b>${domain_usage}</b><span style="font-size:12px"> Domains Accessed</span>
						</div>
					</div>
				</div>
			<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Documents Accessed</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${total_unique_doc}</b><span style="font-size:12px"> Documents Created or Modified</span></div>
					</div>
				</div>
			<div class="col-md-4">
					<div class="frappe-card custom-card">
					<h4 class="custom-title" style="font-size: 14px !important; ">Version Log Count</h4>
					<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${total_version_count}</b><span style="font-size:12px"> Interactions</span></div>

					</div>
				</div>
			</div>
			<div class="row mt-3">
			<div class="col-md-6">
			<div class="frappe-card  custom-card">
				<h4 class="custom-title p-3" style="font-size: 14px !important; " align="center">Applications Used</h4>
				<table class="table">
					<thead>
						<tr>
							<th>Application Name</th>
							<th>Duration</th>
						</tr>
					</thead>
					<tbody>`;

			data.apps_data.forEach(app => {
				wholedata += `
					<tr>
						<td width="60%"><b><a href="#" style="text-decoration:none !important;color:#00A6E0 !important;" class="app-link" data-url="${app.application_name}">${app.application_name}</b></td>
						<td style="color:#2D9596" width="40%">${this.convertSecondsToTime(app.total_duration)}</td>
					</tr>`;
			});

			wholedata += `
								</tbody>
							</table>
						</div>
					</div>
					<div class="col-md-6">
			<div class="frappe-card  custom-card">
				<h4 class="custom-title p-3" style="font-size: 14px !important; " align="center">Domains Used</h4>
				<table class="table">
					<thead>
						<tr>
							<th>Domain</th>
							<th>Duration</th>
						</tr>
					</thead>
					<tbody>`;
					data.urls_visited.forEach(app => {
						wholedata += `
							<tr>
								<td style="color:#FF4001" width="60%"><b><a href="#" style="text-decoration:none !important;color:#FF4001 !important;" class="url-link" data-url="${app.domain}">${app.domain}</a></b></td>
								<td style="color:#FF4001" width="40%">${this.convertSecondsToTime(app.total_duration)}</td>
							</tr>`;
					});
					wholedata += `
					</tbody>
				</table>
			</div>
		</div>`;
		container.append(wholedata);
		$(document).ready(function() {
			$(document).on('click', '.url-link', function(e) {
				e.preventDefault();

				// AJAX call to Python function
				frappe.call({
					method: "productivity_next.productivity_next.page.productify_consolidated_tracking.productify_consolidated_tracking.get_url_brief_data",
					args: {
						url_data: $(this).data('url'),
						start_date: start_date_,
                        end_date: end_date_,
					},
					callback: function(r) {
						if (r.message) {
							let data = r.message;
							console.log('Data:', data);
							render_app_brief_data(data);
						} else {
							$('#URLModal').find('.modal-body').html('No data available for this DOMAIN.');
						}
						$('#URLModal').modal('show');  // Show the modal after data is loaded
					}
				});
			});

			function render_app_brief_data(data) {
				console.log('Data received:', data);

				function convertSecondsToTime(seconds) {
					const hours = Math.floor(seconds / 3600);
					const minutes = Math.floor((seconds % 3600) / 60);
					return `<b>${hours}</b><span style="font-size:12px"> hours </span><b>${minutes}</b><span style="font-size:12px"> minutes</span>`;
				}

				// Helper function to fetch full name, returns a promise
				function getEmployeeFullName(employee) {
					return new Promise((resolve, reject) => {
						frappe.call({
							method: "frappe.client.get_value",
							args: {
								doctype: "Employee",
								filters: { "name": employee },
								fieldname: "employee_name"
							},
							callback: function(r) {
								if (r.message) {
									resolve({ employee, fullName: r.message.employee_name });
								} else {
									resolve({ employee, fullName: employee }); // fallback to employee ID if full_name is not found
								}
							}
						});
					});
				}

				// Create an array of promises to fetch full names for all employees
				let fetchPromises = data.url_data.map(app => getEmployeeFullName(app.employee));

				// Wait for all promises to resolve
				Promise.all(fetchPromises).then(results => {
					let displayContent = `
					<div class="row mt-3">
						<div class="col-md-12">
							<div class="frappe-card custom-card">
								<h4 class="custom-title p-3" style="font-size: 14px !important; " align="center">Top 10 Domain's Used</h4>
								<table class="table">
									<thead>
										<tr style="align:center !important;">
											<th>Employee</th>
											<th>Domain Name</th>
											<th>Duration</th>
										</tr>
									</thead>
									<tbody>`;

					data.url_data.forEach((app, index) => {
						let employeeFullName = results.find(result => result.employee === app.employee).fullName;
						displayContent += `
							<tr>
								<td style="color:#00A6E0 !important;"><b>${employeeFullName}</b></td>
								<td style="color:#62BA46"><b>${app.domain}</b></td>
								<td style="color:#FF4001">${convertSecondsToTime(app.total_duration)}</td>
							</tr>`;
					});

					displayContent += `
									</tbody>
								</table>
							</div>
						</div>
					</div>`;

					$('#URLModal').find('.modal-body').html(displayContent);
				});
			}
		});

		$(document).ready(function() {
			$(document).on('click', '.app-link', function(e) {
				e.preventDefault();
				
				// AJAX call to Python function
				frappe.call({
					method: "productivity_next.productivity_next.page.productify_consolidated_tracking.productify_consolidated_tracking.get_app_brief_data",
					args: {
						app_data: $(this).data('url'),
						start_date: start_date_,
                        end_date: end_date_,
					},
					callback: function(r) {
						if (r.message) {
							let data = r.message;
							console.log('Data:', data);
							render_url_brief_data(data);
						} else {
							$('#appModal').find('.modal-body').html('No data available for this APP.');
						}
						$('#appModal').modal('show');  // Show the modal after data is loaded
					}
				});
			});

			function render_url_brief_data(data) {
				console.log('Data received:', data);

				function convertSecondsToTime(seconds) {
					const hours = Math.floor(seconds / 3600);
					const minutes = Math.floor((seconds % 3600) / 60);
					return `<b>${hours}</b><span style="font-size:12px"> hours </span><b>${minutes}</b><span style="font-size:12px"> minutes</span>`;
				}

				// Helper function to fetch full name, returns a promise
				function getEmployeeFullName(employee) {
					return new Promise((resolve, reject) => {
						frappe.call({
							method: "frappe.client.get_value",
							args: {
								doctype: "Employee",
								filters: { "name": employee },
								fieldname: "employee_name"
							},
							callback: function(r) {
								if (r.message) {
									resolve({ employee, fullName: r.message.employee_name });
								} else {
									resolve({ employee, fullName: employee }); // fallback to employee ID if full_name is not found
								}
							}
						});
					});
				}

				// Create an array of promises to fetch full names for all employees
				let fetchPromises = data.app_data.map(app => getEmployeeFullName(app.employee));

				// Wait for all promises to resolve
				Promise.all(fetchPromises).then(results => {
					let displayContent = `
					<div class="row mt-3">
						<div class="col-md-12">
							<div class="frappe-card custom-card">
								<h4 class="custom-title p-3" style="font-size: 14px !important; " align="center">Top 10 Application's Used</h4>
								<table class="table">
									<thead>
										<tr style="align:center !important;">
											<th>Employee</th>
											<th>Application Name</th>
											<th>Duration</th>
										</tr>
									</thead>
									<tbody>`;

					data.app_data.forEach((app, index) => {
						let employeeFullName = results.find(result => result.employee === app.employee).fullName;
						displayContent += `
							<tr>
								<td style="color:#00A6E0 !important;"><b>${employeeFullName}</b></td>
								<td style="color:#62BA46"><b>${app.application_name}</b></td>
								<td style="color:#FF4001">${convertSecondsToTime(app.total_duration)}</td>
							</tr>`;
					});

					displayContent += `
									</tbody>
								</table>
							</div>
						</div>
					</div>`;

					$('#appModal').find('.modal-body').html(displayContent);
				});
			}
		});

	}
	convertSecondsToTime(seconds) {
		const hours = Math.floor(seconds / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
	
		return `<b>${hours}</b><span style="font-size:12px"> hours </span><b>${minutes}</b><span style="font-size:12px"> minutes</span>`;
	}
	convertSecondsToTime_(seconds) {
		const hours = Math.floor(seconds / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		const formattedMinutes = minutes < 10 ? `0${minutes}` : minutes;
		const formattedHours = hours < 10 ? `0${hours}` : hours;
	
		return `${formattedHours}:${formattedMinutes}`;
	}
	
	render_line_chart() {
		this.update_line_chart_data();
	}

	update_client_calls_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.productify_consolidated_tracking.productify_consolidated_tracking.get_client_calls_chart_data", {
				user: "Administrator",
				start_date: this.selected_start_date,
				end_date: this.selected_end_date
			})
			.then((r) => {
				console.log('Client calls chart data:', r);
				if (r.labels.length === 0) {
				} else {
					const getCurrentThemeLabelColor = () => {
						return {
							labelColor: '#FFFFFF',
							backgroundColor: 'rgba(0,0,0,0)'
						};
					};
					const themeColors = getCurrentThemeLabelColor();
					
					const plotData = [{
						values: r.datasets,
						labels: r.labels,
						type: 'pie',
						marker: {
							colors: [
								'#FF6384',
								'#36A2EB',
								'#FFCE56',
								'#4BC0C0',
								'#9966FF',
								'#FF9966',
								'#66CCCC',
								'#6699FF',
								'#FF6666',
								'#FFCC66'
							]
						},
						hoverinfo: 'label+percent',
						hovertemplate: '%{label}: %{value} Minutes<extra></extra>',
						textposition: 'inside',
						textfont: {
							color: themeColors.labelColor,
							outline: 'black' // Adds outline to the text
						},
						textinfo: 'label+percent',
						insidetextorientation: 'horizontal' // Ensures horizontal text for better readability
					}];
					const plotLayout = {
						height: '50%',
						margin: {
							"t": 0,
							"b": 0,
							"l": 0,
							"r": 0
						},	
						plot_bgcolor: themeColors.backgroundColor,
						paper_bgcolor: themeColors.backgroundColor
					};
					Plotly.newPlot('clients-call-chart', plotData, plotLayout, {
						displayModeBar: false,
					responsive: false,
					scrollZoom: false,

					});
					let container = document.getElementById('clients-call-chart');
					setTimeout(() => {
						Plotly.newPlot(container, plotData, plotLayout, {
							displayModeBar: false
						});
						window.addEventListener('resize', function () {
							Plotly.Plots.resize(container);
						});
					}, 0);
					
				}
			});
	}
	
	update_line_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.productify_consolidated_tracking.productify_consolidated_tracking.get_linechart_data", {
				user: "Administrator",
				start_date: this.selected_start_date,
				end_date: this.selected_end_date
			})
			.then((r) => {
				const getCurrentThemeLabelColor = () => {
					return {
						labelColor: '#FFFFFF',
						backgroundColor: 'rgba(0,0,0,0)'  // Transparent background
					};
				};
				const themeColors = getCurrentThemeLabelColor();
				if (r.labels.length === 0) {
					console.log("No data to show");
				} else {
					console.log("Chart Data:", r);
	
					const colors = [
						'#FF6384', // color for 'Incoming'
						'#36A2EB', // color for 'Outgoing'
						'#FFCE56', // color for 'Missed'
						'#4BC0C0'  // color for 'Rejected'
					];
	
					const traces = r.datasets.map((dataset, index) => ({
						x: r.labels,
						y: dataset.counts,
						name: dataset.name,
						type: 'bar',
						marker: {
							color: colors[index]  // Assigning specific colors to each dataset
						},
						text: dataset.durations.map(duration => `Duration: ${duration} mins`),
						hoverinfo: 'x+y+text',
						textposition: 'auto',
						textfont: {
							color: themeColors.labelColor
						}
					}));
	
					const layout = {
						barmode: 'stack',
						xaxis: { 
							title: 'Employees',
							fixedrange: true  // Fixing the x-axis range
						},
						yaxis: { 
							title: 'Number of Calls',
							fixedrange: true  // Fixing the y-axis range
						},
						plot_bgcolor: themeColors.backgroundColor,
						paper_bgcolor: themeColors.backgroundColor
					};
	
					Plotly.newPlot('performance-line-chart', traces, layout, {
						displayModeBar: false,
						responsive: true,
						scrollZoom: false,
					});
				}
			})
			.catch((error) => {
				console.error("Error fetching chart data:", error);
			});
	}
	
	
	
	
	
	
	
	fetch_and_render_admin_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		
		frappe.call({
			method: "productivity_next.productivity_next.page.productify_consolidated_tracking.productify_consolidated_tracking.get_admin_data",
			args: {
				user: "Administrator",
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			},
			callback: (r) => {
				if (r.message) {
					this.render_admin_data(r.message);
				}
			}
		});
	};
	async render_admin_data(data) {
		console.log('Data received:', data);
        function calculateEffectiveHours(totalHours, totalIdleTime, totalDays) {
            return (((totalHours / 60 / 60) / totalDays) - ((totalIdleTime / 60 / 60) / totalDays)).toFixed(2);
        }
        // Function to convert seconds to time format (hh:mm:ss)
        function convertSecondsToTime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const remainingSeconds = seconds % 60;
            return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(remainingSeconds).padStart(2, '0')}`;
        }
		function getBaseURL() {
			return window.location.origin + '/app/';
		}
	
		let employee_data;
		if (this.selected_employee != null) {
			employee_data = this.selected_employee;
		} else {
			employee_data = this.user_id;
		}
	
		const container = this.main_section.find("#user-activity-data");
		container.empty();
		let wholedata = ``;
		const baseUrl = getBaseURL();
        const fetchPromises = Object.keys(data.total_hours_per_employee).map(async employee => {
            // Fetch employee full name asynchronously
            console.log('employee:', employee); 
            const response = await frappe.db.get_value("Employee", employee, "employee_name");
            const employee_name = response.message.employee_name;
	
            // Check if internal_employee_fincall_data exists before accessing properties
            const internalEmployeeFincallData = data.internal_employee_fincall_data?.[employee] || {};
            const meetingEmployeeData = data.meeting_employee_data?.[employee] || {};
			const issueData = data.issue_data?.[employee] || {};
        
            // Return the employee data along with the fetched employee name
            return {
                employee,
                employeeName: employee_name,
                totalHours: data.total_hours_per_employee[employee] || 0,
                totalIdleTime: data.total_idle_time[employee] || 0,
                incomingFincallCount: data.employee_fincall_data[employee]?.incoming_fincall_count || 0,
                outgoingFincallCount: data.employee_fincall_data[employee]?.outgoing_fincall_count || 0,
                missedFincallCount: data.employee_fincall_data[employee]?.missed_fincall_count || 0,
                rejectedFincallCount: data.employee_fincall_data[employee]?.rejected_fincall_count || 0,
                totalIncomingDuration: data.employee_fincall_data[employee]?.total_incoming_duration || 0,
                totalOutgoingDuration: data.employee_fincall_data[employee]?.total_outgoing_duration || 0,
                totalDays: data.total_days[employee] || 1,
                meetingCount: meetingEmployeeData.count || 0,
                meetingDuration : meetingEmployeeData.duration || 0,
				issueCount: issueData.no_of_issues || 0,
				issueTime: issueData.time_in_issues || 0
            };
        });
        
        const employeeDataArray = await Promise.all(fetchPromises);
        
        employeeDataArray.sort((a, b) => calculateEffectiveHours(a.totalHours, a.totalIdleTime, a.totalDays) - calculateEffectiveHours(b.totalHours, b.totalIdleTime, b.totalDays));
        
        let count = 1;
        console.log('employeeDataArray:', employeeDataArray);
        employeeDataArray.forEach(app => {
                const employeeUrl = `${baseUrl}Productify Employee Tracking?start_date=${encodeURIComponent(this.selected_start_date)}&end_date=${encodeURIComponent(this.selected_end_date)}&employee=${encodeURIComponent(app.employee)}`;
				wholedata += `
					<tr>
						<td align="left">
							<a href="${employeeUrl}" target="_blank">${count}. ${app.employeeName}</a>
						</td>
						<td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_(app.totalHours)}</td>
                        <td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_((app.totalHours) - (app.totalIdleTime))}</td>
                        <td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_(app.totalIdleTime)}</td>
                        <td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_(((app.totalHours) / app.totalDays) - ((app.totalIdleTime) / app.totalDays))}</td>
                        <td align="center" style="color:#62BA46;">${app.incomingFincallCount}</td>
                        <td align="center" style="color:#62BA46;">${app.outgoingFincallCount}</td>
                        <td align="center" style="color:#62BA46;">${app.missedFincallCount}</td>
                        <td align="center" style="color:#62BA46;">${app.rejectedFincallCount}</td>
                        <td align="center" style="color:#FF4001;">${this.convertSecondsToTime_(app.totalIncomingDuration)}</td>
                        <td align="center" style="color:#FF4001;">${this.convertSecondsToTime_(app.totalOutgoingDuration)}</td>
                        <td align="center" style="color:#6420AA;">${app.meetingCount}</td>
                        <td align="center" style="color:#6420AA;">${this.convertSecondsToTime_(app.meetingDuration)}</td>
					</tr>`;
				count++;
		});
		container.append(wholedata);
	};

	render_client_time_chart() {
		this.clienttimechart = new frappe.Chart(".performance-time-client-chart", {
			type: "line",
			height: 250,
			width: 400,
			colors: ["#FF4001"],
			tooltipOptions: {
				formatTooltipX: d => (d + '').toUpperCase(),
				formatTooltipY: d => d + ' Hours',
			},
			data: {labels: [],
            datasets: [
                {
                    values: [] 
                }
            ]},
			isNavigable: true,
		});
		this.update_client_time_chart_data();
		
	}

	update_client_time_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		}
		else{
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.productify_consolidated_tracking.productify_consolidated_tracking.client_time_data", {
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {	
				} else {
					this.clienttimechart.update(r);
				}
			});
	};
}

function create_chart() {
		// Generate time intervals for every 5 minutes within each hour from 7 AM to 6 PM
		var timeLabels = [];
		var hours = [
	'1:00 AM', '2:00 AM', '3:00 AM', '4:00 AM', '5:00 AM', '6:00 AM', '7:00 AM', '8:00 AM', '9:00 AM', '10:00 AM', '11:00 AM', '12:00 PM',
	'1:00 PM', '2:00 PM', '3:00 PM', '4:00 PM', '5:00 PM', '6:00 PM', '7:00 PM', '8:00 PM', '9:00 PM', '10:00 PM', '11:00 PM', '12:00 AM'
	];
		var minuteIntervals = ['00', '05', '10', '15', '20', '25', '30', '35', '40', '45', '50', '55'];
		generateTimes();
		function generateTimes() {
			const times = [];
			const periods = ['AM', 'PM'];
			
			for (let periodIndex = 0; periodIndex < 2; periodIndex++) {
				const period = periods[periodIndex];
				for (let hour = 0; hour < 12; hour++) {
					for (let minute = 0; minute < 60; minute += 5) {
						const formattedHour = hour === 0 ? 12 : hour;
						const formattedMinute = minute < 10 ? '0' + minute : minute;
						timeLabels.push(`${formattedHour}:${formattedMinute} ${period}`);
					}
				}
			}
			
				// return times;
			}
	
		// Generate random productivity data for demonstration
		var productiveValues = [];
		var idleValues = [];
		var meetingValues = [];
		var callValues = [];
		var hoverText = [];
		for (var i = 0; i < timeLabels.length; i++) {
			var productive = Math.floor(Math.random() * 50 + 50); // random value between 50 and 100
			var idle = Math.floor(Math.random() * 30); // random value between 0 and 30
			var meeting = Math.floor(Math.random() * 20); // random value between 0 and 20
			var call = 100 - productive - idle - meeting; // the rest to make total 100
			
			productiveValues.push(productive);
			idleValues.push(idle);
			meetingValues.push(meeting);
			callValues.push(call);
	
			// Create the hover text for each time interval
			hoverText.push(
				`${timeLabels[i]}<br>` +
				`Active Hours: ${(productive + idle + meeting).toFixed(2)} Min<br>` +
				`Productive: ${productive.toFixed(2)} Min<br>` +
				`Meeting: ${meeting.toFixed(2)} Min<br>` +
				`Call: ${call.toFixed(2)} Min <br>` + 
				`Idle: ${idle.toFixed(2)} Min<br>` 
			
			);
		}
	
		var trace1 = {
			x: timeLabels,
			y: productiveValues,
			type: 'bar',
			name: 'Productive',
			marker: {
				color: 'green'
			},
			hoverinfo: 'skip'  // Prevent default hover info
		};
	
		var trace2 = {
			x: timeLabels,
			y: idleValues,
			type: 'bar',
			name: 'Idle',
			marker: {
				color: 'gray'
			},
			hoverinfo: 'skip'  // Prevent default hover info
		};
	
		var trace3 = {
			x: timeLabels,
			y: meetingValues,
			type: 'bar',
			name: 'Meeting',
			marker: {
				color: 'orange'
			},
			hoverinfo: 'skip'  // Prevent default hover info
		};
	
		var trace4 = {
			x: timeLabels,
			y: callValues,
			type: 'bar',
			name: 'Call',
			marker: {
				color: 'blue'
			},
			hoverinfo: 'skip'  // Prevent default hover info
		};
	
		// A dummy trace to handle hover text
		var hoverTrace = {
			x: timeLabels,
			y: new Array(timeLabels.length).fill(0),  // Use a zero height trace
			mode: 'markers',
			marker: {
				opacity: 0
			},
			hoverinfo: 'text',
			hovertext: hoverText,
			showlegend: false
		};
	
		var data = [trace1, trace2, trace3, trace4, hoverTrace];
	
		var layout = {
			barmode: 'stack',
			title: 'Detailed Productivity Bar',
			showlegend: false,
			xaxis: {
				title: 'Time of Day',
				tickmode: 'array',
				tickvals: hours.map((hour, i) => i * minuteIntervals.length),
				ticktext: hours
			},
			yaxis: {
				title: 'Values',
				range: [0, 100]
			},
			hoverlabel: {
				bgcolor: '#000000', // Set the background color of the hover text box with transparency
				bordercolor: 'white',
				font: {
					family: 'Open Sans, sans-serif', // Preferred font
					size: 14, // Larger font size
					color: '#white' // light text color
				},
				align: 'center', // Center text horizontally
				// valign: 'middle', // Center text vertically
				opacity: 0.1 // Slightly transparent label
			}
		};
	
		Plotly.newPlot('productivityBar', data, layout, {displayModeBar: false});
		// document.getElementById("myData").innerHTML = trace1['y'];
		console.log(data)
	}	

frappe.provide("frappe.ui");
frappe.ui.UserProfile = UserProfile;
frappe.pages['admin-productify'].on_page_load = function(wrapper) {
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
        if (urlParams.get('employee') != null && urlParams.get('employee') != 'undefined'){
        this.selected_employee = urlParams.get('employee');
        }
        else{
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
		this.main_section.empty().append(frappe.render_template("admin_productify"));
		this.fetch_and_render_admin_data();	
		this.render_bar_chart();
		// this.fetch_and_render_user_data();
		this.render_line_chart();	
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
			this.page.set_title(this.user.fullname + " ( FROM " + this.selected_start_date + " TO " + this.selected_end_date + " )");
		} else {
			frappe.db.get_doc("Employee", this.selected_employee)
				.then(employee => {
					this.page.set_title(employee.employee_name + " ( FROM " + this.selected_start_date + " TO " + this.selected_end_date + " )"); 
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
			.xcall("productivity_next.productivity_next.page.admin_productify.admin_productify.get_barchart_data", {
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
	// 	frappe.call({
	// 		method: "productivity_next.productivity_next.page.admin_productify.admin_productify.get_admin_data",
	// 		args: {
	// 			user: "Administrator",
	// 			start_date: this.selected_start_date,
	// 			end_date: this.selected_end_date,
	// 		},
	// 		callback: (r) => {
	// 			if (r.message) {
	// 				this.render_user_data(r.message);
	// 				$(document).ready(function() {
	// 					$('#logCountModalTrigger').click(function() {
	// 						$('#logCountModal').modal('show');
	// 					});
	// 				});					
	// 			}
	// 		}
	// 	});
	// };

   
	render_user_data(data) {
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
		let total_days = 0;
	
		for (let i in data.combined_employee_data) {
			const employee = data.combined_employee_data[i];
			total_hours += employee.total_hours/3600 || 0;
			total_idle_hours += employee.total_idle_time/3600 || 0;
			total_meeting_hours += employee.total_meeting_duration || 0;
			total_meeting_count += employee.total_meeting_count || 0;
			total_incoming_fincall_hours += employee.total_incoming_fincall_count || 0;
			total_outgoing_fincall_hours += employee.total_outgoing_fincall_count || 0;
			total_unique_doc += employee.total_unique_doc || 0;
			total_application_usage += employee.application_usage || 0;
			total_version_count += employee.version_count || 0;
			total_incoming_fincall_count += employee.incoming_fincall_count || 0;
			total_outgoing_fincall_count += employee.outgoing_fincall_count || 0;
			total_missed_fincall_count += employee.missed_fincall_count || 0;
			total_rejected_fincall_count += employee.rejected_fincall_count || 0;
			total_days += employee.total_days || 0;
		}
	
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
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Total Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;"><b>${parseFloat(total_hours).toFixed(2)}</b><span style="font-size:12px"> Working Hours</span></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Total Active Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${parseFloat(total_hours - total_idle_hours).toFixed(2)}</b><span style="font-size:12px"> Active Hours</span></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Total Idle Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${parseFloat(total_idle_hours).toFixed(2)}</b><span style="font-size:12px"> Idle Hours</span></div>
					</div>
				</div>
			</div>
			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;"><b>${parseFloat(total_hours / total_days).toFixed(2)}</b><span style="font-size:12px"> Working Hours Per Day</span></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Active Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${parseFloat((total_hours - total_idle_hours) / total_days).toFixed(2)}</b><span style="font-size:12px"> Active Hours Per Day</span></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Idle Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${parseFloat(total_idle_hours / total_days).toFixed(2)}</b><span style="font-size:12px"> Idle Hours Per Day</span></div>
					</div>
				</div>
			</div>
			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Meetings</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;"><b>${total_meeting_count}</b><span style="font-size:12px"> Meetings For </span><b> ${parseFloat(total_meeting_hours / 3600).toFixed(2)}</b><span style="font-size:12px"> Hours</span></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Time On Calls <span style="font-size:11px">(In Hours)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${parseFloat(total_incoming_fincall_hours / 3600).toFixed(2)}</b><span style="font-size:12px"> Incoming </span> |<b> ${parseFloat(total_outgoing_fincall_hours / 3600).toFixed(2)}</b> <span style="font-size:12px"> Outgoing </span></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Documents Accessed</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${total_unique_doc}</b><span style="font-size:12px"> Documents Created or Modified</span></div>
					</div>
				</div>
			</div>
			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Application Usage Log Count</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;">
							<b>${total_application_usage}</b><span style="font-size:12px"> Applications Used</span>
						</div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Fincall Log Call Count</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${total_incoming_fincall_count}</b><span style="font-size:12px"> Incoming </span>|<b> ${total_outgoing_fincall_count}</b><span style="font-size:12px"> Outgoing</span> |<b> ${total_missed_fincall_count}</b><span style="font-size:12px"> Missed</span> |<b> ${total_rejected_fincall_count}</b> <span style="font-size:12px">Rejected</span></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Version Log Count</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${total_version_count}</b><span style="font-size:12px"> Interactions</span></div>
					</div>
				</div>
			</div>`;
		container.append(wholedata);
	}
	
	render_line_chart() {
		this.linechart = new frappe.Chart(".performance-line-chart", {
			type: "line",
			height: 250,
			width: 400,
			colors: ["#62BA46"],
			tooltipOptions: {
				formatTooltipX: d => (d + '').toUpperCase(),
				formatTooltipY: d => d + ' Minutes',
			},
			data: {labels: [],
            datasets: [
                {
                    values: [] 
                }
            ]},
		});
		this.update_line_chart_data();
		
	}

	update_line_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		}
		else{
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.admin_productify.admin_productify.get_linechart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {	
				} else {
					this.linechart.update(r);
				}
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
			method: "productivity_next.productivity_next.page.admin_productify.admin_productify.get_admin_data",
			args: {
				user: "",
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			},
			callback: (r) => {
				if (r.message) {
					this.render_admin_data(r.message);
					this.render_user_data(r.message);
					$(document).ready(function() {
						$('#logCountModalTrigger').click(function() {
							$('#logCountModal').modal('show');
						});
					});					
				}
			}
		});
	};
	async render_admin_data(data) {
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
	
		// Prepare to fetch all employee names asynchronously
		const fetchPromises = data.combined_employee_data.map(app => 
			frappe.db.get_value("Employee", app.employee, "employee_name")
				.then(response => ({
					...app,
					employeeName: response.message.employee_name
				}))
		);
	
		// Await all the promises to get the results
		const results = await Promise.all(fetchPromises);
		results.sort((a, b) => {
			const aEffectiveHours = (a.total_hours/3600) - (a.total_idle_time/3600);
			const bEffectiveHours = (b.total_hours/3600) - (b.total_idle_time/3600);
			return aEffectiveHours - bEffectiveHours;
		});
		// Build the HTML with the results
		let count = 1;  // Initialize a counter variable
		let inactive_count = 1;
		results.forEach(app => {
			if(app.total_hours > 0){
				const employeeUrl = `${baseUrl}employee-productivity-dashboard?start_date=${encodeURIComponent(this.selected_start_date)}&end_date=${encodeURIComponent(this.selected_end_date)}&employee=${encodeURIComponent(app.employee)}`;
				// console.log(app);
				wholedata += `
					<tr>
						<td align="left">
							<a href="${employeeUrl}" target="_blank" style="color:#6420AA;">${count}. ${app.employeeName}</a>
						</td>
						<td align="center" style="color:#00A6E0;">${parseFloat(app.total_hours/3600).toFixed(2)}</td>
						<td align="center" style="color:#00A6E0;">${parseFloat((app.total_hours/3600)-(app.total_idle_time/3600)).toFixed(2)}</td>
						<td align="center" style="color:#00A6E0;">${parseFloat(app.total_idle_time/3600).toFixed(2)}</td>
						<td align="center" style="color:#00A6E0;">${parseFloat(((app.total_hours /60 /60)/app.total_days)-((app.total_idle_time /60 /60)/app.total_days)).toFixed(2)}</td>
						<td align="center" style="color:#62BA46;">${app.incoming_fincall_count}</td>
						<td align="center" style="color:#62BA46;">${app.outgoing_fincall_count}</td>
						<td align="center" style="color:#62BA46;">${app.missed_fincall_count}</td>
						<td align="center" style="color:#62BA46;">${app.rejected_fincall_count}</td>
						<td align="center" style="color:#FF4001;">${parseFloat(app.total_incoming_fincall_count/3600).toFixed(2)}</td>
						<td align="center" style="color:#FF4001;">${parseFloat(app.total_outgoing_fincall_count/3600).toFixed(2)}</td>
						<td align="center" style="color:#6420AA;">${app.total_meeting_count}</td>
						<td align="center" style="color:#6420AA;">${parseFloat(app.total_meeting_duration/3600).toFixed(2)}</td>
					</tr>`;
				count++;
			}
		});
		wholedata += `<tr><td colspan="12"><strong>Inactive Users</strong></td></tr>`;
		results.forEach(app => {
			if(app.total_hours <= 0){
				const employeeUrl = `${baseUrl}employee-productivity-dashboard?start_date=${encodeURIComponent(this.selected_start_date)}&end_date=${encodeURIComponent(this.selected_end_date)}&employee=${encodeURIComponent(app.employee)}`;
				// console.log(app);
				wholedata += `
					<tr>
						<td align="left">
							<a href="${employeeUrl}" target="_blank" style="color:#6420AA;">${inactive_count}. ${app.employeeName}</a>
						</td>
						<td align="center" style="color:#00A6E0;">${parseFloat(app.total_hours/3600).toFixed(2)}</td>
						<td align="center" style="color:#00A6E0;">${parseFloat((app.total_hours/3600)-(app.total_idle_time/3600)).toFixed(2)}</td>
						<td align="center" style="color:#00A6E0;">${parseFloat(app.total_idle_time/3600).toFixed(2)}</td>
						<td align="center" style="color:#00A6E0;">${parseFloat(((app.total_hours /60 /60)/app.total_days)-((app.total_idle_time /60 /60)/app.total_days)).toFixed(2)}</td>
						<td align="center" style="color:#62BA46;">${app.incoming_fincall_count}</td>
						<td align="center" style="color:#62BA46;">${app.outgoing_fincall_count}</td>
						<td align="center" style="color:#62BA46;">${app.missed_fincall_count}</td>
						<td align="center" style="color:#62BA46;">${app.rejected_fincall_count}</td>
						<td align="center" style="color:#FF4001;">${parseFloat(app.total_incoming_fincall_count/3600).toFixed(2)}</td>
						<td align="center" style="color:#FF4001;">${parseFloat(app.total_outgoing_fincall_count/3600).toFixed(2)}</td>
						<td align="center" style="color:#6420AA;">${app.total_meeting_count}</td>
						<td align="center" style="color:#6420AA;">${parseFloat(app.total_meeting_duration/3600).toFixed(2)}</td>
					</tr>`;
				inactive_count++;
			}
		});
		container.append(wholedata);
	};
}
frappe.provide("frappe.ui");
frappe.ui.UserProfile = UserProfile;
frappe.pages['Productify Employee Tracking'].on_page_load = function (wrapper) {
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
			var endDate = new Date();
			var startDate = new Date();
			startDate.setDate(startDate.getDate() - 7); // Set the start date to one week back

			var endDay = endDate.getDate().toString().padStart(2, '0');
			var endMonth = (endDate.getMonth() + 1).toString().padStart(2, '0');
			var endYear = endDate.getFullYear();
			this.selected_end_date = endYear + '-' + endMonth + '-' + endDay;

			var startDay = startDate.getDate().toString().padStart(2, '0');
			var startMonth = (startDate.getMonth() + 1).toString().padStart(2, '0');
			var startYear = startDate.getFullYear();
			this.selected_start_date = startYear + '-' + startMonth + '-' + startDay;
		} else {
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
		this.main_section.empty().append(frappe.render_template("productify_employee_tracking"));
		this.render_heatmap();
		this.fetch_and_render_user_data();
		this.render_activity_chart();
		// this.render_pie_chart();
		this.render_line_chart();
		this.render_bar_chart();
		this.render_images();
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
				console.log(frappe.db.get_value("Employee", { user_id: this.user_id }, "name"))
			},
		});
		dialog.show();
	}
	make_user_profile() {
		this.user = frappe.user_info(this.user_id);
		if (!this.selected_employee) {
			frappe.msgprint(__("Select Employee to view the data"));
		}
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

			// Set up the 'Change Employee' button
			this.$user_search_button = this.page.set_secondary_action(
				__("Change Employee"),
				() => this.show_user_search_dialog(),
				{ icon: "change", size: "sm" }
			);

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
	render_heatmap() {
		this.heatmap = new frappe.Chart(".performance-heatmap", {
			type: "heatmap",
			countLabel: "Productify Count",
			data: {},
			discreteDomains: 1,
			radius: 3,
			height: 150,
		});
		this.update_heatmap_data();
	}

	update_heatmap_data(date_from) {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		}
		else {
			data = this.user_id;
		}

		frappe.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_heatmap_data", {
			user: data,
			date: date_from || frappe.datetime.year_start(),
		})
			.then((r) => {
				this.heatmap.update({ dataPoints: r });
			});
	}

	fetch_and_render_user_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}

		frappe.call({
			method: "productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_user_data",
			args: {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			},
			callback: (r) => {
				if (r.message) {
					this.render_user_data(r.message);
					$(document).ready(function () {
						$('#logCountModalTrigger').click(function () {
							$('#logCountModal').modal('show');
						});
					});
				}
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

		return `<b>${hours}.${minutes}</b>`;
	}
	render_user_data(data) {
		function getBaseURL() {
			return window.location.origin + '/app/';
		}

		let employee_data;
		let start_date_ = this.selected_start_date;
		let end_date_ = this.selected_end_date;

		if (this.selected_employee != null) {
			employee_data = this.selected_employee;
		} else {
			employee_data = this.user_id;
		}

		const baseUrl = getBaseURL();
		const container = this.main_section.find("#user-data-cards");
		container.empty();

		const employeeMeetingUrl = `${baseUrl}meeting?employee=${encodeURIComponent(employee_data)}&meeting_from=${encodeURIComponent(`["Between",["${start_date_}","${end_date_}"]]`)}&docstatus=1`;
		const employeeFincallUrl = `${baseUrl}employee-fincall?employee=${encodeURIComponent(employee_data)}&date=${encodeURIComponent(`["Between",["${start_date_}","${end_date_}"]]`)}&link_to=${encodeURIComponent(`["!=","Company"]`)}`;
		const employeeFincallInternalUrl = `${baseUrl}employee-fincall?employee=${encodeURIComponent(employee_data)}&date=${encodeURIComponent(`["Between",["${start_date_}","${end_date_}"]]`)}&link_to=${encodeURIComponent(`["=","Company"]`)}`;
		let wholedata = `
			<div class="title-area ">
				<h4 class="card-title">Productify Data</h4>
			</div>
			
			<div class="row mt-3">
				<div class="col-md-4">
					
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Total Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;">${this.convertSecondsToTime(data.total_hours)}</div>
					</div>
				</div>
				<div class="col-md-4">
				
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Total Active Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;">${this.convertSecondsToTime((data.total_hours) - (data.total_idle_time))}</div>
					</div>
				</div>
				<div class="col-md-4">
				
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Total Idle Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;">${this.convertSecondsToTime(data.total_idle_time)}</div>
					</div>
				</div>
			</div>

			<div class="row mt-3">
				<div class="col-md-4">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;">${this.convertSecondsToTime((data.total_hours) / (data.total_days) || 1)}</div>
					</div>
				</div>
				<div class="col-md-4">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Active Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;">${this.convertSecondsToTime(((data.total_hours) / (data.total_days) || 1) - ((data.total_idle_time) / (data.total_days) || 1))}</div>
					</div>
				</div>
				<div class="col-md-4">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Idle Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;">${this.convertSecondsToTime((data.total_idle_time) / (data.total_days) || 1)}</b></div>
					</div>
				</div>
			</div>

			<div class="row mt-3">
				<div class="col-md-4">
					
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Meetings<span style="font-size:12px"> (External | Internal)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;"><a href="${employeeMeetingUrl}" target="_blank" style="color:#00A6E0;"><b>${data.total_meeting_count_external}</b><span style="font-size:12px">  Meet - </span>${this.convertSecondsToTime(data.total_meeting_duration_external)}| <b>${data.total_meeting_count_internal}</b><span style="font-size:12px"> Meet - </span>${this.convertSecondsToTime(data.total_meeting_duration_internal)}</a></div>
					</div>
				</div>
				<div class="col-md-4">
					
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Time On Calls <span style="font-size:11px">(In Hours)</span><span style="font-size:12px"> (External)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;">${this.convertSecondsToTime_(data.total_incoming_duration)}<span style="font-size:12px"> Inc </span> | ${this.convertSecondsToTime_(data.total_outgoing_duration)}<span style="font-size:12px"> Out </span></div>
					</div>
				</div>
				<div class="col-md-4">
					
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Fincall Log Call Count<span style="font-size:12px"> (External)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><a href="${employeeFincallUrl}" target="_blank" style="color:#FF4001;"><b>${data.incoming_fincall_count}</b><span style="font-size:12px"> Inc </span>|<b> ${data.outgoing_fincall_count}</b><span style="font-size:12px"> Out</span> |<b> ${data.missed_fincall_count}</b><span style="font-size:12px"> Miss</span> |<b> ${data.rejected_fincall_count}</b> <span style="font-size:12px">Rej</span></a></div>
					</div>
				</div>
			</div>

			<div class="row mt-3">
				<div class="col-md-4">
					
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Application Usage Log Count</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;">
							<b>${data.application_usage}</b><span style="font-size:12px">  Applications Used</span>
						</div>
					</div>
				</div>
				<div class="col-md-4">
					
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Time On Calls <span style="font-size:11px">(In Hours)</span><span style="font-size:12px"> (Internal)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;">${this.convertSecondsToTime_(data.internal_total_incoming_duration)}<span style="font-size:12px"> Inc </span> | ${this.convertSecondsToTime_(data.internal_total_outgoing_duration)}<span style="font-size:12px"> Out </span></div>
					</div>
				</div>
				<div class="col-md-4">
					
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Fincall Log Call Count<span style="font-size:12px"> (Internal)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><a href="${employeeFincallInternalUrl}" target="_blank" style="color:#FF4001;"><b>${data.internal_incoming_fincall_count}</b><span style="font-size:12px"> Inc </span>|<b> ${data.internal_outgoing_fincall_count}</b><span style="font-size:12px"> Out</span> |<b> ${data.internal_missed_fincall_count}</b><span style="font-size:12px"> Miss</span> |<b> ${data.internal_rejected_fincall_count}</b> <span style="font-size:12px">Rej</span></a></div>
					</div>
				</div>
			</div>

			<div class="row mt-3">
				<div class="col-md-4">
					
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Domain Usage Count</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;">
							<b>${data.domain_used || 0}</b><span style="font-size:12px">  Applications Used</span>
						</div>
					</div>
				</div>
				<div class="col-md-4">
					
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Documents Accessed</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${data.total_unique_doc}</b><span style="font-size:12px">  Documents Created or Modified</span></div>
					</div>
				</div>
				<div class="col-md-4">
					
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Version Log Count</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${data.version_count}</b><span style="font-size:12px">  Interactions</span></div>
					</div>
				</div>
			</div>
			<div class="row mt-3">
				<div class="col-md-4">
					
						<h4 class="custom-title p-3" style="font-size: 14px !important; color: #333333;" align="center">Top 10 Applications Used</h4>
						<table class="table">
							<thead>
								<tr>
									<th>Application Name</th>
									<th>Duration</th>
								</tr>
							</thead>
							<tbody>`;

		data.application_name.forEach(app => {
			wholedata += `
				<tr>
					<td style="color:#00A6E0" width="60%"><b>${app.application_name}</b></td>
					<td style="color:#2D9596" width="40%">${this.convertSecondsToTime(app.total_duration)}</td>
				</tr>`;
		});

		wholedata += `
							</tbody>
						</table>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card  custom-card">
						<h4 class="custom-title p-3" style="font-size: 14px !important; color: #333333;" align="center">Top 10 Calls</h4>
						<table class="table">
							<thead>
								<tr>
									<th>Caller Name</th>
									<th>Calls</th>
									<th>Duration</th>
								</tr>
							</thead>
							<tbody>`;

		data.caller_name.forEach(app => {
			wholedata += `
				<tr>
					<td style="color:#62BA46"><b>${app.identifier}</b></td>
					<td style="color:#03B404">${app.call_count}</td>
					<td style="color:#00DF37">${parseFloat(app.total_duration / 60).toFixed(2)} Min</td>
				</tr>`;
		});

		wholedata += `
							</tbody>
						</table>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card  custom-card">
						<h4 class="custom-title p-3" style="font-size: 14px !important; color: #333333;" align="center">Top 10 Doc's Used</h4>
						<table class="table">
							<thead>
								<tr>
									<th>Doc Name</th>
									<th>No of Changes</th>
								</tr>
							</thead>
							<tbody>`;

		data.doc_name.forEach(app => {
			wholedata += `
				<tr>
					<td style="color:#FF4001"><b>${app.ref_doctype}</b></td>
					<td style="color:#FF4001">${app.activity_count}</td>
				</tr>`;
		});

		wholedata += `
							</tbody>
						</table>
					</div>
				</div>
			</div>`;
		wholedata += `
			<div class="row mt-3">
				<div class="col-md-12">
					<div class="frappe-card  custom-card">
						<h4 class="custom-title p-3" style="font-size: 14px !important; color: #333333;" align="center">Top 10 Site's Used</h4>
						<table class="table">
							<thead>
								<tr style="align:center !important;">
									<th>Site Name</th>
									<th>Application Name</th>
									<th>Duration</th>
								</tr>
							</thead>
							<tbody>`;

		data.url_full_data.forEach(app => {
			wholedata += `
				<tr>
					<td style="color:#00A6E0 !important;"><b><a href="#" style="text-decoration:none !important;color:#00A6E0 !important;" class="url-link" data-url="${app.domain}">${app.domain}</a></b></td>
					<td style="color:#62BA46"><b>${app.application_name}</b></td>
					<td style="color:#FF4001">${this.convertSecondsToTime(app.duration)}</td>
				</tr>`;
		});

		wholedata += `
							</tbody>
						</table>
					</div>
				</div>
			</div>`;
		container.append(wholedata);
		$(document).ready(function () {
			$(document).on('click', '.url-link', function (e) {
				e.preventDefault();

				// AJAX call to Python function
				frappe.call({
					method: "productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_url_brief_data",
					args: {
						url_data: $(this).data('url'),
						user: employee_data,
						start_date: start_date_,
						end_date: end_date_,
					},
					callback: function (r) {
						if (r.message) {
							let data = r.message.data;
							render_url_brief_data(data);
						} else {
							$('#urlModal').find('.modal-body').html('No data available for this URL.');
						}
						$('#urlModal').modal('show');  // Show the modal after data is loaded
					}
				});
			});

			function render_url_brief_data(data) {
				function convertSecondsToTime(seconds) {
					const hours = Math.floor(seconds / 3600);
					const minutes = Math.floor((seconds % 3600) / 60);

					return `<b>${hours}</b><span style="font-size:12px"> hours </span><b>${minutes}</b><span style="font-size:12px"> minutes</span>`;
				}
				// Assuming `data` is an object or string you want to display
				let displayContent = `
                <div class="row mt-3">
                    <div class="col-md-12">
                        <div class="frappe-card  custom-card">
                            <h4 class="custom-title p-3" style="font-size: 14px !important; color: #333333;" align="center">Top 10 URL's Used</h4>
                            <table class="table">
                                <thead>
                                    <tr style="align:center !important;">
                                        <th>Site Name</th>
                                        <th>Application Name</th>
                                        <th>Duration</th>
                                    </tr>
                                </thead>
                                <tbody>`;

				data.forEach(app => {
					displayContent += `
                    <tr>
                        <td style="color:#00A6E0 !important;"><b>${app.current_url}</b></td>
                        <td style="color:#62BA46"><b>${app.application_name}</b></td>
                        <td style="color:#FF4001">${convertSecondsToTime(app.duration)}</td>
                    </tr>`;
				});

				displayContent += `
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>`; // Convert data object to string if necessary
				$('#urlModal').find('.modal-body').html(displayContent);
			}
		});

	};

	render_activity_chart() {
		this.progressChart = new frappe.Chart(".performance-activity-chart", {
			type: "bar",
			height: 250,
			width: 400,
			colors: ["#00A6E0"],
			tooltipOptions: {
				formatTooltipX: d => (d + '').toUpperCase(),
				formatTooltipY: d => d + ' Hours',
			},
			data: {
				labels: [],
				datasets: [
					{
						values: []
					}
				]
			},
			isNavigable: true,
		});
		this.update_activity_chart_data();
	}

	update_activity_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		frappe.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_activity_chart_data", {})
			.then((r) => {
				console.log(r)
				$(".performance-activity-chart").html(
					`<div class="progress" style='height:50px'>
						<div class="progress-bar bg-success" role="progressbar" style="width: ${r.incoming}%" aria-valuenow="${r.incoming}" aria-valuemin="0" aria-valuemax="100">${r.incoming}</div>
						<div class="progress-bar bg-info" role="progressbar" style="width: ${r.outgoing}%" aria-valuenow="${r.outgoing}" aria-valuemin="0" aria-valuemax="100">${r.outgoing}</div>
						<div class="progress-bar bg-warning" role="progressbar" style="width: ${r.missed}%" aria-valuenow="${r.missed}" aria-valuemin="0" aria-valuemax="100">${r.missed}</div>
						<div class="progress-bar bg-danger" role="progressbar" style="width: ${r.rejected}%" aria-valuenow="${r.rejected}" aria-valuemin="0" aria-valuemax="100">${r.rejected}</div>
					</div>`
					
				)
			});
	}




	render_line_chart() {
		this.update_line_chart_data();
	};

	update_line_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		}
		else {
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_linechart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {
				} else {
					this.linechart = new frappe.Chart(".performance-line-chart", {
						type: "bar",
						height: 250,
						width: 400,
						colors: ["#fc4f51", "#78d6ff"],
						data: {
							labels: r.labels,
							datasets: r.datasets
						},
						baroptions: { stacked: 1 },
					});
				}
			});
	}


	render_bar_chart() {
		this.barchart = new frappe.Chart(".performance-bar-chart", {
			type: "bar",
			height: 250,
			width: 400,
			colors: ["#01DFA5"],
			tooltipOptions: {
				formatTooltipX: d => (d + '').toUpperCase(),
				formatTooltipY: d => d + ' Modifications',
			},
			data: {
				labels: [],
				datasets: [
					{
						values: []
					}
				]
			},
		});
		this.update_bar_chart_data();

	}

	update_bar_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		}
		else {
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_barchart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {
				} else {
					this.barchart.update(r);
				}
			});
	}

	render_images() {
		let currentOffset = 0;
		const initialLimit = 20;
		const loadLimit = 20;
		let isLoading = false;
		let data;
		let lastHourHeader = ''; // Variable to store the last hour header
		
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		
		const imageContainer = this.main_section.find(".recent-activity-list");
		
		// Debounce function to prevent excessive scroll event calls
		const debounce = (func, delay) => {
			let debounceTimer;
			return function() {
				const context = this;
				const args = arguments;
				clearTimeout(debounceTimer);
				debounceTimer = setTimeout(() => func.apply(context, args), delay);
			};
		};
		
		const loadImages = () => {
			if (isLoading) return;
			isLoading = true;
		
			const limit = currentOffset === 0 ? initialLimit : loadLimit;
		
			frappe.xcall("finbyz.finbyz.page.productify_employee_tracking_finbyz.productify_employee_tracking_finbyz.get_images", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
				offset: currentOffset
			})
			.then((imagedata) => {
				imagedata.reverse();
		
				let slotImages = {};
		
				imagedata.forEach((image) => {
					const imageDateTime = new Date(image.datetime);
					const hour = imageDateTime.getHours();
					const date = imageDateTime.toDateString();
					const slot = Math.floor(imageDateTime.getMinutes() / 5);
		
					if (!slotImages[date]) {
						slotImages[date] = {};
					}
		
					if (!slotImages[date][hour]) {
						slotImages[date][hour] = new Array(12).fill(null);
					}
		
					slotImages[date][hour][slot] = image;
				});
		
				Object.keys(slotImages).reverse().forEach(date => {
					Object.keys(slotImages[date3 ]).reverse().forEach(hour => {
						const currentHourHeader = `${date} ${hour}:00:00`;
						if (currentHourHeader !== lastHourHeader) {
							const hourHeader = `<div class="col-md-12"style="margin-top:2px;"><h5><b>${currentHourHeader}</b></h5></div>`;
							imageContainer.append(hourHeader);
							lastHourHeader = currentHourHeader; 
						}
		
						for (let slot = 11; slot >= 0; slot--) {
							const image = slotImages[date][hour][slot];
							const slotTime = new Date(date);
							slotTime.setHours(hour);
							slotTime.setMinutes(slot * 5);
							const slotTimeString = slotTime.toLocaleTimeString('en-US', { hour12: false });
		
							if (image) {
								const imgElement = `
									<div class="col-md-3">
										<p style="text-align: center;">${slotTimeString}</p>
										<img src="${image.screenshot}" title="${image.datetime_}" alt="User Activity Image" style="margin-bottom: 10px;" class="clickable-image">
									</div>`;
								imageContainer.append(imgElement);
							} else {
								const gapMessage = `
									<div class="col-md-3">
										<p style="text-align: center;">${slotTimeString}</p>
										<div style="width: 100%; height: 240px; background-color: #dddddd;"></div>
									</div>`;
								imageContainer.append(gapMessage);
							}
						}
					});
				});
		
				// Add click event listener for images
				$('.clickable-image').off('click').on('click', function() {
					const imgSrc = $(this).attr('src');
					$('#zoomedImg').attr('src', imgSrc);
					$('#imageModal').modal('show');
				});
		
				currentOffset += imagedata.length;
				isLoading = false;
			})
			.catch(() => {
				isLoading = false; // Reset isLoading flag in case of an error
			});
		};
		
		// Initial load
		currentOffset = 0;
		imageContainer.empty();
		loadImages();
		
		// Add debounced scroll event listener
		const handleScroll = debounce(() => {
			const scrollHeight = $(document).height();
			const scrollPosition = $(window).height() + $(window).scrollTop();
			const scrollThreshold = 50; // Load more images when 50 pixels from the bottom
		
			if (scrollPosition >= scrollHeight - scrollThreshold) {
				loadImages();
			}
		}, 250); // Debounce delay of 250ms
		
		$(window).on('scroll', handleScroll);
	}
	
	
	
	
	
	
}

frappe.provide("frappe.ui");
frappe.ui.UserProfile = UserProfile;

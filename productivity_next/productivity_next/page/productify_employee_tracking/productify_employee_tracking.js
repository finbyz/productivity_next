frappe.pages['Productify Employee Tracking'].on_page_load = function (wrapper) {
	new UserProfile(wrapper);
}


UserProfile = class UserProfile {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
		});

		const urlParams = new URLSearchParams(window.location.search);
		const currentEmployee = urlParams.get('employee');
		console.log("URL employee parameter:", currentEmployee);
		if (currentEmployee && currentEmployee !== 'undefined') {
			this.selected_employee = currentEmployee;
			console.log("Employee set from URL:", this.selected_employee);
		} else {
			const employeePromise = frappe.db.get_value("Employee", {
				"user_id": frappe.session.user
			}, "name");
			Promise.resolve(employeePromise).then(result => {
				if (result && result.message && result.message.name) {
					this.selected_employee = result.message.name;
					const newUrl = new URL(window.location.href);
					newUrl.searchParams.set('employee', result.message.name);
					window.history.pushState({
						path: newUrl.toString()
					}, '', newUrl.toString());
					console.log("Employee set from session and URL updated:", this.selected_employee);
				}
			}).catch(error => {
				console.error("Error retrieving employee:", error);
			});
		}

		this.sidebar = this.wrapper.find(".layout-side-section");
		this.toggle_button = this.wrapper.find(".sidebar-toggle-placeholder");
		this.main_section = this.wrapper.find(".layout-main-section");
		this.buttonsInitialized = false;

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

		this.wrapper.bind("show", () => {
			this.show();
		});
	}


	// hide_sidebar_and_toggle() {
	//     this.sidebar.hide();
	//     // this.toggle_button.hide();
	//     this.main_section.css('width', '100%');
	// }

	show() {
		this.user_id = frappe.session.user;
		frappe.dom.freeze(__("Loading user profile") + "...");

		frappe.db.exists("User", this.user_id)
			.then((exists) => {
			if (exists) {
				this.make_user_profile();
			} else {
					frappe.dom.unfreeze();
				frappe.msgprint(__("User does not exist"));
			}
			})
			.then(() => {
				frappe.dom.unfreeze();
			})
			.catch((error) => {
				frappe.dom.unfreeze();
				console.error("Error loading user data:", error);
			});
	}

	finish_user_profile_setup() {
		this.setup_user_search();
		this.setup_timespan();
		this.main_section.empty().append(frappe.render_template("productify_employee_tracking"));
		// this.render_overall_activity_chart();
		this.render_intensity_heatmap();
		this.update_application_time_chart();
		this.update_domain_time_chart();
		this.update_calls_time_chart();
		this.update_calls_type_chart();
		// this.render_issue_active_chart();
		this.fetch_and_render_user_data();
		// this.fetch_and_render_issue_data();
		// this.render_issue_chart();
		// this.render_issue_time_chart();
		this.render_pie_chart();
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
			fields: [{
				fieldtype: "DateRange",
				fieldname: "timespan_range",
				label: __("Timespan Range"),
				description: __("Select a start and end date"),
			}, ],
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
				window.history.pushState({
					path: newUrl.toString()
				}, '', newUrl.toString());
				const urlParams = new URLSearchParams(window.location.search);
				this.selected_start_date = urlParams.get('start_date');
				this.selected_end_date = urlParams.get('end_date');
				this.make_user_profile();
			},
		});
		dialog.show();
	}
	render_user_details() {
		function getBaseURL() {
			return window.location.origin + '/app/';
		}
		this.start_date_ = this.selected_start_date;
		this.end_date_ = this.selected_end_date;
		const baseUrl = getBaseURL();
		if (this.numberCardData) {
			this.callsHoursIncoming = this.convertSecondsToTime_(this.numberCardData.total_incoming_duration + this.numberCardData.internal_total_incoming_duration)
			this.callsHoursOutgoing = this.convertSecondsToTime_(this.numberCardData.total_outgoing_duration + this.numberCardData.internal_total_outgoing_duration)
			this.meeting_hours = this.convertSecondsToTime_(this.numberCardData.total_meeting_duration_external + this.numberCardData.total_meeting_duration_internal)
			this.internal_meeting_hours = this.convertSecondsToTime_(this.numberCardData.total_meeting_duration_internal)
			this.external_meeting_hours = this.convertSecondsToTime_(this.numberCardData.total_meeting_duration_external)
		} else {
			this.callsHoursIncoming = 0;
			this.callsHoursOutgoing = 0;
			this.meeting_hours = 0;
			this.internal_meeting_hours = 0;
			this.external_meeting_hours = 0;
		}
		frappe.db.get_value("Employee", this.selected_employee, "image")
			.then((result) => {
				const userImage = result.message.image;
				const employeeMeetingUrl = `${baseUrl}meeting?employee=${encodeURIComponent(this.selected_employee)}&meeting_from=${encodeURIComponent(`["Between",["${this.start_date_}","${this.end_date_}"]]`)}&docstatus=1`;
				const employeeFincallUrl = `${baseUrl}employee-fincall?employee=${encodeURIComponent(this.selected_employee)}&date=${encodeURIComponent(`["Between",["${this.start_date_}","${this.end_date_}"]]`)}`;
				this.sidebar.empty().append(
					this.update_activity_chart_data(),
					frappe.render_template("productify_employee_tracking_sidebar", {
						user_image: userImage,
						user_abbr: this.user.abbr,
						user_location: this.user.location,
						numberCardData: this.numberCardData,
						employeeMeetingUrl: employeeMeetingUrl,
						employeeFincallUrl: employeeFincallUrl,
						callsHoursIncoming: this.callsHoursIncoming,
						callsHoursOutgoing: this.callsHoursOutgoing,
						meeting_total_hours: this.meeting_hours,
						internal_meeting_hours: this.internal_meeting_hours,
						external_meeting_hours: this.external_meeting_hours
					})
				);
			})
			.catch((err) => {
				console.error("Error fetching user image:", err);
			});

		this.setup_user_profile_links();
	}
	setup_user_profile_links() {
		if (this.user_id !== frappe.session.user) {
			this.wrapper.find(".profile-links").hide();
		} else {
			this.wrapper.find(".edit-profile-link").on("click", () => {
				this.edit_profile();
			});

			this.wrapper.find(".user-settings-link").on("click", () => {
				this.go_to_user_settings();
			});
		}
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
		if (!this.buttonsInitialized) { // Check if buttons have already been initialized
			// Add a refresh button with an icon
			this.page.add_action_icon("refresh", () => {
				window.location.reload();
			});

			// Set up the 'Change Employee' button
			this.$user_search_button = this.page.set_secondary_action(
				__("Change Employee"),
				() => this.show_user_search_dialog(), {
					icon: "change",
					size: "sm"
				}
			);

			this.buttonsInitialized = true; // Set the flag to true after adding buttons
		}
	}

	show_user_search_dialog() {
		let dialog = new frappe.ui.Dialog({
			title: __("Change Employee"),
			fields: [{
				fieldtype: "Link",
				fieldname: "employee",
				options: "Employee",
				label: __("Employee"),
			}, ],
			primary_action_label: __("Go"),
			primary_action: ({
				employee
			}) => {
				dialog.hide();
				this.selected_employee = employee;
				this.make_user_profile()
				const newUrl = new URL(window.location.href);
				newUrl.searchParams.set('employee', employee);
				window.history.pushState({
					path: newUrl.toString()
				}, '', newUrl.toString());
			},
		});
		dialog.show();

	}
	// render_activity_chart() {
	// 	this.progressChart = new frappe.Chart(".activity-chart-data", {
	// 		type: "bar",
	// 		height: 250,
	// 		width: 400,
	// 		colors: ["#00A6E0"],
	// 		tooltipOptions: {
	// 			formatTooltipX: d => (d + '').toUpperCase(),
	// 			formatTooltipY: d => d + ' Hours',
	// 		},
	// 		data: {
	// 			labels: [],
	// 			datasets: [
	// 				{
	// 					values: []
	// 				}
	// 			]
	// 		},
	// 		isNavigable: true,
	// 	});
	// 	this.update_activity_chart_data();
	// }
	update_activity_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		frappe.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_activity_chart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {

				// Convert time values from seconds to formatted hours and minutes
				const total_hours = this.convertSecondsToTime_(r.total_hours);
				const total_active_hours = this.convertSecondsToTime_(r.total_active_hours);
				const total_idle_time = this.convertSecondsToTime_(r.total_idle_time);
				const total_call_data = this.convertSecondsToTime_(r.total_call_data);
				const total_meeting_data = this.convertSecondsToTime_(r.total_meeting_data);
				const total_inactive_hours = this.convertSecondsToTime_(r.total_inactive_hours);

				let inactiveHoursRow = '';
				if (r.total_inactive_hours > 0) {
					inactiveHoursRow = `
						<tr class='text-white'>
							<td><i>Inactive Hours:</i></td>
							<td>-</td>
							<td><i>${total_inactive_hours} H</i></td>
						</tr>
					`;
				}

				const container = $("#activity-chart-data");
				container.html(
					`<div class="progress" style="max-width: 400px !important;" data-toggle="tooltip" title="
    <div>
        <b>User Activity</b>
        <table class='table table-borderless table-tooltip'>
            <tbody>
                <tr class='text-white border-bottom'>
                    <td><b>Total Time:</b></td>
                    <td>-</td>
                    <td><b>${total_hours} H</b></td>
                </tr>
                <tr class='text-white'>
                    <td><b>Active Hours:</b></td>
                    <td>-</td>
                    <td><b>${total_active_hours} H</b></td>
                </tr>
                <tr class='text-white'>
                    <td><i>Call:</i></td>
                    <td>-</td>
                    <td><i>${total_call_data} H</i></td>
                </tr>
                <tr class='text-white'>
                    <td><i>Meeting:</i></td>
                    <td>-</td>
                    <td><i>${total_meeting_data} H</i></td>
                </tr>
                <tr class='text-white border-bottom'>
                    <td><i>System:</i></td>
                    <td>-</td>
                    <td><i>${this.convertSecondsToTime_(r.total_active_hours - (r.total_meeting_data + r.total_call_data))} H</i></td>
                </tr>
                <tr class='text-white'>
                    <td><b>Idle Time:</b></td>
                    <td>-</td>
                    <td><b>${total_idle_time} H</b></td>
                </tr>
				
                ${inactiveHoursRow}
            </tbody>
        </table>
    </div>"
    data-html="true"
    data-placement="left">
    <div class="progress-bar bg-success" role="progressbar" style="width: ${r.total_active_hours}%" aria-valuenow="${r.total_active_hours}" aria-valuemin="0" aria-valuemax="${r.total_hours}"></div>
    <div class="progress-bar bg-danger" role="progressbar" style="width: ${r.total_idle_time}%" aria-valuenow="${r.total_idle_time}" aria-valuemin="0" aria-valuemax="${r.total_hours}"></div>
    <div class="progress-bar bg-info" role="progressbar" style="width: ${r.total_call_data}%" aria-valuenow="${r.total_call_data}" aria-valuemin="0" aria-valuemax="${r.total_hours}"></div>
    <div class="progress-bar bg-warning" role="progressbar" style="width: ${r.total_meeting_data}%" aria-valuenow="${r.total_meeting_data}" aria-valuemin="0" aria-valuemax="${r.total_hours}"></div>
    <div class="progress-bar bg-dark" role="progressbar" style="width: ${r.total_inactive_hours}%" aria-valuenow="${r.total_inactive_hours}" aria-valuemin="0" aria-valuemax="${r.total_hours}"></div>
</div>`
)

				var myDefaultWhiteList = $.fn.tooltip.Constructor.Default.whiteList;
				myDefaultWhiteList.table = ['class'];
				myDefaultWhiteList.tbody = [];
				myDefaultWhiteList.tr = [];
				myDefaultWhiteList.td = [];

				$('[data-toggle="tooltip"]').tooltip({
				container: 'body',
				html: true,
				whiteList: myDefaultWhiteList,
				title: function () { return '<u>text1</u><table class="table text-light"><tr><td>text2</td></tr></table>'; }
				});


				// Enable tooltips with custom class
				$('[data-toggle="tooltip"]').tooltip({
					html: true,
					container: 'body',
					placement: 'left', // Set tooltip placement to left
					template: '<div class="tooltip-custom" style="max-width: 400px !important;" role="tooltip"><div class="arrow"></div><div class="tooltip-inner"></div></div>'
				});
				const mobilecontainer = $("#activity-chart-data_mobile");
				mobilecontainer.html(`
					<div class="d-lg-none">
						<div class="card border-primary shadow">
							<div class="card-body">
								<h5 class="card-title text-primary border-bottom pb-2 text-center">User Activity</h5>
								<table class="table table-borderless">
									<tbody>
										<tr  style="border-bottom: 1px solid #E5E4E2;">
											<td align="right"><b>Total Time:</b></td>
											<td>-</td>
											<td><b>${total_hours} H</b></td>
										</tr>
										<tr>
											<td align="right"><b>Active Hours:</b></td>
											<td>-</td>
											<td><b>${total_active_hours} H</b></td>
										</tr>
										<tr>
											<td align="right"><i>Call:</i></td>
											<td>-</td>
											<td><i>${total_call_data} H</i></td>
										</tr>
										<tr>
											<td align="right"><i>Meeting:</i></td>
											<td>-</td>
											<td><i>${total_meeting_data} H</i></td>
										</tr>
										<tr  style="border-bottom: 1px solid #E5E4E2;">
											<td align="right"><i>System:</i></td>
											<td>-</td>
											<td><i>${this.convertSecondsToTime_(r.total_active_hours - (r.total_meeting_data + r.total_call_data))} H</i></td>
										</tr>
										<tr>
											<td align="right"><b>Idle Time:</b></td>
											<td>-</td>
											<td><b>${total_idle_time} H<b></td>
										</tr>
										 ${inactiveHoursRow}
									</tbody>
								</table>
							</div>
						</div>
					</div>`
				)

			});
	}
		render_overall_activity_chart() {
			var data = [
				{
					x: ["2009-01-01", "2009-03-05", "2009-02-20"],
					x0: ["2009-02-28", "2009-04-15", "2009-05-30"],
					y: ["Alex", "Alex", "Max"],
					type: "scatter",
					mode: "lines+markers",
					marker: {color: "blue"},
					name: "Alex"
				},
				{
					x: ["2009-01-01", "2009-03-05", "2009-02-20"],
					x0: ["2009-02-28", "2009-04-15", "2009-05-30"],
					y: ["Alex", "Alex", "Max"],
					type: "scatter",
					mode: "lines+markers",
					marker: {color: "red"},
					name: "Max"
				}
			];
	
			var layout = {
				title: "Timeline",
				xaxis: {
					title: "Time"
				},
				yaxis: {
					title: "Resource"
				}
			};
			Plotly.newPlot('overall-activity-gantt-container', data, layout);
		}
	

		render_intensity_heatmap() {
			let data;
			if (this.selected_employee !== null) {
				data = this.selected_employee;
			} else {
				data = this.user_id;
			}
			frappe.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_intensityChart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			}).then((r) => {
				if (r.values.length === 0) {
					console.log("No data available for the selected period.");
				} else {
					const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
					const allLabels = r.labels;
					const allValues = r.values;
		
					// Generate static x-axis labels for 7-23 hours, each divided into four 15-minute intervals
					const xLabels = [];
					for (let hour = 7; hour < 24; hour++) {
						for (let quarter = 0; quarter < 4; quarter++) {
							const minute = quarter * 15;
							xLabels.push(`${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`);
						}
					}
		
					// Generate labels for the x-axis ticks (7:00, 8:00, ..., 23:00)
					const tickVals = [];
					const tickText = [];
					for (let hour = 7; hour < 24; hour++) {
						tickVals.push(xLabels.findIndex(label => label.startsWith(`${hour.toString().padStart(2, '0')}:00`)));
						tickText.push(`${hour.toString().padStart(2, '0')}:00`);
					}
		
					const zData = Array.from({ length: 7 }, () => Array(xLabels.length).fill(0));
		
					allValues.forEach((dayValues, dayIndex) => {
						dayValues.forEach((value, timeIndex) => {
							const label = allLabels[dayIndex][timeIndex];
							const xIndex = xLabels.indexOf(label);
							if (xIndex !== -1) {
								zData[dayIndex][xIndex] = value;
							}
						});
					});
		
					const heatmapData = [{
						z: zData,
						x: xLabels,
						y: days,
						type: 'heatmap',
						showscale: false,
						colorscale: [
							[0, 'rgb(230,250,255)'],
							[1, 'rgb(0,100,200)']
						],
						hovertemplate: '<b>%{y}</b><br>%{x}<br>Value: %{z}<extra></extra>',
						hoverinfo: 'x+y+z',
						zmin: 0,
						zmax: Math.max(...zData.flat()),
						xgap: 4,
						ygap: 4
					}];
		
					const plotLayout = {
						hoverlabel: {
							bgcolor: '#0073CF',
							font: {
								color: 'white'
							}
						},
						xaxis: {
							tickmode: 'array',
							tickvals: tickVals,
							ticktext: tickText,
							fixedrange: true
						},
						yaxis: {
							tickmode: 'array',
							tickvals: days,
							ticktext: days,
							fixedrange: true
						},
						height: window.innerHeight * 0.3,
						margin: {
							t: 20,
							b: 50,
							l: 90,
							r: 20
						},
						plot_bgcolor: 'rgba(0,0,0,0)',
						paper_bgcolor: 'rgba(0,0,0,0)',
					};
		
					const config = {
						displayModeBar: false,
						responsive: false,
						scrollZoom: false,
						// staticPlot: true
					};
		
					Plotly.newPlot('intensity-heatmap-container', heatmapData, plotLayout, config);
		
					// Adding CSS for the border between each square
					const style = document.createElement('style');
					style.innerHTML = `
						#intensity-heatmap-container .plotly .heatmap rect {
							stroke-width: 1;
							stroke: #FFFFFF;
						}
					`;
					document.head.appendChild(style);
				}
			}).catch((error) => {
				console.error("Error fetching data:", error);
			});
		}
		


	update_application_time_chart() {
		let data = this.selected_employee;

		// Fetch the data and render the pie chart
		frappe
			.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_applicationTimeChart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {
					// Handle empty data
				} else {
					// Example function to get current theme's label color
					const getCurrentThemeLabelColor = () => {
						// Replace this with your actual theme color retrieval logic
						// This is just a placeholder
						return {
							labelColor: '#FFFFFF', // Default to black
							backgroundColor: 'rgba(0,0,0,0)' // Default to transparent
						};
					};

					const themeColors = getCurrentThemeLabelColor();

					const plotData = [{
						values: r.values,
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
						hovertemplate: '%{label}: %{value} hours<extra></extra>',
						textinfo: 'label+percent',
						textposition: 'inside',
						textfont: {
							color: themeColors.labelColor,
							outline: 'black' // Adds outline to the text
						},
						textinfo: 'label+percent',
						insidetextorientation: 'horizontal' // Ensures horizontal text for better readability
					}];
					const plotLayout = {
						height: '100%',
						margin: {
							"t": 0,
							"b": 0,
							"l": 0,
							"r": 0
						},
						plot_bgcolor: themeColors.backgroundColor,
						paper_bgcolor: themeColors.backgroundColor
					};
					const config = {
						displayModeBar: false,
					responsive: false,
					staticPlot: true
					};
	
					Plotly.newPlot('application-usage-time-chart', plotData, plotLayout, config); // Update the target element ID
				}
			});
	}

	update_domain_time_chart() {
		let data;
		if (this.selected_employee !== null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}

		// Fetch the data and render the pie chart
		frappe
			.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_domainTimeChart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {
					// Handle empty data
				} else {
					// Example function to get current theme's label color
					const getCurrentThemeLabelColor = () => {
						// Replace this with your actual theme color retrieval logic
						// This is just a placeholder
						return {
							labelColor: '#FFFFFF', // Default to black
							backgroundColor: 'rgba(0,0,0,0)' // Default to transparent
						};
					};

					const themeColors = getCurrentThemeLabelColor();

					const plotData = [{
						values: r.values,
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
						hovertemplate: '%{label}: %{value} minutes<extra></extra>',
						textinfo: 'label+percent',
						textposition: 'inside',
						textfont: {
							color: themeColors.labelColor,
							outline: 'black' // Adds outline to the text
						},
						textinfo: 'label+percent',
						insidetextorientation: 'horizontal' // Ensures horizontal text for better readability
					}];
					const plotLayout = {
						height: '100%',
						margin: {
							"t": 0,
							"b": 0,
							"l": 0,
							"r": 0
						},
						plot_bgcolor: themeColors.backgroundColor,
						paper_bgcolor: themeColors.backgroundColor
					};
					const config = {
						displayModeBar: false,
					responsive: false,
					staticPlot: true
					};
	
					Plotly.newPlot('domain-usage-time-chart', plotData, plotLayout, config); // Update the target element ID
				}
			});
	}



	update_calls_time_chart() {
		let data;
		if (this.selected_employee !== null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_callsTimeChart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {
					// Handle empty data
				} else {
					const getCurrentThemeLabelColor = () => {
						// Replace this with your actual theme color retrieval logic
						// This is just a placeholder
						return {
							labelColor: '#FFFFFF', // Default to white for better contrast
							backgroundColor: 'rgba(0,0,0,0)' // Default to transparent
						};
					};
					const themeColors = getCurrentThemeLabelColor();

					// Create a Plotly pie chart
					const plotData = [{
						values: r.values,
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
					Plotly.newPlot('calls-time-chart', plotData, plotLayout, {
						displayModeBar: false,
					responsive: false,
					staticPlot: true

					});
					let container = document.getElementById('calls-time-chart');
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
	update_calls_type_chart() {
		let data;
		if (this.selected_employee !== null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
	
		frappe
			.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_callsTypeChart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				const getCurrentThemeLabelColor = () => {
					return {
						labelColor: '#FFFFFF',
						backgroundColor: 'rgba(0,0,0,0)'
					};
				};
				const themeColors = getCurrentThemeLabelColor();
	
				const plotData = [{
					values: r.time,
					labels: r.labels,
					type: 'pie',
					hole: 0.5,
					marker: {
						colors: [
							'#36A2EB',
							'#9966FF'
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
					showlegend: false,
					height: '50%',
					margin: {
						t: 0,
						b: 0,
						l: 0,
						r: 0    
					},
					plot_bgcolor: themeColors.backgroundColor,
					paper_bgcolor: themeColors.backgroundColor
					
				};
				const config = {
					displayModeBar: false,
					responsive: false,
					staticPlot: true
				};

	
				Plotly.newPlot('calls-type-chart', plotData, plotLayout, config);
				;
			});
	}
	render_work_stats_chart() {
		const container = this.main_section.find(".working-stats-bar-chart");
		container.empty();

		frappe.call({
			method: "productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.work_stats_chart",
			args: {
				user: "selected_employee", // Replace with your dynamic values
				start_date: "selected_start_date", // Replace with your dynamic values
				end_date: "selected_end_date" // Replace with your dynamic values
			},
			callback: function (response) {
				const chartData = JSON.parse(response.message);

				const ctx = document.createElement('canvas');
				container.append(ctx);

				chart = new frappe.Chart(ctx, {
					type: 'bar',
					data: chartData,
					options: {
						scales: {
							xAxes: [{
								stacked: true,
								scaleLabel: {
									display: true,
									labelString: 'Time'
								}
							}],
							yAxes: [{
								stacked: true,
								scaleLabel: {
									display: true,
									labelString: 'Productivity'
								},
								ticks: {
									min: 0,
									max: 1,
									callback: function (value) {
										return (value * 100) + '%';
									}
								}
							}]
						},
						title: {
							display: true,
							text: 'Productivity Bar Chart'
						}
					}
				});
			}
		});
	}


	fetch_and_render_user_data() {

		this.numberCardData = {};
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
					this.numberCardData = r.message;
					this.render_user_data(r.message);
					// console.log("URL DATA", r.message.url_full_data);
					$(document).ready(function () {
						$('#logCountModalTrigger').click(function () {
							$('#logCountModal').modal('show');
						});
					});
					this.render_user_details();
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
		const formattedMinutes = minutes < 10 ? `0${minutes}` : minutes;
		const formattedHours = hours < 10 ? `0${hours}` : hours;
		return `${formattedHours}:${formattedMinutes}`;
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
		let wholedata = `
			<div class="title-area">
				<h4 class="card-title">URL Data</h4>
			</div>`;
		wholedata += `
			<div class="row mt-3">
				<div class="col-md-12">
					<div class="custom-card">
						<h4 class="custom-title p-3" style="font-size: 14px !important;" align="center">Top 10 Site's Used</h4>
						<table class="table">
							<thead>
								<tr style="align:center !important;">
									<th>Domain</th>
									<th>No. of Visits</th>
									<th>Application</th>
									<th>Duration</th>
								</tr>
							</thead>
							<tbody>`;
	
		data.url_full_data.forEach(app => {
			wholedata += `
				<tr>
					<td style="color:#00A6E0 !important;"><b><a href="#" style="text-decoration:none !important;color:#00A6E0 !important;" class="url-link" data-url="${app.domain}">${app.domain}</a></b></td>
					<td style="color:#62BA46"><b>${app.count}</b></td>
					<td style="color:#62BA46"><b>${app.application_name}</b></td>
					<td style="color:#FF4001">${this.convertSecondsToTime(app.total_duration)}</td>
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
				let clickedLink = $(this); // Store reference to clicked link
	
				// AJAX call to Python function
				frappe.call({
					method: "productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_url_brief_data",
					args: {
						url_data: clickedLink.data('url'),
						user: employee_data,
						start_date: start_date_,
						end_date: end_date_,
					},
					freeze: true, // Optional: Freeze the screen until data is loaded
					callback: function (r) {
						if (r.message) {
							let data = r.message.data;
							render_url_brief_data(data);
							$('#urlModal').modal('show'); // Show the modal after data is loaded
						} else {
							$('#urlModal').find('.modal-body').html('No data available for this URL.');
							$('#urlModal').modal('show'); // Show the modal even if no data is available
						}
					}
				});
			});
	
			function render_url_brief_data(data) {
				function convertSecondsToTime_(seconds) {
					const hours = Math.floor(seconds / 3600);
					const minutes = Math.floor((seconds % 3600) / 60);
					const formattedMinutes = minutes < 10 ? `0${minutes}` : minutes;
			
					return `${hours}:${formattedMinutes}`;
				}
				// Assuming `data` is an object or string you want to display
				let displayContent = `
				<div class="row mt-3">
					<div class="col-md-12">
						<div class="frappe-card  custom-card">
							<h4 class="custom-title p-3" style="font-size: 14px !important;" align="center">Top 10 URL's Used</h4>
							<table class="table">
								<thead>
									<tr style="align:center !important;">
										<th>Page Title</th>
										<th>Page URL</th>
										<th>Page Visits</th>
										<th>Duration</th>
									</tr>
								</thead>
								<tbody>`;
	
				data.forEach(app => {
					displayContent += `
					<tr>
					<td style="color:#00A6E0 !important; width: 50% !important;"><b>${app.current_title}</b></td>
					<td style="color:#00A6E0 !important; width: 15% !important;"><b>${app.url}</b></td>
					<td style="color:#62BA46; width: 15% !important;"><b>${app.count}</b></td>
					<td style="color:#FF4001; width: 20% !important;">${convertSecondsToTime_(app.duration)}</td>
				</tr>`;
				});
	
				displayContent += `
								</tbody>
							</table>
						</div>
					</div>
				</div>`;
				$('#urlModal').find('.modal-body').html(displayContent);
			}
		});
	};


	fetch_and_render_issue_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}

		frappe.call({
			method: "productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_issue_data",
			args: {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			},
			callback: (r) => {
				if (r.message) {
					this.render_issue_data(r.message);
				}
			}
		});
	}


	render_issue_data(data) {
		const container = this.main_section.find("#user-issue-cards");
		container.empty();

		let wholedata = `
			<div class="title-area">
				<h4 class="card-title">Issue Data</h4>
			</div>
			
			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Total Issues Worked On</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;"><b>${data.no_of_issues}</b><span style="font-size:12px"> Issues</span></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Total Hours In Issues</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${data.time_in_issues || 0}</b><span style="font-size:12px"> Hours Worked On Issues</span></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; ">Average Time Per Issue Resolved</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${parseFloat(data.time_in_issues/(data.no_of_issues)|| 0).toFixed(2)}</b><span style="font-size:12px"> Hours</span></div>
					</div>
				</div>
			</div>`;
		container.append(wholedata);
	}
	render_issue_active_chart() {
		this.update_issue_active_chart_data();
	}

	update_issue_active_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_issue_active_chart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {} else {
					this.issue_active_chart = new frappe.Chart(".performance-issue-active-chart", {
						type: "bar",
						height: 250,
						width: 400,
						data: {
							labels: r.labels,
							datasets: r.datasets
						},
					});
				}
			});
	}

	render_issue_chart() {
		this.update_issue_chart_data();

	}

	update_issue_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_issuechart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {} else {
					this.issuechart = new frappe.Chart(".performance-issue-chart", {
						type: "bar",
						height: 250,
						width: 400,
						colors: ["#5F04B4"],
						tooltipOptions: {
							formatTooltipX: d => (d + '').toUpperCase(),
							formatTooltipY: d => d + ' Issues',
						},
						data: {
							labels: r.labels,
							datasets: r.datasets
						},
						isNavigable: true,
					});
					this.issuechart.update(r);
				}
			});
	}

	render_issue_time_chart() {
		this.update_issue_time_chart_data();

	}

	update_issue_time_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_issue_time_chart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {} else {
					this.issuetimechart = new frappe.Chart(".performance-time-chart ", {
						type: "line",
						height: 250,
						width: 400,
						colors: ["#62BA46"],
						tooltipOptions: {
							formatTooltipX: d => (d + '').toUpperCase(),
							formatTooltipY: d => d + ' Hours',
						},
						data: {
							labels: r.labels,
							datasets: r.datasets
						},
						isNavigable: true,
					});
				}
			});
	}

	render_pie_chart() {
		this.update_pie_chart_data();
	}

	update_pie_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_piechart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {} else {
					this.piechart = new frappe.Chart(".performance-pie-chart", {
						type: "bar",
						height: 250,
						width: 400,
						colors: ["#00A6E0"],
						tooltipOptions: {
							formatTooltipX: d => (d + '').toUpperCase(),
							formatTooltipY: d => d + ' Hours',
						},
						data: {
							labels: r.labels,
							datasets: r.datasets
						},
						isNavigable: true,
					});
				}
			});
	}

	render_line_chart() {
		this.update_line_chart_data();

	}

	update_line_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
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
					// Handle case where there are no labels
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
						barOptions: {
							stacked: 1
						},
						tooltipOptions: {
							formatTooltipY: d => (d + " Min") // Add "Min" to values
						}
					});
				}
			});
	}


	render_bar_chart() {
		this.update_bar_chart_data();
	}

	update_bar_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_barchart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {} else {
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
							labels: r.labels,
							datasets: r.datasets
						},
					});
				}
			});
	}

	async render_images(){
		let startDatetime = new Date(this.selected_start_date + " 00:00:00"); // Replace with your start datetime
		let endDatetime = new Date(this.selected_end_date + " 23:59:59"); // Replace with your end datetime
		let data = null;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}

		let lastPrintedDate = null;
		let lastPrintedHour = null;
		let slotTimeString  = null;

		const imageContainer = this.main_section.find(".recent-activity-list");
		const debounce = (func, delay) => {
			let debounceTimer;
			return function () {
				const context = this;
				const args = arguments;
				clearTimeout(debounceTimer);
				debounceTimer = setTimeout(() => func.apply(context, args), delay);
			};
		};

		async function loadImages(user, start_time, end_time) {
			let flag = 0;
			await frappe.xcall("productivity_next.productivity_next.page.productify_employee_tracking.productify_employee_tracking.get_images", {
				user: user,
				start_date: start_time,
				end_date: end_time,
			})
			.then((imagedata) => {
				if (imagedata.length > 0) {
					flag = 1;
				}
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
					Object.keys(slotImages[date]).reverse().forEach(hour => {
						if (lastPrintedDate !== date || lastPrintedHour !== hour) {
							const hourHeader = `<div class="col-md-12"><h5><b>${date} ${hour}:00:00</b></h5></div>`;
							imageContainer.append(hourHeader);
							lastPrintedDate = date;
							lastPrintedHour = hour;
						}

						for (let slot = 11; slot >= 0; slot--) {
							const image = slotImages[date][hour][slot];
							const slotTime = new Date(date);
							slotTime.setHours(hour);
							slotTime.setMinutes(slot * 5);
							const slotTimeString = slotTime.toLocaleTimeString('en-US', {
								hour12: false
							});

							if (image) {
								const imgElement = `
								<div class="col-md-3">
								<div style="display: flex; justify-content: center; align-items: center; height: 160px;">
									<img src="${image.screenshot}" title="${image.datetime_}" alt="User Activity Image" style="max-width: 100%; max-height: 100%; object-fit: contain;" class="clickable-image">
								</div>
								<p style="text-align: center;"><b>${slotTimeString}</b></p>
								</div>`;
								imageContainer.append(imgElement);
							} else {
								const gapMessage = `
								<div class="col-md-3">
								<div style="width: 100%; height: 160px; background-color: #dddddd; display: flex; justify-content: center; align-items: center;">
									<span style="font-weight: bold;">Not Active</span>
								</div>
								<p style="text-align: center;"><b>${slotTimeString}</b></p>
								</div>`;
								imageContainer.append(gapMessage);
							}
							
							}
						});
				});
				function setImageHeight() {
					const windowHeight = window.innerHeight;
					const imageHeight = windowHeight * 0.2;
					const images = document.querySelectorAll('.clickable-image');
					images.forEach(img => {
						img.style.height = `${imageHeight}px`;
					});
				}
				setImageHeight();
				window.addEventListener('resize', setImageHeight);
				$('.clickable-image').off('click').on('click', function () {
					const imgSrc = $(this).attr('src');
					$('#zoomedImg').attr('src', imgSrc);
					$('#imageModal').modal('show');
				});

			});
			return flag;
		}
		
		// let ct = new Date();

		// if (endDatetime > new Date()){
		// 	endDatetime = ct;
		// }

		// Loop through hours from start to end datetime
		let currentDatetime = endDatetime;
		let start_time = new Date(currentDatetime);
		let end_time = new Date(currentDatetime);

		imageContainer.empty();

		end_time = new Date(currentDatetime);
		currentDatetime.setHours(currentDatetime.getHours(), currentDatetime.getMinutes(), currentDatetime.getSeconds(), 0);
		currentDatetime.setHours(currentDatetime.getHours() - 1);
		start_time = new Date(currentDatetime);

		if (start_time < startDatetime) {
			return;
		}
		else {
			let flag = await loadImages(data, start_time.toLocaleString(), end_time.toLocaleString());

			while ((flag == 0) && (start_time > startDatetime)) {
				end_time = new Date(currentDatetime);
				currentDatetime.setHours(currentDatetime.getHours(), currentDatetime.getMinutes(), currentDatetime.getSeconds(), 0);
				currentDatetime.setHours(currentDatetime.getHours() - 1);
				start_time = new Date(currentDatetime);

				flag = await loadImages(data, start_time.toLocaleString(), end_time.toLocaleString());
			}
		}
		
		if (currentDatetime > startDatetime) {
			const handleScroll = debounce(async () => {
				const scrollHeight = $(document).height();
				const scrollPosition = $(window).height() + $(window).scrollTop();
				const scrollThreshold = 400;

				if (scrollPosition >= scrollHeight - scrollThreshold) {
					end_time = new Date(currentDatetime);
					currentDatetime.setHours(currentDatetime.getHours(), currentDatetime.getMinutes(), currentDatetime.getSeconds(), 0);
					currentDatetime.setHours(currentDatetime.getHours() - 1);
					start_time = new Date(currentDatetime);

					if (start_time < startDatetime) {
						return;
					}
					else {
						let flag = await loadImages(data, start_time.toLocaleString(), end_time.toLocaleString());

						while ((flag == 0) && (start_time > startDatetime)) {
							end_time = new Date(currentDatetime);
							currentDatetime.setHours(currentDatetime.getHours(), currentDatetime.getMinutes(), currentDatetime.getSeconds(), 0);
							currentDatetime.setHours(currentDatetime.getHours() - 1);
							start_time = new Date(currentDatetime);
	
							flag = await loadImages(data, start_time.toLocaleString(), end_time.toLocaleString());
						}
					}
				}
			}, 100);

			$(window).on('scroll', handleScroll);
		}
	}
}
frappe.provide("frappe.ui");
frappe.ui.UserProfile = UserProfile;
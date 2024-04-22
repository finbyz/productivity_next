frappe.pages['productify-web-page'].on_page_load = function(wrapper) {
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
        this.selected_employee = null;
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

    make_user_profile() {
		this.user = frappe.user_info(this.user_id);
		if (!this.selected_employee) { 
			this.page.set_title(this.user.fullname);
		} else {
			frappe.db.get_doc("Employee", this.selected_employee)
				.then(employee => {
					this.page.set_title(employee.employee_name); 
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
	
	finish_user_profile_setup() {
		this.setup_user_search();
		this.setup_timespan();
		this.main_section.empty().append(frappe.render_template("user_profile"));
		this.render_heatmap();
		this.render_pie_chart();
		this.render_images();
		this.fetch_and_render_user_data();
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
	
				this.selected_start_date = startDate;
				this.selected_end_date = endDate;
				this.make_user_profile();
				
				dialog.hide();
			},
		});
		dialog.show();
	}
	
    setup_user_search() {
        this.$user_search_button = this.page.set_secondary_action(
            __("Change Employee"),
            () => this.show_user_search_dialog(),
            { icon: "change", size: "sm" }
        );
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
				this.selected_employee = employee;
                dialog.hide();
				this.make_user_profile()
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
		else{
			data = this.user_id;
		}
	
		frappe.xcall("productivity_next.productivity_next.page.productify_web_page.user_profile.get_heatmap_data", {
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
			method: "productivity_next.productivity_next.page.productify_web_page.user_profile.get_user_data",
			args: {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			},
			callback: (r) => {
				if (r.message) {
					this.render_user_data(r.message);
				}
			}
		});
	}
	
    
	render_user_data(data) {
		const container = this.main_section.find("#user-data-cards");
		container.empty();

		let wholedata = `
			<div class="title-area dynamic-spacing">
				<h4 class="card-title">Productify Data</h4>
			</div>
			
			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Total Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;"><b>${parseFloat(data.total_hours /60 / 60).toFixed(2)} Working Hours</b></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Total Active Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${parseFloat((data.total_hours /60 / 60)-(data.total_idle_time /60 / 60)).toFixed(2)} Active Hours</b></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Total Idle Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${parseFloat(data.total_idle_time /60 / 60).toFixed(2)} Idle Hours</b></div>
					</div>
				</div>
			</div>

			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;"><b>${parseFloat((data.total_hours /60 / 60)/data.total_days).toFixed(2)} Working Hours Per Day</b></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Active Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${parseFloat(((data.total_hours /60 / 60)/data.total_days)-((data.total_idle_time /60 / 60)/data.total_days)).toFixed(2)} Active Hours Per Day</b></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Idle Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${parseFloat((data.total_idle_time /60 / 60)/data.total_days).toFixed(2)} Idle Hours Per Day</b></div>
					</div>
				</div>
			</div>

			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Application Usage Log Count</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;"><b>${data.application_usage} Applications Used</b></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Fincall Log Count</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${data.fincall_count} Calls Attended</b></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Version Log Count</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${data.version_count} Interactions</b></div>
					</div>
				</div>
			</div>
			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
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
					<td style="color:#00A6E0"><b>${app.application_name}</b></td>
					<td style="color:#2D9596">${parseFloat(app.total_duration/60/60).toFixed(2)} Hours</td>
				</tr>`;
		});
	
		wholedata += `
							</tbody>
						</table>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
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
					<td style="color:#62BA46"><b>${app.client}</b></td>
					<td style="color:#03B404">${app.call_count}</td>
					<td style="color:#00DF37">${parseFloat(app.total_duration/60).toFixed(2)} Min</td>
				</tr>`;
		});
	
		wholedata += `
							</tbody>
						</table>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card dynamic-spacing custom-card">
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
					<td style="color:#FF8100">${app.activity_count}</td>
				</tr>`;
		});
	
		wholedata += `
							</tbody>
						</table>
					</div>
				</div>
			</div>`;
		container.append(wholedata);
	}
	
	render_pie_chart() {
		this.piechart = new frappe.Chart(".performance-pie-chart", {
			type: "pie",
			height: 250,
			data: {labels: [],
            datasets: [
                {
                    values: [] 
                }
            ]},
		});
		this.update_pie_chart_data();
		
	}

	update_pie_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		}
		else{
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.productify_web_page.user_profile.get_linechart_data", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {	
				} else {
					this.piechart.update(r);
				}
			});
	}

	render_images() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
	
		frappe.xcall("productivity_next.productivity_next.page.productify_web_page.user_profile.get_images", {
			user: data,
			start_date: this.selected_start_date,
			end_date: this.selected_end_date,
		})
		.then((images) => {
			const imageContainer = this.main_section.find(".recent-activity-list");
			imageContainer.empty();
			images.forEach((screenshot) => {
				const imgElement = `<div class="col-md-3"><img src="${screenshot}" alt="User Activity Image" style="margin-bottom: 10px;"></div>`;
				imageContainer.append(imgElement);
			});
		});
	}
	
}

frappe.provide("frappe.ui");
frappe.ui.UserProfile = UserProfile;
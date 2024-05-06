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
            var startDate = new Date();
            startDate.setFullYear(startDate.getFullYear() - 1);
            var day = startDate.getDate().toString().padStart(2, '0');
            var month = (startDate.getMonth() + 1).toString().padStart(2, '0');
            var year = startDate.getFullYear();
            this.selected_start_date = year + '-' + month + '-' + day;
            this.selected_end_date = new Date().toJSON().slice(0, 10)
        }
        else{
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
		this.fetch_and_render_user_data();
		this.fetch_and_render_admin_data();	
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

	fetch_and_render_user_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		
		frappe.call({
			method: "productivity_next.productivity_next.page.admin_productify.admin_productify.get_user_data",
			args: {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			},
			callback: (r) => {
				if (r.message) {
					this.render_user_data(r.message);
					$(document).ready(function() {
						$('#logCountModalTrigger').click(function() {
							$('#logCountModal').modal('show');
						});
					});					
				}
			}
		});
	}
   
	render_user_data(data) {
		let employee_data;
		if (this.selected_employee != null) {
			employee_data = this.selected_employee;
		} else {
			employee_data = this.user_id;
		}
		// console.log(data.meetings)
		const container = this.main_section.find("#user-data-cards");
		container.empty();
		const sortedIdleTimes = data.total_idle_time_user.sort((a, b) => a.total_idle_time - b.total_idle_time);

		let wholedata = `
			<div class="title-area dynamic-spacing">
				<h4 class="card-title">Overall Data</h4>
			</div>
			
			<div class="row mt-1">
				<div class="col-md-3">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Total Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #08088A !important;"><b>${parseFloat(data.total_hours /60 / 60).toFixed(2)}</b><span style="font-size:12px">  Working Hours</span></div>
					</div>
				</div>
				<div class="col-md-3">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;"><b>${parseFloat((data.total_hours /60 / 60)/data.total_days).toFixed(2)}</b><span style="font-size:12px">  Working Hours Per Day</span></div>
					</div>
				</div>
				<div class="col-md-3">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Active Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${parseFloat(((data.total_hours /60 /60)/data.total_days)-((data.total_idle_time /60 /60)/data.total_days)).toFixed(2)}</b><span style="font-size:12px">  Active Hours Per Day</span></div>
					</div>
				</div>
				<div class="col-md-3">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Idle Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${parseFloat((data.total_idle_time /60 /60)/data.total_days).toFixed(2)}</b><span style="font-size:12px">  Idle Hours Per Day</span></div>
					</div>
				</div>
				
				
			</div>

			<div class="row mt-1">
				
				<div class="col-md-3">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Time On Calls Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #08088A !important;"><b>${parseFloat(((data.total_incoming_fincall_count+data.total_outgoing_fincall_count)/60/60)/data.total_days).toFixed(2)}</b><span style="font-size:12px"> Hours on Call Per Day </span></div>
					</div>
				</div>
				<div class="col-md-6">`;
				wholedata += `<div class="frappe-card dynamic-spacing custom-card row">
				<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Top Performers</h4>`;
				// Assuming sortedIdleTimes is an array and is available here
			for (let i = 0; i < Math.min(3, sortedIdleTimes.length); i++) {
				const app = sortedIdleTimes[i];
				wholedata += `<div class="col-md-12">
					<div class="frappe-card dynamic-spacing custom-card">
						<div class="number custom-number" style="font-size: 18px !important; color: #2E2E2E !important;">
							<b>${app.employee}</b>
							<span style="font-size:12px; align:right;"><b align="right">${parseFloat(app.total_idle_time / 3600).toFixed(2)}</b></span>
						</div>
					</div>
				</div>`;
			}

			wholedata += `</div>`;
			wholedata +=`
				</div>
				
				<div class="col-md-3">
					<div class="frappe-card dynamic-spacing custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Meetings Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b> ${parseFloat((data.total_meeting_duration /60 /60)/data.total_days).toFixed(2)}</b><span style="font-size:12px">  Hours In Meeting Per Day</span></div>
					</div>
				</div>
			</div>
			<div class="row mt-3">
				<div class="col-md-12">
				<div class="frappe-card dynamic-spacing custom-card">
				<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">All Employees</h4>`;
				wholedata += `<div class="row">`;
				// Assuming sortedIdleTimes is an array and is available here
sortedIdleTimes.forEach(app => {
    wholedata += `<div class="col-md-3">
        <div class="frappe-card dynamic-spacing custom-card">
            <div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;">
                <b>${app.employee}</b>
                <span style="font-size:12px; align:right;"><b align="right">${parseFloat(app.total_idle_time / 3600).toFixed(2)}</b></span>
            </div>
        </div>
    </div>`;
});

			wholedata += `</div>`;
		wholedata +=	`</div>
					</div>
				</div>`;
		container.append(wholedata);
        $(document).ready(function() {
            $(document).on('click', '.url-link', function(e) {
                e.preventDefault();
                
                // AJAX call to Python function
                frappe.call({
                    method: "productivity_next.productivity_next.page.admin_productify.admin_productify.get_url_brief_data",
                    args: {
                        url_data: $(this).data('url'),
                        user: employee_data,
                        start_date: self.selected_start_date,
                        end_date: self.selected_end_date,
                    },
                    callback: function(r) {
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
                // Assuming `data` is an object or string you want to display
                let displayContent = `
                <div class="row mt-3">
                    <div class="col-md-12">
                        <div class="frappe-card dynamic-spacing custom-card">
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
                        <td style="color:#FF4001">${parseFloat(app.duration/60/60).toFixed(2)} Hours</td>
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
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			},
			callback: (r) => {
				if (r.message) {
					this.render_admin_data(r.message);
					$(document).ready(function() {
						$('#logCountModalTrigger').click(function() {
							$('#logCountModal').modal('show');
						});
					});					
				}
			}
		});
	};
	render_admin_data(data) {
		let employee_data;
		if (this.selected_employee != null) {
			employee_data = this.selected_employee;
		} else {
			employee_data = this.user_id;
		}
		// console.log(data.meetings)
		const container = this.main_section.find("#user-activity-data");
		container.empty();
		let wholedata = ``;
		data.total_hours_data.forEach(app => {
			wholedata += `
				<tr>
					<td>${app.employee}</td>
					<td>${parseFloat(app.total_hours).toFixed(2)}</td>
				</tr>`;
		});
		container.append(wholedata);
	};
}
frappe.provide("frappe.ui");
frappe.ui.UserProfile = UserProfile;
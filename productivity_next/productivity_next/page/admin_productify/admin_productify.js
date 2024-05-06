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
		data.combined_employee_data.forEach(app => {
			wholedata += `
				<tr>
					<td align="center">
					<a href="https://website.finbyz.com/app/employee-productivity-dashboard?start_date=${encodeURIComponent(this.selected_start_date)}&end_date=${encodeURIComponent(this.selected_end_date)}&employee=${encodeURIComponent(app.employee)}" target="_blank">${app.employee}</a>
					</td>
					<td align="center">${parseFloat(app.total_hours).toFixed(2)}</td>
					<td align="center"></td>
					<td align="center"></td>
					<td align="center">${app.fincall_details.Incoming.count}</td>
					<td align="center">${app.fincall_details.Outgoing.count}</td>
					<td align="center">${app.fincall_details.Missed.count}</td>
					<td align="center">${app.fincall_details.Rejected.count}</td>
					<td align="center">${parseFloat(app.fincall_details.Incoming.total_duration/3600).toFixed(2)}</td>
					<td align="center">${parseFloat(app.fincall_details.Outgoing.total_duration/3600).toFixed(2)}</td>
					<td align="center">${app.meeting_details.meeting_count}</td>
					<td align="center">${parseFloat(app.meeting_details.total_meeting_duration/3600).toFixed(2)}</td>
				</tr>`;
		});
		container.append(wholedata);
	};
}
frappe.provide("frappe.ui");
frappe.ui.UserProfile = UserProfile;
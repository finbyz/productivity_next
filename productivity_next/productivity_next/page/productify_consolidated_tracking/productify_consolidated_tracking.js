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
    fetch_and_render_user_data() {	
    	frappe.call({
    		method: "productivity_next.productivity_next.page.productify_consolidated_tracking.productify_consolidated_tracking.get_number_card_data",
    		args: {
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
    };
    render_user_data(data) {
        let start_date_ = this.selected_start_date;
        let end_date_ = this.selected_end_date;
        console.log('Data received:', data);

        let total_hours = 0;
        let total_idle_hours = 0;
        // let total_meeting_hours = 0;
        // let total_meeting_count = 0;
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
        let total_days = 0;
        // let internal_meeting_hours = 0;
        // let internal_meeting_count = 0;
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
            total_days += employee.total_days || 0;
            domain_usage += employee.domain_used || 0;
        }
        // total_meeting_hours = data.combined_employee_data[0].meeting_admin_data[0].total_meeting_duration || 0;
        // total_meeting_count = data.combined_employee_data[0].meeting_admin_data[0].meeting_count || 0;
        // internal_meeting_hours = data.combined_employee_data[0].meetings_admin_data_internal[0].total_meeting_duration || 0;
        // internal_meeting_count = data.combined_employee_data[0].meetings_admin_data_internal[0].meeting_count || 0;

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
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;">${this.convertSecondsToTime(total_hours)}</div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Total Active Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;">${this.convertSecondsToTime((total_hours - total_idle_hours))}</div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Total Idle Hours</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;">${this.convertSecondsToTime(total_idle_hours)}</div>
					</div>
				</div>
			</div>
			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;">${this.convertSecondsToTime(total_hours / total_days || 1)}</div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Active Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;">${this.convertSecondsToTime((total_hours - total_idle_hours) / total_days || 1)}</div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Average Idle Hours Per Day</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;">${this.convertSecondsToTime(total_idle_hours / total_days || 1)}</div>
					</div>
				</div>
			</div>
			<div class="row mt-3">
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Meetings<span style="font-size:12px"> (External | Internal)</span></h4>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Time On Calls <span style="font-size:11px">(In Hours)(External)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;">
                        <svg fill="#62BA46" xmlns="http://www.w3.org/2000/svg" height="17px" viewBox="0 -960 960 960" width="17px"
                            fill="#e8eaed">
                            <path
                            d="M798-120q-125 0-247-54.5T329-329Q229-429 174.5-551T120-798q0-18 12-30t30-12h162q14 0 25 9.5t13 22.5l26 140q2 16-1 27t-11 19l-97 98q20 37 47.5 71.5T387-386q31 31 65 57.5t72 48.5l94-94q9-9 23.5-13.5T670-390l138 28q14 4 23 14.5t9 23.5v162q0 18-12 30t-30 12ZM520-520v-240h80v104l200-200 56 56-200 200h104v80H520Z" />
                        </svg>
                        <b>${this.convertSecondsToTime_(total_incoming_fincall_hours)}</b>
                        |
                        <svg fill="#62BA46" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1"
                            width="14px" height="14px" viewBox="0 0 1000 1000" xml:space="preserve">
                            <rect x="0" y="0" width="100%" height="100%" fill="#ffffff" />
                            <g transform="matrix(1.2267 0 0 1.2267 463.2126 527.828)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-480, 480)"
                                    d="M 798 -120 q -125 0 -247 -54.5 T 329 -329 Q 229 -429 174.5 -551 T 120 -798 q 0 -18 12 -30 t 30 -12 h 162 q 14 0 25 9.5 t 13 22.5 l 26 140 q 2 16 -1 27 t -11 19 l -97 98 q 20 37 47.5 71.5 T 387 -386 q 31 31 65 57.5 t 72 48.5 l 94 -94 q 9 -9 23.5 -13.5 T 670 -390 l 138 28 q 14 4 23 14.5 t 9 23.5 v 162 q 0 18 -12 30 t -30 12 Z" />
                            </g>
                            <g transform="matrix(0.025 0 0 0.025 500 500)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-460, 460)"
                                    d="m 216 -160 l -56 -56 l 464 -464 H 360 v -80 h 400 v 400 h -80 v -264 L 216 -160 Z" />
                                    </g>
                                    <g transform="matrix(0.6801 0 0 0.6801 646.7528 303.4615)">
                                    <path vector-effect="non-scaling-stroke" transform="translate(-460, 460)"
                                    d="m 216 -160 l -56 -56 l 464 -464 H 360 v -80 h 400 v 400 h -80 v -264 L 216 -160 Z" />
                                    </g>
                        </svg>
                        <b>${this.convertSecondsToTime_(total_outgoing_fincall_hours)}</b>
                        </div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Fincall Log Call Count<span style="font-size:11px">(External)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;">
                        <svg fill="#FF4001" xmlns="http://www.w3.org/2000/svg" height="17px" viewBox="0 -960 960 960" width="17px"
                            fill="#e8eaed">
                            <path
                                d="M798-120q-125 0-247-54.5T329-329Q229-429 174.5-551T120-798q0-18 12-30t30-12h162q14 0 25 9.5t13 22.5l26 140q2 16-1 27t-11 19l-97 98q20 37 47.5 71.5T387-386q31 31 65 57.5t72 48.5l94-94q9-9 23.5-13.5T670-390l138 28q14 4 23 14.5t9 23.5v162q0 18-12 30t-30 12ZM520-520v-240h80v104l200-200 56 56-200 200h104v80H520Z" />
                        </svg>
                        <b>${total_incoming_fincall_count}</b>
                        |
                        <svg fill="#FF4001" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1"
                            width="14px" height="14px" viewBox="0 0 1000 1000" xml:space="preserve">
                            <rect x="0" y="0" width="100%" height="100%" fill="#ffffff" />
                            <g transform="matrix(1.2267 0 0 1.2267 463.2126 527.828)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-480, 480)"
                                    d="M 798 -120 q -125 0 -247 -54.5 T 329 -329 Q 229 -429 174.5 -551 T 120 -798 q 0 -18 12 -30 t 30 -12 h 162 q 14 0 25 9.5 t 13 22.5 l 26 140 q 2 16 -1 27 t -11 19 l -97 98 q 20 37 47.5 71.5 T 387 -386 q 31 31 65 57.5 t 72 48.5 l 94 -94 q 9 -9 23.5 -13.5 T 670 -390 l 138 28 q 14 4 23 14.5 t 9 23.5 v 162 q 0 18 -12 30 t -30 12 Z" />
                            </g>
                            <g transform="matrix(0.025 0 0 0.025 500 500)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-460, 460)"
                                    d="m 216 -160 l -56 -56 l 464 -464 H 360 v -80 h 400 v 400 h -80 v -264 L 216 -160 Z" />
                            </g>
                            <g transform="matrix(0.6801 0 0 0.6801 646.7528 303.4615)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-460, 460)"
                                    d="m 216 -160 l -56 -56 l 464 -464 H 360 v -80 h 400 v 400 h -80 v -264 L 216 -160 Z" />
                            </g>
                        </svg>
                        <b> ${total_outgoing_fincall_count}</b>
                        |
                        <svg fill="#FF4001" xmlns="http://www.w3.org/2000/svg" height="17px" viewBox="0 -960 960 960" width="17px"
                            fill="#e8eaed">
                            <path
                                d="m136-144-92-90q-12-12-12-28t12-28q88-95 203-142.5T480-480q118 0 232.5 47.5T916-290q12 12 12 28t-12 28l-92 90q-11 11-25.5 12t-26.5-8l-116-88q-8-6-12-14t-4-18v-114q-38-12-78-19t-82-7q-42 0-82 7t-78 19v114q0 10-4 18t-12 14l-116 88q-12 9-26.5 8T136-144Zm342-362L280-704v104h-80v-240h240v80H336l141 141 226-226 57 57-282 282Z" />
                        </svg>
                        <b> ${total_missed_fincall_count}</b>
                        |
                        <svg fill="#FF4001" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1"
                            width="14px" height="14px" viewBox="0 0 1000 1000" xml:space="preserve">
                            <rect x="0" y="0" width="100%" height="100%" fill="#ffffff" />
                            <g transform="matrix(1.2626 0 0 1.2626 499.9905 499.9905)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-480, 480)"
                                    d="M 798 -120 q -125 0 -247 -54.5 T 329 -329 Q 229 -429 174.5 -551 T 120 -798 q 0 -18 12 -30 t 30 -12 h 162 q 14 0 25 9.5 t 13 22.5 l 26 140 q 2 16 -1 27 t -11 19 l -97 98 q 20 37 47.5 71.5 T 387 -386 q 31 31 65 57.5 t 72 48.5 l 94 -94 q 9 -9 23.5 -13.5 T 670 -390 l 138 28 q 14 4 23 14.5 t 9 23.5 v 162 q 0 18 -12 30 t -30 12 Z"
                                    stroke-linecap="round" />
                            </g>
                            <g transform="matrix(0.5193 0 0 0.5193 745.8186 234.0324)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-480, 480)"
                                    d="m 256 -200 l -56 -56 l 224 -224 l -224 -224 l 56 -56 l 224 224 l 224 -224 l 56 56 l -224 224 l 224 224 l -56 56 l -224 -224 l -224 224 Z"
                                    stroke-linecap="round" />
                            </g>
                        </svg>
                        <b> ${total_rejected_fincall_count}</b>
                        </div>
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
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Time On Calls <span style="font-size:11px">(In Hours)(Internal)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;">
                        <svg fill="#62BA46" xmlns="http://www.w3.org/2000/svg" height="17px" viewBox="0 -960 960 960" width="17px"
                            fill="#e8eaed">
                            <path
                                d="M798-120q-125 0-247-54.5T329-329Q229-429 174.5-551T120-798q0-18 12-30t30-12h162q14 0 25 9.5t13 22.5l26 140q2 16-1 27t-11 19l-97 98q20 37 47.5 71.5T387-386q31 31 65 57.5t72 48.5l94-94q9-9 23.5-13.5T670-390l138 28q14 4 23 14.5t9 23.5v162q0 18-12 30t-30 12ZM520-520v-240h80v104l200-200 56 56-200 200h104v80H520Z" />
                        </svg>
                        <b>${this.convertSecondsToTime_(internal_total_incoming_fincall_hours)}</b>
                        | 
                        <svg fill="#62BA46" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1"
                            width="14px" height="14px" viewBox="0 0 1000 1000" xml:space="preserve">
                            <rect x="0" y="0" width="100%" height="100%" fill="#ffffff" />
                            <g transform="matrix(1.2267 0 0 1.2267 463.2126 527.828)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-480, 480)"
                                    d="M 798 -120 q -125 0 -247 -54.5 T 329 -329 Q 229 -429 174.5 -551 T 120 -798 q 0 -18 12 -30 t 30 -12 h 162 q 14 0 25 9.5 t 13 22.5 l 26 140 q 2 16 -1 27 t -11 19 l -97 98 q 20 37 47.5 71.5 T 387 -386 q 31 31 65 57.5 t 72 48.5 l 94 -94 q 9 -9 23.5 -13.5 T 670 -390 l 138 28 q 14 4 23 14.5 t 9 23.5 v 162 q 0 18 -12 30 t -30 12 Z" />
                            </g>
                            <g transform="matrix(0.025 0 0 0.025 500 500)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-460, 460)"
                                    d="m 216 -160 l -56 -56 l 464 -464 H 360 v -80 h 400 v 400 h -80 v -264 L 216 -160 Z" />
                            </g>
                            <g transform="matrix(0.6801 0 0 0.6801 646.7528 303.4615)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-460, 460)"
                                    d="m 216 -160 l -56 -56 l 464 -464 H 360 v -80 h 400 v 400 h -80 v -264 L 216 -160 Z" />
                            </g>
                        </svg>
                        <b>${this.convertSecondsToTime_(internal_total_outgoing_fincall_hours)}</b>
                        </div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Fincall Log Call Count<span style="font-size:11px">(Internal)</span></h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;">

                        <svg fill="#FF4001" xmlns="http://www.w3.org/2000/svg" height="17px" viewBox="0 -960 960 960" width="17px"
                            fill="#e8eaed">
                            <path
                                d="M798-120q-125 0-247-54.5T329-329Q229-429 174.5-551T120-798q0-18 12-30t30-12h162q14 0 25 9.5t13 22.5l26 140q2 16-1 27t-11 19l-97 98q20 37 47.5 71.5T387-386q31 31 65 57.5t72 48.5l94-94q9-9 23.5-13.5T670-390l138 28q14 4 23 14.5t9 23.5v162q0 18-12 30t-30 12ZM520-520v-240h80v104l200-200 56 56-200 200h104v80H520Z" />
                        </svg>
                        <b>${internal_incoming_fincall_count}</b>
                        |
                        <svg fill="#FF4001" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1"
                            width="14px" height="14px" viewBox="0 0 1000 1000" xml:space="preserve">
                            <rect x="0" y="0" width="100%" height="100%" fill="#ffffff" />
                            <g transform="matrix(1.2267 0 0 1.2267 463.2126 527.828)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-480, 480)"
                                    d="M 798 -120 q -125 0 -247 -54.5 T 329 -329 Q 229 -429 174.5 -551 T 120 -798 q 0 -18 12 -30 t 30 -12 h 162 q 14 0 25 9.5 t 13 22.5 l 26 140 q 2 16 -1 27 t -11 19 l -97 98 q 20 37 47.5 71.5 T 387 -386 q 31 31 65 57.5 t 72 48.5 l 94 -94 q 9 -9 23.5 -13.5 T 670 -390 l 138 28 q 14 4 23 14.5 t 9 23.5 v 162 q 0 18 -12 30 t -30 12 Z" />
                            </g>
                            <g transform="matrix(0.025 0 0 0.025 500 500)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-460, 460)"
                                    d="m 216 -160 l -56 -56 l 464 -464 H 360 v -80 h 400 v 400 h -80 v -264 L 216 -160 Z" />
                            </g>
                            <g transform="matrix(0.6801 0 0 0.6801 646.7528 303.4615)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-460, 460)"
                                    d="m 216 -160 l -56 -56 l 464 -464 H 360 v -80 h 400 v 400 h -80 v -264 L 216 -160 Z" />
                            </g>
                        </svg>
                        <b> ${internal_outgoing_fincall_count}</b>
                        |
                        <svg fill="#FF4001" xmlns="http://www.w3.org/2000/svg" height="17px" viewBox="0 -960 960 960" width="17px"
                            fill="#e8eaed">
                            <path
                                d="m136-144-92-90q-12-12-12-28t12-28q88-95 203-142.5T480-480q118 0 232.5 47.5T916-290q12 12 12 28t-12 28l-92 90q-11 11-25.5 12t-26.5-8l-116-88q-8-6-12-14t-4-18v-114q-38-12-78-19t-82-7q-42 0-82 7t-78 19v114q0 10-4 18t-12 14l-116 88q-12 9-26.5 8T136-144Zm342-362L280-704v104h-80v-240h240v80H336l141 141 226-226 57 57-282 282Z" />
                        </svg>
                        <b> ${internal_missed_fincall_count}</b>
                        |
                        <svg fill="#FF4001" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1"
                            width="14px" height="14px" viewBox="0 0 1000 1000" xml:space="preserve">
                            <rect x="0" y="0" width="100%" height="100%" fill="#ffffff" />
                            <g transform="matrix(1.2626 0 0 1.2626 499.9905 499.9905)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-480, 480)"
                                    d="M 798 -120 q -125 0 -247 -54.5 T 329 -329 Q 229 -429 174.5 -551 T 120 -798 q 0 -18 12 -30 t 30 -12 h 162 q 14 0 25 9.5 t 13 22.5 l 26 140 q 2 16 -1 27 t -11 19 l -97 98 q 20 37 47.5 71.5 T 387 -386 q 31 31 65 57.5 t 72 48.5 l 94 -94 q 9 -9 23.5 -13.5 T 670 -390 l 138 28 q 14 4 23 14.5 t 9 23.5 v 162 q 0 18 -12 30 t -30 12 Z"
                                    stroke-linecap="round" />
                            </g>
                            <g transform="matrix(0.5193 0 0 0.5193 745.8186 234.0324)">
                                <path vector-effect="non-scaling-stroke" transform="translate(-480, 480)"
                                    d="m 256 -200 l -56 -56 l 224 -224 l -224 -224 l 56 -56 l 224 224 l 224 -224 l 56 56 l -224 224 l 224 224 l -56 56 l -224 -224 l -224 224 Z"
                                    stroke-linecap="round" />
                            </g>
                        </svg>
                        <b> ${internal_rejected_fincall_count}</b>
                        
                        </div>
					</div>
				</div>
			</div>
			<div class="row mt-3">
			<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Domain Usage Count</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #00A6E0 !important;">
							<b>${domain_usage}</b><span style="font-size:12px"> Domains Accessed</span>
						</div>
					</div>
				</div>
			<div class="col-md-4">
					<div class="frappe-card custom-card">
						<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Documents Accessed</h4>
						<div class="number custom-number" style="font-size: 18px !important; color: #62BA46 !important;"><b>${total_unique_doc}</b><span style="font-size:12px"> Documents Created or Modified</span></div>
					</div>
				</div>
			<div class="col-md-4">
					<div class="frappe-card custom-card">
					<h4 class="custom-title" style="font-size: 14px !important; color: #333333;">Version Log Count</h4>
					<div class="number custom-number" style="font-size: 18px !important; color: #FF4001 !important;"><b>${total_version_count}</b><span style="font-size:12px"> Interactions</span></div>

					</div>
				</div>
			</div>
			<div class="row mt-3">
			<div class="col-md-6">
			<div class="frappe-card  custom-card">
				<h4 class="custom-title p-3" style="font-size: 14px !important; color: #333333;" align="center">Applications Used</h4>
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
				<h4 class="custom-title p-3" style="font-size: 14px !important; color: #333333;" align="center">Domains Used</h4>
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
        $(document).ready(function () {
            $(document).on('click', '.url-link', function (e) {
                e.preventDefault();

                // AJAX call to Python function
                frappe.call({
                    method: "productivity_next.productivity_next.page.productify_consolidated_tracking.productify_consolidated_tracking.get_url_brief_data",
                    args: {
                        url_data: $(this).data('url'),
                        start_date: start_date_,
                        end_date: end_date_,
                    },
                    callback: function (r) {
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
                            callback: function (r) {
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
								<h4 class="custom-title p-3" style="font-size: 14px !important; color: #333333;" align="center">Top 10 Domain's Used</h4>
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

        $(document).ready(function () {
            $(document).on('click', '.app-link', function (e) {
                e.preventDefault();

                // AJAX call to Python function
                frappe.call({
                    method: "productivity_next.productivity_next.page.productify_consolidated_tracking.productify_consolidated_tracking.get_app_brief_data",
                    args: {
                        app_data: $(this).data('url'),
                        start_date: start_date_,
                        end_date: end_date_,
                    },
                    callback: function (r) {
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
                            callback: function (r) {
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
								<h4 class="custom-title p-3" style="font-size: 14px !important; color: #333333;" align="center">Top 10 Application's Used</h4>
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

        return `${hours}.${minutes}`;
    }

    render_line_chart() {
        this.update_line_chart_data();

    }

    update_line_chart_data() {
        let data;
        if (this.selected_employee != null) {
            data = this.selected_employee;
        }
        else {
            data = this.user_id;
        }
        frappe
            .xcall("productivity_next.productivity_next.page.productify_consolidated_tracking.productify_consolidated_tracking.get_linechart_data", {
                user: "Administrator",
                start_date: this.selected_start_date,
                end_date: this.selected_end_date,
            })
            .then((r) => {
                if (r.labels.length === 0) {
                    // No data to show
                } else {
                    this.linechart = new frappe.Chart(".performance-line-chart", {
                        type: "bar",
                        height: 250,
                        colors: ["#fc4f51", "#78d6ff", "#AA0078", "#7575ff"],
                        data: {
                            labels: r.labels,
                            datasets: r.datasets
                        },
                        baroptions: {
                            stacked: true
                        },
                    });
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
            method: "productivity_next.productivity_next.page.productify_consolidated_tracking.productify_consolidated_tracking.get_admin_data",
            args: {
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
                internalIncomingFincallCount: internalEmployeeFincallData.incoming_fincall_count || 0,
                internalOutgoingFincallCount: internalEmployeeFincallData.outgoing_fincall_count || 0,
                internalMissedFincallCount: internalEmployeeFincallData.missed_fincall_count || 0,
                internalRejectedFincallCount: internalEmployeeFincallData.rejected_fincall_count || 0,
                internalTotalIncomingDuration: internalEmployeeFincallData.total_incoming_duration || 0,
                internalTotalOutgoingDuration: internalEmployeeFincallData.total_outgoing_duration || 0,
                totalDays: data.total_days[employee] || 1,
                meetingCount: meetingEmployeeData.count || 0,
                meetingDuration : meetingEmployeeData.duration || 0,
            };
        });
        
        const employeeDataArray = await Promise.all(fetchPromises);
        
        employeeDataArray.sort((a, b) => calculateEffectiveHours(a.totalHours, a.totalIdleTime, a.totalDays) - calculateEffectiveHours(b.totalHours, b.totalIdleTime, b.totalDays));
        
        let count = 1;
        let inactive_count = 1;
        console.log('employeeDataArray:', employeeDataArray);
        employeeDataArray.forEach(app => {
            if (app.totalHours > 0) {
                const employeeUrl = `${baseUrl}Productify Employee Tracking?start_date=${encodeURIComponent(this.selected_start_date)}&end_date=${encodeURIComponent(this.selected_end_date)}&employee=${encodeURIComponent(app.employee)}`;
                wholedata += `
                    <tr>
                        <td align="left">
                            <a href="${employeeUrl}" target="_blank" style="color:#6420AA;">${count}. ${app.employeeName}</a>
                        </td>
                        <td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_(app.totalHours)}</td>
                        <td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_((app.totalHours) - (app.totalIdleTime))}</td>
                        <td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_(app.totalIdleTime)}</td>
                        <td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_(((app.totalHours) / app.totalDays) - ((app.totalIdleTime) / app.totalDays))}</td>
                        <td align="center" style="color:#62BA46;">${app.incomingFincallCount}/${app.internalIncomingFincallCount}</td>
                        <td align="center" style="color:#62BA46;">${app.outgoingFincallCount}/${app.internalOutgoingFincallCount}</td>
                        <td align="center" style="color:#62BA46;">${app.missedFincallCount}/${app.internalMissedFincallCount}</td>
                        <td align="center" style="color:#62BA46;">${app.missedFincallCount}/${app.internalRejectedFincallCount}</td>
                        <td align="center" style="color:#FF4001;">${this.convertSecondsToTime_(app.totalIncomingDuration)}/${this.convertSecondsToTime_(app.internalTotalIncomingDuration)}</td>
                        <td align="center" style="color:#FF4001;">${this.convertSecondsToTime_(app.totalOutgoingDuration)}/${this.convertSecondsToTime_(app.internalTotalOutgoingDuration)}</td>
                        <td align="center" style="color:#6420AA;">${app.meetingCount}</td>
                        <td align="center" style="color:#6420AA;">${this.convertSecondsToTime_(app.meetingDuration)}</td>
                    </tr>`;
                count++;
            }
        });

        wholedata += `<tr><td colspan="12"><strong>Inactive Users</strong></td></tr>`;
        employeeDataArray.forEach(app => {
            if (app.total_hours <= 0) {
                const employeeUrl = `${baseUrl}Productify Employee Tracking?start_date=${encodeURIComponent(this.selected_start_date)}&end_date=${encodeURIComponent(this.selected_end_date)}&employee=${encodeURIComponent(app.employee)}`;
                wholedata += `
                    <tr>
                        <td align="left">
                            <a href="${employeeUrl}" target="_blank" style="color:#6420AA;">${inactive_count}. ${app.employeeName}</a>
                        </td>
                        <td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_(app.total_hours)}</td>
                        <td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_((app.total_hours) - (app.total_idle_time))}</td>
                        <td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_(app.total_idle_time)}</td>
                        <td align="center" style="color:#00A6E0;">0.0</td>
                        <td align="center" style="color:#62BA46;">${app.incoming_fincall_count}/${app.internal_incoming_fincall_count}</td>
                        <td align="center" style="color:#62BA46;">${app.outgoing_fincall_count}/${app.internal_outgoing_fincall_count}</td>
                        <td align="center" style="color:#62BA46;">${app.missed_fincall_count}/${app.internal_missed_fincall_count}</td>
                        <td align="center" style="color:#62BA46;">${app.rejected_fincall_count}/${app.internal_rejected_fincall_count}</td>
                        <td align="center" style="color:#FF4001;">${this.convertSecondsToTime_(app.total_incoming_fincall_count)}/${this.convertSecondsToTime_(app.internal_total_incoming_fincall_count)}</td>
                        <td align="center" style="color:#FF4001;">${this.convertSecondsToTime_(app.total_outgoing_fincall_count)}/${this.convertSecondsToTime_(app.internal_total_outgoing_fincall_count)}</td>
                        <td align="center" style="color:#6420AA;">${app.total_meeting_count}</td>
                        <td align="center" style="color:#6420AA;">${this.convertSecondsToTime_(app.total_meeting_duration)}</td>
                    </tr>`;
                inactive_count++;
            }
        });
        container.append(wholedata);
    };

}
frappe.provide("frappe.ui");
frappe.ui.UserProfile = UserProfile;
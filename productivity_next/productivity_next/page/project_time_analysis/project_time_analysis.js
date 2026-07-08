frappe.pages["project-time-analysis"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Project Time Analysis",
		single_column: true,
	});

	new ProjectTimeHierarchy(page);
};

class ProjectTimeHierarchy {
	constructor(page) {
		this.page = page;
		this.is_admin = false;
		this.tree = [];
		this.navigation_candidates = [];
		this.columns = [];
		this.data_cache = {};
		this.sort_state = {};
		this.hidden_columns = new Set();
		this.quick_filter_states = {
			resource_based_project: 0,
			hourly_based_project: 0,
			show_daily_data: 0,
			is_internal_project: 0,
			show_employee: 1,
			show_deployment_rate: 1
		};
		this.search_term = '';
		this.current_view = 'hierarchy';
		this.selected_employee = null; // Store selected employee to preserve selection when switching views
		this.bookmarked_employees = this.load_bookmarks();
		this.recent_views = this.load_recent_views();
		this.compare_list = [];
		this.alerts_threshold = {
			low_utilization: 50,
			high_utilization: 90,
			no_activity_days: 3
		};
		
		this.init();
	}

	async init() {
		this.setup_filters();
		this.setup_body();
		this.setup_styles();
		await this.load_columns();
		await this.load_tree();
	}

	// =================================================================
	// FILTERS
	// =================================================================
	setup_filters() {
		const today = frappe.datetime.get_today();

		// Committed date filter values actually used by data loads.
		// These only update when the user explicitly applies the filters
		// (via the existing Refresh button) — not on every keystroke/change
		// of the date fields below. This mirrors the CRM Insight page's
		// "pick values, then Apply" logic, while keeping the exact same
		// field UI (Period / From Date / To Date) as before.
		this.date_filters = {
			from_date: today,
			to_date: today,
		};

		// Date Presets for quick selection
		this.date_preset_field = this.page.add_field({
			fieldname: "date_preset",
			label: "",
			fieldtype: "Select",
			options: [
				"Today",
				"Yesterday",
				"This Week",
				"This Month",
				"Last Week",
				"Last Month",
				"Last Quarter"
			],
			default: "Today",
			change: () => {
				// Only updates the From/To fields on screen; does NOT
				// refresh data. The user still needs to hit Refresh
				// (or change project/checkbox filters, which do apply
				// immediately) to load data with the new date range.
				const preset = this.date_preset_field.get_value();
				this.set_date_preset(preset);
			}
		});

		this.from_date_field = this.page.add_field({
			fieldname: "from_date",
			label: "",
			fieldtype: "Date",
			default: today,
			reqd: 1,
			change: () => {
				// Manual edits no longer use a "Custom" preset option.
			},
		});

		this.to_date_field = this.page.add_field({
			fieldname: "to_date",
			label: "",
			fieldtype: "Date",
			default: today,
			reqd: 1,
			change: () => {
				// Manual edits no longer use a "Custom" preset option.
			},
		});

		this.project_field = this.page.add_field({
			fieldname: "project",
			label: "Project",
			fieldtype: "Link",
			options: "Project",
			change: () => this.refresh_all(),
		});

		// this.resource_based_field = this.page.add_field({
		// 	fieldname: "resource_based_project",
		// 	label: "Resource Based Project",
		// 	fieldtype: "Check",
		// 	change: () => this.refresh_all(),
		// });

		// this.hourly_based_field = this.page.add_field({
		// 	fieldname: "hourly_based_project",
		// 	label: "Hourly Based Project",
		// 	fieldtype: "Check",
		// 	change: () => this.refresh_all(),
		// });

		// this.show_daily_data_field = this.page.add_field({
		// 	fieldname: "show_daily_data",
		// 	label: "Show Daily Data",
		// 	fieldtype: "Check",
		// 	change: () => this.refresh_all(),
		// });

		// this.is_internal_field = this.page.add_field({
		// 	fieldname: "is_internal_project",
		// 	label: "Internal Project",
		// 	fieldtype: "Check",
		// 	change: () => this.refresh_all(),
		// });

		this.show_employee_field = this.page.add_field({
			fieldname: "show_employee",
			label: "Show Employee Details",
			default: 1,
			fieldtype: "Check",
			change: () => this.refresh_all(),
		});

		this.deployment_field = this.page.add_field({
			fieldname: "show_deployment_rate",
			label: "Show Deployment Rate",
			fieldtype: "Check",
			default: 1,
			change: () => {
				this.hidden_columns.clear();
				this.load_columns(() => this.refresh_all());
			},
		});

		// Admin navigation
		this.admin_filter_field = this.page.add_field({
			fieldname: "jump_to_team",
			label: "Quick Navigation",
			fieldtype: "Link",
			options: "Employee",
			placeholder: "Jump to any employee...",
			get_query: () => {
				const employee_ids = this.navigation_candidates || [];
				if (!employee_ids.length) {
					return { filters: { name: ["in", [""]] } };
				}
				return { filters: { status: "Active", name: ["in", employee_ids] } };
			},
			change: () => {
				const emp = this.admin_filter_field.get_value();
				if (emp) {
					this.scroll_to_employee(emp);
					this.admin_filter_field.set_value('');
				}
			},
		});
		this.admin_filter_field.$wrapper.hide();

		// Primary Action — this is the explicit "Apply" trigger for the
		// date filters (as well as a general refresh).
		this.page.set_primary_action("Refresh", () => this.apply_filters());
		
		// Menu Items for additional features
		// this.page.add_menu_item("Dashboard Overview", () => this.show_dashboard());
		// this.page.add_menu_item("All Employees Report", () => this.show_all_employees());
		// this.page.add_menu_item("Compare Employees", () => this.show_compare_dialog());
		// this.page.add_menu_item("Bookmarks", () => this.show_bookmarks());
		this.page.add_menu_item("Export CSV", () => this.export_csv());
		// this.page.add_menu_item("Copy Summary", () => this.copy_summary());
		// this.page.add_menu_item("Expand All", () => this.expand_all(true));
		// this.page.add_menu_item("Collapse All", () => this.expand_all(false));
		// this.page.add_menu_item("Pick Columns", () => this.open_pick_columns_dialog());
	}

	set_date_preset(preset) {
		const today = frappe.datetime.get_today();
		let from_date, to_date;

		switch(preset) {
			case "Today":
				from_date = today;
				to_date = today;
				break;

			case "Yesterday":
				from_date = frappe.datetime.add_days(today, -1);
				to_date = frappe.datetime.add_days(today, -1);
				break;
			case "This Week":
				from_date = frappe.datetime.week_start(today);
				to_date = frappe.datetime.week_end(today);
				break;
			case "This Month":
				from_date = frappe.datetime.month_start(today);
				to_date = frappe.datetime.month_end(today);
				break;
			case "Last Week":
				from_date = frappe.datetime.add_days(today, -7);
				to_date = today;
				break;
			case "Last Month":
				from_date = frappe.datetime.add_days(today, -30);
				to_date = today;
				break;
			case "Last Quarter":
				from_date = frappe.datetime.add_months(today, -3);
				to_date = today;
				break;
			default:
				return;
		}

		this.from_date_field.set_value(from_date);
		this.to_date_field.set_value(to_date);
	}

	// Commits the current From/To field values into this.date_filters
	// and then refreshes. This is the single point where date changes
	// actually take effect, matching the "select, then Apply" logic of
	// the reference page — triggered here by the existing Refresh button
	// rather than any new UI element.
	apply_filters() {
		this.date_filters.from_date = this.from_date_field.get_value();
		this.date_filters.to_date = this.to_date_field.get_value();
		this.refresh_all();
	}

	get_from_date() {
		return this.date_filters.from_date;
	}

	get_to_date() {
		return this.date_filters.to_date;
	}

	get_report_filters() {
		return {
			project: this.project_field.get_value() || null,
			// resource_based_project: this.resource_based_field.get_value() ? 1 : 0,
			// hourly_based_project: this.hourly_based_field.get_value() ? 1 : 0,
			// show_daily_data: this.show_daily_data_field.get_value() ? 1 : 0,
			// is_internal_project: this.is_internal_field.get_value() ? 1 : 0,
			show_employee: this.show_employee_field.get_value() ? 1 : 0,
			show_deployment_rate: this.deployment_field.get_value() ? 1 : 0,
		};
	}

	// =================================================================
	// BODY SETUP
	// =================================================================
	setup_body() {
		this.$main_container = $(`
			<div class="pta-main-wrapper">
				<!-- Alert Bar for important notifications -->
				<div class="pta-alert-bar" style="display:none;" id="pta-alerts"></div>
				
				<!-- Quick Stats Overview -->
				<div class="pta-quick-stats" id="pta-quick-stats"></div>
				
				<!-- Toolbar -->
				<div class="pta-toolbar">
					<div class="pta-toolbar-left">
						<div class="pta-search-box">
							<input type="text" class="pta-search-input" placeholder="Search team members...">
						</div>
						<div class="pta-view-tabs">
							<button class="pta-tab active" data-view="hierarchy">Team Hierarchy</button>
							<button class="pta-tab" data-view="all_employees">All Employees</button>
							<button class="pta-tab" data-view="dashboard">Dashboard</button>
						</div>
					</div>
					<div class="pta-toolbar-right">
						
						<button class="btn btn-default btn-xs pta-compare-btn" title="Compare employees">
							Compare
						</button>
						
						<button class="btn btn-default btn-xs pta-expand-all">Expand All</button>
						<button class="btn btn-default btn-xs pta-collapse-all">Collapse All</button>
						
					</div>
				</div>

				<!-- Main Content -->
				<div class="pta-content-area">
					<div class="pta-tree-panel">
						<div class="pta-tree-header">
							<h4>Team Hierarchy</h4>
							
						</div>
						<div class="pta-tree-inner"></div>
					</div>
					<div class="pta-data-panel">
						<div class="pta-data-toolbar">
							<div class="pta-data-title"></div>
							<div class="pta-data-actions">
								
							</div>
						</div>
						<div class="pta-data-inner"></div>
					</div>
				</div>

				<!-- Compare Panel (hidden by default) -->
				<div class="pta-compare-panel" id="pta-compare-panel">
					<div class="pta-compare-header">
						<h5>Compare Employees</h5>
						<div>
							<button class="btn btn-xs btn-default pta-compare-clear">Clear All</button>
							<button class="btn btn-xs btn-primary pta-compare-run">Run Comparison</button>
							<button class="btn btn-xs btn-default pta-compare-close">Close</button>
						</div>
					</div>
					<div class="pta-compare-chips" id="pta-compare-chips"></div>
					<div class="pta-compare-results" id="pta-compare-results"></div>
				</div>
			</div>
		`).appendTo(this.page.main);

		this.bind_events();
	}

	bind_events() {
		// Search with debounce
		let searchTimeout;
		this.$main_container.find('.pta-search-input').on('input', (e) => {
			clearTimeout(searchTimeout);
			searchTimeout = setTimeout(() => {
				this.search_term = e.target.value.toLowerCase();
				if (this.current_view === 'hierarchy') {
					this.render_tree();
				} else if (this.current_view === 'all_employees') {
					this.render_all_employees();
				}
			}, 300);
		});

		// View tabs
		this.$main_container.find('.pta-tab').on('click', (e) => {
			const view = $(e.currentTarget).data('view');
			this.switch_view(view);
		});

		// Toolbar buttons
		this.$main_container.find('.pta-expand-all').on('click', () => this.expand_all(true));
		this.$main_container.find('.pta-collapse-all').on('click', () => this.expand_all(false));
		this.$main_container.find('.pta-pick-columns').on('click', () => this.open_pick_columns_dialog());
		this.$main_container.find('.pta-bookmark-btn').on('click', () => this.bookmark_current_view());
		this.$main_container.find('.pta-compare-btn').on('click', () => this.toggle_compare_panel());
		this.$main_container.find('.pta-export-btn').on('click', () => this.export_csv());
		this.$main_container.find('.pta-copy-btn').on('click', () => this.copy_current_data());
		this.$main_container.find('.pta-refresh-data-btn').on('click', () => this.refresh_current_view());
		this.$main_container.find('.pta-bookmarked-btn').on('click', () => this.show_bookmarks());
		this.$main_container.find('.pta-pin-btn').on('click', function() {
			$(this).toggleClass('active');
			frappe.show_alert({
				message: $(this).hasClass('active') ? 'View pinned' : 'View unpinned',
				indicator: 'blue'
			});
		});

		// Compare panel
		this.$main_container.find('.pta-compare-clear').on('click', () => this.clear_compare_list());
		this.$main_container.find('.pta-compare-run').on('click', () => this.run_comparison());
		this.$main_container.find('.pta-compare-close').on('click', () => this.toggle_compare_panel(false));
	}

	setup_styles() {
		frappe.dom.set_style(`
			.pta-main-wrapper {
				display: flex;
				flex-direction: column;
				height: calc(100vh - 200px);
				background: linear-gradient(135deg, #f5f7fb 0%, #f0f2f7 100%);
			}

			/* Alert Bar */
			.pta-alert-bar {
				padding: 12px 20px;
				display: flex;
				gap: 12px;
				flex-wrap: wrap;
			}
			.pta-alert {
				padding: 8px 14px;
				border-radius: 8px;
				font-size: 12px;
				font-weight: 600;
				cursor: pointer;
				display: flex;
				align-items: center;
				gap: 8px;
				transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
				box-shadow: 0 2px 8px rgba(0,0,0,0.08);
			}
			.pta-alert:hover {
				transform: translateY(-2px);
				box-shadow: 0 4px 12px rgba(0,0,0,0.12);
			}
			.pta-alert.warning {
				background: linear-gradient(135deg, #fff3cd, #ffe9b1);
				color: #8d6e1e;
				border: 1px solid #ffc107;
			}
			.pta-alert.danger {
				background: linear-gradient(135deg, #f8d7da, #f5c2c7);
				color: #842029;
				border: 1px solid #dc3545;
			}
			.pta-alert.info {
				background: linear-gradient(135deg, #d1ecf1, #b6e4ee);
				color: #055160;
				border: 1px solid #17a2b8;
			}
			.pta-alert.success {
				background: linear-gradient(135deg, #d4edda, #c3e6cb);
				color: #1e5631;
				border: 1px solid #28a745;
			}

			/* Quick Stats */
			.pta-quick-stats {
				display: grid;
				grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
				gap: 14px;
				padding: 16px 20px;
				background: transparent;
				border-bottom: none;
			}
			.pta-quick-stat {
				display: flex;
				align-items: center;
				gap: 14px;
				padding: 16px 18px;
				border-radius: 12px;
				background: rgba(255, 255, 255, 0.95);
				border: 1px solid rgba(224, 229, 236, 0.8);
				box-shadow: 0 4px 15px rgba(0,0,0,0.08);
				transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
			}
			.pta-quick-stat:hover {
				transform: translateY(-4px);
				box-shadow: 0 8px 25px rgba(0,0,0,0.12);
				background: #fff;
			}
			.pta-quick-stat-icon {
				width: 44px;
				height: 44px;
				border-radius: 12px;
				display: flex;
				align-items: center;
				justify-content: center;
				font-weight: 700;
				font-size: 18px;
				color: #fff;
				flex-shrink: 0;
				box-shadow: 0 4px 12px rgba(0,0,0,0.15);
			}
			.pta-quick-stat-icon.blue { background: linear-gradient(135deg, #667eea, #764ba2); }
			.pta-quick-stat-icon.green { background: linear-gradient(135deg, #34d399, #10b981); }
			.pta-quick-stat-icon.orange { background: linear-gradient(135deg, #f97316, #fb923c); }
			.pta-quick-stat-icon.red { background: linear-gradient(135deg, #ef4444, #dc2626); }
			.pta-quick-stat-info { flex: 1; }
			.pta-quick-stat-value { font-size: 22px; font-weight: 800; color: #1f2937; line-height: 1.2; letter-spacing: -0.5px; }
			.pta-quick-stat-label { font-size: 11px; color: #6b7280; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }

			/* Toolbar */
			.pta-toolbar {
				display: flex;
				justify-content: space-between;
				align-items: center;
				padding: 12px 20px;
				background: rgba(255, 255, 255, 0.95);
				border-bottom: 1px solid rgba(224, 229, 236, 0.5);
				flex-shrink: 0;
				backdrop-filter: blur(10px);
			}
			.pta-toolbar-left {
				display: flex;
				align-items: center;
				gap: 18px;
			}
			.pta-search-box input {
				padding: 8px 14px;
				border: 1px solid #d1d8dd;
				border-radius: 8px;
				font-size: 13px;
				width: 240px;
				transition: all 0.2s;
				background: #fff;
				box-shadow: 0 2px 4px rgba(0,0,0,0.04);
			}
			.pta-search-box input:focus {
				outline: none;
				border-color: #667eea;
				box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
				transform: scale(1.01);
			}
			.pta-view-tabs {
				display: flex;
				gap: 4px;
				background: #f0f2f7;
				border-radius: 10px;
				padding: 4px;
				box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
			}
			.pta-tab {
				padding: 6px 16px;
				border: none;
				background: transparent;
				border-radius: 8px;
				font-size: 12px;
				font-weight: 600;
				cursor: pointer;
				color: #6b7280;
				transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
			}
			.pta-tab.active {
				background: linear-gradient(135deg, #667eea, #764ba2);
				color: #fff;
				box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
				transform: scale(1.02);
			}
			.pta-tab:hover:not(.active) {
				color: #667eea;
				background: rgba(102, 126, 234, 0.05);
			}
			.pta-toolbar-right {
				display: flex;
				gap: 8px;
			}

			/* Content Area */
			.pta-content-area {
				display: flex;
				flex: 1;
				overflow: hidden;
				gap: 12px;
				padding: 12px;
			}
			.pta-tree-panel {
				width: 320px;
				flex-shrink: 0;
				background: rgba(255, 255, 255, 0.95);
				border-right: none;
				display: flex;
				flex-direction: column;
				border-radius: 12px;
				box-shadow: 0 4px 15px rgba(0,0,0,0.08);
				overflow: hidden;
			}
			.pta-tree-header {
				display: flex;
				justify-content: space-between;
				align-items: center;
				padding: 14px 16px;
				border-bottom: 1px solid rgba(224, 229, 236, 0.5);
				background: linear-gradient(135deg, #f8fafc, #f0f2f7);
			}
			.pta-tree-header h4 {
				margin: 0;
				font-size: 14px;
				font-weight: 700;
				color: #1f2937;
				letter-spacing: -0.3px;
			}
			.pta-tree-inner {
				flex: 1;
				overflow-y: auto;
				padding: 10px;
			}
			.pta-data-panel {
				flex: 1;
				background: rgba(255, 255, 255, 0.95);
				display: flex;
				flex-direction: column;
				overflow: hidden;
				border-radius: 12px;
				box-shadow: 0 4px 15px rgba(0,0,0,0.08);
			}
			.pta-data-toolbar {
				display: flex;
				justify-content: space-between;
				align-items: center;
				padding: 14px 20px;
				border-bottom: 1px solid rgba(224, 229, 236, 0.5);
				background: linear-gradient(135deg, #f8fafc, #f0f2f7);
			}
			.pta-data-title {
				font-size: 15px;
				font-weight: 700;
				color: #1f2937;
				letter-spacing: -0.3px;
			}
			.pta-data-inner {
				flex: 1;
				overflow: auto;
				padding: 18px;
			}

			/* Tree Styles */
			.pta-tree-item {
				margin-bottom: 4px;
			}
			.pta-tree-head {
				display: flex;
				align-items: center;
				padding: 10px 12px;
				border-radius: 8px;
				cursor: pointer;
				transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
				gap: 10px;
			}
			.pta-tree-head:hover {
				background: rgba(102, 126, 234, 0.08);
				transform: translateX(2px);
			}
			.pta-tree-head.selected {
				background: linear-gradient(135deg, rgba(102, 126, 234, 0.15), rgba(118, 75, 162, 0.1));
				border: 1.5px solid #667eea;
				box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
			}
			.pta-tree-avatar {
				width: 36px;
				height: 36px;
				border-radius: 50%;
				display: flex;
				align-items: center;
				justify-content: center;
				font-weight: 700;
				font-size: 14px;
				color: #fff;
				flex-shrink: 0;
				box-shadow: 0 2px 8px rgba(0,0,0,0.15);
			}
			.pta-tree-avatar.lead { background: linear-gradient(135deg, #667eea, #764ba2); }
			.pta-tree-avatar.member { background: linear-gradient(135deg, #9ca3af, #6b7280); width: 30px; height: 30px; font-size: 12px; }
			.pta-tree-info { flex: 1; min-width: 0; }
			.pta-tree-name { font-size: 13px; font-weight: 600; color: #1f2937; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
			.pta-tree-role { font-size: 10px; color: #9ca3af; }
			.pta-tree-count {
				font-size: 11px;
				background: linear-gradient(135deg, #667eea, #764ba2);
				color: #fff;
				padding: 2px 8px;
				border-radius: 12px;
				font-weight: 700;
				box-shadow: 0 2px 4px rgba(102, 126, 234, 0.2);
			}
			.pta-tree-arrow {
				color: #9ca3af;
				font-size: 10px;
				transition: transform 0.2s;
			}
			.pta-tree-arrow.open { transform: rotate(90deg); }
			.pta-tree-children {
				display: none;
				margin-left: 18px;
				border-left: 2px solid rgba(102, 126, 234, 0.2);
				padding-left: 10px;
			}
			.pta-tree-children.open { display: block; }
			.pta-member-row {
				display: flex;
				align-items: center;
				padding: 8px 10px;
				border-radius: 8px;
				cursor: pointer;
				transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
				gap: 10px;
			}
			.pta-member-row:hover { 
				background: rgba(102, 126, 234, 0.08);
				transform: translateX(2px);
			}
			.pta-member-row.selected { 
				background: linear-gradient(135deg, rgba(102, 126, 234, 0.15), rgba(118, 75, 162, 0.1));
				border: 1px solid #667eea;
			}

			/* Pin button active state */
			.pta-pin-btn.active {
				background: linear-gradient(135deg, #667eea, #764ba2);
				color: #fff;
				border-color: #667eea;
				box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
			}

			/* Compare Panel */
			.pta-compare-panel {
				position: fixed;
				bottom: 0;
				left: 0;
				right: 0;
				background: linear-gradient(135deg, #fff, #f8fafc);
				border-top: 4px solid #667eea;
				box-shadow: 0 -8px 24px rgba(0,0,0,0.15);
				padding: 18px;
				z-index: 1000;
				display: none;
				max-height: 350px;
				overflow-y: auto;
				backdrop-filter: blur(10px);
			}
			.pta-compare-panel.show { display: block; }
			.pta-compare-header {
				display: flex;
				justify-content: space-between;
				align-items: center;
				margin-bottom: 12px;
			}
			.pta-compare-header h5 {
				margin: 0;
				font-size: 15px;
				font-weight: 700;
				color: #1f2937;
			}
			.pta-compare-chips {
				display: flex;
				gap: 8px;
				flex-wrap: wrap;
				margin-bottom: 12px;
			}
			.pta-compare-chip {
				background: linear-gradient(135deg, #667eea, #764ba2);
				color: #fff;
				padding: 6px 12px;
				border-radius: 18px;
				font-size: 12px;
				font-weight: 600;
				display: flex;
				align-items: center;
				gap: 6px;
				box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
				transition: all 0.2s;
			}
			.pta-compare-chip:hover {
				transform: scale(1.05);
			}
			.pta-compare-chip .remove {
				cursor: pointer;
				font-weight: bold;
				font-size: 14px;
				opacity: 0.8;
				transition: opacity 0.2s;
			}
			.pta-compare-chip .remove:hover {
				opacity: 1;
			}

			/* Table Styles */
			.pta-table-wrapper { 
				overflow-x: auto;
				border-radius: 8px;
				box-shadow: 0 2px 8px rgba(0,0,0,0.06);
			}
			.pta-table {
				width: 100%;
				border-collapse: collapse;
				font-size: 12px;
				background: #fff;
			}
			.pta-table thead th {
				background: linear-gradient(135deg, #f8fafc, #f0f2f7);
				padding: 10px 12px;
				text-align: right;
				font-weight: 700;
				color: #4b5563;
				font-size: 11px;
				border-bottom: 2px solid #667eea;
				white-space: nowrap;
				position: sticky;
				top: 0;
				z-index: 1;
				letter-spacing: 0.3px;
			}
			.pta-table thead th:first-child {
				text-align: left;
				position: sticky;
				left: 0;
				z-index: 2;
				background: linear-gradient(135deg, #f8fafc, #f0f2f7);
			}
			.pta-table tbody td {
				padding: 10px 12px;
				border-bottom: 1px solid #f0f2f7;
				text-align: right;
				color: #4b5563;
				transition: background 0.15s;
			}
			.pta-table tbody td:first-child {
				text-align: left;
				font-weight: 600;
				position: sticky;
				left: 0;
				background: #fff;
				color: #1f2937;
			}
			.pta-table tbody tr:hover td { 
				background: linear-gradient(90deg, #f8fafc, #f0f2f7);
			}
			.pta-table tbody tr:hover td:first-child { 
				background: linear-gradient(90deg, #f8fafc, #f0f2f7);
			}
			.pta-table tfoot td {
				font-weight: 800;
				background: linear-gradient(135deg, #667eea15, #764ba215) !important;
				border-top: 2px solid #667eea;
				border-bottom: 2px solid #667eea;
				padding: 12px 12px;
				text-align: right;
				color: #1f2937;
			}
			.pta-table tfoot td:first-child {
				text-align: left;
				position: sticky;
				left: 0;
				background: linear-gradient(135deg, #667eea15, #764ba215) !important;
			}

			/* Section Title */
			.pta-section-title {
				font-size: 15px;
				font-weight: 800;
				color: #1f2937;
				margin: 18px 0 12px;
				padding-bottom: 10px;
				border-bottom: 3px solid;
				border-image: linear-gradient(90deg, #667eea, #764ba2) 1;
				display: inline-block;
				letter-spacing: -0.3px;
			}

			/* Welcome & Loading */
			.pta-welcome {
				display: flex;
				flex-direction: column;
				align-items: center;
				justify-content: center;
				height: 100%;
				min-height: 300px;
				color: #9ca3af;
				text-align: center;
			}
			.pta-welcome h4 { 
				color: #6b7280; 
				margin: 12px 0 6px; 
				font-size: 15px;
				font-weight: 700;
			}
			.pta-loading {
				display: flex;
				align-items: center;
				justify-content: center;
				height: 200px;
				color: #9ca3af;
				gap: 10px;
				font-weight: 500;
			}

			/* Scrollbar */
			.pta-tree-inner::-webkit-scrollbar,
			.pta-data-inner::-webkit-scrollbar { width: 6px; }
			.pta-tree-inner::-webkit-scrollbar-track,
			.pta-data-inner::-webkit-scrollbar-track { background: transparent; }
			.pta-tree-inner::-webkit-scrollbar-thumb,
			.pta-data-inner::-webkit-scrollbar-thumb { 
				background: linear-gradient(180deg, #667eea, #764ba2);
				border-radius: 3px;
				box-shadow: 0 0 10px rgba(0,0,0,0.1);
			}
			.pta-tree-inner::-webkit-scrollbar-thumb:hover,
			.pta-data-inner::-webkit-scrollbar-thumb:hover {
				background: linear-gradient(180deg, #764ba2, #667eea);
			}
		`);
	}

	// =================================================================
	// VIEW SWITCHING
	// =================================================================
	switch_view(view) {
		this.current_view = view;
		
		// Update tabs
		this.$main_container.find('.pta-tab').removeClass('active');
		this.$main_container.find(`.pta-tab[data-view="${view}"]`).addClass('active');

		switch(view) {
			case 'hierarchy':
				this.render_tree();
				// Restore previously selected employee if exists
				if (this.selected_employee) {
					this.restore_selected_employee();
				} else {
					this.$main_container.find('.pta-data-inner').html(`
						<div class="pta-welcome">
							<h4>Select a team member</h4>
							<p>Click on any name in the hierarchy to view their detailed time analysis</p>
						</div>
					`);
				}
				break;
			case 'all_employees':
				this.render_all_employees();
				break;
			case 'dashboard':
				this.show_dashboard();
				break;
		}
	}

	restore_selected_employee() {
		if (!this.selected_employee) return;
		
		// Find and select the employee element
		const selector = `.pta-tree-head[data-employee="${this.selected_employee.id}"], .pta-member-row[data-employee="${this.selected_employee.id}"]`;
		const $element = this.$main_container.find(selector);
		
		if ($element.length) {
			// Remove selected class from all elements
			this.$main_container.find('.pta-tree-head.selected, .pta-member-row.selected').removeClass('selected');
			// Add selected class to the element
			$element.addClass('selected');
			
			// Trigger click to load the data
			if (this.selected_employee.type === 'lead') {
				// Find the lead node in the tree
				const leadNode = this.tree.find(node => node.id === this.selected_employee.id);
				if (leadNode) this.load_team_data(leadNode);
			} else {
				// Find the member node in the tree
				let memberNode = null;
				for (let lead of this.tree) {
					const found = this.flatten_tree(lead).find(node => node.id === this.selected_employee.id);
					if (found) {
						memberNode = found;
						break;
					}
				}
				if (memberNode) this.load_employee_data(memberNode);
			}
		}
	}

	// =================================================================
	// DATA LOADING
	// =================================================================
	load_columns(cb) {
		frappe.call({
			method: "productivity_next.productivity_next.page.project_time_analysi.project_time_analysi.get_columns",
			args: { show_deployment_rate: this.deployment_field.get_value() ? 1 : 0 },
			callback: (r) => {
				this.columns = (r.message || []).filter((c) => c.fieldname !== "employee_name");
				if (cb) cb();
			},
		});
	}

	load_tree() {
		this.$main_container.find('.pta-tree-inner').html('<div class="pta-loading">Loading hierarchy...</div>');
		frappe.call({
			method: "productivity_next.productivity_next.page.project_time_analysi.project_time_analysi.get_team_tree",
			callback: (r) => {
				const msg = r.message || {};
				this.is_admin = !!msg.is_admin;
				this.tree = msg.tree || [];
				this.navigation_candidates = this.get_navigation_candidates(this.tree);
				if (this.is_admin) {
					this.admin_filter_field.$wrapper.show();
				}
				this.render_tree();
				this.update_quick_stats();
			},
		});
	}

	get_navigation_candidates(tree = this.tree) {
		const candidates = [];
		const visit = (nodes) => {
			nodes.forEach((node) => {
				if (node && node.id) {
					candidates.push(node.id);
				}
				if (node && node.children && node.children.length) {
					visit(node.children);
				}
			});
		};
		visit(tree || []);
		return candidates;
	}

	refresh_all() {
		this.data_cache = {};
		this.render_tree();
		this.update_quick_stats();
		this.$main_container.find('.pta-data-inner').html(`
			<div class="pta-welcome">
				<h4>Select a team member</h4>
				<p>Click on any name in the hierarchy to view their detailed time analysis</p>
			</div>
		`);
	}

	refresh_current_view() {
		const selected = this.$main_container.find('.pta-tree-head.selected, .pta-member-row.selected');
		if (selected.length) {
			selected.trigger('click');
		}
	}

	// =================================================================
	// TREE RENDERING
	// =================================================================
	render_tree() {
		const $tree = this.$main_container.find('.pta-tree-inner').empty();
		
		if (!this.tree.length) {
			$tree.html('<div class="pta-loading">No team data available</div>');
			return;
		}

		this.tree.forEach(node => {
			if (!this.search_term || this.match_search(node)) {
				$tree.append(this.render_team_node(node));
			}
		});
	}

	match_search(node) {
		if (node.name.toLowerCase().includes(this.search_term)) return true;
		if (node.children && node.children.some(c => this.match_search(c))) return true;
		return false;
	}

	render_team_node(node) {
		const hasChildren = node.children && node.children.length > 0;
		const isBookmarked = this.bookmarked_employees.includes(node.id);
		const $item = $(`<div class="pta-tree-item"></div>`);
		
		const $head = $(`
			<div class="pta-tree-head ${isBookmarked ? 'bookmarked' : ''}" data-employee="${node.id}" data-type="lead">
				<div class="pta-tree-avatar lead">${node.name.charAt(0).toUpperCase()}</div>
				<div class="pta-tree-info">
					<div class="pta-tree-name">${frappe.utils.escape_html(node.name)}</div>
					<div class="pta-tree-role">Team Lead</div>
				</div>
				${hasChildren ? `<span class="pta-tree-count">${node.children.length}</span>` : ''}
				${hasChildren ? '<span class="pta-tree-arrow">&#9654;</span>' : ''}
				<button class="btn btn-xs btn-default pta-add-compare" title="Add to compare" style="opacity:0.5;font-size:10px;padding:1px 5px;">+</button>
			</div>
		`);

		const $children = $(`<div class="pta-tree-children"></div>`);
		let childrenRendered = false;

		$head.on('click', '.pta-add-compare', (e) => {
			e.stopPropagation();
			this.add_to_compare(node);
		});

		$head.on('click', (e) => {
			if ($(e.target).hasClass('pta-add-compare')) return;
			e.stopPropagation();
			
			if (hasChildren) {
				const $arrow = $head.find('.pta-tree-arrow');
				if ($children.hasClass('open')) {
					$children.removeClass('open');
					$arrow.removeClass('open');
				} else {
					$children.addClass('open');
					$arrow.addClass('open');
					
					if (!childrenRendered) {
						node.children.forEach(child => {
							$children.append(this.render_member_node(child));
						});
						childrenRendered = true;
					}
				}
			}
			
			this.$main_container.find('.pta-tree-head.selected, .pta-member-row.selected').removeClass('selected');
			$head.addClass('selected');
			this.load_team_data(node);
		});

		$item.append($head);
		if (hasChildren) $item.append($children);
		
		return $item;
	}

	render_member_node(node) {
		const hasChildren = node.children && node.children.length > 0;
		const isBookmarked = this.bookmarked_employees.includes(node.id);
		const $item = $(`<div class="pta-tree-item"></div>`);
		
		const $row = $(`
			<div class="pta-member-row ${isBookmarked ? 'bookmarked' : ''}" data-employee="${node.id}" data-type="member">
				<div class="pta-tree-avatar member">${node.name.charAt(0).toUpperCase()}</div>
				<div class="pta-tree-info">
					<div class="pta-tree-name">${frappe.utils.escape_html(node.name)}</div>
				</div>
				${hasChildren ? `<span class="pta-tree-count" style="font-size:10px;">${node.children.length}</span>` : ''}
				${hasChildren ? '<span class="pta-tree-arrow" style="font-size:9px;">&#9654;</span>' : ''}
				<button class="btn btn-xs btn-default pta-add-compare" title="Add to compare" style="opacity:0.5;font-size:10px;padding:1px 5px;">+</button>
			</div>
		`);

		const $children = $(`<div class="pta-tree-children"></div>`);
		let childrenRendered = false;

		$row.on('click', '.pta-add-compare', (e) => {
			e.stopPropagation();
			this.add_to_compare(node);
		});

		$row.on('click', (e) => {
			if ($(e.target).hasClass('pta-add-compare')) return;
			e.stopPropagation();
			
			if (hasChildren) {
				const $arrow = $row.find('.pta-tree-arrow');
				if ($children.hasClass('open')) {
					$children.removeClass('open');
					$arrow.removeClass('open');
				} else {
					$children.addClass('open');
					$arrow.addClass('open');
					
					if (!childrenRendered) {
						node.children.forEach(child => {
							$children.append(this.render_member_node(child));
						});
						childrenRendered = true;
					}
				}
			}
			
			this.$main_container.find('.pta-tree-head.selected, .pta-member-row.selected').removeClass('selected');
			$row.addClass('selected');
			this.load_employee_data(node);
		});

		$item.append($row);
		if (hasChildren) $item.append($children);
		
		return $item;
	}

	// =================================================================
	// LOAD AND DISPLAY DATA
	// =================================================================
	async load_team_data(leadNode) {
		// Store selected employee to preserve selection when switching views
		this.selected_employee = { id: leadNode.id, name: leadNode.name, type: 'lead' };
		
		const $dataPanel = this.$main_container.find('.pta-data-inner');
		const $dataTitle = this.$main_container.find('.pta-data-title');
		$dataPanel.html('<div class="pta-loading">Loading team data...</div>');
		$dataTitle.text(`${leadNode.name} - Team Report`);

		const filters = this.get_report_filters();
		const dateParams = {
			from_date: this.get_from_date(),
			to_date: this.get_to_date(),
		};

		// Save to recent views
		this.add_recent_view(leadNode);

		// Load lead data
		const leadCacheKey = JSON.stringify({ employee: leadNode.id, ...dateParams, ...filters });
		let leadData = this.data_cache[leadCacheKey];
		if (!leadData) {
			const r = await frappe.call({
				method: "productivity_next.productivity_next.page.project_time_analysi.project_time_analysi.get_node_data",
				args: { employee: leadNode.id, include_subtree: 0, ...dateParams, ...filters }
			});
			leadData = r.message || [];
			this.data_cache[leadCacheKey] = leadData;
		}

		// Load all member data
		const membersData = [];
		if (leadNode.children && leadNode.children.length) {
			for (const child of leadNode.children) {
				const childCacheKey = JSON.stringify({ employee: child.id, ...dateParams, ...filters });
				let childData = this.data_cache[childCacheKey];
				if (!childData) {
					const r = await frappe.call({
						method: "productivity_next.productivity_next.page.project_time_analysi.project_time_analysi.get_node_data",
						args: { employee: child.id, include_subtree: 0, ...dateParams, ...filters }
					});
					childData = r.message || [];
					this.data_cache[childCacheKey] = childData;
				}
				membersData.push({ node: child, data: childData });
			}
		}

		this.render_team_table($dataPanel, leadNode, leadData, membersData);
	}

	async load_employee_data(node) {
		// Store selected employee to preserve selection when switching views
		this.selected_employee = { id: node.id, name: node.name, type: 'member' };
		
		const $dataPanel = this.$main_container.find('.pta-data-inner');
		const $dataTitle = this.$main_container.find('.pta-data-title');
		$dataPanel.html('<div class="pta-loading">Loading employee data...</div>');
		$dataTitle.text(`${node.name} - Individual Report`);

		// Save to recent views
		this.add_recent_view(node);

		const filters = this.get_report_filters();
		const dateParams = {
			from_date: this.get_from_date(),
			to_date: this.get_to_date(),
		};

		const cacheKey = JSON.stringify({ employee: node.id, ...dateParams, ...filters });
		let data = this.data_cache[cacheKey];
		if (!data) {
			const r = await frappe.call({
				method: "productivity_next.productivity_next.page.project_time_analysi.project_time_analysi.get_node_data",
				args: { employee: node.id, include_subtree: 0, ...dateParams, ...filters }
			});
			data = r.message || [];
			this.data_cache[cacheKey] = data;
		}

		this.render_single_table($dataPanel, node, data);
	}

	// =================================================================
	// RENDER TABLES
	// =================================================================
	render_team_table($panel, leadNode, leadData, membersData) {
		const allRows = [];
		
		// Add lead row
		if (leadData.length > 0) {
			allRows.push({
				name: leadNode.name,
				role: 'Team Lead',
				id: leadNode.id,
				row: this.summarize_row(leadData)
			});
		} else {
			allRows.push({
				name: leadNode.name,
				role: 'Team Lead',
				id: leadNode.id,
				row: this.get_empty_row()
			});
		}

		// Add member rows
		membersData.forEach(m => {
			if (m.data.length > 0) {
				allRows.push({
					name: m.node.name,
					role: 'Member',
					id: m.node.id,
					row: this.summarize_row(m.data)
				});
			} else {
				allRows.push({
					name: m.node.name,
					role: 'Member',
					id: m.node.id,
					row: this.get_empty_row()
				});
			}
		});

		// Calculate totals
		const totals = this.calculate_totals(allRows);

		const cols = this.columns.length ? this.columns : this.get_default_columns();
		let html = `
			<div class="pta-section-title">${leadNode.name} - Team Report</div>
			<div style="margin-bottom:10px;">
				<small style="color:#718096;">
					Period: ${this.get_from_date()} to ${this.get_to_date()}
					| Team Size: ${leadNode.children ? leadNode.children.length + 1 : 1}
				</small>
			</div>
			<div class="pta-table-wrapper">
				<table class="pta-table">
					<thead>
						<tr>
							<th>#</th>
							<th>Resource</th>
							<th>Role</th>
							${cols.map(c => `<th>${c.label}</th>`).join('')}
						</tr>
					</thead>
					<tbody>
		`;

		allRows.forEach((item, index) => {
			const stats = this.calculate_employee_stats([item.row]);
			let rowClass = '';
			if (stats.totalHours === 0) rowClass = 'pta-highlight';
			
			html += `
				<tr class="${rowClass}">
					<td>${index + 1}</td>
					<td><strong>${frappe.utils.escape_html(item.name)}</strong></td>
					<td>${item.role}</td>
					${cols.map(c => {
						let val = item.row[c.fieldname];
						if (val === undefined || val === null) val = '';
						if (c.fieldname === 'percentage_billable' && val !== '') {
							val = this.format_percentage_value(val);
						} else if (typeof val === 'number' && val !== '') {
							val = this.format_numeric_value(val);
						}
						if (c.fieldname === 'percentage_billable' && parseFloat(val) < 50) {
							return `<td style="color:#dc3545;font-weight:600;">${val}</td>`;
						}
						return `<td>${val}</td>`;
					}).join('')}
				</tr>
			`;
		});

		html += `
					</tbody>
					<tfoot>
						<tr>
							<td colspan="3"><strong>Team Total</strong></td>
							${cols.map(c => {
								let val = totals[c.fieldname];
								if (val === undefined || val === null) val = '';
								if (c.fieldname === 'percentage_billable' && val !== '') {
									val = this.format_percentage_value(val);
								} else if (typeof val === 'number' && val !== '') {
									val = this.format_numeric_value(val);
								}
								return `<td>${val}</td>`;
							}).join('')}
						</tr>
					</tfoot>
				</table>
			</div>
		`;

		$panel.html(html);
	}

	render_single_table($panel, node, data) {
		if (!data.length) {
			$panel.html(`
				<div class="pta-section-title">${node.name} - Individual Report</div>
				<p style="color:#a0aec0;">No data available for this period.</p>
			`);
			return;
		}

		const cols = this.columns.length ? this.columns : this.get_default_columns();
		const row = this.summarize_row(data);

		let html = `
			<div class="pta-section-title">${node.name} - Individual Report</div>
			<div style="margin-bottom:10px;">
				<small style="color:#718096;">
					Period: ${this.get_from_date()} to ${this.get_to_date()}
				</small>
			</div>
			<div class="pta-table-wrapper">
				<table class="pta-table">
					<thead>
						<tr>
							${cols.map(c => `<th>${c.label}</th>`).join('')}
						</tr>
					</thead>
					<tbody>
						<tr>
							${cols.map(c => {
								let val = row[c.fieldname];
								if (val === undefined || val === null) val = '';
								if (c.fieldname === 'percentage_billable' && val !== '') {
									val = this.format_percentage_value(val);
								} else if (typeof val === 'number' && val !== '') {
									val = this.format_numeric_value(val);
								}
								return `<td>${val}</td>`;
							}).join('')}
						</tr>
					</tbody>
				</table>
			</div>
		`;

		// Show detailed entries if daily data is available
		if (data.length > 1 && data[0].date) {
			html += `
				<div class="pta-section-title" style="margin-top:20px;">Daily Breakdown</div>
				<div class="pta-table-wrapper">
					<table class="pta-table">
						<thead>
							<tr>
								<th>Date</th>
								<th>Project</th>
								<th>Hours</th>
								<th>Billable Hours</th>
							</tr>
						</thead>
						<tbody>
							${data.slice(0, 30).map(d => `
								<tr>
									<td>${d.date || '-'}</td>
									<td>${d.project || '-'}</td>
									<td>${(d.hours || d.total_hours || 0).toFixed(1)}</td>
									<td>${(d.billable_hours || 0).toFixed(1)}</td>
								</tr>
							`).join('')}
						</tbody>
					</table>
				</div>
				${data.length > 30 ? `<p style="color:#718096;font-size:12px;margin-top:5px;">Showing 30 of ${data.length} entries</p>` : ''}
			`;
		}

		$panel.html(html);
	}

	// =================================================================
	// DASHBOARD VIEW
	// =================================================================
	async show_dashboard() {
		const $dataPanel = this.$main_container.find('.pta-data-inner');
		const $dataTitle = this.$main_container.find('.pta-data-title');
		$dataPanel.html('<div class="pta-loading">Building dashboard...</div>');
		$dataTitle.text('Dashboard Overview');

		const filters = this.get_report_filters();
		const dateParams = {
			from_date: this.get_from_date(),
			to_date: this.get_to_date(),
		};

		// Collect all employees
		const allEmployees = [];
		this.tree.forEach(team => {
			allEmployees.push(...this.flatten_tree(team));
		});

		// Load data for all employees
		const allStats = [];
		for (const emp of allEmployees.slice(0, 20)) { // Limit to 20 for performance
			const cacheKey = JSON.stringify({ employee: emp.id, ...dateParams, ...filters });
			if (!this.data_cache[cacheKey]) {
				const r = await frappe.call({
					method: "productivity_next.productivity_next.page.project_time_analysi.project_time_analysi.get_node_data",
					args: { employee: emp.id, include_subtree: 0, ...dateParams, ...filters }
				});
				this.data_cache[cacheKey] = r.message || [];
			}
			const stats = this.calculate_employee_stats(this.data_cache[cacheKey]);
			allStats.push({ name: emp.name, id: emp.id, ...stats });
		}

		// Sort by utilization
		allStats.sort((a, b) => a.billablePercent - b.billablePercent);

		const totalEmployees = allEmployees.length;
		const totalHours = allStats.reduce((s, e) => s + e.totalHours, 0);
		const totalBillable = allStats.reduce((s, e) => s + e.billableHours, 0);
		const avgUtilization = totalHours > 0 ? Math.round((totalBillable / totalHours) * 100) : 0;
		const lowUtilization = allStats.filter(e => e.billablePercent < 50 && e.totalHours > 0).length;

		let html = `
			<div class="pta-dashboard">
				<div class="pta-dashboard-card">
					<h5>Team Overview</h5>
					<p>Total Employees: <strong>${totalEmployees}</strong></p>
					<p>Total Hours: <strong>${totalHours.toFixed(1)}</strong></p>
					<p>Total Billable: <strong>${totalBillable.toFixed(1)}</strong></p>
					<p>Avg Utilization: <strong style="color:${avgUtilization >= 70 ? '#28a745' : '#dc3545'}">${avgUtilization}%</strong></p>
					<p>Low Utilization (<50%): <strong style="color:#dc3545">${lowUtilization}</strong></p>
				</div>
				
				<div class="pta-dashboard-card">
					<h5>Utilization Distribution</h5>
					<div class="pta-table-wrapper">
						<table class="pta-table">
							<thead>
								<tr>
									<th>Employee</th>
									<th>Total Hours</th>
									<th>Billable Hours</th>
									<th>Billable %</th>
								</tr>
							</thead>
							<tbody>
								${allStats.map(e => `
									<tr style="cursor:pointer;" onclick="cur_page.page.pta_instance.load_employee_data({id:'${e.id}',name:'${e.name}'})">
										<td>${frappe.utils.escape_html(e.name)}</td>
										<td>${e.totalHours.toFixed(1)}</td>
										<td>${e.billableHours.toFixed(1)}</td>
										<td style="color:${e.billablePercent >= 70 ? '#28a745' : e.billablePercent >= 50 ? '#ffc107' : '#dc3545'};font-weight:600;">
											${e.billablePercent}%
										</td>
									</tr>
								`).join('')}
							</tbody>
						</table>
					</div>
				</div>
			</div>
		`;

		$dataPanel.html(html);
		
		// Store instance reference for click handlers
		this.page.pta_instance = this;
	}

	// =================================================================
	// ALL EMPLOYEES VIEW
	// =================================================================
	async render_all_employees() {
		const $dataPanel = this.$main_container.find('.pta-data-inner');
		const $dataTitle = this.$main_container.find('.pta-data-title');
		$dataPanel.html('<div class="pta-loading">Loading all employees...</div>');
		$dataTitle.text('All Employees Report');

		const filters = this.get_report_filters();
		const dateParams = {
			from_date: this.get_from_date(),
			to_date: this.get_to_date(),
		};

		const allEmployees = [];
		this.tree.forEach(team => {
			allEmployees.push(...this.flatten_tree(team));
		});

		const allRows = [];
		for (const emp of allEmployees) {
			const cacheKey = JSON.stringify({ employee: emp.id, ...dateParams, ...filters });
			if (!this.data_cache[cacheKey]) {
				const r = await frappe.call({
					method: "productivity_next.productivity_next.page.project_time_analysi.project_time_analysi.get_node_data",
					args: { employee: emp.id, include_subtree: 0, ...dateParams, ...filters }
				});
				this.data_cache[cacheKey] = r.message || [];
			}
			
			if (this.data_cache[cacheKey].length > 0) {
				allRows.push({
					name: emp.name,
					id: emp.id,
					row: this.summarize_row(this.data_cache[cacheKey])
				});
			}
		}

		const cols = this.columns.length ? this.columns : this.get_default_columns();
		const totals = this.calculate_totals(allRows);

		let html = `
			<div class="pta-section-title">All Employees Report</div>
			<div style="margin-bottom:10px;">
				<small style="color:#718096;">
					Period: ${this.get_from_date()} to ${this.get_to_date()}
					| Total: ${allRows.length} employees
				</small>
			</div>
			<div class="pta-table-wrapper">
				<table class="pta-table">
					<thead>
						<tr>
							<th>#</th>
							<th>Resource</th>
							${cols.map(c => `<th>${c.label}</th>`).join('')}
						</tr>
					</thead>
					<tbody>
		`;

		allRows.forEach((item, index) => {
			html += `
				<tr>
					<td>${index + 1}</td>
					<td><strong>${frappe.utils.escape_html(item.name)}</strong></td>
					${cols.map(c => {
						let val = item.row[c.fieldname];
						if (val === undefined || val === null) val = '';
						if (c.fieldname === 'percentage_billable' && val !== '') {
							val = this.format_percentage_value(val);
						} else if (typeof val === 'number' && val !== '') {
							val = this.format_numeric_value(val);
						}
						return `<td>${val}</td>`;
					}).join('')}
				</tr>
			`;
		});

		html += `
					</tbody>
					<tfoot>
						<tr>
							<td colspan="2"><strong>Total</strong></td>
							${cols.map(c => {
								let val = totals[c.fieldname];
								if (val === undefined || val === null) val = '';
								if (c.fieldname === 'percentage_billable' && val !== '') {
									val = this.format_percentage_value(val);
								} else if (typeof val === 'number' && val !== '') {
									val = this.format_numeric_value(val);
								}
								return `<td>${val}</td>`;
							}).join('')}
						</tr>
					</tfoot>
				</table>
			</div>
		`;

		$dataPanel.html(html);
	}

	// =================================================================
	// COMPARE FEATURE
	// =================================================================
	add_to_compare(node) {
		if (this.compare_list.find(c => c.id === node.id)) {
			frappe.show_alert({ message: `${node.name} is already in compare list`, indicator: 'orange' });
			return;
		}
		
		if (this.compare_list.length >= 5) {
			frappe.show_alert({ message: 'Maximum 5 employees can be compared', indicator: 'red' });
			return;
		}

		this.compare_list.push(node);
		this.update_compare_chips();
		this.toggle_compare_panel(true);
		frappe.show_alert({ message: `${node.name} added to compare`, indicator: 'green' });
	}

	update_compare_chips() {
		const $chips = this.$main_container.find('#pta-compare-chips');
		$chips.html(
			this.compare_list.map(c => `
				<div class="pta-compare-chip">
					${frappe.utils.escape_html(c.name)}
					<span class="remove" data-id="${c.id}">&times;</span>
				</div>
			`).join('')
		);

		$chips.find('.remove').on('click', (e) => {
			const id = $(e.currentTarget).data('id');
			this.compare_list = this.compare_list.filter(c => c.id !== id);
			this.update_compare_chips();
			if (this.compare_list.length === 0) {
				this.toggle_compare_panel(false);
			}
		});
	}

	toggle_compare_panel(show) {
		const $panel = this.$main_container.find('#pta-compare-panel');
		if (show === undefined) {
			$panel.toggleClass('show');
		} else if (show) {
			$panel.addClass('show');
		} else {
			$panel.removeClass('show');
		}
	}

	clear_compare_list() {
		this.compare_list = [];
		this.update_compare_chips();
		this.$main_container.find('#pta-compare-results').empty();
	}

	async run_comparison() {
		if (this.compare_list.length < 2) {
			frappe.show_alert({ message: 'Select at least 2 employees to compare', indicator: 'orange' });
			return;
		}

		const $results = this.$main_container.find('#pta-compare-results');
		$results.html('<div class="pta-loading">Running comparison...</div>');

		const filters = this.get_report_filters();
		const dateParams = {
			from_date: this.get_from_date(),
			to_date: this.get_to_date(),
		};

		const compareData = [];
		for (const emp of this.compare_list) {
			const cacheKey = JSON.stringify({ employee: emp.id, ...dateParams, ...filters });
			if (!this.data_cache[cacheKey]) {
				const r = await frappe.call({
					method: "productivity_next.productivity_next.page.project_time_analysi.project_time_analysi.get_node_data",
					args: { employee: emp.id, include_subtree: 0, ...dateParams, ...filters }
				});
				this.data_cache[cacheKey] = r.message || [];
			}
			const row = this.summarize_row(this.data_cache[cacheKey]);
			const stats = this.calculate_employee_stats(this.data_cache[cacheKey]);
			compareData.push({ name: emp.name, row, stats });
		}

		// Build comparison table
		const cols = this.columns.length ? this.columns.filter(c => 
			['total_hours', 'billable_hours', 'percentage_billable', 'days_available', 'total_utilised_hours', 'internal_task_hours'].includes(c.fieldname)
		) : [
			{ fieldname: 'total_hours', label: 'Total Hours' },
			{ fieldname: 'billable_hours', label: 'Billable Hours' },
			{ fieldname: 'percentage_billable', label: 'Billable %' },
		];

		let html = `
			<table class="pta-table">
				<thead>
					<tr>
						<th>Metric</th>
						${compareData.map(d => `<th>${frappe.utils.escape_html(d.name)}</th>`).join('')}
					</tr>
				</thead>
				<tbody>
					${cols.map(c => `
						<tr>
							<td><strong>${c.label}</strong></td>
							${compareData.map(d => {
								let val = d.row[c.fieldname];
								if (val === undefined || val === null) val = '-';
								if (c.fieldname === 'percentage_billable') val = this.format_percentage_value(val);
								else if (typeof val === 'number' && val !== '') val = this.format_numeric_value(val);
								return `<td>${val}</td>`;
							}).join('')}
						</tr>
					`).join('')}
				</tbody>
			</table>
		`;

		$results.html(html);
	}

	// =================================================================
	// BOOKMARKS
	// =================================================================
	load_bookmarks() {
		try {
			return JSON.parse(localStorage.getItem('pta_bookmarks') || '[]');
		} catch(e) {
			return [];
		}
	}

	save_bookmarks() {
		localStorage.setItem('pta_bookmarks', JSON.stringify(this.bookmarked_employees));
		this.$main_container.find('.pta-bookmark-count').text(this.bookmarked_employees.length);
	}

	bookmark_current_view() {
		const selected = this.$main_container.find('.pta-tree-head.selected, .pta-member-row.selected');
		if (!selected.length) {
			frappe.show_alert({ message: 'Select an employee first', indicator: 'orange' });
			return;
		}

		const empId = selected.data('employee');
		const empName = selected.find('.pta-tree-name').text();
		
		if (this.bookmarked_employees.includes(empId)) {
			this.bookmarked_employees = this.bookmarked_employees.filter(id => id !== empId);
			frappe.show_alert({ message: `${empName} removed from bookmarks`, indicator: 'rbed' });
		} else {
			this.bookmarked_employees.push(empId);
			frappe.show_alert({ message: `${empName} bookmarked`, indicator: 'green' });
		}
		
		this.save_bookmarks();
		this.render_tree();
	}

	show_bookmarks() {
		if (!this.bookmarked_employees.length) {
			frappe.show_alert({ message: 'No bookmarks yet', indicator: 'orange' });
			return;
		}

		// Find bookmarked nodes
		const bookmarked = [];
		this.tree.forEach(team => {
			const all = this.flatten_tree(team);
			all.forEach(emp => {
				if (this.bookmarked_employees.includes(emp.id)) {
					bookmarked.push(emp);
				}
			});
		});

		const $dataPanel = this.$main_container.find('.pta-data-inner');
		const $dataTitle = this.$main_container.find('.pta-data-title');
		$dataTitle.text('Bookmarked Employees');

		let html = '<div class="pta-section-title">Bookmarked Employees</div>';
		html += '<div style="display:flex;flex-wrap:wrap;gap:10px;">';
		
		bookmarked.forEach(emp => {
			html += `
				<div class="pta-bookmark-card" style="padding:10px;border:1px solid #e2e8f0;border-radius:8px;cursor:pointer;min-width:150px;" 
				     data-employee="${emp.id}" onclick="cur_page.page.pta_instance.load_employee_data({id:'${emp.id}',name:'${emp.name}'})">
					<strong>${frappe.utils.escape_html(emp.name)}</strong>
				</div>
			`;
		});
		
		html += '</div>';
		$dataPanel.html(html);
	}

	// =================================================================
	// RECENT VIEWS
	// =================================================================
	load_recent_views() {
		try {
			return JSON.parse(localStorage.getItem('pta_recent_views') || '[]');
		} catch(e) {
			return [];
		}
	}

	add_recent_view(node) {
		this.recent_views = this.recent_views.filter(v => v.id !== node.id);
		this.recent_views.unshift({ id: node.id, name: node.name });
		if (this.recent_views.length > 10) this.recent_views.pop();
		localStorage.setItem('pta_recent_views', JSON.stringify(this.recent_views));
	}

	// =================================================================
	// EXPORT & COPY
	// =================================================================
	export_csv() {
		const $table = this.$main_container.find('.pta-table');
		if (!$table.length) {
			frappe.show_alert({ message: 'No data to export', indicator: 'orange' });
			return;
		}

		let csv = '';
		$table.find('tr').each(function() {
			const row = [];
			$(this).find('th, td').each(function() {
				row.push('"' + $(this).text().trim() + '"');
			});
			csv += row.join(',') + '\n';
		});

		const blob = new Blob([csv], { type: 'text/csv' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `project_time_analysis_${frappe.datetime.get_today()}.csv`;
		a.click();
		URL.revokeObjectURL(url);
		
		frappe.show_alert({ message: 'CSV exported successfully', indicator: 'green' });
	}

	copy_summary() {
		const $table = this.$main_container.find('.pta-table');
		if (!$table.length) {
			frappe.show_alert({ message: 'No data to copy', indicator: 'orange' });
			return;
		}

		let text = '';
		$table.find('tr').each(function() {
			const row = [];
			$(this).find('th, td').each(function() {
				row.push($(this).text().trim());
			});
			text += row.join('\t') + '\n';
		});

		navigator.clipboard.writeText(text).then(() => {
			frappe.show_alert({ message: 'Summary copied to clipboard', indicator: 'green' });
		});
	}

	copy_current_data() {
		this.copy_summary();
	}

	// =================================================================
	// DATA HELPERS
	// =================================================================
	format_percentage_value(val) {
		if (val === undefined || val === null || val === '') return '';
		const numericValue = parseFloat(val);
		if (Number.isNaN(numericValue)) return val;
		return `${numericValue.toFixed(2)}%`;
	}

	format_numeric_value(val) {
		if (val === undefined || val === null || val === '') return '';
		const numericValue = parseFloat(val);
		if (Number.isNaN(numericValue)) return val;
		return numericValue.toFixed(2);
	}

	summarize_row(rows) {
		if (rows.length === 0) return this.get_empty_row();
		if (rows.length === 1) return rows[0];
		
		const summary = {};
		const firstRow = rows[0];
		
		for (const key in firstRow) {
			if (typeof firstRow[key] === 'number') {
				summary[key] = rows.reduce((sum, r) => sum + (r[key] || 0), 0);
			} else if (key === 'percentage_billable') {
				const totalHrs = rows.reduce((sum, r) => sum + (r.total_hours || r.hours || 0), 0);
				const billableHrs = rows.reduce((sum, r) => sum + (r.billable_hours || r.total_billable || 0), 0);
				summary[key] = totalHrs > 0 ? Math.round((billableHrs / totalHrs) * 100) : 0;
			} else {
				summary[key] = firstRow[key];
			}
		}
		
		return summary;
	}

	get_empty_row() {
		const row = {};
		if (this.columns.length) {
			this.columns.forEach(c => {
				row[c.fieldname] = c.fieldtype === 'Percent' ? 0 : 0;
			});
		}
		row.percentage_billable = 0;
		return row;
	}

	calculate_totals(rows) {
		const totals = {};
		
		rows.forEach(item => {
			for (const key in item.row) {
				if (typeof item.row[key] === 'number') {
					totals[key] = (totals[key] || 0) + item.row[key];
				}
			}
		});

		if (totals.total_hours || totals.hours) {
			const totalHrs = totals.total_hours || totals.hours || 0;
			const billableHrs = totals.billable_hours || totals.total_billable || 0;
			totals.percentage_billable = totalHrs > 0 ? Math.round((billableHrs / totalHrs) * 100) : 0;
		}

		return totals;
	}

	calculate_employee_stats(data) {
		const totalHours = data.reduce((sum, r) => sum + (r.total_hours || r.hours || 0), 0);
		const billableHours = data.reduce((sum, r) => sum + (r.billable_hours || r.total_billable || 0), 0);
		const billablePercent = totalHours > 0 ? Math.round((billableHours / totalHours) * 100) : 0;
		return { totalHours, billableHours, billablePercent };
	}

	get_default_columns() {
		return [
			{ fieldname: 'days_available', label: 'Days Available' },
			{ fieldname: 'hours_per_day', label: 'Hours Per Day' },
			{ fieldname: 'total_hours', label: 'Total Hours' },
			{ fieldname: 'total_billable', label: 'Total Billable' },
			{ fieldname: 'percentage_billable', label: '% Billable' },
			{ fieldname: 'total_utilised_hours', label: 'Total Utilised Hours' }
		];
	}

	flatten_tree(node) {
		let result = [node];
		if (node.children) {
			node.children.forEach(child => {
				result = result.concat(this.flatten_tree(child));
			});
		}
		return result;
	}

	// =================================================================
	// QUICK STATS
	// =================================================================
	update_quick_stats() {
		const totalTeams = this.tree.length;
		const totalEmployees = this.tree.reduce((sum, t) => sum + this.flatten_tree(t).length, 0);
		const period = `${this.get_from_date()} to ${this.get_to_date()}`;

		this.$main_container.find('#pta-quick-stats').html(`
			<div class="pta-quick-stat">
				<div class="pta-quick-stat-icon blue">T</div>
				<div class="pta-quick-stat-info">
					<div class="pta-quick-stat-value">${totalTeams}</div>
					<div class="pta-quick-stat-label">Teams</div>
				</div>
			</div>
			<div class="pta-quick-stat">
				<div class="pta-quick-stat-icon green">E</div>
				<div class="pta-quick-stat-info">
					<div class="pta-quick-stat-value">${totalEmployees}</div>
					<div class="pta-quick-stat-label">Total Employees</div>
				</div>
			</div>
			<div class="pta-quick-stat">
				<div class="pta-quick-stat-icon orange">P</div>
				<div class="pta-quick-stat-info">
					<div class="pta-quick-stat-value" style="font-size:13px;">${period}</div>
					<div class="pta-quick-stat-label">Period</div>
				</div>
			</div>
			
		`);
	}

	// =================================================================
	// UTILITY METHODS
	// =================================================================
	expand_all(open) {
		if (open) {
			this.$main_container.find('.pta-tree-head').each((i, el) => {
				const $children = $(el).next('.pta-tree-children');
				if ($children.length && !$children.hasClass('open')) {
					$(el).trigger('click');
				}
			});
		} else {
			this.$main_container.find('.pta-tree-head').each((i, el) => {
				const $children = $(el).next('.pta-tree-children');
				if ($children.length && $children.hasClass('open')) {
					$(el).trigger('click');
				}
			});
		}
	}

	scroll_to_employee(employee_id) {
		const $target = this.$main_container.find(`[data-employee="${employee_id}"]`).first();
		if (!$target.length) {
			frappe.show_alert({ message: "Employee not found", indicator: "orange" });
			return;
		}

		$target.parents('.pta-tree-children').each(function() {
			if (!$(this).hasClass('open')) {
				$(this).siblings('.pta-tree-head, .pta-member-row').trigger('click');
			}
		});

		this.$main_container.find('.pta-tree-panel').find('.pta-tree-inner').animate({
			scrollTop: $target.offset().top - 250
		}, 300);

		$target.trigger('click');
	}

	open_pick_columns_dialog() {
		if (!this.columns.length) {
			frappe.show_alert({ message: "Columns are still loading", indicator: "orange" });
			return;
		}

		const fields = this.columns.map((c) => ({
			fieldname: c.fieldname,
			fieldtype: "Check",
			label: c.label,
			default: this.hidden_columns.has(c.fieldname) ? 0 : 1,
		}));

		const d = new frappe.ui.Dialog({
			title: "Pick Columns",
			fields,
			primary_action_label: "Apply",
			primary_action: (values) => {
				this.hidden_columns.clear();
				this.columns.forEach((c) => {
					if (!values[c.fieldname]) this.hidden_columns.add(c.fieldname);
				});
				d.hide();
				this.refresh_current_view();
			},
		});
		d.show();
	}

	show_compare_dialog() {
		this.toggle_compare_panel(true);
	}

	show_alert_settings() {
		const d = new frappe.ui.Dialog({
			title: "Alert Settings",
			fields: [
				{
					fieldname: "low_utilization",
					fieldtype: "Int",
					label: "Low Utilization Threshold (%)",
					default: this.alerts_threshold.low_utilization
				},
				{
					fieldname: "high_utilization",
					fieldtype: "Int",
					label: "High Utilization Threshold (%)",
					default: this.alerts_threshold.high_utilization
				}
			],
			primary_action_label: "Save",
			primary_action: (values) => {
				this.alerts_threshold.low_utilization = values.low_utilization;
				this.alerts_threshold.high_utilization = values.high_utilization;
				d.hide();
				frappe.show_alert({ message: 'Alert settings saved', indicator: 'green' });
			}
		});
		d.show();
	}
}
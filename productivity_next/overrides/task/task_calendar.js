// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt
frappe.views.calendar["Task"] = {
	field_map: {
		start: "exp_start_date",
		end: "exp_end_date",
		id: "name",
		title: "title",
		allDay: "allDay",
		progress: "progress",
	},
	gantt: true,
	get_events_method: "productivity_next.productivity_next.calendar.get_custom_events",
};


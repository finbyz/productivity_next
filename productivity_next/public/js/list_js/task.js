frappe.listview_settings['Task'] = {
	add_fields: ["project", "status", "priority", "exp_start_date",
		"exp_end_date", "subject", "progress", "depends_on_tasks"],
	filters: [["status", "=", "Open"]],
	get_indicator: function (doc) {
		var colors = {
			"Open": "purple",
			"Overdue": "orange",
			"Pending Review": "orange",
			"Unplanned": "red",
			"Working": "orange",
			"Completed": "green", // Previously #A5D6A7
			"Cancelled": "grey", // Previously dark grey
			"In-Progress": "yellow", // Previously #F7F3BD
			"Scheduled": "blue", // Previously #9DACF7
			"Planned": "pink", // Previously #DAEBFC
			"Template": "blue",
			"Change Pending": "#F0F8FF",
		}
		return [__(doc.status), colors[doc.status], "status,=," + doc.status];
	},
	gantt_custom_popup_html: function (ganttobj, task) {
		let html = `
			<a class="text-white mb-2 inline-block cursor-pointer"
				href="/app/task/${ganttobj.id}"">
				${ganttobj.name}
			</a>
		`;

		if (task.project) {
			html += `<p class="mb-1">${__("Project")}:
				<a class="text-white inline-block"
					href="/app/project/${task.project}"">
					${task.project}
				</a>
			</p>`;
		}
		html += `<p class="mb-1">
			${__("Progress")}:
			<span class="text-white">${ganttobj.progress}%</span>
		</p>`;

		if (task._assign) {
			const assign_list = JSON.parse(task._assign);
			const assignment_wrapper = `
				<span>Assigned to:</span>
				<span class="text-white">
					${assign_list.map((user) => frappe.user_info(user).fullname).join(", ")}
				</span>
			`;
			html += assignment_wrapper;
		}

		return `<div class="p-3" style="min-width: 220px">${html}</div>`;
	},
};

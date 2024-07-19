frappe.views.calendar["Meeting"] = {
	field_map: {
		"start": "meeting_from",
		"end": "meeting_to",
		"id": "name",
		"title": "organization",
	},
	get_events_method: "productivity_next.productivity_next.doctype.meeting.meeting.get_events"
};
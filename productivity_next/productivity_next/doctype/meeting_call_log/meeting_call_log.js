// Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Meeting Call Log", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Fetch Transcript"), () => {
			frappe.call({
				method: "productivity_next.productivity_next.doctype.meeting_call_log.meeting_call_log.queue_fetch_transcript",
				args: { docname: frm.doc.name },
				callback() {
					frappe.show_alert({ message: __("Transcript fetch started"), indicator: "green" });
				},
			});
		});
		frappe.db.get_value("Meeting", { meeting_call_log: frm.doc.name }, "name").then((r) => {
			const meeting = r.message && r.message.name;
			if (meeting) {
				frm.add_custom_button(__("Open Meeting"), () => frappe.set_route("Form", "Meeting", meeting));
			}
		});
	},
});

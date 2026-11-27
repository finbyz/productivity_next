// Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Meeting Sync Settings", {
	refresh(frm) {
		const site = frappe.boot.sitename;
		const elsewhere = [
			[frm.doc.enable_teams, frm.doc.teams_active_site, __("Microsoft Teams")],
			[frm.doc.enable_google_meet, frm.doc.google_active_site, __("Google Meet")],
		].filter(([on, active]) => on && active && active !== site);
		if (elsewhere.length) {
			const names = elsewhere.map(([, active, label]) => `${label} (${__("enabled on")} ${active})`).join(", ");
			frm.set_intro(
				__("Sync is paused here: {0}. This looks like a copy of another site. Click Activate on This Site to run it here.", [names]),
				"orange"
			);
			frm.add_custom_button(__("Activate on This Site"), () => {
				frappe.confirm(
					__("Run the sync on this site? If the original site is still live, both will process the same calls."),
					() => frm.call("activate_on_this_site").then(() => frm.reload_doc())
				);
			});
		}
		if (frm.doc.enable_teams) {
			frm.add_custom_button(__("Renew Teams Subscriptions"), () => {
				frappe.call({
					method: "productivity_next.meeting_sync.teams.subscriptions.queue_ensure_subscriptions",
					freeze: true,
					freeze_message: __("Renewing Microsoft Graph subscriptions..."),
					callback() {
						frappe.show_alert({ message: __("Subscription renewal started"), indicator: "green" });
					},
				});
			}, __("Actions"));
		}
		if (frm.doc.enable_google_meet) {
			frm.add_custom_button(__("Test Google Connection"), () => {
				frappe.call({
					method: "productivity_next.meeting_sync.google_meet.sync.test_connection",
					freeze: true,
					freeze_message: __("Checking Google Meet access..."),
					callback(r) {
						if (r.message) {
							frappe.msgprint({
								title: __("Google Meet Connection"),
								message: `<pre>${frappe.utils.escape_html(JSON.stringify(r.message, null, 2))}</pre>`,
							});
						}
					},
				});
			}, __("Actions"));
			frm.add_custom_button(__("Sync Google Meet Now"), () => {
				frappe.call({
					method: "productivity_next.meeting_sync.google_meet.sync.queue_sync",
					callback() {
						frappe.show_alert({ message: __("Google Meet sync started"), indicator: "green" });
					},
				});
			}, __("Actions"));
		}
	},
});

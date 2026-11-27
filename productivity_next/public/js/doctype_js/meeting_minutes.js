// Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on('Meeting', {
	refresh: function(frm) {
		if (!frm.is_new() && frm.doc.docstatus < 2) {
			frm.add_custom_button(__('Send MOM'), function() {
				frm.trigger('send_mom');
			});
		}
	},

	on_submit: function(frm) {
		// Draft the MOM e-mail as soon as the Meeting is submitted; the user only clicks Send.
		open_meeting_minutes_email(frm, 1);
	},

	send_mom: function(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__('Please save the document before sending the MOM.'));
			return;
		}
		open_meeting_minutes_email(frm, 0);
	},
});

function open_meeting_minutes_email(frm, quiet) {
	frappe.call({
		method: 'productivity_next.meeting_sync.minutes_email.get_mom_email',
		args: { meeting_name: frm.doc.name, quiet: quiet },
		callback: function(r) {
			if (!r.message) return;
			// Opens the standard e-mail dialog so the MOM can be checked before it goes out;
			// the sent mail is kept on the Meeting's timeline.
			new frappe.views.CommunicationComposer({
				doc: frm.doc,
				frm: frm,
				subject: r.message.subject,
				recipients: (r.message.recipients || []).join(', '),
				cc: (r.message.cc || []).join(', '),
				message: r.message.message,
				attach_document_print: 0,
			});
		}
	});
}

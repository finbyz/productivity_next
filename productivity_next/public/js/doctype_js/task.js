frappe.ui.form.on('Task', {
    before_save: function(frm) {
        if (frm.doc.status == "Completed") {
            frm.set_value('completed_on', frappe.datetime.nowdate());
            frm.set_value('completed_by', frappe.session.user);
        }
    },
    after_save: function(frm) {
        frappe.xcall("productivity_next.productivity_next.doc_events.task.validate", {
			doc: frm.doc,
		}).then((response) => {
			console.log("Nacho")
            frm.doc.refresh()
        })
    }
});

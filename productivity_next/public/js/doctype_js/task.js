frappe.ui.form.on('Task', {
    before_save: function(frm) {
        if (frm.doc.status == "Completed") {
            frm.set_value('completed_on', frappe.datetime.nowdate());
            frm.set_value('completed_by', frappe.session.user);
        }
    }
});

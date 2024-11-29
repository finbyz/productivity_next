frappe.ui.form.on('Task', {
    before_save: function(frm) {
        if (frm.doc.status == "Completed") {
            if (frm.doc.completed_on == " ")
                frm.set_value('completed_on', frappe.datetime.nowdate());
            frm.set_value('completed_by', frappe.session.user);
        }
    }
});

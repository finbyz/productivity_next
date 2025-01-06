frappe.ui.form.on("Task", {
    setup: function (frm) {
        frm.trigger("hide_and_show_add_remove_button");
    },
    before_save: function (frm) {
        frappe.run_serially([
            () => frm.trigger("set_completed_on_and_completed_by"),
            () => frm.trigger("set_color"),
        ]);
    },
    status: function (frm) {
        frappe.run_serially([
            () => frm.trigger("set_completed_on_and_completed_by"),
            () => frm.trigger("set_color"),
        ]);
    },
    process_flow: function (frm) {
        frappe.run_serially([
            () => frm.trigger("fetch_process_steps"),
            () => frm.trigger("fetch_process_checks"),
            () => frm.trigger("hide_and_show_add_remove_button"),
        ]);
    },
    hide_and_show_add_remove_button: function (frm) {
        if (!frm.doc.process_flow) {
            frm.set_df_property("process_flow_steps", "cannot_add_rows", false);
            frm.set_df_property("process_flow_steps", "cannot_delete_rows", false);
            frm.set_df_property("process_flow_steps", "cannot_delete_all_rows", false);
            frm.set_df_property("process_flow_checks", "cannot_add_rows", false);
            frm.set_df_property("process_flow_checks", "cannot_delete_rows", false);
            frm.set_df_property("process_flow_checks", "cannot_delete_all_rows", false);
        } else {
            frm.set_df_property("process_flow_steps", "cannot_add_rows", true);
            frm.set_df_property("process_flow_steps", "cannot_delete_rows", true);
            frm.set_df_property("process_flow_steps", "cannot_delete_all_rows", true);
            frm.set_df_property("process_flow_checks", "cannot_add_rows", true);
            frm.set_df_property("process_flow_checks", "cannot_delete_rows", true);
            frm.set_df_property("process_flow_checks", "cannot_delete_all_rows", true);
        }
    },
    fetch_process_steps: function (frm) {
        frm.call({
            doc: frm.doc,
            method: "fetch_process_flow_steps",
            callback: (r) => {
                frm.doc.process_flow_steps = [];
                r.message.forEach((row) => frm.add_child("process_flow_steps", row));
                frm.refresh_field("process_flow_steps");
            },
        })
    },
    fetch_process_checks: function (frm) {
        frm.call({
            doc: frm.doc,
            method: "fetch_process_flow_checks",
            callback: (r) => {
                frm.doc.process_flow_checks = [];
                r.message.forEach((row) => frm.add_child("process_flow_checks", row));
                frm.refresh_field("process_flow_checks");
            },
        })
    },
    set_completed_on_and_completed_by: function (frm) {
        if (frm.doc.status == "Completed") {
            if (!frm.doc.completed_on) {
                frm.set_value("completed_on", frappe.datetime.nowdate());
            }
            if (!frm.doc.completed_by && frappe.session.user != "Administrator") {
                frm.set_value("completed_by", frappe.session.user);
            }
        } else {
            frm.set_value("completed_on", null);
            frm.set_value("completed_by", null);
        }
    },
    set_color: function (frm) {
        if (frm.doc.status == "Completed") {
            frm.set_value("color", "#e4f5e9");
        } else if (frm.doc.status == "Cancelled") {
            frm.set_value("color", "#f3f3f3");
        } else if (frm.doc.status == "Open") {
            frm.set_value("color", "#fff1e7");
        } else if (frm.doc.status == "Overdue") {
            frm.set_value("color", "#fff0f0");
        } else if (frm.doc.status == "Working") {
            frm.set_value("color", "#fff7d3");
        } else if (frm.doc.status == "Pending Review") {
            frm.set_value("color", "#fcd4fc");
        } else {
            frm.set_value("color", null)
        }
        
        frm.refresh_field("color");
    }
});

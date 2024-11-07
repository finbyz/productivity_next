frappe.ui.form.on('Auto Repeat', {
    onload: function(frm) {
        frm.trigger('reference_doctype');
    },
    refresh: function(frm) {
        frm.trigger('reference_doctype');
    },
    reference_doctype: async function(frm) {
        let get_select_options = function (df, parent_field) {
            // Append parent_field name along with fieldname for child table fields
            let select_value = df.fieldname;
        
            return {
                value: select_value,
                label: df.fieldname + " (" + __(df.label, null, df.parent) + ")",
            };
        };
        
        if (!frm.doc.reference_doctype) {
            return;
        }
        
        let fields = await frappe.get_doc("DocType", frm.doc.reference_doctype);

        if (!fields) {
            return;
        }

        fields = fields.fields;
        
        fields = await fields.filter(function (f) {return f.fieldtype == "Date"})
        
        let options = await fields.map(function (f) {return get_select_options(f, frm.doc.reference_doctype)});
        
        // frm.set_df_property("start_date_field", "options", [""].concat(options));
        // frm.set_df_property("end_date_field", "options", [""].concat(options));
        frm.fields_dict["task_due_date"].grid.update_docfield_property(
            "date_field", "options", [""].concat(options)
        );
    }
});



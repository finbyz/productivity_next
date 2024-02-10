function ButtonFunction(listview) {
	frappe.call({
		method:
			"productivity_next.productivity_next.productivity_next.doctype.fincall_log.fincall_call_log_list.bg_employee_log_generation",
			callback: function(){

			}
	})
}

frappe.listview_settings['Fincall Log'] = {
   refresh: function(listview) {
	   listview.page.add_inner_button("Create Employee Logs", function() {
		   ButtonFunction(listview);
	   }).addClass("btn-warning").css({'color':'white','font-weight': 'normal', "background": "#2490EF"});
	   ;
   },
};
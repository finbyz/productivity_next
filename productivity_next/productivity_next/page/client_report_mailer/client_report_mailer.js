frappe.pages['client-report-mailer'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Client Report Mailer',
		single_column: true
	});
}
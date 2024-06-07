frappe.listview_settings['Application Checkin Checkout'] = {
    add_fields: ["status"],
    get_indicator(doc) {
        if (doc.status === 'Out') {
            return [__("OUT"), "red", "status,=,Out"];
        } else {
            return [__("IN"), "green", "status,=,In"];
        }
    },
}
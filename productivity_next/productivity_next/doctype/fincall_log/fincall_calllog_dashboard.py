from frappe import _


def get_data():
	return {
		"heatmap": True,
		"heatmap_message": _(
			"This is based on transactions against this Supplier. See timeline below for details"
		),
		"fieldname": "fincall_log_ref",
		"transactions": [
			{"label": _("Emplopyee Logs"), "items": ["Employee Fincall"]},
		],
	}

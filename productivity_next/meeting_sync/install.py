"""Create the Meeting fields used by Teams and Google Meet sync."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from productivity_next.meeting_sync.common import GOOGLE_MEET, TEAMS

CUSTOM_FIELDS = {
	"Meeting": [
		{
			"fieldname": "meeting_source",
			"label": "Meeting Source",
			"fieldtype": "Select",
			"options": f"\n{TEAMS}\n{GOOGLE_MEET}",
			"insert_after": "internal_meeting",
			"read_only": 1,
			"in_standard_filter": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "meeting_call_log",
			"label": "Meeting Call Log",
			"fieldtype": "Link",
			"options": "Meeting Call Log",
			"insert_after": "meeting_source",
			"read_only": 1,
			"no_copy": 1,
			"search_index": 1,
		},
		{
			"fieldname": "join_web_url",
			"label": "Join Web Url",
			"fieldtype": "Small Text",
			"insert_after": "meeting_call_log",
			"read_only": 1,
			"no_copy": 1,
		},
	],
}


def ensure_meeting_fields():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)

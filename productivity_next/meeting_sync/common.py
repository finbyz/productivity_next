"""Pieces shared by the Teams and Google Meet sync.

Meeting creation, participant matching and transcript parsing were written for Teams
(productivity_next.meeting_sync.teams.webhook) and work unchanged for any provider; they are re-exported
here so provider code does not depend on the Teams module directly.
"""

import re
from datetime import datetime

import frappe
import pytz
from frappe.utils import get_system_timezone

TEAMS = "Microsoft Teams"
GOOGLE_MEET = "Google Meet"

# Placeholder discussions used by new and previously synced meetings.
DEFAULT_DISCUSSIONS = ("Online Meeting", "Teams Meeting", "Google Meet")

_ISO_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|z|[+-]\d{2}:\d{2})?$")


def parse_iso_utc(value):
	"""ISO 8601 timestamp from Graph or Google ("2026-11-25T08:30:00.1234567Z", with or
	without fraction or offset) -> aware datetime. A value without offset is taken as UTC."""
	if not value:
		return None
	match = _ISO_RE.match(str(value).strip())
	if not match:
		raise ValueError(f"Not an ISO 8601 timestamp: {value!r}")
	base, fraction, offset = match.groups()
	# Python < 3.11 fromisoformat takes at most 6 fraction digits (Graph sends 7)
	text = base + (f".{fraction[:6].ljust(6, '0')}" if fraction else "")
	text += "+00:00" if offset in (None, "Z", "z") else offset
	return datetime.fromisoformat(text)


def utc_to_system(value):
	"""ISO 8601 timestamp -> naive datetime in the site's time zone, as Frappe stores
	Datetime fields."""
	dt = parse_iso_utc(value)
	if dt is None:
		return None
	local = dt.astimezone(pytz.timezone(get_system_timezone()))
	return local.replace(tzinfo=None, microsecond=0)


PROVIDER_FIELDS = {
	TEAMS: ("enable_teams", "teams_active_site"),
	GOOGLE_MEET: ("enable_google_meet", "google_active_site"),
}


def is_enabled(provider):
	"""A provider runs when it is ticked in Meeting Sync Settings on this very site. Ticking
	it stores the site name; a restored copy of the database (UAT, a laptop) has another
	site name, so it never polls Google or takes over the live Graph subscriptions until
	someone ticks it there too."""
	enabled_field, site_field = PROVIDER_FIELDS[provider]
	values = frappe.db.get_value(
		"Meeting Sync Settings", "Meeting Sync Settings", [enabled_field, site_field], as_dict=True
	) or {}
	return bool(values.get(enabled_field)) and values.get(site_field) == frappe.local.site


def __getattr__(name):
	# Lazy re-exports, so importing this module does not import the Teams module at load.
	shared = {
		"add_meeting",
		"_is_internal",
		"_parse_vtt",
		"_should_create_meeting",
		"_normalize_participant_emails",
		"_fit",
		"_meeting_for_log",
		"MIN_MEETING_DURATION_SECONDS",
	}
	if name in shared:
		from productivity_next.meeting_sync.teams import webhook

		return getattr(webhook, name)
	raise AttributeError(name)


def internal_employee_emails():
	"""Company e-mail of every active Employee on an internal domain (the people whose
	meetings are synced)."""
	from productivity_next.meeting_sync.teams.webhook import _is_internal

	emails = set()
	for row in frappe.get_all(
		"Employee", filters={"status": "Active"}, fields=["user_id", "company_email"]
	):
		for email in (row.company_email, row.user_id):
			if email and _is_internal(email):
				emails.add(email.strip().lower())
				break
	return sorted(emails)

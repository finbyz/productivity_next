"""Turn on automatic transcription for upcoming Google Meet meetings.

Like the Teams job: for every Calendar event an employee organizes in the next
LOOKAHEAD_DAYS days that has a Meet link, set the meeting space's
config.artifactConfig.transcriptionConfig.autoTranscriptionGeneration to ON, impersonating
the organizer (only the space owner may change it).

Needs the meetings.space.settings scope in domain-wide delegation, and transcription
allowed for these users by the Workspace admin. Off by default (Meeting Sync Settings >
Google Meet > Turn On Transcription Automatically).

NOT YET VERIFIED against a live Workspace: the field path and the "ON" value come from
Google's Meet v2 reference (SpaceConfig.ArtifactConfig.TranscriptionConfig). Run
run(dry_run=True) first and check one meeting before enabling it.
"""

from datetime import datetime, timedelta, timezone

import frappe

from productivity_next.meeting_sync.common import GOOGLE_MEET, internal_employee_emails, is_enabled
from productivity_next.meeting_sync.google_meet.client import (
	CALENDAR_BASE,
	MEET_BASE,
	SCOPE_CALENDAR_READ,
	SCOPE_MEET_SETTINGS,
	GoogleAPIError,
	get_session,
	paginate,
	request,
)

LOOKAHEAD_DAYS = 14
FIELD_PATH = "config.artifactConfig.transcriptionConfig.autoTranscriptionGeneration"
DONE_CACHE_SECONDS = LOOKAHEAD_DAYS * 24 * 3600
ERROR_CACHE_SECONDS = 24 * 3600


def _cache_key(kind, meeting_code):
	return f"meeting_sync:gmeet_auto_transcribe:{kind}:{meeting_code}"


def _organized_meet_codes(email, start, end):
	"""{meeting code: subject} of non-cancelled events this user organizes with a Meet link."""
	session = get_session(email, [SCOPE_CALENDAR_READ])
	found = {}
	events = paginate(
		session,
		f"{CALENDAR_BASE}/calendars/{email}/events",
		"items",
		params={
			"timeMin": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
			"timeMax": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
			"singleEvents": "true",
		},
		page_size=250,
		page_size_param="maxResults",
	)
	for event in events:
		conference = event.get("conferenceData") or {}
		solution = ((conference.get("conferenceSolution") or {}).get("key") or {}).get("type")
		organizer = ((event.get("organizer") or {}).get("email") or "").lower()
		if (
			event.get("status") != "cancelled"
			and solution == "hangoutsMeet"
			and conference.get("conferenceId")
			and organizer == email
		):
			found.setdefault(conference["conferenceId"], event.get("summary") or "")
	return found


def run(dry_run=False, only_emails=None):
	if not is_enabled(GOOGLE_MEET):
		return {"skipped": "Google Meet sync is not enabled"}
	if not frappe.db.get_single_value("Meeting Sync Settings", "google_auto_transcribe"):
		return {"skipped": "turned off in Meeting Sync Settings"}

	cache = frappe.cache()
	start = datetime.now(timezone.utc)
	end = start + timedelta(days=LOOKAHEAD_DAYS)
	summary = {"calendars": 0, "meetings": 0, "already_on": 0, "turned_on": [], "failed": []}

	for email in only_emails or internal_employee_emails():
		try:
			codes = _organized_meet_codes(email, start, end)
			summary["calendars"] += 1
		except GoogleAPIError as e:
			if e.status not in (401, 403, 404):
				summary["failed"].append((email, str(e)[:200]))
			continue

		for code, subject in codes.items():
			summary["meetings"] += 1
			if cache.get_value(_cache_key("done", code)):
				summary["already_on"] += 1
				continue
			try:
				session = get_session(email, [SCOPE_MEET_SETTINGS])
				space = request(session, "GET", f"{MEET_BASE}/spaces/{code}")
				current = (
					((space.get("config") or {}).get("artifactConfig") or {}).get("transcriptionConfig") or {}
				).get("autoTranscriptionGeneration")
				if current == "ON":
					summary["already_on"] += 1
					if not dry_run:
						cache.set_value(_cache_key("done", code), 1, expires_in_sec=DONE_CACHE_SECONDS)
					continue
				if dry_run:
					summary["turned_on"].append((email, subject))
					continue
				request(
					session,
					"PATCH",
					f"{MEET_BASE}/{space['name']}",
					params={"updateMask": FIELD_PATH},
					json_body={"config": {"artifactConfig": {"transcriptionConfig": {"autoTranscriptionGeneration": "ON"}}}},
				)
				summary["turned_on"].append((email, subject))
				cache.set_value(_cache_key("done", code), 1, expires_in_sec=DONE_CACHE_SECONDS)
			except Exception as e:
				summary["failed"].append((email, subject, str(e)[:200]))
				if not dry_run and not cache.get_value(_cache_key("err", code)):
					cache.set_value(_cache_key("err", code), 1, expires_in_sec=ERROR_CACHE_SECONDS)
					frappe.log_error(
						title="Google Meet auto transcribe failed",
						message=f"organizer={email}\nsubject={subject}\nmeeting_code={code}\n{e}",
					)
	return summary

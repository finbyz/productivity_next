"""Google Meet -> Meeting Call Log -> Meeting.

Google has no single tenant-wide feed of calls like Teams' callRecords, so every
SYNC run reads, for each active employee, the conference records that started in the
last `google_lookback_hours` (Meet REST API, as that employee through domain-wide
delegation). Each ended conference becomes one Meeting Call Log (provider "Google Meet",
call_id = conference record name). The transcript is read entry by entry and stored as
WebVTT in raw_vtt, the same format Teams gives. Both providers use the same
Meeting creation logic.
"""

import json
from datetime import datetime, timedelta, timezone

import frappe
from frappe.utils import add_to_date, cint, now_datetime

from productivity_next.meeting_sync.common import (
	GOOGLE_MEET,
	MIN_MEETING_DURATION_SECONDS,
	_meeting_for_log,
	_normalize_participant_emails,
	_should_create_meeting,
	add_meeting,
	internal_employee_emails,
	is_enabled,
	parse_iso_utc,
	utc_to_system,
)
from productivity_next.meeting_sync.google_meet.client import (
	CALENDAR_BASE,
	MEET_BASE,
	SCOPE_CALENDAR_READ,
	SCOPE_MEET_READ,
	GoogleAPIError,
	directory_email,
	get_session,
	paginate,
	request,
)

DEFAULT_LOOKBACK_HOURS = 6
# How long after a call the transcript is still looked for.
TRANSCRIPT_RETRY_HOURS = 24
# Calendar events are matched to a conference within this margin around its times.
CALENDAR_MARGIN = timedelta(hours=2)
SUBJECT_MAX_LENGTH = 140


def _log_error(title, docname=None):
	frappe.log_error(
		title=title[:140],
		message=frappe.get_traceback(),
		reference_doctype="Meeting Call Log" if docname else None,
		reference_name=docname,
	)


def _iso_z(dt):
	return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _parse_google_ts(value):
	return parse_iso_utc(value)


# ---------------------------------------------------------------------------
# Meet API reads
# ---------------------------------------------------------------------------


def list_conference_records(session, since):
	"""Conference records the impersonated user can see that started after `since` (UTC)."""
	return list(
		paginate(
			session,
			f"{MEET_BASE}/conferenceRecords",
			"conferenceRecords",
			params={"filter": f'start_time>="{_iso_z(since)}"'},
		)
	)


def get_space(session, space_name):
	try:
		return request(session, "GET", f"{MEET_BASE}/{space_name}")
	except GoogleAPIError as e:
		if e.status in (403, 404):
			return {}
		raise


def list_participants(session, record_name):
	return list(paginate(session, f"{MEET_BASE}/{record_name}/participants", "participants", page_size=250))


def _participant_identity(participant):
	"""(display name, Meet user id or None) for any kind of participant."""
	for kind in ("signedinUser", "anonymousUser", "phoneUser"):
		info = participant.get(kind)
		if info:
			return (info.get("displayName") or "").strip(), info.get("user")
	return "", None


def find_calendar_event(session, calendar_email, meeting_code, start, end):
	"""The Calendar event of this Meet call in the user's calendar, matched on the meeting
	code (conferenceData.conferenceId). None for an ad hoc call without an event."""
	if not meeting_code:
		return None
	try:
		events = paginate(
			session,
			f"{CALENDAR_BASE}/calendars/{calendar_email}/events",
			"items",
			params={
				"timeMin": _iso_z(start - CALENDAR_MARGIN),
				"timeMax": _iso_z(end + CALENDAR_MARGIN),
				"singleEvents": "true",
			},
			page_size=250,
			page_size_param="maxResults",
		)
		for event in events:
			conference = event.get("conferenceData") or {}
			if conference.get("conferenceId") == meeting_code:
				return event
	except GoogleAPIError as e:
		if e.status not in (403, 404):
			raise
	return None


# ---------------------------------------------------------------------------
# Sync: conference records -> Meeting Call Log
# ---------------------------------------------------------------------------


def sync_recent_conferences(lookback_hours=None, only_emails=None):
	"""Scheduled every 15 minutes (productivity_next.meeting_sync.tasks). Returns a summary dict."""
	if not is_enabled(GOOGLE_MEET):
		return {"skipped": "Google Meet sync is not enabled"}

	hours = cint(lookback_hours) or cint(
		frappe.db.get_single_value("Meeting Sync Settings", "google_lookback_hours")
	) or DEFAULT_LOOKBACK_HOURS
	since = datetime.now(timezone.utc) - timedelta(hours=hours)
	summary = {"users": 0, "records": 0, "ended": 0, "created": 0, "updated": 0, "failed": []}
	seen = set()

	for email in only_emails or internal_employee_emails():
		try:
			session = get_session(email, [SCOPE_MEET_READ])
			records = list_conference_records(session, since)
			summary["users"] += 1
		except GoogleAPIError as e:
			# 401/403: user not in Workspace, no Meet licence or delegation missing
			if e.status not in (401, 403, 404):
				summary["failed"].append((email, str(e)[:200]))
			continue
		except Exception:
			summary["failed"].append((email, "list failed"))
			_log_error(f"[GMEET] Listing conference records failed for {email}")
			continue

		for record in records:
			name = record.get("name")
			if not name or name in seen:
				continue
			seen.add(name)
			summary["records"] += 1
			if not record.get("endTime"):
				continue  # still running; picked up by a later run
			summary["ended"] += 1
			try:
				action = upsert_call_log(record, email)
				if action:
					summary[action] += 1
				frappe.db.commit()
			except Exception:
				frappe.db.rollback()
				summary["failed"].append((name, "upsert failed"))
				_log_error(f"[GMEET] Saving conference record failed ({name})")

	return summary


def upsert_call_log(record, accessed_as):
	"""Create the Meeting Call Log of an ended conference, or refresh its times. Returns
	"created", "updated" or None (nothing changed)."""
	record_name = record["name"]
	start_utc = _parse_google_ts(record.get("startTime"))
	end_utc = _parse_google_ts(record.get("endTime"))
	actual_start = utc_to_system(record.get("startTime"))
	actual_end = utc_to_system(record.get("endTime"))

	existing = frappe.db.get_value(
		"Meeting Call Log", {"provider": GOOGLE_MEET, "call_id": record_name}, ["name", "actual_end"], as_dict=True
	)
	if existing:
		if existing.actual_end and existing.actual_end == actual_end:
			return None
		doc = frappe.get_doc("Meeting Call Log", existing.name)
		doc.actual_start = actual_start
		doc.actual_end = actual_end
		doc.save(ignore_permissions=True)
		# a draft Meeting follows the latest call times (as the Teams refresh does)
		meeting = frappe.db.get_value(
			"Meeting", {"meeting_call_log": doc.name, "docstatus": 0}, "name"
		)
		if meeting:
			frappe.db.set_value(
				"Meeting", meeting, {"meeting_from": actual_start, "meeting_to": actual_end}
			)
		return "updated"

	session = get_session(accessed_as, [SCOPE_MEET_READ])
	space = get_space(session, record.get("space")) if record.get("space") else {}
	meeting_code = space.get("meetingCode")

	event = None
	try:
		cal_session = get_session(accessed_as, [SCOPE_CALENDAR_READ])
		event = find_calendar_event(cal_session, accessed_as, meeting_code, start_utc, end_utc)
	except Exception:
		# the call is still logged without its subject and invitees
		_log_error(f"[GMEET] Calendar lookup failed ({record_name})")

	participants = list_participants(session, record_name)
	emails, display_names = [], []
	for participant in participants:
		display_name, user = _participant_identity(participant)
		email = directory_email(user) if user else None
		if email:
			if email not in emails:
				emails.append(email)
		elif display_name and display_name not in display_names:
			display_names.append(display_name)

	organizer_email, organizer_name = "", ""
	if event:
		organizer = event.get("organizer") or {}
		organizer_email = (organizer.get("email") or "").strip().lower()
		organizer_name = organizer.get("displayName") or ""
		for attendee in event.get("attendees") or []:
			email = (attendee.get("email") or "").strip().lower()
			if (
				email
				and not attendee.get("resource")
				and attendee.get("responseStatus") != "declined"
				and email not in emails
			):
				emails.append(email)

	names_for_display = display_names + [e for e in emails if e not in display_names]
	doc = frappe.new_doc(
		"Meeting Call Log",
		provider=GOOGLE_MEET,
		call_id=record_name,
		online_meeting_id=record.get("space"),
		join_web_url=space.get("meetingUri") or "",
		meeting_subject=((event or {}).get("summary") or "").strip()[:SUBJECT_MAX_LENGTH],
		meeting_type="scheduled" if event else "ad hoc",
		actual_start=actual_start,
		actual_end=actual_end,
		organizer=organizer_name,
		organizer_email=organizer_email,
		accessed_as=accessed_as,
		participants=", ".join(names_for_display),
		participant_count=len(participants),
		status="Call Record Received",
		raw_payload=json.dumps(
			{
				"conferenceRecord": record,
				"space": space,
				"participants": participants,
				"participantEmails": emails,
				"participantNames": display_names,
				"calendarEvent": {
					"id": (event or {}).get("id"),
					"summary": (event or {}).get("summary"),
					"organizer": (event or {}).get("organizer"),
				}
				if event
				else None,
			},
			indent=2,
		),
	)
	doc.insert(ignore_permissions=True)
	# transcript right away when it is ready; retry_pending_transcripts covers the rest
	frappe.enqueue(
		"productivity_next.meeting_sync.google_meet.sync.fetch_transcript_for_log",
		docname=doc.name,
		queue="long",
		job_id=f"gmeet-transcript::{doc.name}",
		deduplicate=True,
		enqueue_after_commit=True,
	)
	return "created"


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------


def _vtt_time(seconds):
	seconds = max(seconds, 0)
	hours, rest = divmod(seconds, 3600)
	minutes, secs = divmod(rest, 60)
	return f"{int(hours):02d}:{int(minutes):02d}:{secs:06.3f}"


def _vtt_text(value):
	# a cue may not contain a blank line or "-->"; "<" would start a tag
	return " ".join((value or "").split()).replace("-->", "->").replace("<", "‹")


def build_vtt(entries, participant_names, conference_start):
	"""Transcript entries -> WebVTT with "<v Speaker>" cues (what Teams returns), so the
	same parser can handle both providers."""
	lines = ["WEBVTT", ""]
	for index, entry in enumerate(entries, start=1):
		text = _vtt_text(entry.get("text"))
		if not text:
			continue
		start = _parse_google_ts(entry.get("startTime"))
		end = _parse_google_ts(entry.get("endTime")) or start
		offset_start = (start - conference_start).total_seconds() if start and conference_start else 0
		offset_end = (end - conference_start).total_seconds() if end and conference_start else offset_start
		speaker = _vtt_text(participant_names.get(entry.get("participant")) or "Unknown speaker")
		lines += [str(index), f"{_vtt_time(offset_start)} --> {_vtt_time(offset_end)}", f"<v {speaker}>{text}</v>", ""]
	return "\n".join(lines) if len(lines) > 2 else ""


def fetch_transcript_for_log(docname):
	"""Store the conference's transcript on the log. Returns True when stored, False when
	there is none (yet). Saving the log queues Meeting creation if needed."""
	doc = frappe.get_doc("Meeting Call Log", docname)
	if doc.provider != GOOGLE_MEET or doc.raw_vtt:
		return bool(doc.raw_vtt)
	if not doc.accessed_as:
		return False
	try:
		session = get_session(doc.accessed_as, [SCOPE_MEET_READ])
		transcripts = list(paginate(session, f"{MEET_BASE}/{doc.call_id}/transcripts", "transcripts"))
		# a conference has one transcript per start/stop of transcription
		ready = sorted(
			(t for t in transcripts if t.get("state") in ("ENDED", "FILE_GENERATED")),
			key=lambda t: t.get("startTime") or "",
		)
		if not ready:
			return False

		participant_names = {}
		for participant in list_participants(session, doc.call_id):
			display_name, _user = _participant_identity(participant)
			participant_names[participant.get("name")] = display_name

		entries = []
		for transcript in ready:
			entries.extend(paginate(session, f"{MEET_BASE}/{transcript['name']}/entries", "transcriptEntries"))
		entries.sort(key=lambda e: e.get("startTime") or "")

		record = (json.loads(doc.raw_payload or "{}") or {}).get("conferenceRecord") or {}
		vtt = build_vtt(entries, participant_names, _parse_google_ts(record.get("startTime")))
		if not vtt:
			return False

		doc.reload()
		doc.raw_vtt = vtt
		doc.transcript_id = ", ".join(t["name"] for t in ready)[:1000]
		doc.status = "Complete"
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		return True
	except Exception:
		frappe.db.rollback()
		_log_error(f"[GMEET] Transcript fetch failed ({docname})", docname)
		if frappe.db.get_value("Meeting Call Log", docname, "status") != "Complete":
			frappe.db.set_value("Meeting Call Log", docname, "status", "Transcript Fetch Failed", update_modified=False)
			frappe.db.commit()
		return False


def retry_pending_transcripts():
	"""Scheduled every 15 minutes. Google writes the transcript some minutes after the call
	ends; retry calls that ended in the last TRANSCRIPT_RETRY_HOURS without one."""
	now = now_datetime()
	rows = frappe.db.sql(
		"""SELECT name FROM `tabMeeting Call Log`
		WHERE provider = 'Google Meet'
		  AND IFNULL(raw_vtt, '') = ''
		  AND actual_end BETWEEN %(oldest)s AND %(newest)s
		  AND TIMESTAMPDIFF(SECOND, actual_start, actual_end) >= %(min_seconds)s
		ORDER BY actual_end DESC
		LIMIT 50""",
		{
			"oldest": add_to_date(now, hours=-TRANSCRIPT_RETRY_HOURS),
			"newest": add_to_date(now, minutes=-5),
			"min_seconds": MIN_MEETING_DURATION_SECONDS,
		},
		pluck=True,
	)
	for name in rows:
		frappe.enqueue(
			"productivity_next.meeting_sync.google_meet.sync.fetch_transcript_for_log",
			docname=name,
			queue="long",
			job_id=f"gmeet-transcript::{name}",
			deduplicate=True,
		)


# ---------------------------------------------------------------------------
# Meeting
# ---------------------------------------------------------------------------


def _payload(doc):
	try:
		return json.loads(doc.raw_payload or "{}") or {}
	except (TypeError, ValueError):
		return {}


def create_meeting_from_log(log_name, force=0):
	"""Create (or with force, update) the draft Meeting of a Google Meet log. Called from
	the Meeting Call Log update hook once the log has its times."""
	force = cint(force)
	doc = frappe.get_doc("Meeting Call Log", log_name)
	existing = _meeting_for_log(doc.name)
	if existing and not force:
		return {"status": "skipped", "meeting": existing}
	if not _should_create_meeting(doc.actual_start, doc.actual_end):
		return {"status": "skipped", "message": "call too short or missing times"}

	payload = _payload(doc)
	emails = _normalize_participant_emails(payload.get("participantEmails") or [], doc.organizer_email)
	if not emails and doc.accessed_as:
		emails = [doc.accessed_as]

	meeting_name = add_meeting(
		existing_meeting_name=existing if force else None,
		actual_start=doc.actual_start,
		actual_end=doc.actual_end,
		participant_emails=emails,
		discussion=doc.meeting_subject or GOOGLE_MEET,
		subject=doc.meeting_subject or "",
		organizer_email=doc.organizer_email or None,
		display_names=payload.get("participantNames") or [],
		teams_meeting_log=doc.name,
		join_web_url=doc.join_web_url,
		provider=GOOGLE_MEET,
	)
	doc.db_set("is_meeting_created", 1, update_modified=False)

	return {"status": "success", "meeting": meeting_name}


# ---------------------------------------------------------------------------
# Settings form buttons
# ---------------------------------------------------------------------------


@frappe.whitelist()
def queue_sync():
	frappe.only_for("System Manager")
	frappe.enqueue(
		"productivity_next.meeting_sync.google_meet.sync.sync_recent_conferences",
		queue="long",
		job_id="gmeet-sync-now",
		deduplicate=True,
	)
	return True


@frappe.whitelist()
def test_connection(email=None):
	"""Check the service account against one employee (or `email`): Meet, Calendar and
	Directory access. Returns what worked and the error text of what did not."""
	frappe.only_for("System Manager")
	from productivity_next.meeting_sync.google_meet.client import SCOPE_DIRECTORY_READ, admin_email

	email = email or admin_email()
	result = {"user": email}
	checks = (
		("meet", [SCOPE_MEET_READ], lambda s: len(list_conference_records(s, datetime.now(timezone.utc) - timedelta(days=1)))),
		(
			"calendar",
			[SCOPE_CALENDAR_READ],
			lambda s: request(s, "GET", f"{CALENDAR_BASE}/calendars/{email}/events", params={"maxResults": 1}).get("summary"),
		),
		(
			"directory",
			[SCOPE_DIRECTORY_READ],
			lambda s: request(s, "GET", f"https://admin.googleapis.com/admin/directory/v1/users/{email}", params={"fields": "primaryEmail"}).get("primaryEmail"),
		),
	)
	for key, scopes, check in checks:
		try:
			result[key] = {"ok": True, "result": check(get_session(email, scopes))}
		except Exception as e:
			result[key] = {"ok": False, "error": str(e)[:500]}
	return result

from datetime import timedelta
from urllib.parse import quote

import pytz
import requests
import frappe
from frappe.utils import get_datetime, get_system_timezone, now_datetime
from productivity_next.meeting_sync.teams.token_manager import get_access_token

GRAPH = "https://graph.microsoft.com/v1.0"

# Teams usually needs a few minutes after the call ends before the transcript
# object exists. Anything younger than this is not treated as a failure.
TRANSCRIPT_GRACE_MINUTES = 90
# How long after a call retry_pending_transcripts keeps looking for its transcript.
TRANSCRIPT_RETRY_HOURS = 6

# Errors (HTTP 4xx/5xx) always go to the Error Log. Set "meeting_sync_debug_graph": 1 in
# site_config.json to also log successful Graph responses while debugging.
def _debug_graph():
	return bool(frappe.conf.get("meeting_sync_debug_graph"))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


import time

LOCK_RETRY_ATTEMPTS = 5
LOCK_RETRY_BASE_DELAY = 2   # seconds; grows 2, 4, 6, 8, 10


def _set(doc, **fields):
	"""Direct UPDATE with retry on MySQL 1205 (lock wait timeout).

	We no longer take a SELECT ... FOR UPDATE (that was doc.db_set()), but
	another transaction may still be holding an X lock on this row. Retry
	with backoff instead of failing the whole transcript pull.
	"""
	last_exc = None
	for attempt in range(1, LOCK_RETRY_ATTEMPTS + 1):
		try:
			frappe.db.set_value(
				"Meeting Call Log",
				doc.name,
				fields,
				update_modified=False,
			)
			frappe.db.commit()
			for key, value in fields.items():
				doc.set(key, value)
			return
		except Exception as exc:
			last_exc = exc
			# frappe.QueryTimeoutError wraps pymysql 1205
			msg = str(exc)
			if "1205" not in msg and "Lock wait timeout" not in msg:
				raise
			if attempt == LOCK_RETRY_ATTEMPTS:
				break
			delay = LOCK_RETRY_BASE_DELAY * attempt
			_log(
				f"Lock contention retry {attempt}/{LOCK_RETRY_ATTEMPTS} - {doc.name}",
				f"fields={list(fields.keys())}\n"
				f"sleeping {delay}s\n"
				f"{exc}",
				doc.name,
			)
			frappe.db.rollback()
			time.sleep(delay)

	# Out of retries — surface the original error
	# pyrefly: ignore [bad-raise]
	raise last_exc

def _truncate(value, limit=3000):
	text = value if isinstance(value, str) else frappe.as_json(value)
	if text and len(text) > limit:
		return text[:limit] + f"\n... [truncated, total {len(text)} chars]"
	return text


def _log(title, message, docname=None):
	"""Always log through frappe.log_error, and also print to stdout so the
	message shows up in `bench worker` output when debugging."""
	frappe.log_error(
		title=f"{title}"[:140],
		message=message,
		reference_doctype="Meeting Call Log" if docname else None,
		reference_name=docname,
	)


def _log_response(resp, label, docname=None, extra=None):
	"""Log EVERY Graph response — success or failure — with status, URL,
	body snippet and any caller-supplied context. This is what you asked for:
	every response is both printed and written to the Error Log."""
	body = None
	try:
		body = resp.json()
		body_str = _truncate(body)
	except Exception:
		body_str = _truncate(resp.text)

	context = ""
	if extra:
		context = (
			"\n".join(f"{k}={v}" for k, v in extra.items()) + "\n"
		)

	message = (
		f"{context}"
		f"status={resp.status_code}\n"
		f"url={resp.url}\n"
		f"method={resp.request.method if resp.request else 'GET'}\n"
		f"body={body_str}"
	)

	title = f"{label} - {docname}" if docname else label

	if resp.status_code >= 400:
		_log(title, message, docname)
	elif _debug_graph():
		# 2xx responses only while debugging, with a prefix that is easy to filter out.
		_log(f"OK: {title}", message, docname)

	return body


def _graph_get(url, token, accept="application/json", timeout=60, params=None):
	headers = {"Authorization": f"Bearer {token}", "Accept": accept}
	return requests.get(url, headers=headers, params=params, timeout=timeout)


def _graph_get_logged(url, token, label, docname=None, accept="application/json",
                      timeout=60, params=None, extra=None):
	"""Wrapper around _graph_get that always logs the response."""
	try:
		resp = _graph_get(url, token, accept=accept, timeout=timeout, params=params)
	except Exception:
		_log(
			f"{label} - EXCEPTION - {docname}" if docname else f"{label} - EXCEPTION",
			f"url={url}\n{frappe.get_traceback()}",
			docname,
		)
		raise

	# _log_response(resp, label, docname=docname, extra=extra)
	return resp


def _utc_iso(value, shift_minutes=0):
	dt = get_datetime(value)
	if dt is None:
		return None
	if dt.tzinfo is None:
		dt = pytz.timezone(get_system_timezone()).localize(dt)
	dt = dt.astimezone(pytz.utc) + timedelta(minutes=shift_minutes)
	return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _describe_error(resp):
	try:
		err = resp.json().get("error", {})
		return (
			f"status={resp.status_code} code={err.get('code')} "
			f"inner={(err.get('innerError') or {}).get('code')}\n"
			f"{err.get('message')}"
		)
	except Exception:
		return f"status={resp.status_code}\nbody={resp.text[:1000]}"


def _download_content(content_url, token, docname):
	"""Transcript content endpoint. text/vtt is the format we want; if the tenant
	has speaker attribution turned off Graph answers 403 and only the plain
	text projection is available."""
	resp = _graph_get_logged(
		content_url,
		token,
		"Transcript Content (text/vtt)",
		docname=docname,
		accept="text/vtt",
		timeout=90,
	)

	if resp.status_code in (403, 406, 415):
		resp = _graph_get_logged(
			content_url,
			token,
			"Transcript Content (text fallback)",
			docname=docname,
			accept="application/vnd.microsoft.graph.transcript+text",
			timeout=90,
		)

	if resp.status_code != 200:
		_log(
			f"Teams Transcript Content Failed - {docname}",
			f"url={content_url}\n{_describe_error(resp)}",
			docname,
		)
		return None

	# Log the first few lines of the transcript so you can confirm it is real.
	preview = "\n".join(resp.text.splitlines()[:5])
	# _log(
	# 	f"OK: Transcript Content Downloaded - {docname}",
	# 	f"chars={len(resp.text)}\npreview:\n{_truncate(preview, 500)}",
	# 	docname,
	# )
	return resp.text


def _save_transcript(self, text, transcript_id=None, call_id=None,
                     online_meeting_id=None):
    """One single UPDATE for everything we learned. The lock is held for
    milliseconds because every Graph call has already finished by the time
    we get here."""
    fields = {"raw_vtt": text}
    if transcript_id:
        fields["transcript_id"] = transcript_id
    if call_id and not self.call_id:
        fields["call_id"] = call_id
    if online_meeting_id:
        fields["online_meeting_id"] = online_meeting_id
    if self.status != "Complete":
        fields["status"] = "Complete"

    _set(self, **fields)          # _set commits internally

    # _set writes with db.set_value, which skips on_update, so trigger the same follow-up
    # explicitly.
    from productivity_next.meeting_sync.meeting_events import queue_missing_meeting

    queue_missing_meeting(self)
    return True


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def fetch_transcript_for_doc(docname):
	"""Returns True when raw_vtt was stored, False when nothing is available yet."""
	try:
		frappe.db.commit()

		doc = frappe.get_doc("Meeting Call Log", docname)
		# _log(
		# 	f"OK: Fetch Started - {docname}",
		# 	f"organizer_user_id={doc.organizer_user_id}\n"
		# 	f"join_web_url={doc.join_web_url}\n"
		# 	f"actual_start={doc.actual_start}\n"
		# 	f"actual_end={doc.actual_end}\n"
		# 	f"call_id={doc.call_id}\n"
		# 	f"has_raw_vtt={bool(doc.raw_vtt)}",
		# 	docname,
		# )

		if doc.raw_vtt:
			return True
		if not doc.organizer_user_id:
			_log(
				f"Teams Transcript Skipped - {docname}",
				"organizer_user_id is empty; Graph needs the organizer's AAD object id.",
				docname,
			)
			return False

		if doc.join_web_url:
			if get_transcript(doc):
				return True
		return get_transcript_adhoc_for_doc(doc)
	except Exception:
		_log(
			f"Meeting Call Log transcript pull failed: {docname}",
			frappe.get_traceback(),
			docname,
		)
		try:
			frappe.db.rollback()
		except Exception:
			pass
		return False


# ---------------------------------------------------------------------------
# scheduled meetings
# ---------------------------------------------------------------------------


def _match_transcript(doc, transcripts):
	"""Pick the transcript that belongs to this log's call.

	A recurring meeting (or a reused Teams link) has one onlineMeeting with transcripts from
	many calls, and an organizer's ad hoc calls overlap the lookup window, so "the newest
	transcript" is often another call's. Match on callId; without a call id, accept only a
	single transcript created during this call (plus a grace period for processing).
	"""
	if doc.call_id:
		for transcript in transcripts:
			if transcript.get("callId") == doc.call_id:
				return transcript
		return None

	if not (doc.actual_start and doc.actual_end):
		return None
	start = _utc_iso(doc.actual_start, shift_minutes=-5)
	end = _utc_iso(doc.actual_end, shift_minutes=TRANSCRIPT_GRACE_MINUTES)
	in_window = [
		t for t in transcripts
		if start <= (t.get("createdDateTime") or "")[:19] + "Z" <= end
	]
	return in_window[0] if len(in_window) == 1 else None


def get_transcript(self):
    from productivity_next.meeting_sync.teams.resource import meeting_organizer_id
    from productivity_next.meeting_sync.teams.token_manager import get_access_token

    # transcripts live under the meeting's owner, who may not be the call organizer
    organizer_id = meeting_organizer_id(self.join_web_url, self.organizer_user_id)
    token = get_access_token()

    lookup = _graph_get_logged(
        f"{GRAPH}/users/{organizer_id}/onlineMeetings",
        token,
        "Lookup onlineMeeting by JoinWebUrl",
        docname=self.name,
        params={"$filter": f"JoinWebUrl eq '{self.join_web_url}'"},
        timeout=30,
        extra={"join_web_url": self.join_web_url, "organizer_id": organizer_id},
    )
    if lookup.status_code != 200:
        return False

    meetings = lookup.json().get("value", [])
    if not meetings:
        return False

    real_meeting_id = meetings[0]["id"]
    # _log(
    #     f"OK: Found onlineMeeting - {self.name}",
    #     f"id={real_meeting_id}\nvalue_count={len(meetings)}",
    #     self.name,
    # )

    # *** NO DB WRITE HERE *** — keep the row untouched while we make more
    # Graph calls. We'll persist online_meeting_id together with raw_vtt at
    # the end in a single UPDATE.

    transcripts_url = (
        f"{GRAPH}/users/{organizer_id}/onlineMeetings/{real_meeting_id}/transcripts"
    )
    resp = _graph_get_logged(
        transcripts_url,
        token,
        "List transcripts",
        docname=self.name,
        timeout=30,
        extra={"online_meeting_id": real_meeting_id},
    )
    if resp.status_code != 200:
        return False

    transcripts = resp.json().get("value", [])
    if not transcripts:
        # No transcript yet. Do a best-effort, non-blocking write of the
        # meeting id so a later retry can reuse it — but never block the job
        # on it.
        _set_best_effort(self, online_meeting_id=real_meeting_id)
        return False

    transcript = _match_transcript(self, transcripts)
    if not transcript:
        _set_best_effort(self, online_meeting_id=real_meeting_id)
        return False

    content_url = transcript.get("transcriptContentUrl") or (
        f"{transcripts_url}/{transcript['id']}/content"
    )
    text = _download_content(content_url, token, self.name)
    if text is None:
        _set_best_effort(self, online_meeting_id=real_meeting_id)
        return False

    # Single write, everything together, at the end.
    return _save_transcript(
        self,
        text,
        transcript_id=transcript["id"],
        online_meeting_id=real_meeting_id,
    )


# ---------------------------------------------------------------------------
# peer-to-peer / ad hoc calls
# ---------------------------------------------------------------------------


def _organizer_not_in_tenant(resp):
	if resp.status_code != 404:
		return False
	try:
		message = resp.json().get("error", {}).get("message") or ""
	except Exception:
		return False
	return "failed to find user" in message.lower()


def _adhoc_transcript_urls(organizer_id, start_iso, end_iso):
	args = [
		f"userId='{organizer_id}'",
		f"userId={organizer_id}",
	]
	bases = [
		f"{GRAPH}/users/{organizer_id}/adhocCalls/getAllTranscripts",
		f"{GRAPH}/adhocCalls/getAllTranscripts",
	]
	urls = []
	for base in bases:
		for arg in args:
			urls.append(
				f"{base}({arg},startDateTime={start_iso},endDateTime={end_iso})"
			)
	return urls


def get_transcript_adhoc_for_doc(self):
	from productivity_next.meeting_sync.teams.token_manager import get_access_token

	organizer_id = self.organizer_user_id
	token = get_access_token()

	if not self.actual_start:
		_log(
			f"Teams Adhoc Transcript Skipped - {self.name}",
			"actual_start is empty; cannot build the date window.",
			self.name,
		)
		return False

	start_iso = _utc_iso(self.actual_start, shift_minutes=-10)
	end_iso = _utc_iso(self.actual_end or now_datetime(), shift_minutes=120)

	# _log(
	# 	f"OK: Adhoc Transcript Sweep - {self.name}",
	# 	f"organizer={organizer_id}\nstart={start_iso}\nend={end_iso}",
	# 	self.name,
	# )

	transcripts = None
	last_error = None

	for url in _adhoc_transcript_urls(organizer_id, start_iso, end_iso):
		resp = _graph_get_logged(
			url,
			token,
			"getAllTranscripts",
			docname=self.name,
			timeout=60,
			extra={"start": start_iso, "end": end_iso},
		)
		if resp.status_code == 200:
			transcripts = resp.json().get("value", [])
			break
		if _organizer_not_in_tenant(resp):
			# External organizer: Graph has no transcripts for them, so there is
			# nothing to fetch and nothing to report.
			return False
		last_error = f"url={url}\n{_describe_error(resp)}"
		if resp.status_code == 403:
			break

	if transcripts is None:
		_log(
			f"Teams Adhoc Transcript API Error - {self.name}",
			last_error or "no response",
			self.name,
		)
		return False

	if not transcripts:
		# _log(
		# 	f"Teams Adhoc Transcript Not Found - {self.name}",
		# 	f"organizer={organizer_id}\nstart={start_iso}\nend={end_iso}",
		# 	self.name,
		# )
		return False

	matched = _match_transcript(self, transcripts)
	if not matched:
		return False

	content_url = matched.get("transcriptContentUrl")
	if not content_url and matched.get("callId"):
		content_url = (
			f"{GRAPH}/users/{organizer_id}/adhocCalls/{matched['callId']}"
			f"/transcripts/{quote(matched['id'], safe='')}/content"
		)

	if not content_url:
		_log(
			f"Teams Adhoc Transcript Content URL Missing - {self.name}",
			frappe.as_json(matched),
			self.name,
		)
		return False

	text = _download_content(content_url, token, self.name)
	if text is None:
		return False

	return _save_transcript(
		self,
		text,
		transcript_id=matched.get("id"),
		call_id=matched.get("callId"),
	)


# ---------------------------------------------------------------------------
# retry sweep
# ---------------------------------------------------------------------------


def retry_pending_transcripts():
	"""Scheduled every 30 minutes. Teams publishes a transcript some minutes after the call,
	so the attempt made right after the call record usually finds nothing. Retry calls that
	ended between 15 minutes and TRANSCRIPT_RETRY_HOURS ago and still have no transcript."""
	from productivity_next.meeting_sync.teams.webhook import MIN_MEETING_DURATION_SECONDS

	now = now_datetime()
	rows = frappe.db.sql(
		"""SELECT name FROM `tabMeeting Call Log`
		WHERE provider = 'Microsoft Teams'
		  AND IFNULL(raw_vtt, '') = ''
		  AND IFNULL(organizer_user_id, '') != ''
		  AND actual_end BETWEEN %(oldest)s AND %(newest)s
		  AND TIMESTAMPDIFF(SECOND, actual_start, actual_end) >= %(min_seconds)s
		ORDER BY actual_end DESC
		LIMIT 50""",
		{
			"oldest": now - timedelta(hours=TRANSCRIPT_RETRY_HOURS),
			"newest": now - timedelta(minutes=15),
			"min_seconds": MIN_MEETING_DURATION_SECONDS,
		},
		pluck=True,
	)
	for name in rows:
		frappe.enqueue(
			"productivity_next.meeting_sync.teams.transcript.fetch_transcript_for_doc",
			docname=name,
			queue="long",
			job_id=f"ms-teams-transcript::{name}",
			deduplicate=True,
		)


def _set_best_effort(doc, **fields):
    """Try a non-critical write; give up quickly if the row is locked.
    Used for intermediate bookkeeping that must never block the transcript pull.
    """
    try:
        frappe.db.sql("SET SESSION innodb_lock_wait_timeout = 3")
    except Exception:
        pass

    try:
        frappe.db.set_value(
            "Meeting Call Log", doc.name, fields, update_modified=False
        )
        frappe.db.commit()
        for k, v in fields.items():
            doc.set(k, v)
    except Exception:
        frappe.db.rollback()
        frappe.log_error(
            title=f"Meeting Call Log best-effort update failed - {doc.name}",
            message=f"fields={list(fields)}\n\n{frappe.get_traceback()}",
            reference_doctype="Meeting Call Log",
            reference_name=doc.name,
        )
    finally:
        try:
            frappe.db.sql("SET SESSION innodb_lock_wait_timeout = DEFAULT")
        except Exception:
            pass




import frappe
import requests
from urllib.parse import quote


def get_user_id_by_email(access_token, email):
    """
    Resolve a user's email (UPN) to their Microsoft Graph user GUID.
    Graph's /onlineMeetings endpoint requires a GUID, not an email.
    """
    url = f"https://graph.microsoft.com/v1.0/users/{quote(email, safe='')}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    resp = requests.get(url, headers=headers, timeout=30)

    if not resp.ok:
        frappe.log_error(
            title="Graph User Lookup Failed",
            message=(
                f"Email: {email}\n"
                f"Request URL: {resp.url}\n"
                f"HTTP Status: {resp.status_code}\n"
                f"Response: {resp.text}"
            ),
        )
        frappe.throw(
            f"Could not resolve user '{email}' to a GUID. "
            f"Microsoft Graph returned HTTP {resp.status_code}. "
            "Check the Error Log for details."
        )

    try:
        data = resp.json()
    except ValueError:
        frappe.log_error(
            title="Invalid Graph User Lookup Response",
            message=resp.text,
        )
        frappe.throw("Microsoft Graph returned invalid JSON during user lookup.")

    user_id = data.get("id")
    if not user_id:
        frappe.throw(f"No 'id' returned for user '{email}'.")

    return user_id


def update_meeting_subject(meeting_log_name):
	"""
	Fetch the Microsoft Teams meeting subject using join_web_url, store it on the
	Meeting Call Log and fill it into the log's own Meeting (only if empty).
	"""
	from productivity_next.meeting_sync.teams.resource import organizer_from_join_url
	from productivity_next.meeting_sync.teams.webhook import _is_internal

	doc = frappe.get_doc("Meeting Call Log", meeting_log_name)
	join_web_url = doc.get("join_web_url")
	organizer = (doc.get("organizer_email") or "").strip().lower()
	if not join_web_url:
		return

	# The meeting belongs to the owner named in its link, not necessarily to the call
	# organizer (whoever started the call). Graph only resolves meetings of our own
	# tenant, and only under their owner; for anything else it answers 403.
	link_tenant, link_owner = organizer_from_join_url(join_web_url)
	our_tenant = frappe.db.get_single_value("Meeting Sync Settings", "tenant_id")
	if link_tenant and our_tenant and link_tenant.lower() != our_tenant.lower():
		return
	if not link_owner and not _is_internal(organizer):
		return

	try:
		access_token = get_access_token()
		organizer_id = link_owner or doc.get("organizer_user_id") or get_user_id_by_email(access_token, organizer)

		# Do NOT pre-encode join_web_url: requests encodes the $filter value once.
		response = requests.get(
			f"{GRAPH}/users/{quote(organizer_id, safe='')}/onlineMeetings",
			headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
			params={"$filter": f"JoinWebUrl eq '{join_web_url}'"},
			timeout=30,
		)
	except Exception:
		frappe.log_error(
			title=f"Teams Meeting Subject Fetch Failed - {doc.name}",
			message=frappe.get_traceback(),
			reference_doctype="Meeting Call Log",
			reference_name=doc.name,
		)
		return

	if response.status_code == 404:
		# 3004 "Specified meeting is not found": the meeting was deleted or was a "Meet now"
		# meeting that has expired; there is no subject to fetch
		return

	if not response.ok:
		frappe.log_error(
			title=f"Teams Meeting Subject Fetch Failed - {doc.name}",
			message=(
				f"Organizer Email: {organizer}\n"
				f"Request URL: {response.url}\n"
				f"HTTP Status: {response.status_code}\n"
				f"Response: {response.text[:2000]}"
			),
			reference_doctype="Meeting Call Log",
			reference_name=doc.name,
		)
		return

	meetings = (response.json() or {}).get("value") or []
	subject = (meetings[0].get("subject") or "").strip()[:140] if meetings else ""  # Data fields
	if not subject:
		# ad hoc calls and "Meet now" meetings have no subject; nothing to map
		return

	if doc.get("meeting_subject") != subject:
		doc.db_set("meeting_subject", subject, update_modified=False)
	update_linked_meeting_subject(doc, subject)

	return {
		"success": True,
		"meeting_log": doc.name,
		"meeting_subject": subject,
	}


def update_linked_meeting_subject(meeting_log=None, subject=None):
	"""
	Fill the Teams subject into the Meeting created from this log, if its subject is empty.

	Only this log's own Meeting is touched, and it is never re-linked: matching by
	join_web_url used to pick another occurrence of a recurring meeting and move it to
	this log, so the new call never got a Meeting of its own.
	"""
	if not meeting_log:
		return

	if isinstance(meeting_log, str):
		if not frappe.db.exists("Meeting Call Log", meeting_log):
			return
		doc = frappe.get_doc("Meeting Call Log", meeting_log)
	else:
		doc = meeting_log

	final_subject = subject or doc.get("meeting_subject")
	if not final_subject:
		return

	meeting_name = frappe.db.get_value("Meeting", {"meeting_call_log": doc.name}, "name")
	if not meeting_name:
		# the Meeting is created later; add_meeting copies meeting_subject then
		return

	current = (frappe.db.get_value("Meeting", meeting_name, "subject") or "").strip()
	if current:
		# keep what the user (or the AI) already set
		return

	frappe.db.set_value("Meeting", meeting_name, "subject", final_subject, update_modified=True)
	frappe.logger("meeting_sync").info(
		f"Set Meeting {meeting_name} subject to '{final_subject}' from Meeting Call Log {doc.name}"
	)

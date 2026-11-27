"""Google Workspace access for the Meet sync: a service account with domain-wide delegation
impersonates one Workspace user per call, and talks REST through google-auth's
AuthorizedSession (no discovery client needed).

APIs used:
- Meet REST API v2: conferenceRecords, participants, transcripts, transcripts.entries, spaces
- Calendar API v3: events (subject, organizer and invited e-mails of a meeting)
- Admin SDK Directory API: users.get (Meet gives participant ids, not e-mails)
"""

import json
import time

import frappe

MEET_BASE = "https://meet.googleapis.com/v2"
CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"
DIRECTORY_BASE = "https://admin.googleapis.com/admin/directory/v1"

SCOPE_MEET_READ = "https://www.googleapis.com/auth/meetings.space.readonly"
SCOPE_MEET_SETTINGS = "https://www.googleapis.com/auth/meetings.space.settings"
SCOPE_CALENDAR_READ = "https://www.googleapis.com/auth/calendar.events.readonly"
SCOPE_DIRECTORY_READ = "https://www.googleapis.com/auth/admin.directory.user.readonly"

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
RETRY_DELAYS = (0, 2, 5, 10)


class GoogleAPIError(Exception):
	def __init__(self, status, url, body):
		self.status = status
		self.url = url
		self.body = body
		super().__init__(f"Google API {status} for {url}: {body[:500]}")


def _service_account_info():
	settings = frappe.get_cached_doc("Meeting Sync Settings")
	file_url = settings.get("google_service_account_key")
	if not file_url:
		frappe.throw("Upload the Google service account key in Meeting Sync Settings.")
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()
	if isinstance(content, bytes):
		content = content.decode("utf-8")
	return json.loads(content)


def get_session(subject, scopes):
	"""AuthorizedSession acting as `subject` (a Workspace user's e-mail). Ask only for the
	scopes a call needs: a token request for any scope not granted to the service account
	in domain-wide delegation fails as a whole."""
	from google.auth.transport.requests import AuthorizedSession
	from google.oauth2 import service_account

	# per request / job: a token is reused within a job, never kept across sites
	if not getattr(frappe.local, "meeting_sync_google_sessions", None):
		frappe.local.meeting_sync_google_sessions = {}
	cache = frappe.local.meeting_sync_google_sessions
	key = (subject, tuple(sorted(scopes)))
	if key not in cache:
		credentials = service_account.Credentials.from_service_account_info(
			_service_account_info(), scopes=list(scopes), subject=subject
		)
		cache[key] = AuthorizedSession(credentials)
	return cache[key]


def request(session, method, url, params=None, json_body=None, timeout=60):
	"""One call with retry on 429/5xx. Returns the parsed JSON (or {} for an empty body);
	raises GoogleAPIError on any other error status."""
	res = None
	for delay in RETRY_DELAYS:
		if delay:
			time.sleep(delay)
		res = session.request(method, url, params=params, json=json_body, timeout=timeout)
		if res.status_code not in RETRYABLE_STATUS:
			break
	if res.status_code >= 400:
		raise GoogleAPIError(res.status_code, url, res.text)
	return res.json() if res.content else {}


def paginate(session, url, items_key, params=None, page_size=100, page_size_param="pageSize"):
	"""Every item across pages of a Google list call (nextPageToken / pageToken)."""
	params = dict(params or {})
	params.setdefault(page_size_param, page_size)
	while True:
		body = request(session, "GET", url, params=params)
		yield from body.get(items_key) or []
		token = body.get("nextPageToken")
		if not token:
			return
		params["pageToken"] = token


def admin_email():
	return (frappe.db.get_single_value("Meeting Sync Settings", "google_admin_email") or "").strip()


def directory_email(user_resource):
	"""E-mail for a Meet participant id ("users/1234..."), via the Admin Directory. Only
	users of this Workspace resolve; others return None. Cached for a day."""
	if not user_resource:
		return None
	user_id = user_resource.split("/")[-1]
	cache_key = f"meeting_sync:gdir:{user_id}"
	cached = frappe.cache().get_value(cache_key)
	if cached is not None:
		return cached or None
	email = ""
	admin = admin_email()
	if admin:
		try:
			session = get_session(admin, [SCOPE_DIRECTORY_READ])
			body = request(session, "GET", f"{DIRECTORY_BASE}/users/{user_id}", params={"fields": "primaryEmail"})
			email = (body.get("primaryEmail") or "").strip().lower()
		except GoogleAPIError as e:
			if e.status not in (403, 404):
				raise
	frappe.cache().set_value(cache_key, email, expires_in_sec=24 * 3600)
	return email or None

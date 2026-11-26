"""Turn on "Record and transcribe automatically" for upcoming Teams meetings.

Teams has no tenant-wide default for this meeting option, so this job sets it through
Microsoft Graph for every Teams meeting an internal user organizes in the next
LOOKAHEAD_DAYS days. A recurring series shares one onlineMeeting, so one change covers it.

Needs on the Azure app (Meeting Sync Settings): OnlineMeetings.ReadWrite.All and
Calendars.ReadBasic.All (application permissions with admin consent).

Runs only where Teams sync is enabled (see productivity_next.meeting_sync.common.is_enabled) and
"Turn On Recording and Transcription Automatically" is ticked in Meeting Sync Settings.
"""

from datetime import datetime, timedelta, timezone

import frappe
import requests

from productivity_next.meeting_sync.teams.resource import find_online_meeting_by_join_url
from productivity_next.meeting_sync.teams.subscriptions import is_teams_sync_enabled
from productivity_next.meeting_sync.teams.token_manager import get_access_token
from productivity_next.meeting_sync.teams.webhook import GRAPH_BASE, _is_internal

LOOKAHEAD_DAYS = 14
# Meetings already set are remembered so each run only looks them up once.
DONE_CACHE_SECONDS = LOOKAHEAD_DAYS * 24 * 3600
# A meeting that fails is logged once a day, not every run.
ERROR_CACHE_SECONDS = 24 * 3600


def _cache_key(kind, meeting_key):
    return f"meeting_sync:teams_auto_transcribe:{kind}:{frappe.safe_encode(meeting_key).hex()[:200]}"


def _organizer_emails():
    """Company e-mail of every active Employee on an internal domain."""
    rows = frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["user_id", "company_email"],
    )
    emails = set()
    for row in rows:
        for email in (row.company_email, row.user_id):
            if email and _is_internal(email):
                emails.add(email.strip().lower())
                break
    return sorted(emails)


def _teams_meetings_in_calendar(email, headers, start, end):
    """{joinUrl: (organizer email, subject)} for Teams meetings in this user's calendar
    that an internal user organizes. A delegate's calendar also shows the boss's
    meetings as "isOrganizer", so the organizer is taken from the event itself."""
    url = f"{GRAPH_BASE}/users/{email}/calendarView"
    params = {
        "startDateTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endDateTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        # isOnlineMeeting must be selected, else Graph returns onlineMeeting as null
        "$select": "subject,isOnlineMeeting,onlineMeeting,isOrganizer,isCancelled,organizer",
        "$top": 100,
    }
    found = {}
    while url:
        res = requests.get(url, params=params, headers=headers, timeout=60)
        if res.status_code in (403, 404):
            # no mailbox / no Exchange licence: nothing to do for this person
            return {}
        res.raise_for_status()
        body = res.json()
        for ev in body.get("value") or []:
            join_url = (ev.get("onlineMeeting") or {}).get("joinUrl")
            organizer = ((ev.get("organizer") or {}).get("emailAddress") or {}).get("address") or ""
            organizer = organizer.strip().lower()
            if (
                ev.get("isOrganizer")
                and ev.get("isOnlineMeeting")
                and join_url
                and not ev.get("isCancelled")
                and _is_internal(organizer)
            ):
                found.setdefault(join_url, (organizer, ev.get("subject") or ""))
        url = body.get("@odata.nextLink")
        params = None
    return found


def _user_id(email, headers, ids):
    if email not in ids:
        res = requests.get(f"{GRAPH_BASE}/users/{email}?$select=id", headers=headers, timeout=30)
        ids[email] = res.json().get("id") if res.status_code == 200 else None
    return ids[email]


def run(dry_run=False, only_emails=None):
    """Scheduled every 10 minutes. Returns a summary dict (used by dry runs)."""
    if not is_teams_sync_enabled():
        return {"skipped": "Teams sync is not enabled"}
    if not frappe.db.get_single_value("Meeting Sync Settings", "teams_auto_transcribe"):
        return {"skipped": "turned off in Meeting Sync Settings"}

    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    cache = frappe.cache()
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=LOOKAHEAD_DAYS)
    summary = {"calendars": 0, "meetings": 0, "already_on": 0, "turned_on": [], "failed": []}

    meetings = {}
    for email in only_emails or _organizer_emails():
        try:
            for join_url, value in _teams_meetings_in_calendar(email, headers, start, end).items():
                meetings.setdefault(join_url, value)
            summary["calendars"] += 1
        except Exception:
            summary["failed"].append((email, "calendar read failed"))
            if not dry_run:
                frappe.log_error(
                    title="Teams auto transcribe: calendar read failed",
                    message=f"{email}\n{frappe.get_traceback()}",
                )

    ids = {}
    for join_url, (organizer, subject) in meetings.items():
        summary["meetings"] += 1
        if cache.get_value(_cache_key("done", join_url)):
            summary["already_on"] += 1
            continue
        try:
            user_id = _user_id(organizer, headers, ids)
            if not user_id:
                raise Exception("organizer not found in Microsoft 365")
            meeting = find_online_meeting_by_join_url(user_id, join_url, token)
            if not meeting:
                raise Exception("onlineMeeting not found for joinUrl")
            if meeting.get("recordAutomatically"):
                summary["already_on"] += 1
                if not dry_run:
                    cache.set_value(_cache_key("done", join_url), 1, expires_in_sec=DONE_CACHE_SECONDS)
                continue
            if dry_run:
                summary["turned_on"].append((organizer, subject))
                continue
            res = requests.patch(
                f"{GRAPH_BASE}/users/{user_id}/onlineMeetings/{meeting['id']}",
                json={"recordAutomatically": True},
                headers={**headers, "Content-Type": "application/json"},
                timeout=60,
            )
            if res.status_code != 200:
                raise Exception(f"PATCH {res.status_code}: {res.text[:500]}")
            summary["turned_on"].append((organizer, subject))
            cache.set_value(_cache_key("done", join_url), 1, expires_in_sec=DONE_CACHE_SECONDS)
        except Exception as e:
            summary["failed"].append((organizer, subject, str(e)[:200]))
            if not dry_run and not cache.get_value(_cache_key("err", join_url)):
                cache.set_value(_cache_key("err", join_url), 1, expires_in_sec=ERROR_CACHE_SECONDS)
                frappe.log_error(
                    title="Teams auto transcribe failed",
                    message=f"organizer={organizer}\nsubject={subject}\njoinUrl={join_url}\n{e}",
                )

    if summary["turned_on"] and not dry_run:
        frappe.logger("teams_auto_transcribe").info(f"turned on: {summary['turned_on']}")
    return summary

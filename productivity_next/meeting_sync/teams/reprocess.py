import glob
import json
import os

import frappe
import requests

from productivity_next.meeting_sync.teams.resource import (
    GRAPH_BASE,
    _graph_get,
    call_record_url,
    fetch_call_record,
    fetch_scheduled_attendees,
    fetch_transcript_vtt,
    iter_call_record_identities,
    meeting_organizer_id,
    parse_transcript_resource,
)
from productivity_next.meeting_sync.common import TEAMS
from productivity_next.meeting_sync.teams.token_manager import get_access_token
from productivity_next.meeting_sync.teams.webhook import (
    MIN_MEETING_DURATION_SECONDS,
    _get_internal_domains,
    _call_duration_seconds,
    _extract_emails_from_record,
    _normalize_participant_emails,
    _parse_dt,
    _parse_vtt,
    _meeting_for_log,
    _should_create_meeting,
    add_meeting,
    participants_from_log,
    process_transcript,
)

_FAILED_RESOURCE_MARKER = "[TRANSCRIPT] Bad resource format: "


def _iter_frappe_log_files():
    seen = set()
    site_log_dir = frappe.get_site_path("logs")
    for path in sorted(glob.glob(os.path.join(site_log_dir, "frappe.log*"))):
        seen.add(path)
        yield path

    bench_log_dir = os.path.abspath(os.path.join(frappe.get_site_path(), "..", "..", "logs"))
    if os.path.isdir(bench_log_dir):
        for path in sorted(glob.glob(os.path.join(bench_log_dir, "frappe.log*"))):
            if path not in seen:
                seen.add(path)
                yield path


def extract_failed_transcript_resources():
    resources = []
    seen = set()

    for log_path in _iter_frappe_log_files():
        try:
            with open(log_path, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if _FAILED_RESOURCE_MARKER not in line:
                        continue
                    resource = line.split(_FAILED_RESOURCE_MARKER, 1)[1].strip()
                    if resource and resource not in seen:
                        seen.add(resource)
                        resources.append(resource)
        except OSError as err:
            frappe.logger().warning(f"[REPROCESS] Could not read log file {log_path}: {err}")

    return resources


def _get_log_for_transcript(transcript_id):
    return frappe.db.get_value(
        "Meeting Call Log",
        {"transcript_id": transcript_id, "provider": TEAMS},
        ["name", "status", "raw_vtt"],
        as_dict=True,
    )


def reprocess_transcript_resource(resource, skip_if_complete=1):
    """Reprocess a single transcript notification resource string."""
    skip_if_complete = frappe.utils.cint(skip_if_complete)
    user_id, meeting_id, transcript_id = parse_transcript_resource(resource)
    if not all((user_id, meeting_id, transcript_id)):
        return {
            "status": "error",
            "resource": resource,
            "message": "Could not parse transcript resource",
        }

    if skip_if_complete:
        existing = _get_log_for_transcript(transcript_id)
        if existing and existing.status == "Complete" and existing.raw_vtt:
            return {
                "status": "skipped",
                "resource": resource,
                "transcript_id": transcript_id,
                "teams_meeting_log": existing.name,
                "message": "Already complete with VTT content",
            }

    try:
        process_transcript({"resource": resource})
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"reprocess_transcript_resource: {transcript_id}")
        return {
            "status": "error",
            "resource": resource,
            "transcript_id": transcript_id,
            "message": frappe.get_traceback(),
        }

    log_doc = _get_log_for_transcript(transcript_id)
    if not log_doc:
        return {
            "status": "error",
            "resource": resource,
            "transcript_id": transcript_id,
            "message": "Processed but no Meeting Call Log was created",
        }

    if log_doc.status == "Transcript Fetch Failed" or not log_doc.raw_vtt:
        return {
            "status": "forbidden",
            "resource": resource,
            "transcript_id": transcript_id,
            "teams_meeting_log": log_doc.name,
            "message": (
                "Transcript ID saved but Graph returned no VTT content. "
                "Configure Teams Application Access Policy (see verify_transcript_access)."
            ),
        }

    return {
        "status": "success",
        "resource": resource,
        "transcript_id": transcript_id,
        "teams_meeting_log": log_doc.name,
    }


@frappe.whitelist()
def verify_transcript_access(user_id=None):
    """Test whether the Azure app can fetch transcript content for a user."""
    frappe.only_for("System Manager")
    from productivity_next.meeting_sync.teams.token_manager import get_access_token

    settings = frappe.get_single("Meeting Sync Settings")
    client_id = settings.client_id
    token = get_access_token()

    if not user_id:
        user_id = frappe.db.get_value(
            "Meeting Call Log",
            {"organizer_user_id": ["is", "set"], "provider": TEAMS},
            "organizer_user_id",
            order_by="actual_start desc",
        )

    result = {
        "client_id": client_id,
        "user_id": user_id,
        "meeting_access_ok": False,
        "transcript_access_ok": False,
        "policy_required": True,
        "powershell": [
            "Install-Module -Name MicrosoftTeams -Force -AllowClobber",
            "Connect-MicrosoftTeams",
            f'New-CsApplicationAccessPolicy -Identity "FinbyzMeetingLogs" -AppIds "{client_id}" -Description "Allow FinbyzMeetingLogs app to read Teams transcripts"',
            'Grant-CsApplicationAccessPolicy -PolicyName "FinbyzMeetingLogs" -Global',
        ],
        "notes": [
            "Azure app permissions alone are not enough for transcript download.",
            "A Teams Application Access Policy must grant this app access to user meeting data.",
            "Policy changes can take up to 30 minutes to propagate.",
        ],
    }

    if not user_id:
        result["error"] = "No organizer_user_id found on any Meeting Call Log"
        return result

    headers = {"Authorization": f"Bearer {token}"}
    meetings_res = requests.get(
        f"https://graph.microsoft.com/v1.0/users/{user_id}/onlineMeetings?$top=1",
        headers=headers,
        timeout=30,
    )
    result["meeting_access_status"] = meetings_res.status_code
    result["meeting_access_ok"] = meetings_res.status_code == 200
    if meetings_res.status_code != 200:
        result["meeting_access_error"] = meetings_res.text[:500]

    rows = frappe.db.sql(
        """SELECT online_meeting_id, transcript_id FROM `tabMeeting Call Log`
        WHERE provider = 'Microsoft Teams' AND organizer_user_id = %s AND transcript_id IS NOT NULL AND transcript_id != ''
        ORDER BY modified DESC LIMIT 1""",
        user_id,
        as_dict=True,
    )
    if rows:
        row = rows[0]
        content_res = fetch_transcript_vtt(
            user_id, row.online_meeting_id, row.transcript_id, token
        )
        result["transcript_access_status"] = content_res.status_code
        result["transcript_access_ok"] = content_res.status_code == 200
        if content_res.status_code != 200:
            result["transcript_access_error"] = content_res.text[:500]
    else:
        result["transcript_test"] = "skipped_no_transcript_id"

    return result


def _extract_emails_from_log(doc):
    """Rebuild participant emails from stored Meeting Call Log data (and the meeting's
    scheduled attendees), the same way the transcript path does."""
    return participants_from_log(doc)


def _discussion_from_log(doc):
    return doc.get("meeting_subject") or "Online Meeting"


def reprocess_call_record_from_log(log_name, force=0):
    """Re-fetch call record from Graph and update participant fields on a log."""
    force = frappe.utils.cint(force)
    doc = frappe.get_doc("Meeting Call Log", log_name)
    if not doc.call_id:
        return {"status": "error", "message": "No call_id on log"}

    token = get_access_token()
    res = fetch_call_record(doc.call_id, token)
    res.raise_for_status()
    record = res.json()

    organizer_v2 = record.get("organizer_v2") or {}
    org_user = (organizer_v2.get("identity") or {}).get("user") or {}
    organizer_user_id = org_user.get("id", "")
    join_web_url = record.get("joinWebUrl", "")

    scheduled_attendees = fetch_scheduled_attendees(
        meeting_organizer_id(join_web_url, organizer_user_id), join_web_url, token
    )
    participant_emails, display_names = _extract_emails_from_record(
        record, token, scheduled_attendees=scheduled_attendees
    )

    doc.organizer = org_user.get("displayName") or doc.organizer
    doc.organizer_email = org_user.get("userPrincipalName") or doc.organizer_email
    doc.organizer_user_id = organizer_user_id or doc.organizer_user_id
    doc.join_web_url = join_web_url or doc.join_web_url
    doc.participants = ", ".join(filter(None, display_names))
    doc.participant_count = len(display_names)
    doc.raw_payload = json.dumps(record, indent=2)
    doc.save(ignore_permissions=True)

    result = {
        "status": "success",
        "teams_meeting_log": doc.name,
        "participants": doc.participants,
        "participant_count": doc.participant_count,
        "scheduled_attendees_found": len(scheduled_attendees),
    }

    if force or participant_emails or doc.organizer_email:
        meeting_result = reprocess_meeting_from_log(log_name, force=force)
        result["meeting"] = meeting_result

    return result


def reprocess_meeting_from_log(log_name, force=0):
    """Create or update a Meeting from a stored Meeting Call Log."""
    force = frappe.utils.cint(force)
    doc = frappe.get_doc("Meeting Call Log", log_name)

    # Only this log's own Meeting counts. A Meeting found by join_web_url may belong to
    # another occurrence of a recurring meeting.
    existing_meeting = _meeting_for_log(doc.name)

    if existing_meeting and not force:
        return {
            "status": "skipped",
            "teams_meeting_log": doc.name,
            "meeting": existing_meeting,
            "message": "Meeting already linked (use force=1 to reprocess)",
        }

    if not doc.actual_start or not doc.actual_end:
        # expected while only the transcript has arrived; the call record fills these in
        return {
            "status": "error",
            "teams_meeting_log": doc.name,
            "message": "Missing actual_start or actual_end",
        }

    if not _should_create_meeting(doc.actual_start, doc.actual_end):
        duration = _call_duration_seconds(doc.actual_start, doc.actual_end)
        return {
            "status": "skipped",
            "teams_meeting_log": doc.name,
            "message": f"Call lasted {duration:.0f}s, under {MIN_MEETING_DURATION_SECONDS}s",
        }

    participant_emails = _extract_emails_from_log(doc)
    if not participant_emails and not doc.get("organizer_email"):
        title = f"[REPROCESS] Meeting not created - no participants ({doc.name})"
        if not frappe.db.exists("Error Log", {"method": title}):  # retried every 30 min; report once
            frappe.log_error(title=title, message=f"call_id={doc.get('call_id')}")
        return {
            "status": "error",
            "teams_meeting_log": doc.name,
            "message": "No participant or organizer email found on log",
        }

    try:
        meeting_name = add_meeting(
            existing_meeting_name=existing_meeting if force else None,
            actual_start=doc.actual_start,
            actual_end=doc.actual_end,
            participant_emails=participant_emails,
            discussion=_discussion_from_log(doc),
            subject=doc.get("meeting_subject") or "",
            organizer_email=doc.get("organizer_email"),
            teams_meeting_log=doc.name,
            join_web_url=doc.join_web_url,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"reprocess_meeting_from_log: {log_name}")
        return {
            "status": "error",
            "teams_meeting_log": doc.name,
            "message": frappe.get_traceback(),
        }

    doc.db_set("is_meeting_created", 1, update_modified=False)

    meeting = frappe.get_doc("Meeting", meeting_name)
    return {
        "status": "success",
        "teams_meeting_log": doc.name,
        "meeting": meeting_name,
        "internal_meeting": meeting.internal_meeting,
        "party_type": meeting.party_type,
        "party": meeting.party,
    }


def backfill_meetings_from_logs(dry_run=0, limit=0, force=0, external_only=0):
    """Backfill Meeting records from Meeting Call Logs that have no linked Meeting."""
    dry_run = frappe.utils.cint(dry_run)
    limit = frappe.utils.cint(limit)
    force = frappe.utils.cint(force)
    external_only = frappe.utils.cint(external_only)

    filters = [["provider", "=", TEAMS], ["actual_start", "is", "set"], ["actual_end", "is", "set"]]
    if not force:
        filters.append(["is_meeting_created", "=", 0])
    if external_only:
        for domain in _get_internal_domains():
            filters.append(["organizer_email", "not like", f"%{domain}"])

    log_names = frappe.get_all(
        "Meeting Call Log",
        filters=filters,
        pluck="name",
        order_by="actual_start desc",
        limit=limit or None,
    )

    summary = {
        "found": len(log_names),
        "success": 0,
        "skipped": 0,
        "error": 0,
        "dry_run": bool(dry_run),
        "results": [],
    }

    for log_name in log_names:
        if dry_run:
            doc = frappe.get_doc("Meeting Call Log", log_name)
            summary["results"].append(
                {
                    "status": "dry_run",
                    "teams_meeting_log": log_name,
                    "organizer_email": doc.organizer_email,
                    "participant_emails": _extract_emails_from_log(doc),
                    "has_raw_payload": bool(doc.get("raw_payload")),
                }
            )
            continue

        result = reprocess_meeting_from_log(log_name, force=force)
        summary["results"].append(result)
        status = result.get("status")
        if status in summary:
            summary[status] += 1

    frappe.logger().info(f"[REPROCESS] Meeting backfill summary: {summary}")
    return summary


def backfill_failed_transcripts(dry_run=0, skip_if_complete=1):
    """Scan frappe logs and reprocess transcript notifications that failed parsing."""
    dry_run = frappe.utils.cint(dry_run)
    skip_if_complete = frappe.utils.cint(skip_if_complete)
    resources = extract_failed_transcript_resources()

    summary = {
        "found": len(resources),
        "success": 0,
        "forbidden": 0,
        "partial": 0,
        "skipped": 0,
        "error": 0,
        "dry_run": bool(dry_run),
        "results": [],
    }

    for resource in resources:
        if dry_run:
            user_id, meeting_id, transcript_id = parse_transcript_resource(resource)
            summary["results"].append(
                {
                    "status": "dry_run",
                    "resource": resource,
                    "transcript_id": transcript_id,
                    "user_id": user_id,
                    "meeting_id": meeting_id,
                }
            )
            continue

        result = reprocess_transcript_resource(resource, skip_if_complete=skip_if_complete)
        summary["results"].append(result)
        status = result.get("status")
        if status in summary:
            summary[status] += 1

    frappe.logger().info(f"[REPROCESS] Backfill summary: {summary['found']} found")
    return summary


def retry_missing_meetings():
    """Scheduled every 30 minutes. Re-run Meeting creation for calls that ended between
    10 minutes and 6 hours ago, lasted long enough, and still have no Meeting - e.g. after
    a transient database error during the webhook job. reprocess_meeting_from_log skips
    anything that should not get a Meeting."""
    now = frappe.utils.now_datetime()
    rows = frappe.db.sql(
        """SELECT t.name FROM `tabMeeting Call Log` t
        WHERE t.provider = 'Microsoft Teams'
          AND t.actual_end BETWEEN %(oldest)s AND %(newest)s
          AND TIMESTAMPDIFF(SECOND, t.actual_start, t.actual_end) >= %(min_seconds)s
          AND NOT EXISTS (SELECT 1 FROM `tabMeeting` m WHERE m.meeting_call_log = t.name)
        ORDER BY t.actual_end DESC
        LIMIT 50""",
        {
            "oldest": frappe.utils.add_to_date(now, hours=-6),
            "newest": frappe.utils.add_to_date(now, minutes=-10),
            "min_seconds": MIN_MEETING_DURATION_SECONDS,
        },
        pluck=True,
    )
    for name in rows:
        frappe.enqueue(
            "productivity_next.meeting_sync.teams.reprocess.reprocess_meeting_from_log",
            log_name=name,
            queue="long",
            job_id=f"ms-teams-reprocess::{name}",
            deduplicate=True,
        )


def refresh_call_records():
    """Scheduled every 30 minutes. Teams publishes a call record before the call is
    complete and keeps adding sessions to it for hours (a later version can start earlier
    and end later), but the subscription only notifies on creation. Re-read calls that
    ended in the last 6 hours and re-run the call record job for those whose start or end
    changed; it updates the log and a draft Meeting."""
    rows = frappe.get_all(
        "Meeting Call Log",
        filters={
            "provider": TEAMS,
            "actual_end": [">=", frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=-6)],
            "call_id": ["is", "set"],
        },
        fields=["name", "call_id", "actual_start", "actual_end"],
    )
    if not rows:
        return
    token = get_access_token()
    for row in rows:
        try:
            res = _graph_get(call_record_url(row.call_id), token)
            if res.status_code >= 400:
                continue
            record = res.json()
            start = _parse_dt(record.get("startDateTime"))
            end = _parse_dt(record.get("endDateTime"))
        except Exception:
            frappe.log_error(
                title=f"[CALL RECORD] Refresh failed ({row.name})",
                message=frappe.get_traceback(),
            )
            continue
        stored = tuple(d and d.replace(microsecond=0) for d in (row.actual_start, row.actual_end))
        if not start or not end or (start, end) == stored:
            continue
        frappe.enqueue(
            "productivity_next.meeting_sync.teams.webhook.process_call_record",
            notification={"resourceData": {"id": row.call_id}},
            queue="long",
            job_id=f"ms-teams-call-refresh::{row.call_id}",
            deduplicate=True,
        )



SWEEP_HOURS = 3
SWEEP_WINDOW_MINUTES = 30   # a single long startDateTime range returns nothing; query in slices


def sync_missing_call_records():
    """Scheduled every 30 minutes. Ask Graph for the calls of the last SWEEP_HOURS hours and
    run the call record job for any call that has no Meeting Call Log, so a lost
    notification (subscription gap, endpoint down) does not lose the Meeting."""
    from datetime import datetime, timedelta, timezone

    token = get_access_token()
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = end - timedelta(hours=SWEEP_HOURS)
    while start < end:
        stop = min(start + timedelta(minutes=SWEEP_WINDOW_MINUTES), end)
        url = (
            f"{GRAPH_BASE}/communications/callRecords?$select=id&$filter=startDateTime ge "
            f"{start:%Y-%m-%dT%H:%M:%SZ} and startDateTime lt {stop:%Y-%m-%dT%H:%M:%SZ}"
        )
        while url:
            try:
                res = _graph_get(url, token, timeout=60)
                res.raise_for_status()
                page = res.json()
            except Exception:
                frappe.log_error(
                    title="[CALL RECORD] Sweep for missing calls failed",
                    message=frappe.get_traceback(),
                )
                return
            for call in page.get("value", []):
                if frappe.db.exists("Meeting Call Log", {"call_id": call["id"]}):
                    continue
                frappe.enqueue(
                    "productivity_next.meeting_sync.teams.webhook.process_call_record",
                    notification={"resourceData": {"id": call["id"]}},
                    queue="long",
                    job_id=f"ms-teams-call-sweep::{call['id']}",
                    deduplicate=True,
                )
            url = page.get("@odata.nextLink")
        start = stop

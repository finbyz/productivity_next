import re
import hmac
import html
import time
import json
import requests
import frappe
from datetime import datetime, timedelta
from werkzeug.wrappers import Response
from productivity_next.meeting_sync.common import DEFAULT_DISCUSSIONS, TEAMS, is_enabled
from productivity_next.meeting_sync.teams.token_manager import get_access_token
from productivity_next.meeting_sync.teams.resource import (
    GRAPH_BASE,
    fetch_call_record,
    fetch_online_meeting,
    fetch_scheduled_attendees,
    fetch_transcript_metadata,
    fetch_transcript_vtt,
    find_online_meeting_by_join_url,
    iter_call_record_identities,
    meeting_organizer_id,
    parse_call_record_id,
    parse_transcript_resource,
)

DEFAULT_INTERNAL_DOMAINS = "@finbyz.tech"
MIN_MEETING_DURATION_SECONDS = 120  # skip Meeting creation for calls under 2 minutes
# Meeting.party_type options; any other party a contact is linked to (Prospect, Sales
# Partner, ...) is not a valid value and would make the Meeting insert fail
MEETING_PARTY_TYPES = ("Customer", "Supplier", "Lead")
# Data fields (Meeting.subject, Meeting Call Log.meeting_subject) hold 140 characters
SUBJECT_MAX_LENGTH = 140

# Subscription renewal. Graph maximums: callRecord 4,230 min, callTranscript 4,320 min.
# 4,200 stays safely under both.
SUBSCRIPTION_RENEW_MINUTES = 4200
# Graph warns against reauthorize + PATCH on the same subscription within 10 minutes.
SUBSCRIPTION_RENEW_GUARD_SECONDS = 600

# Call record fetch can 404 briefly right after the call ends; retry with backoff.
CALL_RECORD_RETRY_DELAYS = (0, 10, 30, 60)
CALL_RECORD_RETRYABLE_STATUS = {404, 429, 500, 502, 503, 504}


def _call_duration_seconds(actual_start, actual_end):
    if not actual_start or not actual_end:
        return None
    return (actual_end - actual_start).total_seconds()


def _should_create_meeting(actual_start, actual_end):
    duration = _call_duration_seconds(actual_start, actual_end)
    if duration is None:
        return False
    return duration >= MIN_MEETING_DURATION_SECONDS


def _fit(value, length=SUBJECT_MAX_LENGTH):
    """Trim a value so it fits a Data field instead of failing the save."""
    return (value or "").strip()[:length]


def _meeting_for_log(log_name):
    """The Meeting created from a Meeting Call Log: the Meeting's own link is the only source."""
    if not log_name:
        return None
    return frappe.db.get_value("Meeting", {"meeting_call_log": log_name}, "name")


def _get_internal_domains():
    settings = frappe.get_single("Meeting Sync Settings")
    raw = (settings.get("internal_email_domains") or DEFAULT_INTERNAL_DOMAINS).strip()
    domains = [d.strip().lower() for d in raw.split(",") if d.strip()]
    return domains or [DEFAULT_INTERNAL_DOMAINS]


def _parse_dt(dt_str):
    # Graph timestamps are UTC; stored in the site's time zone (the original code
    # added a fixed +05:30, which is the same for an IST site).
    from productivity_next.meeting_sync.common import utc_to_system

    return utc_to_system(dt_str)


def _is_internal(email):
    if not email:
        return False
    email = email.strip().lower()
    return any(email.endswith(domain) for domain in _get_internal_domains())


def _normalize_participant_emails(participant_emails, organizer_email=None):
    emails = [e.strip().lower() for e in (participant_emails or []) if e and e.strip()]
    if organizer_email:
        org = organizer_email.strip().lower()
        if org and org not in emails:
            emails.insert(0, org)
    return emails


def _is_internal_meeting(participant_emails, organizer_email=None):
    """External if organizer or any participant uses a non-company email."""
    if organizer_email and not _is_internal(organizer_email):
        return False
    emails = _normalize_participant_emails(participant_emails, organizer_email=None)
    for email in emails:
        if not _is_internal(email):
            return False
    return True


def _resolve_employee(email):
    rows = frappe.get_all(
        "Employee",
        filters={"user_id": email.strip().lower()},
        fields=["name", "employee_name", "status"],
        order_by="creation desc",
    )
    active = [r for r in rows if r.status == "Active"]
    return (active or rows or [None])[0]


def _resolve_contact_and_party(email):
    rows = frappe.db.sql(
        """SELECT parent FROM `tabContact Email`
        WHERE email_id = %s AND parenttype = 'Contact' LIMIT 1""",
        email.strip().lower(), as_dict=True,
    )
    if not rows:
        return None, None, None
    contact_name = rows[0].parent
    links = frappe.db.sql(
        """SELECT link_doctype, link_name FROM `tabDynamic Link`
        WHERE parent = %s AND parenttype = 'Contact'""",
        contact_name, as_dict=True,
    )
    for dtype in MEETING_PARTY_TYPES:
        for lnk in links:
            if lnk.link_doctype == dtype and frappe.db.exists(dtype, lnk.link_name):
                return contact_name, dtype, lnk.link_name
    # linked only to other doctypes (Prospect, Sales Partner, ...): keep the contact,
    # leave the party empty
    return contact_name, None, None


def _get_primary_contact(party_type, party):
    row = frappe.db.sql(
        """SELECT dl.parent FROM `tabDynamic Link` dl
        JOIN `tabContact` c ON c.name = dl.parent
        WHERE dl.link_doctype = %s AND dl.link_name = %s AND c.is_primary_contact = 1 LIMIT 1""",
        (party_type, party), as_dict=True,
    )
    if row:
        return row[0].parent
    # parenttype: Addresses link to the party through the same table
    row = frappe.db.sql(
        """SELECT dl.parent FROM `tabDynamic Link` dl
        WHERE dl.link_doctype = %s AND dl.link_name = %s AND dl.parenttype = 'Contact' LIMIT 1""",
        (party_type, party), as_dict=True,
    )
    return row[0].parent if row else None


def _get_project(party_type, party):
    if party_type == "Customer":
        return frappe.db.get_value("Project", {"customer": party}, "name")
    return None


def _get_meeting_purpose(internal):
    if internal:
        return frappe.db.get_value("Meeting Purpose", {"internal_meeting": 1}, "name")
    return frappe.db.get_value("Meeting Purpose", {"internal_meeting": 0}, "name")


def _find_log_for_transcript(call_id, transcript_id):
    """A transcript belongs to exactly one call: match it by transcript id (re-delivery) or by
    the call id Graph reports on the transcript. Never by onlineMeeting id, joinWebUrl or
    organizer: a recurring or reused Teams link is shared by many calls, and matching on it
    attached transcripts to (and overwrote) other calls' logs."""
    if transcript_id:
        name = frappe.db.get_value("Meeting Call Log", {"transcript_id": transcript_id}, "name")
        if name:
            return frappe.get_doc("Meeting Call Log", name)

    if call_id:
        name = frappe.db.get_value("Meeting Call Log", {"call_id": call_id}, "name")
        if name:
            return frappe.get_doc("Meeting Call Log", name)

    return frappe.new_doc("Meeting Call Log", provider=TEAMS)


# ---------------------------------------------------------------------------
# VTT parsing
# ---------------------------------------------------------------------------

# "00:00:16.246 --> 00:00:17.726" (hours optional per the WebVTT spec)
_VTT_TIMING_RE = re.compile(r"^\s*(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}\s*-->")
# "<v Speaker Name>text</v>"  (optional class suffix: <v.loud Name>)
_VTT_VOICE_RE = re.compile(r"^<v(?:\.[^\s>]+)?\s+([^>]*)>(.*?)(?:</v>)?\s*$", re.DOTALL)
_VTT_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


def _format_vtt_cue(cue_text):
    speaker = ""
    body = cue_text
    match = _VTT_VOICE_RE.match(cue_text)
    if match:
        speaker = match.group(1).strip()
        body = match.group(2)

    body = _VTT_TAG_RE.sub("", body).strip()
    if not body:
        return ""

    body = html.escape(body)
    if speaker:
        return f"{html.escape(speaker)}: {body}"
    return body


def _parse_vtt(vtt_text):
    """Turn WebVTT (speaker-attributed or plain) into 'Speaker: text' lines joined by <br>.

    Every cue is kept — repeated phrases ("Yes.", "Okay.") are real speech, not duplicates.
    Handles the unattributed format, which has a blank line between timing and text.
    """
    if not vtt_text:
        return ""

    lines = vtt_text.splitlines()
    out = []
    n = len(lines)
    i = 0
    while i < n:
        if _VTT_TIMING_RE.match(lines[i]):
            i += 1
            # unattributed format puts a blank line after the timing line
            while i < n and not lines[i].strip():
                i += 1
            text_lines = []
            while i < n and lines[i].strip() and not _VTT_TIMING_RE.match(lines[i]):
                text_lines.append(lines[i].strip())
                i += 1
            formatted = _format_vtt_cue(" ".join(text_lines))
            if formatted:
                out.append(formatted)
        else:
            i += 1
    return "<br>".join(out)


def _fetch_email_for_user_id(user_id, token):
    try:
        res = requests.get(
            f"https://graph.microsoft.com/v1.0/users/{user_id}?$select=userPrincipalName,displayName",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if res.status_code == 200:
            return res.json().get("userPrincipalName", "")
    except Exception:
        frappe.log_error(
            title="[WEBHOOK] Failed to fetch email for user",
            message=f"user_id={user_id}\n\n{frappe.get_traceback()}",
        )
    return ""


def _append_participant(emails, display_names, email, name, uid=None, token=None):
    if not email and uid and token:
        email = _fetch_email_for_user_id(uid, token)
    # names are only a fallback for participants Teams gives no email for; a name of
    # someone already found by email could match a different employee (first-name match)
    if name and not email and name not in display_names:
        display_names.append(name)
    if email:
        email = email.strip().lower()
        if email not in emails:
            emails.append(email)


def _extract_emails_from_record(record, token, scheduled_attendees=None):
    emails = []
    display_names = []

    for user in iter_call_record_identities(record):
        _append_participant(
            emails,
            display_names,
            user.get("userPrincipalName", ""),
            user.get("displayName", ""),
            uid=user.get("id", ""),
            token=token,
        )

    for attendee in scheduled_attendees or []:
        _append_participant(
            emails,
            display_names,
            attendee.get("email", ""),
            attendee.get("name", ""),
        )

    return emails, display_names


def participants_from_log(doc, token=None):
    """Participant emails for a Meeting Call Log, rebuilt from the stored call record
    (organizer, participants, session segments) plus the meeting's scheduled attendees,
    which Graph returns for the meeting owner. Nothing extra is stored on the log: the
    Meeting's representative tables hold the participants."""
    emails = []
    record = {}
    if doc.get("raw_payload"):
        try:
            record = json.loads(doc.raw_payload)
        except (TypeError, ValueError):
            record = {}
    for user in iter_call_record_identities(record):
        email = (user.get("userPrincipalName") or "").strip().lower()
        if email and email not in emails:
            emails.append(email)

    if doc.get("join_web_url"):
        try:
            token = token or get_access_token()
            owner = meeting_organizer_id(doc.join_web_url, doc.get("organizer_user_id"))
            for attendee in fetch_scheduled_attendees(owner, doc.join_web_url, token):
                email = (attendee.get("email") or "").strip().lower()
                if email and email not in emails:
                    emails.append(email)
        except Exception:
            frappe.log_error(
                title=f"[TEAMS] Scheduled attendees lookup failed ({doc.name})",
                message=frappe.get_traceback(),
                reference_doctype="Meeting Call Log",
                reference_name=doc.name,
            )

    return _normalize_participant_emails(emails, doc.get("organizer_email"))


def add_meeting(existing_meeting_name, actual_start, actual_end, participant_emails, discussion, subject, organizer_email=None, display_names=None, teams_meeting_log=None, join_web_url=None, provider=TEAMS):
    """Create or update the draft Meeting of a call. Provider neutral: `teams_meeting_log`
    is the Meeting Call Log name (kept for the original call sites), `provider` is stored
    on the Meeting as meeting_source."""
    participant_emails = _normalize_participant_emails(participant_emails, organizer_email)

    if teams_meeting_log:
        # Serialise Meeting creation per call: two jobs for the same log (call record,
        # transcript, reprocess) must not both find "no Meeting yet" and create one each.
        frappe.db.sql("SELECT name FROM `tabMeeting Call Log` WHERE name = %s FOR UPDATE", teams_meeting_log)
        # A submitted Meeting has been reviewed and cannot change; a later version of the
        # call record (or a transcript) must not create a second Meeting next to it.
        submitted = frappe.db.get_value(
            "Meeting", {"meeting_call_log": teams_meeting_log, "docstatus": 1}, "name", for_update=True
        )
        if submitted:
            return submitted

    meeting = None

    if existing_meeting_name and frappe.db.exists("Meeting", existing_meeting_name):
        if frappe.db.get_value("Meeting", existing_meeting_name, "docstatus") == 0:
            meeting = frappe.get_doc("Meeting", existing_meeting_name)

    # --- Duplicate guard ---
    if not meeting and teams_meeting_log:
        matched = frappe.db.get_value(
            "Meeting",
            {
                "meeting_call_log": teams_meeting_log,
                "docstatus": 0,
            },
            "name",
            for_update=True,
        )
        if matched:
            meeting = frappe.get_doc("Meeting", matched)

    # No match on join_web_url: every occurrence of a recurring meeting shares it, so
    # matching on it made a new call update the previous call's Meeting.
    # -----------------------

    if not meeting:
        meeting = frappe.new_doc("Meeting")
    # Teams publishes a call record before the call is complete and adds sessions to it
    # later (refresh_call_records picks those up), so a draft Meeting follows the latest times.
    if actual_start:
        meeting.meeting_from = actual_start
    if actual_end:
        meeting.meeting_to = actual_end

    if teams_meeting_log:
        meeting.meeting_call_log = teams_meeting_log
    if join_web_url and not meeting.get("join_web_url"):
        meeting.join_web_url = join_web_url

    is_internal = _is_internal_meeting(participant_emails, organizer_email)
    meeting.internal_meeting = 1 if is_internal else 0

    if is_internal:
        purpose = _get_meeting_purpose(is_internal)
        if purpose:
            meeting.purpose = purpose
    else:
        meeting.purpose = None

    if organizer_email:
        user = frappe.db.get_value("User", {"email": organizer_email.strip().lower()}, "name")
        if user:
            meeting.meeting_arranged_by = user

    if not meeting.subject:
        meeting.subject = _fit(subject)

    if provider:
        meeting.meeting_source = provider

    if not meeting.discussion:
        meeting.discussion = subject or DEFAULT_DISCUSSIONS[0]

    # Values the old sync stored that are not valid any more (an Address as contact
    # person, a party type Meeting does not allow) make every later save of the Meeting
    # fail link validation; clear them so they are resolved again below.
    if meeting.get("contact_person") and not frappe.db.exists("Contact", meeting.contact_person):
        meeting.contact_person = None
    if meeting.get("party_type") and meeting.party_type not in MEETING_PARTY_TYPES:
        meeting.party_type = meeting.party = None
    if meeting.get("party_type") and meeting.get("party") and not meeting.get("contact_person"):
        meeting.contact_person = _get_primary_contact(meeting.party_type, meeting.party)

    party_resolved = bool(meeting.party_type and meeting.party)
    if not is_internal and not party_resolved:
        for email in [e for e in participant_emails if not _is_internal(e)]:
            contact_name, party_type, party = _resolve_contact_and_party(email)
            if party_type and party:
                meeting.party_type = party_type
                meeting.party = party
                project = _get_project(party_type, party)
                if project:
                    meeting.project = project
                primary = _get_primary_contact(party_type, party)
                if primary:
                    meeting.contact_person = primary
                party_resolved = True
                break
            if contact_name and not meeting.contact_person:
                meeting.contact_person = contact_name

        if not party_resolved:
            external_emails = [e for e in participant_emails if not _is_internal(e)]
            frappe.logger().warning(
                f"[MEETING] External meeting without ERP party match. "
                f"Emails: {', '.join(external_emails) or organizer_email or 'unknown'}"
            )

    if not is_internal and not meeting.get("email_id"):
        if organizer_email and not _is_internal(organizer_email):
            meeting.email_id = organizer_email.strip().lower()
        else:
            for email in [e for e in participant_emails if not _is_internal(e)]:
                meeting.email_id = email
                break

    if meeting.get("contact_person") and not meeting.get("email_id"):
        contact_email = frappe.db.get_value(
            "Contact Email",
            {"parent": meeting.contact_person, "parenttype": "Contact"},
            "email_id",
        )
        if contact_email:
            meeting.email_id = contact_email.strip().lower()

    existing_employees = {r.employee for r in meeting.meeting_company_representative}
    existing_contacts = {r.contact for r in meeting.meeting_party_representative}

    for email in participant_emails:
        if not email:
            continue
        if _is_internal(email):
            emp = _resolve_employee(email)
            if emp and emp.name not in existing_employees:
                meeting.append("meeting_company_representative", {"employee": emp.name})
                existing_employees.add(emp.name)
        else:
            contact_name, _, _ = _resolve_contact_and_party(email)
            if contact_name and contact_name not in existing_contacts:
                meeting.append("meeting_party_representative", {"contact": contact_name})
                existing_contacts.add(contact_name)

    # Fallback: resolve employees by display name when email lookup fails
    if not is_internal:
        pass  # display name fallback only meaningful for internal meetings
    elif display_names:
        for display_name in display_names:
            if not display_name:
                continue
            # Try matching by employee_name first (exact match), then by first name
            emp = frappe.db.get_value(
                "Employee",
                {"employee_name": display_name, "status": "Active"},
                ["name", "employee_name"],
                as_dict=True,
            )
            if not emp:
                # Try matching by first_name (from User via employee's user_id)
                emp = frappe.db.sql("""
                    SELECT e.name, e.employee_name
                    FROM `tabEmployee` e
                    JOIN `tabUser` u ON u.name = e.user_id
                    WHERE u.first_name = %s AND e.status = 'Active'
                    LIMIT 2
                """, display_name.split()[0] if display_name else "", as_dict=True)
                # only when the first name is unique, otherwise it is a guess
                emp = emp[0] if len(emp) == 1 else None
            if emp and emp.name not in existing_employees:
                meeting.append("meeting_company_representative", {"employee": emp.name})
                existing_employees.add(emp.name)

    if not meeting.get("meeting_arranged_by"):
        # organizer outside the company: the first internal participant arranges it
        # (productivity_next assigns the Task created on submit to this user)
        for rep in meeting.meeting_company_representative:
            user = frappe.db.get_value("Employee", rep.employee, "user_id")
            if user and frappe.db.exists("User", user):
                meeting.meeting_arranged_by = user
                break

    meeting.flags.ignore_validate = True
    meeting.flags.ignore_mandatory = True
    # allows this sync to set meeting_from / meeting_to, which users may not change
    meeting.flags.from_meeting_sync = True
    if meeting.is_new():
        meeting.insert(ignore_permissions=True)
    else:
        meeting.save(ignore_permissions=True)

    return meeting.name


# ---------------------------------------------------------------------------
# Webhook endpoints
# ---------------------------------------------------------------------------

def _filter_by_client_state(notifications):
    """Split notifications into (valid, rejected) by comparing clientState to our secret.

    - Constant-time comparison.
    - If the secret isn't configured, everything is rejected (never accept "empty == empty").
    - One bad notification no longer rejects the rest of the batch.
    """
    settings = frappe.get_single("Meeting Sync Settings")
    secret = settings.get_password("webhook_secret", raise_exception=False)
    if not secret:
        frappe.log_error(
            title="[WEBHOOK] webhook_secret is not configured",
            message="Rejecting all notifications until Meeting Sync Settings.webhook_secret is set.",
        )
        return [], list(notifications)

    secret_bytes = secret.encode("utf-8")
    valid, rejected = [], []
    for n in notifications:
        state = n.get("clientState")
        if isinstance(state, str) and hmac.compare_digest(state.encode("utf-8"), secret_bytes):
            valid.append(n)
        else:
            rejected.append(n)
    return valid, rejected


def _receive(job_path, queue="long"):
    """Shared handler for Graph webhook POSTs: handshake, clientState check, enqueue, 202."""
    validation_token = frappe.request.args.get("validationToken")
    if validation_token:
        return Response(validation_token, status=200, mimetype="text/plain")

    if not is_enabled(TEAMS):
        return Response(status=202)

    data = frappe.request.get_json(force=True, silent=True) or {}
    notifications = data.get("value") or []

    valid, rejected = _filter_by_client_state(notifications)
    if rejected:
        frappe.log_error(
            title=f"[WEBHOOK] Dropped {len(rejected)} notification(s) with invalid clientState",
            message=f"job={job_path}\n\n{json.dumps(rejected, indent=2, default=str)[:3000]}",
        )
    if notifications and not valid:
        frappe.response.http_status_code = 401
        return "Unauthorized"

    # Enqueue first: if this raises, Frappe returns 5xx and Graph retries the delivery.
    for n in valid:
        frappe.enqueue(job_path, notification=n, queue=queue)

    frappe.response.http_status_code = 202
    return "Accepted"


@frappe.whitelist(allow_guest=True)
def callrecords():
    return _receive("productivity_next.meeting_sync.teams.webhook.process_call_record_as_admin", queue="long")


@frappe.whitelist(allow_guest=True)
def transcripts():
    return _receive("productivity_next.meeting_sync.teams.webhook.process_transcript_as_admin", queue="long")


# Webhook requests arrive as Guest. Process calls and transcripts as Administrator.
def process_call_record_as_admin(notification):
    frappe.set_user("Administrator")
    process_call_record(notification)


def process_transcript_as_admin(notification):
    frappe.set_user("Administrator")
    process_transcript(notification)


@frappe.whitelist(allow_guest=True)
def lifecycle():
    """Lifecycle notifications: reauthorizationRequired / subscriptionRemoved / missed."""
    return _receive("productivity_next.meeting_sync.teams.webhook.process_lifecycle", queue="short")


# ---------------------------------------------------------------------------
# Subscription lifecycle / renewal
# ---------------------------------------------------------------------------

def _cache():
    c = frappe.cache
    return c() if callable(c) else c


def renew_subscription(subscription_id, token=None):
    """Renew (and thereby reauthorize) a subscription with a single PATCH.

    Graph: a PATCH with a new expirationDateTime does both. Don't send /reauthorize and
    PATCH for the same subscription within 10 minutes, so a short cache guard is used.
    """
    if not subscription_id:
        return False

    guard_key = f"teams_sub_renewed:{subscription_id}"
    if _cache().get_value(guard_key):
        frappe.logger().info(f"[LIFECYCLE] Skipping renew (recent) subscription_id={subscription_id}")
        return True

    token = token or get_access_token()
    expiry = (datetime.utcnow() + timedelta(minutes=SUBSCRIPTION_RENEW_MINUTES)).strftime(
        "%Y-%m-%dT%H:%M:%S.0000000Z"
    )
    res = requests.patch(
        f"{GRAPH_BASE}/subscriptions/{subscription_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"expirationDateTime": expiry},
        timeout=30,
    )
    if res.status_code == 200:
        _cache().set_value(guard_key, 1, expires_in_sec=SUBSCRIPTION_RENEW_GUARD_SECONDS)
        frappe.logger().info(
            f"[LIFECYCLE] Renewed subscription_id={subscription_id} until {expiry}"
        )
        return True

    frappe.log_error(
        title=f"[LIFECYCLE] Subscription renew failed (subscription_id={subscription_id})",
        message=f"status={res.status_code}\nbody={res.text[:1000]}",
    )
    return False


def process_lifecycle(notification):
    event = (notification or {}).get("lifecycleEvent")
    subscription_id = (notification or {}).get("subscriptionId")
    frappe.logger().info(f"[LIFECYCLE] event={event} subscription_id={subscription_id}")

    try:
        if event == "reauthorizationRequired":
            renew_subscription(subscription_id)
        elif event in ("subscriptionRemoved", "missed"):
            # Not documented as sent for callRecord/callTranscript, but if it ever arrives a
            # human must recreate the subscription / backfill. Surface it in Error Log.
            frappe.log_error(
                title=f"[LIFECYCLE] {event} (subscription_id={subscription_id})",
                message=json.dumps(notification, indent=2, default=str),
            )
        else:
            frappe.logger().warning(f"[LIFECYCLE] Unknown lifecycleEvent={event}")
    except Exception:
        frappe.log_error(
            title=f"[LIFECYCLE] Handling failed (event={event}, subscription_id={subscription_id})",
            message=frappe.get_traceback(),
        )


def renew_subscriptions():
    """Safety net for the scheduler (e.g. daily): renew this app's call-record and
    transcript subscriptions even if a lifecycle notification was never delivered.

    Not scheduled: subscriptions.ensure_subscriptions renews them every 10 minutes.
    """
    from productivity_next.meeting_sync.teams.subscriptions import is_teams_sync_enabled

    if not is_teams_sync_enabled():
        return
    try:
        token = get_access_token()
        url = f"{GRAPH_BASE}/subscriptions"
        while url:
            res = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
            if res.status_code != 200:
                frappe.log_error(
                    title="[LIFECYCLE] List subscriptions failed",
                    message=f"status={res.status_code}\nbody={res.text[:1000]}",
                )
                return
            body = res.json()
            for sub in body.get("value") or []:
                resource = (sub.get("resource") or "").lower()
                if "callrecords" in resource or "transcripts" in resource:
                    renew_subscription(sub.get("id"), token=token)
            url = body.get("@odata.nextLink")
    except Exception:
        frappe.log_error(
            title="[LIFECYCLE] renew_subscriptions failed",
            message=frappe.get_traceback(),
        )


# ---------------------------------------------------------------------------
# Background jobs
# ---------------------------------------------------------------------------

def _fetch_call_record_with_retry(call_id, token):
    """Fetch the call record, retrying briefly on 404/429/5xx and network errors."""
    res = None
    last_exc = None
    for delay in CALL_RECORD_RETRY_DELAYS:
        if delay:
            time.sleep(delay)
        try:
            res = fetch_call_record(call_id, token)
            last_exc = None
        except Exception as exc:
            last_exc = exc
            continue
        if res.status_code < 400:
            return res
        if res.status_code not in CALL_RECORD_RETRYABLE_STATUS:
            return res
    if res is None and last_exc is not None:
        raise last_exc
    return res


def process_call_record(notification):
    call_id = None
    try:
        call_id = parse_call_record_id(notification)
        if not call_id:
            frappe.log_error(
                title="[CALL RECORD] Missing call_id in notification",
                message=json.dumps(notification, indent=2, default=str),
            )
            return

        token = get_access_token()
        res = _fetch_call_record_with_retry(call_id, token)
        res.raise_for_status()
        record = res.json()
    except Exception:
        frappe.log_error(
            title=f"[CALL RECORD] Fetch/parse failed (call_id={call_id})",
            message=frappe.get_traceback(),
        )
        return                                    # <-- no raise

    # --- load or create (in memory) ---
    try:
        if frappe.db.exists("Meeting Call Log", {"call_id": call_id}):
            doc = frappe.get_doc("Meeting Call Log", {"call_id": call_id})
        else:
            doc = frappe.new_doc("Meeting Call Log", provider=TEAMS)
    except Exception:
        frappe.log_error(
            title=f"[CALL RECORD] Doc load/create failed (call_id={call_id})",
            message=frappe.get_traceback(),
        )
        return

    # --- populate + persist ---
    try:
        organizer_v2 = record.get("organizer_v2", {}) or {}
        org_user = organizer_v2.get("identity", {}).get("user", {}) or {}
        organizer_email   = org_user.get("userPrincipalName", "")
        organizer_name    = org_user.get("displayName", "")
        organizer_user_id = org_user.get("id", "")
        join_web_url      = record.get("joinWebUrl", "")

        scheduled_attendees = fetch_scheduled_attendees(
            meeting_organizer_id(join_web_url, organizer_user_id), join_web_url, token
        )
        participant_emails, display_names = _extract_emails_from_record(
            record, token, scheduled_attendees=scheduled_attendees
        )

        actual_start = _parse_dt(record.get("startDateTime"))
        actual_end   = _parse_dt(record.get("endDateTime"))

        doc.call_id            = record.get("id")
        doc.join_web_url       = join_web_url
        doc.meeting_type       = record.get("type")
        doc.actual_start       = actual_start
        doc.actual_end         = actual_end
        doc.organizer          = organizer_name
        doc.organizer_email    = organizer_email
        doc.organizer_user_id  = organizer_user_id
        doc.participants       = ", ".join(filter(None, display_names))
        doc.participant_count  = len(display_names)
        doc.raw_payload         = json.dumps(record, indent=2)
        if doc.status != "Complete":              # a refresh must not undo a saved transcript
            doc.status         = "Call Record Received"
    except Exception:
        frappe.log_error(
            title=f"[CALL RECORD] Populate failed (call_id={call_id})",
            message=frappe.get_traceback(),
        )
        return

    if not _persist_teams_meeting_log(doc, context="CALL RECORD", identifier=call_id):
        return                                    # helper already logged

    # --- post-save fallbacks (best-effort, never fail the job) ---
    try:
        if not organizer_email and organizer_user_id:
            organizer_email = _fetch_email_for_user_id(organizer_user_id, token)
            if organizer_email:
                doc.db_set("organizer_email", organizer_email, update_modified=False)

        for user in iter_call_record_identities(record):
            uid = user.get("id", "")
            upn = (user.get("userPrincipalName") or "").strip().lower()
            if uid and not upn:
                fetched = _fetch_email_for_user_id(uid, token)
                if fetched and fetched.strip().lower() not in participant_emails:
                    participant_emails.append(fetched.strip().lower())
    except Exception:
        frappe.log_error(
            title=f"[CALL RECORD] Post-save fallback failed (call_id={call_id})",
            message=frappe.get_traceback(),
        )

    # --- meeting upsert (no commit; save happens at end of job) ---
    has_participants = bool(participant_emails or organizer_email or display_names)
    if not has_participants:
        if _should_create_meeting(actual_start, actual_end):
            frappe.log_error(
                title=f"[CALL RECORD] Meeting not created - no participants ({doc.name})",
                message=f"call_id={call_id}",
            )
        return

    if not actual_start or not actual_end:
        frappe.log_error(
            message=f"[CALL RECORD] Skipping Meeting for {doc.name} — missing timestamps",
            title="Meeting Skipped - Missing Timestamps"
        )
        return

    if not _should_create_meeting(actual_start, actual_end):
        duration = _call_duration_seconds(actual_start, actual_end)
        frappe.logger().info(
            f"[CALL RECORD] Skipping Meeting for {doc.name} — "
            f"{duration:.0f}s < {MIN_MEETING_DURATION_SECONDS}s"
        )
        return

    try:
        meeting_name = add_meeting(
            existing_meeting_name=_meeting_for_log(doc.name),
            actual_start=actual_start,
            actual_end=actual_end,
            participant_emails=participant_emails,
            discussion=doc.meeting_subject or record.get("subject") or "Online Meeting",
            subject=doc.meeting_subject or record.get("subject") or "",
            organizer_email=organizer_email,
            display_names=display_names,
            teams_meeting_log=doc.name,
            join_web_url=doc.join_web_url,
        )
        if meeting_name:
            doc.db_set("is_meeting_created", 1, update_modified=False)
    except Exception:
        frappe.log_error(
            title=f"[CALL RECORD] Meeting upsert failed (call_id={call_id})",
            message=frappe.get_traceback(),
        )


def process_transcript(notification):
    resource = (notification or {}).get("resource", "")
    frappe.logger().info(f"[TRANSCRIPT] received resource={resource}")

    meeting_id = None
    try:
        user_id, meeting_id, transcript_id = parse_transcript_resource(resource)
    except Exception:
        frappe.log_error(
            title="[TRANSCRIPT] parse_transcript_resource raised",
            message=f"resource={resource}\n\n{frappe.get_traceback()}",
        )
        return

    if not all((user_id, meeting_id, transcript_id)):
        frappe.log_error(
            title="[TRANSCRIPT] Bad resource format",
            message=f"resource={resource}",
        )
        return

    try:
        token = get_access_token()
    except Exception:
        frappe.log_error(
            title="[TRANSCRIPT] get_access_token failed",
            message=frappe.get_traceback(),
        )
        return

    # --- 0. which call this transcript belongs to ---
    call_id = None
    try:
        meta_res = fetch_transcript_metadata(user_id, meeting_id, transcript_id, token)
        if meta_res.status_code == 200:
            call_id = (meta_res.json() or {}).get("callId")
        else:
            frappe.log_error(
                title=f"[TRANSCRIPT] Transcript metadata fetch failed status={meta_res.status_code}",
                message=f"user_id={user_id} meeting_id={meeting_id} transcript_id={transcript_id}\n\nbody={meta_res.text[:500]}",
            )
    except Exception:
        frappe.log_error(
            title="[TRANSCRIPT] Transcript metadata fetch raised",
            message=f"user_id={user_id} meeting_id={meeting_id}\n\n{frappe.get_traceback()}",
        )

    # --- 1. meeting details (best-effort) ---
    meeting_data, join_web_url, subject = None, None, None
    participant_emails = []
    try:
        meeting_res = fetch_online_meeting(user_id, meeting_id, token)
        if meeting_res.status_code == 200:
            meeting_data  = meeting_res.json()
            join_web_url  = meeting_data.get("joinWebUrl")
            subject       = meeting_data.get("subject")
            attendees     = meeting_data.get("participants", {}) or {}
            org           = attendees.get("organizer", {}) or {}
            org_email     = (
                org.get("upn")
                or (org.get("identity", {}) or {}).get("user", {}).get("userPrincipalName")
            )
            if org_email:
                participant_emails.append(org_email.strip().lower())
            for a in attendees.get("attendees", []) or []:
                email = (
                    a.get("upn")
                    or ((a.get("identity", {}) or {}).get("user", {}) or {}).get("userPrincipalName")
                    or ""
                )
                if email:
                    email = email.strip().lower()
                    if email not in participant_emails:
                        participant_emails.append(email)
        else:
            frappe.log_error(
                title=f"[TRANSCRIPT] Meeting fetch failed status={meeting_res.status_code}",
                message=f"user_id={user_id} meeting_id={meeting_id}",
            )
    except Exception:
        frappe.log_error(
            title="[TRANSCRIPT] Meeting fetch raised",
            message=f"user_id={user_id} meeting_id={meeting_id}\n\n{frappe.get_traceback()}",
        )

    # --- 2. find or create doc, then SAVE EARLY (no commit) ---
    try:
        doc = _find_log_for_transcript(call_id, transcript_id)
        if call_id and not doc.get("call_id"):
            # transcript arrived before the call record; process_call_record finds this log by call_id
            doc.call_id = call_id
        if join_web_url and not doc.get("join_web_url"):
            doc.join_web_url = join_web_url
        if meeting_data:
            doc.online_meeting_id = meeting_id
            doc.meeting_subject   = _fit(subject) or doc.get("meeting_subject")
    except Exception:
        frappe.log_error(
            title=f"[TRANSCRIPT] Doc build failed (meeting_id={meeting_id})",
            message=f"join_web_url={join_web_url}\n\n{frappe.get_traceback()}",
        )
        return

    if not _persist_teams_meeting_log(doc, context="TRANSCRIPT", identifier=meeting_id):
        return

    # --- 3. transcript fetch (best-effort) ---
    # The meeting id from the notification is the id the transcript API expects, so try it
    # first. Only if that fails do we look up an alternative id from joinWebUrl and retry.
    vtt_content = ""
    try:
        content_res = fetch_transcript_vtt(user_id, meeting_id, transcript_id, token)

        if content_res.status_code != 200 and doc.get("join_web_url"):
            try:
                resolved = resolve_online_meeting_id(user_id, doc.join_web_url, token)
            except Exception:
                resolved = None
                frappe.log_error(
                    title="[TRANSCRIPT] resolve_online_meeting_id raised",
                    message=f"join_web_url={doc.join_web_url}\n\n{frappe.get_traceback()}",
                )
            if resolved and resolved != meeting_id:
                doc.online_meeting_id = resolved
                content_res = fetch_transcript_vtt(user_id, resolved, transcript_id, token)

        if content_res.status_code == 200:
            vtt_content = content_res.text
        else:
            frappe.log_error(
                title=f"[TRANSCRIPT] Transcript fetch failed status={content_res.status_code}",
                message=(
                    f"user_id={user_id} meeting_id={doc.get('online_meeting_id') or meeting_id} "
                    f"transcript_id={transcript_id}\n\nbody={content_res.text[:500]}"
                ),
            )
    except Exception:
        frappe.log_error(
            title="[TRANSCRIPT] Transcript fetch raised",
            message=frappe.get_traceback(),
        )

    # --- update doc + persist (no commit) ---
    try:
        doc.transcript_id = transcript_id
        doc.raw_vtt       = vtt_content
        doc.status        = "Complete" if vtt_content else "Transcript Fetch Failed"
    except Exception:
        frappe.log_error(
            title=f"[TRANSCRIPT] Doc update failed (meeting_id={meeting_id})",
            message=frappe.get_traceback(),
        )
        return

    if not _persist_teams_meeting_log(doc, context="TRANSCRIPT", identifier=meeting_id):
        return

    if not vtt_content:
        return

    # --- 4. parse + meeting upsert (no commit) ---
    try:
        discussion = _parse_vtt(vtt_content)
    except Exception:
        frappe.log_error(
            title=f"[TRANSCRIPT] VTT parse failed (meeting_id={meeting_id})",
            message=frappe.get_traceback(),
        )
        return

    if not participant_emails:
        participant_emails = participants_from_log(doc, token)
    emails_for_meeting = _normalize_participant_emails(participant_emails, doc.organizer_email)

    if not emails_for_meeting:
        if _should_create_meeting(doc.actual_start, doc.actual_end):
            frappe.log_error(
                title=f"[TRANSCRIPT] Meeting not created - no participants ({doc.name})",
                message=f"meeting_id={meeting_id} transcript_id={transcript_id}",
            )
        return
    if not (doc.actual_start and doc.actual_end):
        frappe.logger().warning(
            f"[TRANSCRIPT] Skipping Meeting upsert — missing timestamps on {doc.name}"
        )
        return
    if not _should_create_meeting(doc.actual_start, doc.actual_end):
        duration = _call_duration_seconds(doc.actual_start, doc.actual_end)
        frappe.logger().info(
            f"[TRANSCRIPT] Skipping Meeting for {doc.name} — "
            f"{duration:.0f}s < {MIN_MEETING_DURATION_SECONDS}s"
        )
        return

    try:
        meeting_name = add_meeting(
            existing_meeting_name=_meeting_for_log(doc.name),
            actual_start=doc.actual_start,
            actual_end=doc.actual_end,
            participant_emails=emails_for_meeting,
            discussion=discussion,
            subject=subject or doc.meeting_subject or "",
            organizer_email=doc.organizer_email,
            teams_meeting_log=doc.name,
            join_web_url=doc.join_web_url,
        )
        if meeting_name:
            doc.db_set("is_meeting_created", 1, update_modified=False)
    except Exception:
        frappe.log_error(
            title=f"[TRANSCRIPT] Meeting upsert failed (meeting_id={meeting_id})",
            message=frappe.get_traceback(),
        )


# Helper to resolve meeting ID from joinWebUrl.
def resolve_online_meeting_id(user_id, join_web_url, token):
    """Resolve the actual onlineMeeting id from joinWebUrl.

    Graph only supports looking up onlineMeetings with a filter, so there is no
    "list everything and match" fallback (an unfiltered list returns 400).
    """
    if not user_id or not join_web_url:
        return None

    meeting = find_online_meeting_by_join_url(user_id, join_web_url, token)
    if meeting and meeting.get("id"):
        return meeting["id"]

    frappe.log_error(
        title="[RESOLVE] Could not resolve meeting id",
        message=f"joinWebUrl={join_web_url}",
    )
    return None


def _persist_teams_meeting_log(doc, context, identifier=None):
    """Save the Meeting Call Log and log any failure to Error Log.
    Never commits, never rolls back, never raises — so the surrounding
    background job always completes and Frappe's end-of-job commit persists
    both the doc and the Error Log together.
    Returns True on success, False on failure.
    """
    try:
        doc.save(ignore_permissions=True)
        frappe.logger().info(
            f"[{context}] Meeting Call Log saved | name={doc.name} identifier={identifier}"
        )
        return True
    except Exception:
        frappe.log_error(
            title=f"[{context}] Meeting Call Log save failed (identifier={identifier})",
            message=(
                f"identifier={identifier}\n"
                f"docname={getattr(doc, 'name', None)}\n"
                f"call_id={doc.get('call_id')}\n"
                f"online_meeting_id={doc.get('online_meeting_id')}\n"
                f"join_web_url={doc.get('join_web_url')}\n\n"
                f"{frappe.get_traceback()}"
            ),
        )
        return False

import re
from urllib.parse import quote, unquote

import frappe
import requests

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

TRANSCRIPT_ACCEPT_VTT = "text/vtt"
# Plain format (no <v Speaker> tags). Needed when a tenant admin disables speaker
# attribution: text/vtt then returns 403 SpeakerAttributionNotAllowed.
TRANSCRIPT_ACCEPT_PLAIN = "application/vnd.microsoft.graph.transcript+text"

# Accepts both documented shapes of the notification "resource":
#   users('<id>')/onlineMeetings('<id>')/transcripts('<id>')
#   users/<id>/onlineMeetings('<id>')/transcripts('<id>')
# plus the fully slash-separated form handled by the fallback below.
_TRANSCRIPT_RESOURCE_RE = re.compile(
    r"users(?:\('([^']+)'\)|/([^/(]+))"
    r"/onlineMeetings(?:\('([^']+)'\)|/([^/(]+))"
    r"/transcripts(?:\('([^']+)'\)|/([^/(]+))",
    re.IGNORECASE,
)

_CALL_RECORD_RESOURCE_RE = re.compile(r"callRecords(?:\('([^']+)'\)|/([^/?(]+))", re.IGNORECASE)


def parse_transcript_resource(resource):
    """Parse Graph transcript notification resource into user/meeting/transcript IDs."""
    if not resource:
        return None, None, None

    match = _TRANSCRIPT_RESOURCE_RE.search(resource)
    if match:
        g = match.groups()
        user_id = g[0] or g[1]
        meeting_id = g[2] or g[3]
        transcript_id = g[4] or g[5]
        return user_id, meeting_id, transcript_id

    return None, None, None


def build_transcript_notification(user_id, meeting_id, transcript_id):
    """Build a Graph-style transcript resource string for reprocessing."""
    return (
        f"users('{user_id}')/onlineMeetings('{meeting_id}')"
        f"/transcripts('{transcript_id}')"
    )


def parse_call_record_id(notification):
    notification = notification or {}
    call_id = (notification.get("resourceData") or {}).get("id")
    if call_id:
        return call_id

    # Fallback: communications/callRecords/{id}
    match = _CALL_RECORD_RESOURCE_RE.search(notification.get("resource") or "")
    if match:
        return match.group(1) or match.group(2)
    return None


def transcript_content_url(user_id, meeting_id, transcript_id):
    # Content format is chosen with the Accept header (see fetch_transcript_vtt).
    meeting_id_path = quote(meeting_id, safe="")
    transcript_id_path = quote(transcript_id, safe="")
    return (
        f"{GRAPH_BASE}/users/{user_id}"
        f"/onlineMeetings/{meeting_id_path}/transcripts/{transcript_id_path}/content"
    )


_LINK_CONTEXT_RE = {
    key: re.compile(rf'"{key}"\s*:\s*"([^"]+)"') for key in ("Tid", "Oid")
}


def organizer_from_join_url(join_web_url):
    """(tenant id, organizer object id) from a Teams meeting link's context, or (None, None).

    The link names the meeting's owner. A call record's organizer is whoever started the
    call, which differs when someone else starts or joins the meeting first; Graph only
    resolves the meeting (subject, attendees, transcripts) under its owner and answers
    403 "User does not have access to lookup meeting" for anyone else.
    """
    text = unquote(unquote(join_web_url or ""))
    found = {key: (rx.search(text) or [None, None])[1] for key, rx in _LINK_CONTEXT_RE.items()}
    return found["Tid"], found["Oid"]


def meeting_organizer_id(join_web_url, fallback=None):
    """The meeting owner's object id from the link, else `fallback` (the call organizer)."""
    return organizer_from_join_url(join_web_url)[1] or fallback


def transcript_metadata_url(user_id, meeting_id, transcript_id):
    meeting_id_path = quote(meeting_id, safe="")
    transcript_id_path = quote(transcript_id, safe="")
    return (
        f"{GRAPH_BASE}/users/{user_id}"
        f"/onlineMeetings/{meeting_id_path}/transcripts/{transcript_id_path}"
    )


def fetch_transcript_metadata(user_id, meeting_id, transcript_id, token):
    """callTranscript resource. Its callId ties the transcript to exactly one call, which a
    recurring meeting's onlineMeeting id or joinWebUrl cannot do."""
    return requests.get(
        transcript_metadata_url(user_id, meeting_id, transcript_id),
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def online_meeting_url(user_id, meeting_id):
    meeting_id_path = quote(meeting_id, safe="")
    return f"{GRAPH_BASE}/users/{user_id}/onlineMeetings/{meeting_id_path}"


def call_record_url(call_id):
    return f"{GRAPH_BASE}/communications/callRecords/{call_id}"


def call_record_participants_v2_url(call_id):
    return f"{GRAPH_BASE}/communications/callRecords/{call_id}?$expand=participants_v2"


def call_record_sessions_url(call_id):
    return (
        f"{GRAPH_BASE}/communications/callRecords/{call_id}"
        f"?$expand=sessions($expand=segments)"
    )


class GraphResponse:
    """Minimal response wrapper so fetch helpers stay compatible with requests."""

    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"Graph API error {self.status_code}", response=self)


def _is_speaker_attribution_blocked(response):
    """True for the documented 403 / SpeakerAttributionNotAllowed response."""
    if response.status_code != 403:
        return False
    try:
        inner = ((response.json() or {}).get("error") or {}).get("innerError") or {}
        return inner.get("code") == "SpeakerAttributionNotAllowed"
    except Exception:
        return "SpeakerAttributionNotAllowed" in (response.text or "")


def fetch_transcript_vtt(user_id, meeting_id, transcript_id, token):
    """Fetch transcript content.

    Asks for speaker-attributed WebVTT first. If the tenant has speaker attribution
    turned off (403 SpeakerAttributionNotAllowed), retries with the unattributed format.
    """
    url = transcript_content_url(user_id, meeting_id, transcript_id)

    content_res = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": TRANSCRIPT_ACCEPT_VTT},
        timeout=30,
    )

    if _is_speaker_attribution_blocked(content_res):
        frappe.logger().info(
            f"[TRANSCRIPT] Speaker attribution disabled for tenant — retrying unattributed "
            f"user_id={user_id} transcript_id={transcript_id}"
        )
        content_res = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": TRANSCRIPT_ACCEPT_PLAIN},
            timeout=30,
        )

    if content_res.status_code != 200:
        frappe.logger().error(
            f"[TRANSCRIPT] VTT fetch failed status={content_res.status_code} "
            f"user_id={user_id} transcript_id={transcript_id} body={content_res.text[:500]}"
        )
    return content_res


def fetch_online_meeting(user_id, meeting_id, token):
    return requests.get(
        online_meeting_url(user_id, meeting_id),
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def _graph_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _graph_get(url, token, timeout=30):
    return requests.get(url, headers=_graph_headers(token), timeout=timeout)


def _collect_odata_pages(first_url, token, collection_key):
    """Follow @odata.nextLink for an expanded collection."""
    items = []
    url = first_url
    while url:
        res = _graph_get(url, token)
        if res.status_code != 200:
            break
        data = res.json()
        chunk = data.get(collection_key)
        if chunk is None and collection_key == "value":
            chunk = data.get("value")
        if isinstance(chunk, list):
            items.extend(chunk)
        url = data.get(f"{collection_key}@odata.nextLink") or data.get("@odata.nextLink")
        if url and not isinstance(chunk, list):
            break
    return items


def _merge_participants_v2(record, participants_v2):
    if participants_v2:
        record["participants_v2"] = participants_v2


def _merge_sessions(record, sessions):
    if sessions:
        record["sessions"] = sessions


def fetch_call_record(call_id, token):
    """Fetch call record with separate expands (Graph allows only one $expand)."""
    base_res = _graph_get(call_record_url(call_id), token)
    if base_res.status_code != 200:
        return base_res

    record = base_res.json()

    p2_res = _graph_get(call_record_participants_v2_url(call_id), token)
    if p2_res.status_code == 200:
        p2_data = p2_res.json()
        participants_v2 = list(p2_data.get("participants_v2") or [])
        next_link = p2_data.get("participants_v2@odata.nextLink")
        if next_link:
            participants_v2.extend(
                _collect_odata_pages(next_link, token, "value")
            )
        _merge_participants_v2(record, participants_v2)

    sess_res = _graph_get(call_record_sessions_url(call_id), token)
    if sess_res.status_code == 200:
        _merge_sessions(record, sess_res.json().get("sessions") or [])

    return GraphResponse(record)


def find_online_meeting_by_join_url(user_id, join_web_url, token):
    """Return the onlineMeeting dict for a joinWebUrl, or None.

    Graph only supports listing onlineMeetings WITH a filter (JoinWebUrl, joinMeetingId,
    VideoTeleconferenceId). An unfiltered list returns 400, so there is no fallback scan.
    """
    if not user_id or not join_web_url:
        return None

    escaped_url = join_web_url.replace("'", "''")
    filter_url = (
        f"{GRAPH_BASE}/users/{user_id}/onlineMeetings"
        f"?$filter=JoinWebUrl eq '{escaped_url}'"
    )
    res = _graph_get(filter_url, token)
    if res.status_code != 200:
        frappe.logger().warning(
            f"[RESOURCE] onlineMeetings filter lookup failed status={res.status_code} "
            f"user_id={user_id} body={res.text[:300]}"
        )
        return None

    meetings = res.json().get("value") or []
    return meetings[0] if meetings else None


def fetch_scheduled_attendees(user_id, join_web_url, token):
    """Return scheduled invitees from onlineMeetings (requires Teams AAP for app access)."""
    meeting = find_online_meeting_by_join_url(user_id, join_web_url, token)
    if not meeting:
        return []

    attendees = []
    participants = meeting.get("participants") or {}
    org = participants.get("organizer") or {}
    org_user = (org.get("identity") or {}).get("user") or {}
    org_entry = {
        "email": (org.get("upn") or org_user.get("userPrincipalName") or "").strip().lower(),
        "name": org_user.get("displayName") or "",
        "source": "scheduled",
    }
    if org_entry["email"] or org_entry["name"]:
        attendees.append(org_entry)

    for attendee in participants.get("attendees") or []:
        user = (attendee.get("identity") or {}).get("user") or {}
        entry = {
            "email": (
                attendee.get("upn") or user.get("userPrincipalName") or ""
            ).strip().lower(),
            "name": user.get("displayName") or "",
            "source": "scheduled",
        }
        if entry["email"] or entry["name"]:
            attendees.append(entry)

    return attendees


def identity_from_participant(participant):
    """Extract user dict from call-record participant or segment identity."""
    if not participant:
        return {}
    identity = participant.get("identity") or participant
    return (
        identity.get("user")
        or participant.get("user")
        or {}
    )


def iter_call_record_identities(record):
    """Yield user identity dicts from organizer, participants, and session segments.

    Uses organizer_v2 / participants_v2 (the old organizer / participants fields stopped
    returning data on 2026-06-30).
    """
    organizer_v2 = record.get("organizer_v2") or {}
    org_user = identity_from_participant(organizer_v2)
    if org_user:
        yield org_user

    for participant in record.get("participants_v2") or record.get("participants") or []:
        user = identity_from_participant(participant)
        if user:
            yield user

    for session in record.get("sessions") or []:
        for segment in session.get("segments") or []:
            for role in ("caller", "callee"):
                user = identity_from_participant((segment.get(role) or {}))
                if user:
                    yield user
from datetime import datetime, time, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

from productivity_next.meeting_sync.teams.token_manager import get_access_token
from productivity_next.meeting_sync.teams.resource import (
    GRAPH_BASE,
    call_record_participants_v2_url,
    identity_from_participant,
)

_GRAPH_TS_FMT = "%Y-%m-%dT%H:%M:%S"


def _graph_ts_to_local(ts, tz):
    """callRecord timestamps are UTC ISO strings, e.g. 2026-10-22T04:30:00.1234567Z."""
    if not ts:
        return None
    naive = datetime.strptime(ts[:19], _GRAPH_TS_FMT)
    return naive.replace(tzinfo=timezone.utc).astimezone(tz)


def _day_window(tz, day=None):
    """Local-day window as (start_local, end_local); end is exclusive."""
    day = day or datetime.now(tz).date()
    start_local = datetime.combine(day, time.min, tzinfo=tz)
    return start_local, start_local + timedelta(days=1)


def _to_utc_z(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _get_json(url, token, params=None):
    res = requests.get(url, headers=_headers(token), params=params, timeout=30)
    return res


def resolve_user_id(email, token):
    """Entra object id for an email/UPN (needs User.Read.All)."""
    res = _get_json(
        f"{GRAPH_BASE}/users/{quote(email, safe='@')}", token, params={"$select": "id,displayName"}
    )
    if res.status_code != 200:
        raise RuntimeError(f"Could not resolve user {email}: {res.status_code} {res.text[:500]}")
    return res.json()["id"]


def _list_call_records(filter_expr, token):
    """Page through GET /communications/callRecords?$filter=...

    Returns (status_code, records). Non-200 on the first page is returned to the caller so
    it can decide on a fallback; a failure on a later page raises.
    """
    url = f"{GRAPH_BASE}/communications/callRecords"
    params = {"$filter": filter_expr}
    records = []
    first = True
    while url:
        res = _get_json(url, token, params=params)
        if res.status_code != 200:
            if first:
                return res.status_code, res.text
            raise RuntimeError(f"Graph callRecords paging failed: {res.status_code} {res.text[:500]}")
        body = res.json()
        records.extend(body.get("value") or [])
        url = body.get("@odata.nextLink")
        params = None  # nextLink already carries the query
        first = False
    return 200, records


def _fetch_participants(call_id, token):
    """List responses omit participants_v2, so fetch it per record."""
    res = _get_json(call_record_participants_v2_url(call_id), token)
    if res.status_code != 200:
        return []
    out = []
    for p in res.json().get("participants_v2") or []:
        user = identity_from_participant(p)
        if user:
            out.append(
                {
                    "id": user.get("id", ""),
                    "name": user.get("displayName", ""),
                    "email": (user.get("userPrincipalName") or "").lower(),
                }
            )
    return out


def get_todays_call_records(
    email,
    day=None,
    tz_name="Asia/Kolkata",
    include_participants=False,
    user_id=None,
    token=None,
):
    """Return the Teams call records (calls and meetings) `email` took part in on a day.

    Uses GET /communications/callRecords filtered by the user's participant id and the
    day's start-time window. Graph documents each filter on its own; if the combined filter
    is rejected (400) it falls back to the participant filter and checks the date locally.

    Requires application permission CallRecords.Read.All, plus User.Read.All to look up the
    user's object id (or pass user_id to skip that lookup).

    Notes:
      - A call record only exists after the call ends, and can appear up to an hour or more
        later, so very recent calls may be missing.
      - Records are kept for 30 days.
      - include_participants=True makes one extra request per record.
    """
    tz = ZoneInfo(tz_name)
    token = token or get_access_token()
    user_id = user_id or resolve_user_id(email, token)

    start_local, end_local = _day_window(tz, day)
    participant_filter = f"participants_v2/any(p:p/id eq '{user_id}')"
    date_filter = (
        f"startDateTime ge {_to_utc_z(start_local)} and startDateTime lt {_to_utc_z(end_local)}"
    )

    status, result = _list_call_records(f"{date_filter} and {participant_filter}", token)
    if status == 200:
        raw = result
    elif status == 400:
        status, result = _list_call_records(participant_filter, token)
        if status != 200:
            raise RuntimeError(f"Graph callRecords failed for {email}: {status} {str(result)[:500]}")
        raw = result
    else:
        raise RuntimeError(f"Graph callRecords failed for {email}: {status} {str(result)[:500]}")

    records = []
    for rec in raw:
        start = _graph_ts_to_local(rec.get("startDateTime"), tz)
        end = _graph_ts_to_local(rec.get("endDateTime"), tz)
        # also enforces the day when the fallback (participant-only) path was used
        if not start or not (start_local <= start < end_local):
            continue

        organizer = ((rec.get("organizer_v2") or {}).get("identity") or {}).get("user") or {}
        item = {
            "id": rec.get("id"),
            "type": rec.get("type"),  # groupCall / peerToPeer
            "start": start,
            "end": end,
            "duration_seconds": int((end - start).total_seconds()) if end else None,
            "modalities": rec.get("modalities") or [],
            "join_web_url": rec.get("joinWebUrl"),
            "organizer_id": organizer.get("id", ""),
            "organizer_name": organizer.get("displayName", ""),
            "version": rec.get("version"),
        }
        if include_participants:
            item["participants"] = _fetch_participants(rec.get("id"), token)
        records.append(item)

    records.sort(key=lambda r: r["start"])
    return records


# Example:
#   for r in get_todays_call_records("ritik.patwa@finbyz.tech", include_participants=True):
#       print(r["start"].strftime("%H:%M"), r["type"], r["duration_seconds"], r["join_web_url"])
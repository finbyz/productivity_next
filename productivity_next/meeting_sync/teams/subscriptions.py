import frappe
import requests
from datetime import datetime, timedelta
from productivity_next.meeting_sync.teams.token_manager import get_access_token
from productivity_next.meeting_sync.teams.webhook import GRAPH_BASE, SUBSCRIPTION_RENEW_MINUTES, renew_subscription

# Graph subscriptions belong to the Azure app, not to a site: any site with the same
# Meeting Sync Settings (e.g. a development copy of production) sees and can delete the
# live subscriptions. Only the site Teams was enabled on manages them (common.is_enabled).

# Renew a subscription once it has less than this left. The scheduler runs every 10
# minutes, so this leaves plenty of attempts before Graph would drop it.
RENEW_WHEN_HOURS_LEFT = 24


def _wanted_subscriptions(base_url):
    return [
        {
            "key": "callRecords",
            "resource": "/communications/callRecords",
            "changeType": "created",
            "notificationUrl": f"{base_url}/api/method/productivity_next.meeting_sync.teams.webhook.callrecords",
            "lifecycleNotificationUrl": f"{base_url}/api/method/productivity_next.meeting_sync.teams.webhook.lifecycle",
        },
        {
            "key": "transcripts",
            "resource": "/communications/onlineMeetings/getAllTranscripts",
            "changeType": "created",
            "notificationUrl": f"{base_url}/api/method/productivity_next.meeting_sync.teams.webhook.transcripts",
            "lifecycleNotificationUrl": f"{base_url}/api/method/productivity_next.meeting_sync.teams.webhook.lifecycle",
        },
    ]


def _normalize_resource(resource):
    return (resource or "").strip().strip("/").lower()


def _expires_at(subscription):
    value = subscription.get("expirationDateTime") or ""
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def _list_subscriptions(headers):
    """All subscriptions this app created (app-only tokens only see their own)."""
    subscriptions = []
    url = f"{GRAPH_BASE}/subscriptions"
    while url:
        res = requests.get(url, headers=headers, timeout=30)
        res.raise_for_status()
        body = res.json()
        subscriptions.extend(body.get("value") or [])
        url = body.get("@odata.nextLink")
    return subscriptions


def _delete_subscription(subscription, headers, reason):
    res = requests.delete(
        f"{GRAPH_BASE}/subscriptions/{subscription['id']}", headers=headers, timeout=30
    )
    if res.status_code not in (204, 404):
        frappe.log_error(
            title=f"[SUBSCRIPTION] Delete failed ({subscription.get('resource')})",
            message=f"reason={reason}\nid={subscription['id']}\nstatus={res.status_code}\nbody={res.text[:1000]}",
        )


def _create_subscription(sub, webhook_secret, headers):
    body = {
        "changeType": sub["changeType"],
        "notificationUrl": sub["notificationUrl"],
        "lifecycleNotificationUrl": sub["lifecycleNotificationUrl"],
        "resource": sub["resource"],
        "expirationDateTime": (
            datetime.utcnow() + timedelta(minutes=SUBSCRIPTION_RENEW_MINUTES)
        ).strftime("%Y-%m-%dT%H:%M:%S.0000000Z"),
        "clientState": webhook_secret,
    }
    res = requests.post(f"{GRAPH_BASE}/subscriptions", json=body, headers=headers, timeout=60)
    if res.status_code != 201:
        # Without this subscription no meetings/transcripts arrive at all.
        frappe.log_error(
            title=f"[SUBSCRIPTION] Create failed ({sub['key']})",
            message=f"status={res.status_code}\nbody={res.text[:2000]}",
        )
    return res.status_code


def is_teams_sync_enabled():
    from productivity_next.meeting_sync.common import TEAMS, is_enabled

    return is_enabled(TEAMS)


@frappe.whitelist()
def queue_ensure_subscriptions():
    frappe.only_for("System Manager")
    frappe.enqueue(
        "productivity_next.meeting_sync.teams.subscriptions.ensure_subscriptions",
        queue="long",
    )
    return True


def ensure_subscriptions():
    """Keep one Graph subscription per resource alive (scheduled every 10 minutes).

    Existing subscriptions are renewed in place. Deleting and re-creating them every run,
    as before, dropped any notification Graph sent in between, so those calls never got a
    Meeting Call Log.

    Does nothing unless Teams is enabled in Meeting Sync Settings on this site.
    """
    if not is_teams_sync_enabled():
        return [{"action": "skipped", "reason": "Teams is not enabled in Meeting Sync Settings on this site"}]

    try:
        settings = frappe.get_single("Meeting Sync Settings")
        base_url = (settings.base_url or "").rstrip("/")
        webhook_secret = settings.get_password("webhook_secret")
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        existing = _list_subscriptions(headers)
    except Exception:
        frappe.log_error(
            title="[SUBSCRIPTION] Could not check subscriptions",
            message=frappe.get_traceback(),
        )
        return

    renew_before = datetime.utcnow() + timedelta(hours=RENEW_WHEN_HOURS_LEFT)
    results = []

    for sub in _wanted_subscriptions(base_url):
        try:
            same_resource = [
                s for s in existing
                if _normalize_resource(s.get("resource")) == _normalize_resource(sub["resource"])
            ]
            current = [s for s in same_resource if s.get("notificationUrl") == sub["notificationUrl"]]
            keep = max(current, key=lambda s: _expires_at(s) or datetime.min) if current else None

            # duplicates (each would deliver every notification again) and subscriptions
            # pointing at an old URL, e.g. a previous server
            for s in same_resource:
                if s is not keep:
                    _delete_subscription(s, headers, reason="duplicate or old notificationUrl")

            if keep:
                expires = _expires_at(keep)
                if not expires or expires <= renew_before:
                    renewed = renew_subscription(keep["id"], token=token)
                    results.append({"key": sub["key"], "action": "renewed" if renewed else "renew failed"})
                else:
                    results.append({"key": sub["key"], "action": "ok", "expires": keep.get("expirationDateTime")})
            else:
                status = _create_subscription(sub, webhook_secret, headers)
                results.append({"key": sub["key"], "action": "created", "status": status})
        except Exception:
            frappe.log_error(
                title=f"[SUBSCRIPTION] Ensure failed ({sub['key']})",
                message=frappe.get_traceback(),
            )

    return results

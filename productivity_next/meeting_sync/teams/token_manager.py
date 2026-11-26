import requests
import frappe
from datetime import datetime, timedelta

_cached_token = None
_token_expiry = None


def get_access_token():
    global _cached_token, _token_expiry

    if _cached_token and _token_expiry and datetime.now() < _token_expiry - timedelta(minutes=5):
        return _cached_token

    settings = frappe.get_single("Meeting Sync Settings")
    tenant_id = settings.tenant_id
    client_id = settings.client_id
    client_secret = settings.get_password("client_secret")

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }

    # timeout added: without it a stalled token request can hang a worker forever
    res = requests.post(url, data=data, timeout=30)
    res.raise_for_status()

    token_data = res.json()
    _cached_token = token_data["access_token"]
    _token_expiry = datetime.now() + timedelta(seconds=token_data["expires_in"])

    frappe.logger().info("MS Graph access token refreshed successfully")
    return _cached_token
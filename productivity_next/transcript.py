import frappe
import requests
import json

def fetch_transcripts():
    settings = frappe.get_single("Meeting Logs Settings")
    tenant_id = settings.tenant_id
    client_id = settings.client_id
    client_secret = settings.get_password("client_secret")

    organizer_id = "afed83ce-b6ed-4160-9db2-b0a3283e661a"
    meeting_id = "d94c0986-aab7-4250-a09b-bdb4e1183d2a"

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_response = requests.post(
        token_url,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
    )
    token_response.raise_for_status()
    access_token = token_response.json()["access_token"]

    url = f"https://graph.microsoft.com/v1.0/users/{organizer_id}/onlineMeetings/{meeting_id}/transcripts"
    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )
    print("Status Code:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    return response.json()
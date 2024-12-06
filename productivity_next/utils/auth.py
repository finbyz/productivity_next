from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, get_url

import hashlib

import frappe.oauth
import jwt
from oauthlib.oauth2.rfc6749.tokens import random_token_generator


def get_oath_client():
    client = frappe.db.get_value("OAuth Client", {})
    if not client:
        # Make one auto
        client = frappe.get_doc(
            frappe._dict(doctype="OAuth Client", app_name="default", scopes="all openid", redirect_urls=get_url(), default_redirect_uri=get_url(), grant_type="Implicit", response_type="Token")
        )
        client.insert(ignore_permissions=True)
    else:
        client = frappe.get_doc("OAuth Client", client)

    return client


def get_bearer_token(user, expires_in_days=7, purpose=None, date=None):
    if not date:
        date = get_datetime()
    else:
        date = get_datetime(date)

    expiration_time = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=max(cint(expires_in_days), 1))

    client = get_oath_client()
    token = frappe._dict(
        {
            "access_token": random_token_generator(None),
            "expiration_time": expiration_time,
            "expires_in": (expiration_time - get_datetime()).total_seconds(),
            "token_type": "Bearer",
            "scopes": client.scopes,
            "refresh_token": random_token_generator(None),
        }
    )
    if purpose:
        for row in frappe.get_all("OAuth Bearer Token", {"purpose": purpose, "user": user}, pluck="name"):
            frappe.delete_doc("OAuth Bearer Token", row, ignore_permissions=True)

    bearer_token = frappe.new_doc("OAuth Bearer Token")
    bearer_token.client = client.name
    bearer_token.scopes = token["scopes"]
    bearer_token.access_token = token["access_token"]
    bearer_token.refresh_token = token["refresh_token"]
    bearer_token.expiration_time = token["expiration_time"]
    bearer_token.expires_in = token["expires_in"]
    bearer_token.user = user
    bearer_token.purpose = purpose
    bearer_token.save(ignore_permissions=True)
    frappe.db.commit()

    # ID Token
    id_token_header = {"typ": "jwt", "alg": "HS256"}
    id_token = {
        "aud": "token_client",
        "exp": int((frappe.db.get_value("OAuth Bearer Token", token.access_token, "expiration_time") - frappe.utils.datetime.datetime(1970, 1, 1)).total_seconds()),
        "sub": frappe.db.get_value("User Social Login", {"parent": bearer_token.user, "provider": "frappe"}, "userid"),
        "iss": "frappe_server_url",
        "at_hash": frappe.oauth.calculate_at_hash(token.access_token, hashlib.sha256),
    }
    id_token_encoded = jwt.encode(id_token, "client_secret", algorithm="HS256", headers=id_token_header)
    id_token_encoded = frappe.safe_decode(id_token_encoded)
    token.id_token = id_token_encoded
    frappe.flags.jwt = id_token_encoded

    return token


def update_expiry_time(user, refresh_token, expires_in_days=7, purpose=None, date=None):
    if not date:
        date = get_datetime()
    else:
        date = get_datetime(date)

    expiration_time = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=max(cint(expires_in_days), 1))
    outh_bearer_token_name = frappe.db.get_value("OAuth Bearer Token", filters={"refresh_token": refresh_token, "purpose": purpose, "user": user}, fieldname="name")
    
    if outh_bearer_token_name:
       frappe.db.set_value("OAuth Bearer Token", outh_bearer_token_name, "expiration_time", expiration_time)
       frappe.db.set_value("OAuth Bearer Token", outh_bearer_token_name, "expires_in", (expiration_time - get_datetime()).total_seconds())
       frappe.db.set_value("OAuth Bearer Token", outh_bearer_token_name, "refresh_token", random_token_generator(None))

    return outh_bearer_token_name

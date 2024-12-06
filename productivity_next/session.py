import frappe
from frappe.utils import cint


def on_session_creation(login_manager):
    from .utils.auth import get_bearer_token

    if frappe.form_dict.get("use_jwt") and cint(frappe.form_dict.get("use_jwt")):
        expires_in_days = 60
        frappe.local.response["token"] = get_bearer_token(user=login_manager.user, expires_in_days=expires_in_days)["access_token"]
        frappe.flags.jwt_clear_cookies = True
        return frappe.local.response["token"]

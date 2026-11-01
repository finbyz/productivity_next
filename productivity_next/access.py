"""Who may read whose Productify data.

Rule (agreed 1 Nov 2026):
  - an employee sees their own data and that of everyone who reports to them,
    directly or indirectly (Employee "Reports To" chain);
  - Productify Manager and System Manager see everyone's;
  - portal (Website) users see no employee data.

Endpoints called by the desktop / mobile apps start in observe mode: a call that the
rule would refuse is only written to logs/productify_access.log. Endpoints listed in
site_config "productify_access_enforce" (or all, with "*") refuse such calls instead.
"""

import frappe
from frappe import _

MANAGER_ROLES = {"Productify Manager", "System Manager"}
CACHE_SECONDS = 600


def employee_of(value):
	"""Employee for an Employee ID or a User ID; None when it is neither."""
	if not value:
		return None
	if frappe.db.exists("Employee", value):
		return value
	return frappe.db.get_value("Employee", {"user_id": value}, "name")


def visible_employees(user=None):
	"""Employees the user may see; None means everyone."""
	user = user or frappe.session.user
	if user == "Administrator" or MANAGER_ROLES & set(frappe.get_roles(user)):
		return None
	key = f"productify_visible_employees:{user}"
	cached = frappe.cache.get_value(key)
	if cached is not None:
		return set(cached)
	me = frappe.db.get_value("Employee", {"user_id": user}, "name")
	visible = set()
	if me:
		visible, frontier = {me}, [me]
		while frontier:
			reports = frappe.get_all("Employee", filters={"reports_to": ["in", frontier]}, pluck="name")
			frontier = [e for e in reports if e not in visible]
			visible.update(frontier)
	frappe.cache.set_value(key, sorted(visible), expires_in_sec=CACHE_SECONDS)
	return visible


def _enforced(endpoint):
	setting = frappe.conf.get("productify_access_enforce") or []
	return setting == "*" or endpoint in setting


def check_employee_access(*targets, enforce=False):
	"""Check the caller may see every target (Employee or User ID; empty = caller's own data).

	Returns True when allowed. Otherwise logs the call, and raises PermissionError when the
	endpoint is enforced (by argument or by site_config).
	"""
	user = frappe.session.user
	reason = None
	if user == "Guest":
		reason = "not logged in"
	else:
		visible = visible_employees(user)
		if visible is not None:
			for target in targets:
				if not target:
					continue
				employee = employee_of(target)
				if employee not in visible:
					reason = f"{employee or target} is outside the caller's team"
					break
	if not reason:
		return True

	endpoint = (frappe.request.path.rsplit("/", 1)[-1] if getattr(frappe, "request", None) else "") or "?"
	enforce = enforce or _enforced(endpoint)
	# Frappe sets these loggers to ERROR level, so write at that level
	frappe.logger("productify_access", allow_site=True, max_size=5_000_000, file_count=5).error(
		f"{'DENIED' if enforce else 'WOULD-DENY'} {endpoint} caller={user} targets={list(targets)} reason={reason}"
	)
	if enforce:
		frappe.throw(_("You are not permitted to view this employee's data."), frappe.PermissionError)
	return False


import re as _re

_DATE_ARGS = {"start_date", "end_date", "date", "from_date", "to_date"}
_PERSON_ARGS = {"user", "employee"}
_PHONE_ARGS = {"client_no", "customer_no", "employee_mobile"}
_PHONE = _re.compile(r"^[0-9+\-() ]{1,25}$")
_URLISH = _re.compile(r"^[\w.\-:/%?=&#~+@ ]{1,500}$")


def validate_sql_args(**values):
	"""Reject argument values that are not of their expected kind.

	Several Productify queries put these values into SQL text, so anything that is not a
	real date, an existing Employee/User/Project/DocType, an hour or a phone number is
	refused before the query runs.
	"""
	from frappe.utils import get_datetime, getdate

	for name, value in values.items():
		if value in (None, ""):
			continue
		try:
			if name in _DATE_ARGS:
				getdate(value)
				ok = bool(_re.match(r"^\d{4}-\d{2}-\d{2}$", str(value)[:10])) and "'" not in str(value)
			elif name == "call_datetime":
				get_datetime(value)
				ok = "'" not in str(value)
			elif name in _PERSON_ARGS:
				ok = value == "Administrator" or bool(employee_of(value)) or bool(frappe.db.exists("User", value))
			elif name == "project":
				ok = bool(frappe.db.exists("Project", value))
			elif name == "hour":
				ok = 0 <= int(value) <= 23
			elif name in _PHONE_ARGS:
				ok = bool(_PHONE.match(str(value)))
			elif name == "url_data":
				ok = bool(_URLISH.match(str(value)))
			else:
				ok = "'" not in str(value) and "\\" not in str(value)
		except Exception:
			ok = False
		if not ok:
			frappe.throw(_("Invalid value for {0}").format(name), frappe.ValidationError)

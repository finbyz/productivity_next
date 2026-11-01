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

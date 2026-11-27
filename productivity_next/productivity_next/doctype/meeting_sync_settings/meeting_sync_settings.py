# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class MeetingSyncSettings(Document):
	def validate(self):
		self.set_active_sites()
		self.validate_google_key_is_private()

	def set_active_sites(self):
		"""Remember which site a provider was switched on for (see common.is_enabled)."""
		from productivity_next.meeting_sync.common import PROVIDER_FIELDS

		for enabled_field, site_field in PROVIDER_FIELDS.values():
			if not self.get(enabled_field):
				self.set(site_field, None)
			elif self.has_value_changed(enabled_field) or not self.get(site_field):
				self.set(site_field, frappe.local.site)

	@frappe.whitelist()
	def activate_on_this_site(self):
		"""Settings form button for a restored copy: take over the sync on this site."""
		frappe.only_for("System Manager")
		from productivity_next.meeting_sync.common import PROVIDER_FIELDS

		for enabled_field, site_field in PROVIDER_FIELDS.values():
			if self.get(enabled_field):
				self.set(site_field, frappe.local.site)
		self.save()

	def validate_google_key_is_private(self):
		"""The service account key gives access to every mailbox's meetings: it must never be
		a public file."""
		if not self.google_service_account_key:
			return
		is_private = frappe.db.get_value("File", {"file_url": self.google_service_account_key}, "is_private")
		if not is_private and not self.google_service_account_key.startswith("/private/"):
			frappe.throw(_("The Service Account Key must be uploaded as a private file."))

	def on_update(self):
		if self.enable_teams and self.teams_active_site == frappe.local.site:
			frappe.enqueue(
				"productivity_next.meeting_sync.teams.subscriptions.ensure_subscriptions",
				queue="long",
				enqueue_after_commit=True,
			)

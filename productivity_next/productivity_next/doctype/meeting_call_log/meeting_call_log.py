# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from productivity_next.meeting_sync.common import GOOGLE_MEET, TEAMS


class MeetingCallLog(Document):
	"""One call from Microsoft Teams or Google Meet. The sync creates it; the transcript
	lands in raw_vtt (WebVTT for both providers)."""

	def after_insert(self):
		if self.provider == TEAMS:
			self._after_insert_teams()

	def _after_insert_teams(self):
		# Same follow-up jobs the original Teams Meeting Log ran after insert.
		frappe.enqueue(
			"productivity_next.meeting_sync.teams.transcript.update_meeting_subject",
			meeting_log_name=self.name,
			queue="long",
			job_id=f"ms-teams-subject::{self.name}",
			deduplicate=True,
			enqueue_after_commit=True,
		)
		if not self.raw_vtt:
			frappe.enqueue(
				"productivity_next.meeting_sync.teams.transcript.fetch_transcript_for_doc",
				docname=self.name,
				queue="long",
				job_id=f"ms-teams-transcript::{self.name}",
				deduplicate=True,
				enqueue_after_commit=True,
			)


@frappe.whitelist()
def queue_fetch_transcript(docname):
	"""Form button: fetch the transcript again from the call's provider."""
	frappe.has_permission("Meeting Call Log", "write", docname, throw=True)
	provider = frappe.db.get_value("Meeting Call Log", docname, "provider")
	if provider == GOOGLE_MEET:
		method, prefix = "productivity_next.meeting_sync.google_meet.sync.fetch_transcript_for_log", "gmeet-transcript"
	else:
		method, prefix = "productivity_next.meeting_sync.teams.transcript.fetch_transcript_for_doc", "ms-teams-transcript"
	frappe.enqueue(
		method,
		docname=docname,
		queue="long",
		job_id=f"{prefix}::{docname}",
		deduplicate=True,
	)
	return True

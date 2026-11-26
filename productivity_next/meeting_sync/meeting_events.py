# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt
"""Meeting doc events for meetings created by the sync (ported from finbyz doc_events)."""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import format_datetime, get_datetime

from productivity_next.meeting_sync.common import GOOGLE_MEET, TEAMS

# Set from the provider's call record; users may not change them on a synced meeting.
SYNCED_LOCKED_FIELDS = ("meeting_from", "meeting_to")


def queue_missing_meeting(doc, method=None):
	"""Queue Meeting creation when a call log has both times and no linked Meeting."""
	if not (doc.get("actual_start") and doc.get("actual_end")):
		return
	if frappe.db.exists("Meeting", {"meeting_call_log": doc.name}):
		return

	provider = doc.get("provider")
	if provider == GOOGLE_MEET:
		job = "productivity_next.meeting_sync.google_meet.sync.create_meeting_from_log"
		prefix = "gmeet-meeting"
	elif provider == TEAMS:
		job = "productivity_next.meeting_sync.teams.reprocess.reprocess_meeting_from_log"
		prefix = "ms-teams-reprocess"
	else:
		return
	frappe.enqueue(
		job,
		log_name=doc.name,
		queue="long",
		job_id=f"{prefix}::{doc.name}",
		deduplicate=True,
		enqueue_after_commit=True,
	)


def before_validate(doc, method=None):
	set_meeting_source(doc)
	prevent_synced_time_change(doc)
	set_synced_arranged_by(doc)
	shift_synced_start_past_overlaps(doc)


def set_synced_arranged_by(doc):
	"""A synced (Teams / Google Meet) meeting organised by someone outside the company (or by
	a user without an ERP account) has no meeting_arranged_by; productivity_next assigns the Task it creates
	on submit to that user, and Task.assignee is mandatory. Use the first internal
	participant."""
	if not doc.get("meeting_call_log") or doc.get("meeting_arranged_by"):
		return
	for rep in doc.get("meeting_company_representative") or []:
		user = rep.get("emp_user_id") or (rep.employee and frappe.db.get_value("Employee", rep.employee, "user_id"))
		if user and frappe.db.exists("User", user):
			doc.meeting_arranged_by = user
			return


def set_meeting_source(doc):
	# meeting_call_log is always populated by the sync, never by the user. A Meeting linked
	# to a Meeting Call Log takes its provider as meeting_source.
	#
	# Note: this runs in `before_validate` (not `validate`) because the sync saves the
	# Meeting with `flags.ignore_validate = True`, which skips `validate`/`before_save`
	# but not `before_validate`.
	if doc.get("meeting_call_log") and not doc.get("meeting_source"):
		doc.meeting_source = frappe.db.get_value("Meeting Call Log", doc.meeting_call_log, "provider")


def shift_synced_start_past_overlaps(doc):
	"""Synced meetings carry the real call times, so productivity_next's check "Employee
	already has a meeting during this time period" (Meeting.validate, which runs after
	this hook) would refuse to save one that overlaps another submitted meeting of the
	same participant. Start the Teams meeting right after the overlapping meeting ends
	instead. A Teams meeting lying entirely inside another one cannot be fixed that way
	and is left for the overlap check to report. Meetings entered by hand are untouched.
	"""
	if not doc.get("meeting_call_log") or not (doc.meeting_from and doc.meeting_to):
		return
	employees = [r.employee for r in doc.get("meeting_company_representative") or [] if r.employee]
	if not employees:
		return

	original_start = get_datetime(doc.meeting_from)
	meeting_from = original_start
	meeting_to = get_datetime(doc.meeting_to)
	while True:
		# same condition as productivity_next's overlap check
		latest_end = frappe.db.sql(
			"""SELECT MAX(m.meeting_to)
			FROM `tabMeeting` m
			JOIN `tabMeeting Company Representative` cr ON cr.parent = m.name
			WHERE cr.employee IN %(employees)s
				AND m.meeting_from <= %(meeting_to)s AND m.meeting_to >= %(meeting_from)s
				AND m.name != %(name)s AND m.docstatus = 1""",
			{"employees": employees, "meeting_from": meeting_from, "meeting_to": meeting_to, "name": doc.name},
		)[0][0]
		if not latest_end:
			break
		new_start = get_datetime(latest_end) + timedelta(seconds=1)
		if new_start >= meeting_to:
			return  # entirely inside another meeting
		meeting_from = new_start  # the moved window may meet another meeting: check again

	if meeting_from != original_start:
		doc.meeting_from = meeting_from
		frappe.msgprint(
			_("Start time moved to {0} so this meeting does not overlap another meeting of its participants.").format(
				format_datetime(meeting_from)
			),
			alert=True,
		)


def prevent_synced_time_change(doc):
	# The form makes these fields read-only; this also covers API, import and scripts.
	# Runs in before_validate because the sync saves with flags.ignore_validate;
	# the sync itself sets flags.from_productivity_next.meeting_sync.
	if doc.is_new() or doc.flags.from_meeting_sync or not doc.get("meeting_call_log"):
		return
	for fieldname in SYNCED_LOCKED_FIELDS:
		if doc.has_value_changed(fieldname):
			frappe.throw(
				_("{0} of a {1} meeting is taken from the call and cannot be changed.").format(
					_(doc.meta.get_label(fieldname)), doc.get("meeting_source") or _("synced")
				),
				title=_("Synced Meeting"),
			)

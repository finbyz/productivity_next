"""Scheduler entry points. Each provider's jobs run only where that provider is enabled
(ticked in Meeting Sync Settings on this site, see productivity_next.meeting_sync.common.is_enabled), and one
failing job does not stop the others."""

import frappe

from productivity_next.meeting_sync.common import GOOGLE_MEET, TEAMS, is_enabled


def _run(path):
	try:
		frappe.get_attr(path)()
	except Exception:
		frappe.log_error(title=f"Meeting Sync job failed: {path}")


def teams_every_10_minutes():
	if not is_enabled(TEAMS):
		return
	_run("productivity_next.meeting_sync.teams.subscriptions.ensure_subscriptions")
	_run("productivity_next.meeting_sync.teams.auto_transcribe.run")


def teams_every_30_minutes():
	if not is_enabled(TEAMS):
		return
	_run("productivity_next.meeting_sync.teams.transcript.retry_pending_transcripts")
	_run("productivity_next.meeting_sync.teams.reprocess.retry_missing_meetings")
	_run("productivity_next.meeting_sync.teams.reprocess.refresh_call_records")
	_run("productivity_next.meeting_sync.teams.reprocess.sync_missing_call_records")


def google_every_15_minutes():
	if not is_enabled(GOOGLE_MEET):
		return
	_run("productivity_next.meeting_sync.google_meet.sync.sync_recent_conferences")
	_run("productivity_next.meeting_sync.google_meet.sync.retry_pending_transcripts")


def google_hourly():
	if not is_enabled(GOOGLE_MEET):
		return
	_run("productivity_next.meeting_sync.google_meet.auto_transcribe.run")

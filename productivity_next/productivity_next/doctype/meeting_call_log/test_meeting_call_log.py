# Copyright (c) 2026, FinByz Tech Pvt Ltd and Contributors
# See license.txt

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import frappe
from frappe.tests import UnitTestCase

from productivity_next.meeting_sync.common import GOOGLE_MEET, TEAMS
from productivity_next.meeting_sync.google_meet.sync import build_vtt, find_calendar_event
from productivity_next.meeting_sync.meeting_events import queue_missing_meeting
from productivity_next.meeting_sync.teams.webhook import _parse_vtt


class UnitTestMeetingCallLog(UnitTestCase):
	def test_google_entries_become_vtt_the_teams_parser_reads(self):
		start = datetime(2026, 11, 25, 9, 0, tzinfo=timezone.utc)
		entries = [
			{"participant": "p/1", "text": "Let us review the rollout.", "startTime": "2026-11-25T09:00:05.120Z", "endTime": "2026-11-25T09:00:08Z"},
			{"participant": "p/2", "text": "Agreed, <draft> is ready.", "startTime": "2026-11-25T09:01:00Z", "endTime": "2026-11-25T09:01:03Z"},
		]
		vtt = build_vtt(entries, {"p/1": "Asha", "p/2": "Ravi"}, start)
		self.assertTrue(vtt.startswith("WEBVTT"))
		self.assertIn("00:00:05.120 --> 00:00:08.000", vtt)
		parsed = _parse_vtt(vtt)
		self.assertIn("Asha: Let us review the rollout.", parsed)
		self.assertIn("Ravi: Agreed,", parsed)

	def test_no_entries_gives_empty_transcript(self):
		self.assertEqual(build_vtt([], {}, None), "")

	def test_log_queues_meeting_creation_before_transcript_arrives(self):
		for provider, module, function, prefix in (
			(GOOGLE_MEET, "google_meet.sync", "create_meeting_from_log", "gmeet-meeting"),
			(TEAMS, "teams.reprocess", "reprocess_meeting_from_log", "ms-teams-reprocess"),
		):
			with self.subTest(provider=provider):
				log = frappe._dict(
					name="test-call",
					provider=provider,
					actual_start=datetime(2026, 11, 25, 9, 0),
					actual_end=datetime(2026, 11, 25, 9, 10),
				)
				with patch.object(frappe.local, "db", Mock(), create=True), patch.object(frappe, "enqueue") as enqueue:
					frappe.db.exists.return_value = None
					queue_missing_meeting(log)
					enqueue.assert_called_once_with(
						f"productivity_next.meeting_sync.{module}.{function}",
						log_name=log.name,
						queue="long",
						job_id=f"{prefix}::{log.name}",
						deduplicate=True,
						enqueue_after_commit=True,
					)

					enqueue.reset_mock()
					frappe.db.exists.return_value = "Existing Meeting"
					queue_missing_meeting(log)
					enqueue.assert_not_called()

	def test_calendar_lookup_uses_calendar_pagination_parameters(self):
		start = datetime(2026, 11, 25, 9, 0, tzinfo=timezone.utc)
		event = {"conferenceData": {"conferenceId": "abc-defg-hij"}, "summary": "Review"}
		with patch(
			"productivity_next.meeting_sync.google_meet.client.request",
			side_effect=[{"items": [], "nextPageToken": "next"}, {"items": [event]}],
		) as request:
			self.assertEqual(find_calendar_event(Mock(), "organizer@example.com", "abc-defg-hij", start, start), event)
			params = request.call_args.kwargs["params"]
			self.assertEqual(params["maxResults"], 250)
			self.assertEqual(params["pageToken"], "next")
			self.assertNotIn("pageSize", params)

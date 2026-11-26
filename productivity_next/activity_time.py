"""Count every minute of an employee's tracked activity once.

FinByz rule (Nov 2026), used by every Productify time figure that splits time between
tasks, projects or activity types: where activities overlap, the time goes to ONE
activity - a call wins over a meeting, a meeting over the desktop timer (Application
Usage log); between two of the same kind, the one started last wins.

Nightly timesheets (schedule.create_timesheet_logs) already follow this order by cutting
meetings and then calls into the timer logs; reports use allocate() below.
"""

import heapq
from collections import defaultdict
from datetime import datetime, time, timedelta

import frappe
from frappe.utils import get_datetime, getdate

CALL, MEETING, APPLICATION = 0, 1, 2
SOURCE_NAMES = {CALL: "call", MEETING: "meeting", APPLICATION: "application"}


def allocate(intervals):
    """Split overlapping activity so each moment belongs to one activity.

    intervals: iterable of (start, end, rank, item) with rank CALL / MEETING / APPLICATION
    (lower wins) and item any value describing the activity (e.g. a dict with task/project).
    Returns non-overlapping (start, end, rank, item) segments in time order; a segment is
    the part of one interval that it wins, so the same interval can give several segments.
    """
    rows = []
    for order, (start, end, rank, item) in enumerate(intervals):
        if not start or not end:
            continue
        if not isinstance(start, datetime):
            start = get_datetime(start)
        if not isinstance(end, datetime):
            end = get_datetime(end)
        if end > start:
            rows.append((start, end, rank, order, item))
    rows.sort(key=lambda row: row[0])

    boundaries = sorted({moment for row in rows for moment in row[:2]})
    segments = []
    running = []
    position = 0
    for segment_start, segment_end in zip(boundaries, boundaries[1:]):
        while position < len(rows) and rows[position][0] <= segment_start:
            start, end, rank, order, item = rows[position]
            # order breaks ties, so items themselves are never compared
            heapq.heappush(running, (rank, -start.timestamp(), order, end, item))
            position += 1
        while running and running[0][3] <= segment_start:
            heapq.heappop(running)
        if not running:
            continue
        rank, _, order, _, item = running[0]
        if segments and segments[-1][4] == order and segments[-1][1] == segment_start:
            segments[-1][1] = segment_end
        else:
            segments.append([segment_start, segment_end, rank, item, order])
    return [(start, end, rank, item) for start, end, rank, item, _ in segments]


def seconds_by(segments, key):
    """Total seconds of allocated segments per key(rank, item); keys that are None are skipped."""
    totals = defaultdict(float)
    for start, end, rank, item in segments:
        group = key(rank, item)
        if group is not None:
            totals[group] += (end - start).total_seconds()
    return totals


def employee_activity(employee, start_at, end_at):
    """All tracked activity of one employee overlapping [start_at, end_at), clipped to it,
    as allocate() input: (start, end, rank, item) with item = frappe._dict(task, project,
    issue, name, source). Calls that were missed or rejected are left out; meetings count
    only when submitted. Activity without a task or project is included on purpose: it
    still wins its time (a call with no task takes the minute from the task on the timer).
    """
    start_at, end_at = get_datetime(start_at), get_datetime(end_at)
    params = {
        "employee": employee, "start_at": start_at, "end_at": end_at,
        # A row dated the day before can run past midnight into the period
        "from_day": getdate(start_at) - timedelta(days=1), "to_day": getdate(end_at),
    }
    queries = (
        (APPLICATION, """
            SELECT name, task, project, issue, from_time AS start_time, to_time AS end_time,
                IF(IFNULL(url, '') = '', 0, 1) AS is_web
            FROM `tabApplication Usage log`
            WHERE employee = %(employee)s AND `date` BETWEEN %(from_day)s AND %(to_day)s
        """),
        (CALL, """
            SELECT name, task, project, issue, call_datetime AS start_time,
                ADDTIME(call_datetime, SEC_TO_TIME(duration)) AS end_time, calltype,
                IF(link_to = 'Company', 1, 0) AS is_internal
            FROM `tabEmployee Fincall`
            WHERE employee = %(employee)s AND `date` BETWEEN %(from_day)s AND %(to_day)s
                AND calltype NOT IN ('Missed', 'Rejected')
        """),
        (MEETING, """
            SELECT m.name, m.task, m.project, m.issue, m.meeting_from AS start_time,
                m.meeting_to AS end_time, m.internal_meeting AS is_internal
            FROM `tabMeeting` m
            JOIN `tabMeeting Company Representative` r ON r.parent = m.name
            WHERE r.employee = %(employee)s AND m.docstatus = 1
                AND m.meeting_from < %(end_at)s AND m.meeting_to > %(start_at)s
        """),
    )
    intervals = []
    for rank, query in queries:
        for row in frappe.db.sql(query, params, as_dict=True):
            if not row.start_time or not row.end_time:
                continue
            start = max(get_datetime(row.start_time), start_at)
            end = min(get_datetime(row.end_time), end_at)
            if end > start:
                row.source = SOURCE_NAMES[rank]
                intervals.append((start, end, rank, row))
    return intervals


def day_bounds(from_date, to_date):
    """[start of from_date, start of the day after to_date)."""
    return (
        datetime.combine(getdate(from_date), time.min),
        datetime.combine(getdate(to_date) + timedelta(days=1), time.min),
    )


def activity_breakdown(employee, from_date, to_date):
    """One employee's tracked time in the period (to_date included), every second counted
    once by the rule above, split into parts that add up to "total" (seconds):
    call_incoming / call_outgoing / call_other (calls with a customer or other party),
    call_internal_incoming / call_internal_outgoing / call_internal_other (link_to Company),
    meeting_internal / meeting_external, application_web (a URL) / application_app,
    plus the sums call, meeting and application. Idle time is not subtracted here.
    """
    totals = defaultdict(float)
    start_at, end_at = day_bounds(from_date, to_date)
    for start, end, rank, item in allocate(employee_activity(employee, start_at, end_at)):
        seconds = (end - start).total_seconds()
        if rank == CALL:
            kind = {"Incoming": "incoming", "Outgoing": "outgoing"}.get(item.calltype, "other")
            part = f"call_internal_{kind}" if item.is_internal else f"call_{kind}"
            group = "call"
        elif rank == MEETING:
            part = "meeting_internal" if item.is_internal else "meeting_external"
            group = "meeting"
        else:
            part = "application_web" if item.is_web else "application_app"
            group = "application"
        totals[part] += seconds
        totals[group] += seconds
        totals["total"] += seconds
    return {key: round(value) for key, value in totals.items()}

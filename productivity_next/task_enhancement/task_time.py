"""Submitted days are authoritative; unsubmitted days use tracked activity.

On unsubmitted days every second counts once, on the activity that wins it
(activity_time.allocate: a call wins over a meeting, a meeting over the desktop timer),
so the same minute is never counted on two tasks - as in the nightly timesheets.
"""

from collections import defaultdict
from datetime import datetime, time, timedelta

import frappe
from frappe.utils import get_datetime

from productivity_next.activity_time import allocate, employee_activity


def get_task_totals(tasks, start, end, current_day):
    """Return task/employee seconds without caching submission state."""
    if start and start > current_day:
        return {}
    start_at = datetime.combine(start, time.min) if start else None
    end_at = datetime.combine(min(end or current_day, current_day) + timedelta(days=1), time.min)
    historical_end = min(end_at, datetime.combine(current_day, time.min))
    activity = _activity_intervals(tasks, start_at, end_at)
    employees = {employee for _, employee in activity if employee}
    rows = _submitted_rows(tasks, employees, start_at, historical_end)
    totals = _submitted_totals(rows, start_at, historical_end)
    coverage = _submitted_days(rows, start_at, historical_end)
    wanted = set(tasks)
    by_employee = defaultdict(list)
    for (task, employee), intervals in activity.items():
        by_employee[employee].extend(intervals)
    for employee, intervals in by_employee.items():
        if not employee:
            continue
        employee_coverage = coverage.get(employee, [])
        # Only the days not covered by a submitted Timesheet use activity; on those days
        # all of the employee's activity is allocated, not only the listed tasks'.
        for window_start, window_end in _day_windows(
            _subtract(_merge(intervals), employee_coverage), start_at, end_at
        ):
            for begin, finish, _rank, item in allocate(
                employee_activity(employee, window_start, window_end)
            ):
                if item.task not in wanted:
                    continue
                seconds = sum(
                    (piece_end - piece_start).total_seconds()
                    for piece_start, piece_end in _subtract([(begin, finish)], employee_coverage)
                )
                if seconds:
                    employee_totals = totals.setdefault(item.task, {})
                    employee_totals[employee] = employee_totals.get(employee, 0) + seconds
    return totals


def _day_windows(intervals, start_at, end_at):
    """Whole calendar days touched by the intervals, joined into consecutive runs and
    clipped to the period: the windows whose activity is allocated."""
    days = set()
    for begin, finish in intervals:
        day = begin.date()
        while datetime.combine(day, time.min) < finish:
            days.add(day)
            day += timedelta(days=1)
    windows = []
    for day in sorted(days):
        day_start = datetime.combine(day, time.min)
        day_end = day_start + timedelta(days=1)
        if windows and windows[-1][1] == day_start:
            windows[-1][1] = day_end
        else:
            windows.append([day_start, day_end])
    return [
        (max(begin, start_at) if start_at else begin, min(finish, end_at))
        for begin, finish in windows
        if (not start_at or finish > start_at) and begin < end_at
    ]


def _submitted_rows(tasks, employees, start_at, end_at):
    if start_at and start_at >= end_at:
        return []
    conditions = [
        "tsd.task IN %(tasks)s", "ts.docstatus = 1",
        "tsd.from_time < %(end_at)s", "tsd.to_time > tsd.from_time",
    ]
    params = {"tasks": tuple(tasks), "end_at": end_at}
    if start_at:
        conditions.append("tsd.to_time > %(start_at)s")
        params["start_at"] = start_at
    query = """
        SELECT tsd.task, ts.employee, tsd.from_time, tsd.to_time, tsd.hours,
            NULL AS start_date, NULL AS end_date
        FROM `tabTimesheet Detail` tsd
        JOIN `tabTimesheet` ts ON ts.name = tsd.parent
        WHERE """ + " AND ".join(conditions)
    if employees:
        params["employees"] = tuple(sorted(employees))
        lower = "AND end_date >= %(start_at)s" if start_at else ""
        # Read submission coverage and hours in one snapshot. A submission
        # between separate reads could suppress fallback without adding hours.
        query += """
            UNION ALL
            SELECT NULL AS task, employee, NULL AS from_time, NULL AS to_time,
                NULL AS hours, start_date, end_date
            FROM `tabTimesheet`
            WHERE docstatus = 1 AND employee IN %(employees)s
                AND start_date < %(end_at)s
            """ + lower
    return frappe.db.sql(query, params, as_dict=True)


def _submitted_totals(rows, start_at, end_at):
    totals = {}
    for row in rows:
        if not row.task:
            continue
        begin, finish = get_datetime(row.from_time), get_datetime(row.to_time)
        clipped = _clip(begin, finish, start_at, end_at)
        if clipped and finish > begin:
            proportion = (clipped[1] - clipped[0]) / (finish - begin)
            seconds = float(row.hours or 0) * 3600 * proportion
            employees = totals.setdefault(row.task, {})
            employees[row.employee] = employees.get(row.employee, 0) + seconds
    return totals


def _submitted_days(rows, start_at, end_at):
    coverage = defaultdict(list)
    for row in rows:
        if not row.start_date or not row.end_date:
            continue
        interval = _clip(
            get_datetime(row.start_date), get_datetime(row.end_date) + timedelta(days=1),
            start_at, end_at,
        )
        if interval:
            coverage[row.employee].append(interval)
    return {employee: _merge(intervals) for employee, intervals in coverage.items()}


def _activity_intervals(tasks, start_at, end_at):
    params = {"tasks": tuple(tasks), "end_at": end_at}
    sources = (
        ("`tabApplication Usage log`", "employee", "task", "from_time", "to_time", ""),
        ("`tabEmployee Fincall`", "employee", "task", "call_datetime",
         "ADDTIME(call_datetime, SEC_TO_TIME(duration))", "AND calltype NOT IN ('Missed', 'Rejected')"),
        ("`tabMeeting` m JOIN `tabMeeting Company Representative` r ON r.parent = m.name",
         "r.employee", "m.task", "m.meeting_from", "m.meeting_to", "AND m.docstatus = 1"),
    )
    activity = defaultdict(list)
    for table, employee, task, begin, finish, extra in sources:
        lower = ""
        if start_at:
            lower = f"AND {finish} > %(start_at)s"
            params["start_at"] = start_at
        rows = frappe.db.sql(
            f"""
            SELECT {employee} AS employee, {task} AS task,
                {begin} AS start_time, {finish} AS end_time
            FROM {table}
            WHERE {task} IN %(tasks)s AND {begin} < %(end_at)s {lower} {extra}
            """, params, as_dict=True,
        )
        for row in rows:
            if row.start_time and row.end_time:
                interval = _clip(
                    get_datetime(row.start_time), get_datetime(row.end_time), start_at, end_at
                )
                if interval:
                    activity[(row.task, row.employee)].append(interval)
    return activity


def _clip(begin, finish, start_at, end_at):
    begin = max(begin, start_at) if start_at else begin
    finish = min(finish, end_at)
    return (begin, finish) if finish > begin else None


def _merge(intervals):
    merged = []
    for begin, finish in sorted(intervals):
        if merged and begin <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], finish))
        else:
            merged.append((begin, finish))
    return merged


def _subtract(intervals, coverage):
    """Remove submitted calendar days from fallback intervals, including midnight overlaps."""
    remaining = []
    index = 0
    for begin, finish in intervals:
        while index < len(coverage) and coverage[index][1] <= begin:
            index += 1
        cursor = begin
        for coverage_index in range(index, len(coverage)):
            covered_start, covered_end = coverage[coverage_index]
            if covered_start >= finish:
                break
            if covered_start > cursor:
                remaining.append((cursor, min(covered_start, finish)))
            cursor = max(cursor, covered_end)
            if cursor >= finish:
                break
        if cursor < finish:
            remaining.append((cursor, finish))
    return remaining

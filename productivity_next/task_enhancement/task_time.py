"""Submitted days are authoritative; unsubmitted days use tracked activity."""

from collections import defaultdict
from datetime import datetime, time, timedelta

import frappe
from frappe.utils import get_datetime


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
    for (task, employee), intervals in activity.items():
        seconds = sum(
            (finish - begin).total_seconds()
            for begin, finish in _subtract(_merge(intervals), coverage.get(employee, []))
        )
        if seconds:
            employee_totals = totals.setdefault(task, {})
            employee_totals[employee] = employee_totals.get(employee, 0) + seconds
    return totals


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

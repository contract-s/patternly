"""Tester-trial metrics: completion, hints to solve, and longest streak."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

import psycopg

from patternly.evals.testers import LessonRow, format_report, last_complete_day, load, longest_run, report, window
from patternly.service.db import apply_schema

D = date(2026, 11, 16)


def day(i: int) -> date:
    return D + timedelta(i)


def test_window_stops_before_today():
    assert window(D, 7, day(3)) == [day(0), day(1), day(2)]
    assert len(window(D, 7, day(30))) == 7


def test_last_complete_day_waits_for_the_last_time_zone():
    # 11:00 UTC on the 17th is still the 16th at UTC-12, so the 15th is the last day over everywhere.
    assert last_complete_day(datetime(2026, 11, 17, 11, tzinfo=UTC)) == date(2026, 11, 15)
    assert last_complete_day(datetime(2026, 11, 17, 13, tzinfo=UTC)) == date(2026, 11, 16)


def test_longest_run_inside_the_window():
    days = [day(i) for i in range(7)]
    assert longest_run({day(0), day(1), day(3), day(4), day(5)}, days) == 3
    assert longest_run(set(), days) == 0


def test_report():
    lessons = [
        LessonRow(1, day(0), "passed", 0),
        LessonRow(1, day(1), "passed", 2),
        LessonRow(1, day(2), "revealed", 4),
        LessonRow(1, day(4), "open", 1),  # opened, not finished
        LessonRow(2, day(1), "passed", 1),
        LessonRow(2, day(9), "passed", 0),  # after the trial
    ]
    r = report([1, 2, 3], lessons, D, 7, day(30))
    assert (r["days"], r["tester_days"], r["finished_days"]) == (7, 21, 4)
    assert r["completion"] == 4 / 21
    assert (r["passed"], r["revealed"], r["first_try"]) == (3, 1, 1)
    assert r["mean_hints_to_solve"] == 1  # (0 + 2 + 1) / 3; the revealed lesson isn't a solve
    assert [t.longest_streak for t in r["testers"]] == [3, 1, 0]
    assert r["median_longest_streak"] == 1
    text = format_report(r)
    assert "Daily completion: 19.0% (4 of 21 tester-days)" in text
    assert "Longest streak: median 1 days" in text


def test_report_without_data():
    text = format_report(report([], [], D, 7, D))
    assert "no data" in text and "0 testers" in text
    assert "Hints to solve: no solved lessons yet; 0 revealed unsolved" in text


def test_load_counts_failed_attempts_and_filters_testers(clean_db):
    async def go():
        async with await psycopg.AsyncConnection.connect(clean_db, autocommit=True) as conn:
            await apply_schema(conn)
            ids = []
            for email in ("me@x.test", "a@x.test", "b@x.test"):
                cur = await conn.execute(
                    "INSERT INTO learners (email, password_hash, timezone) VALUES (%s, 'x', 'UTC') RETURNING id",
                    (email,),
                )
                ids.append((await cur.fetchone())[0])
            cur = await conn.execute(
                """INSERT INTO lessons (learner_id, local_date, scenario_id, pattern_id, kind, status)
                   VALUES (%s, %s, 's', 'p', 'new', 'passed'), (%s, %s, 's', 'p', 'new', 'passed') RETURNING id""",
                (ids[1], day(0), ids[1], day(8)),
            )
            lesson = (await cur.fetchone())[0]
            for n, verdict in enumerate(["fail", "fail", "pass"], 1):
                await conn.execute(
                    """INSERT INTO attempts (lesson_id, attempt, answer, verdict, items, hint, hint_source,
                                             cost_usd, latency_s) VALUES (%s, %s, 'x', %s, '{}', '', '', 0, 0)""",
                    (lesson, n, verdict),
                )
            everyone = await load(conn, D, 7, exclude=["ME@x.test"])
            just_b = await load(conn, D, 7, only=[ids[2]])
            return ids, everyone, just_b

    ids, (testers, lessons), (only_ids, _) = asyncio.run(go())
    assert testers == ids[1:] and only_ids == [ids[2]]
    assert lessons == [LessonRow(ids[1], day(0), "passed", 2)]


def test_tester_report_command(clean_db, monkeypatch, capsys):
    from patternly.cli import main

    async def schema():
        async with await psycopg.AsyncConnection.connect(clean_db, autocommit=True) as conn:
            await apply_schema(conn)
            await conn.execute("INSERT INTO learners (email, password_hash, timezone) VALUES ('t@x.test', 'x', 'UTC')")

    asyncio.run(schema())
    monkeypatch.setenv("DATABASE_URL", clean_db)
    assert main(["tester-report", "--start", "2026-11-01", "--days", "7"]) == 0
    out = capsys.readouterr().out
    assert "1 testers" in out and "Daily completion: 0.0% (0 of 7 tester-days)" in out

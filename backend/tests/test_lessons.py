"""Lesson logic against a scratch Postgres database, with a fake tutor."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

import psycopg
import pytest

from patternly.service.auth import hash_password
from patternly.service.lessons import (
    MAX_ATTEMPTS,
    Learner,
    LessonError,
    get_progress,
    get_streak,
    local_today,
    submit_attempt,
    todays_lesson,
)

from .conftest import fake_grader, two_pattern_content

NOON = datetime(2026, 11, 11, 12, tzinfo=UTC)


@pytest.fixture
def content(content_dir):
    return two_pattern_content(content_dir)


def run(clean_db, fn):
    async def go():
        async with await psycopg.AsyncConnection.connect(clean_db, autocommit=True) as conn:
            cur = await conn.execute(
                "INSERT INTO learners (email, password_hash, timezone) VALUES ('a@x.test', %s, 'UTC') RETURNING id",
                (hash_password("pw"),),
            )
            learner = Learner((await cur.fetchone())[0], "a@x.test", "UTC")
            return await fn(conn, learner)

    return asyncio.run(go())


def test_local_today_uses_learner_time_zone():
    late = datetime(2026, 11, 11, 3, tzinfo=UTC)  # 10 pm on the 10th in New York
    assert local_today(late, "America/New_York") == date(2026, 11, 10)
    assert local_today(late, "Asia/Tokyo") == date(2026, 11, 11)


def test_todays_lesson_is_stable_within_a_day(clean_db, content):
    async def fn(conn, learner):
        first = await todays_lesson(conn, content, learner, NOON)
        again = await todays_lesson(conn, content, learner, NOON + timedelta(hours=3))
        return first, again

    first, again = run(clean_db, fn)
    assert first == again
    assert (first["scenario_id"], first["kind"], first["status"]) == ("s-a1", "new", "open")


def test_pass_after_a_hint_finishes_and_schedules(clean_db, content):
    async def fn(conn, learner):
        await todays_lesson(conn, content, learner, NOON)
        a1, lesson = await submit_attempt(conn, content, learner, "wrong idea", NOON, fake_grader)
        assert (a1["verdict"], a1["hint_level"], lesson["status"]) == ("fail", 1, "open")
        a2, lesson = await submit_attempt(conn, content, learner, "right idea", NOON, fake_grader)
        assert (a2["attempt"], a2["verdict"], lesson["status"], lesson["outcome"]) == (2, "pass", "passed", "hinted")
        with pytest.raises(LessonError) as e:
            await submit_attempt(conn, content, learner, "again", NOON, fake_grader)
        assert e.value.status == 409
        return await get_progress(conn, learner.id), await get_streak(conn, learner, NOON)

    progress, streak = run(clean_db, fn)
    assert progress["pat-a"].box == 1 and progress["pat-a"].due == date(2026, 11, 12)
    assert (streak.current, streak.done_today) == (1, True)


def test_missed_pattern_comes_back_as_review(clean_db, content):
    async def fn(conn, learner):
        await todays_lesson(conn, content, learner, NOON)
        for _ in range(MAX_ATTEMPTS):
            _, lesson = await submit_attempt(conn, content, learner, "wrong", NOON, fake_grader)
        assert (lesson["status"], lesson["outcome"]) == ("revealed", "missed")
        tomorrow = await todays_lesson(conn, content, learner, NOON + timedelta(days=1))
        return tomorrow

    tomorrow = run(clean_db, fn)
    # Same pattern, a scenario the learner hasn't seen.
    assert (tomorrow["pattern_id"], tomorrow["kind"], tomorrow["scenario_id"]) == ("pat-a", "review", "s-a2")


def test_clean_pass_moves_on_to_a_new_pattern_and_extends_streak(clean_db, content):
    async def fn(conn, learner):
        await todays_lesson(conn, content, learner, NOON)
        await submit_attempt(conn, content, learner, "right", NOON, fake_grader)
        day2 = NOON + timedelta(days=1)
        lesson = await todays_lesson(conn, content, learner, day2)
        await submit_attempt(conn, content, learner, "right", day2, fake_grader)
        return lesson, await get_streak(conn, learner, day2)

    lesson, streak = run(clean_db, fn)
    assert (lesson["pattern_id"], lesson["kind"]) == ("pat-b", "new")
    assert streak.current == 2


def test_submit_without_lesson_and_tutor_errors(clean_db, content):
    def broken(scenario, answer, history, learner_id):
        r = fake_grader(scenario, answer, history, learner_id)
        r.error, r.items = "RuntimeError: boom", None
        return r

    async def fn(conn, learner):
        with pytest.raises(LessonError) as e:
            await submit_attempt(conn, content, learner, "x", NOON, fake_grader)
        assert e.value.status == 404
        lesson = await todays_lesson(conn, content, learner, NOON)
        with pytest.raises(LessonError) as e:
            await submit_attempt(conn, content, learner, "x", NOON, broken)
        assert e.value.status == 502
        cur = await conn.execute("SELECT count(*) FROM attempts WHERE lesson_id = %s", (lesson["id"],))
        return (await cur.fetchone())[0]

    assert run(clean_db, fn) == 0  # nothing saved

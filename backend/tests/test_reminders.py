"""Reminder emails against the scratch database, with a fake sender."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from urllib.parse import parse_qs, urlparse

import psycopg
import pytest
from fastapi.testclient import TestClient

from patternly.service.app import create_app
from patternly.service.auth import hash_password, make_token
from patternly.service.reminders import (
    due,
    read_unsubscribe_token,
    send_due,
    ses_sender,
    unsubscribe_token,
)

from .conftest import fake_grader, two_pattern_content

SECRET = "s" * 32
# 7:30 pm in New York (EST, UTC-5) on 2026-11-12; 4:30 pm in Los Angeles; 9:30 am the next day in Tokyo.
EVENING_NY = datetime(2026, 11, 13, 0, 30, tzinfo=UTC)


class Outbox:
    def __init__(self, fail_for: set[str] = frozenset()) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.fail_for = fail_for

    def __call__(self, to: str, subject: str, body: str) -> None:
        if to in self.fail_for:
            raise RuntimeError("MessageRejected: Email address is not verified.")
        self.sent.append((to, subject, body))


def with_conn(url, fn):
    async def go():
        async with await psycopg.AsyncConnection.connect(url, autocommit=True) as conn:
            return await fn(conn)

    return asyncio.run(go())


def add_learner(url, email: str, tz: str, hour: int = 19) -> int:
    async def fn(conn):
        cur = await conn.execute(
            "INSERT INTO learners (email, password_hash, timezone, reminder_hour) VALUES (%s, %s, %s, %s) RETURNING id",
            (email, hash_password("pw"), tz, hour),
        )
        return (await cur.fetchone())[0]

    return with_conn(url, fn)


def finish_lesson(url, learner_id: int, day: date) -> None:
    async def fn(conn):
        await conn.execute(
            "INSERT INTO lessons (learner_id, local_date, scenario_id, pattern_id, kind, status, outcome)"
            " VALUES (%s, %s, 's-a1', 'pat-a', 'new', 'passed', 'clean')",
            (learner_id, day),
        )

    with_conn(url, fn)


def send(url, outbox, now=EVENING_NY, dry_run=False):
    return with_conn(
        url, lambda conn: send_due(conn, now, outbox, app_url="https://app.test/", secret=SECRET, dry_run=dry_run)
    )


def test_due_respects_each_learners_local_time(clean_db):
    ny = add_learner(clean_db, "ny@x.test", "America/New_York")
    add_learner(clean_db, "la@x.test", "America/Los_Angeles")
    add_learner(clean_db, "tokyo@x.test", "Asia/Tokyo")
    found = with_conn(clean_db, lambda conn: due(conn, EVENING_NY))
    assert [(learner.id, day) for learner, day in found] == [(ny, date(2026, 11, 12))]


def test_each_learner_gets_their_own_reminder_hour(clean_db):
    # At 7:30 pm in New York: 7 pm and 8 am learners are due (8 am's hour has passed), 9 pm isn't yet.
    seven_pm = add_learner(clean_db, "a@x.test", "America/New_York", hour=19)
    add_learner(clean_db, "b@x.test", "America/New_York", hour=21)
    morning = add_learner(clean_db, "c@x.test", "America/New_York", hour=8)
    found = with_conn(clean_db, lambda conn: due(conn, EVENING_NY))
    assert sorted(learner.id for learner, _ in found) == [seven_pm, morning]


def test_finished_lessons_and_unsubscribed_learners_are_skipped(clean_db):
    done = add_learner(clean_db, "done@x.test", "America/New_York")
    off = add_learner(clean_db, "off@x.test", "America/New_York")
    finish_lesson(clean_db, done, date(2026, 11, 12))
    with_conn(
        clean_db, lambda conn: conn.execute("UPDATE learners SET reminders_enabled = false WHERE id = %s", (off,))
    )
    assert with_conn(clean_db, lambda conn: due(conn, EVENING_NY)) == []


def test_an_open_lesson_still_gets_a_reminder(clean_db):
    learner = add_learner(clean_db, "open@x.test", "America/New_York")

    async def open_lesson(conn):
        await conn.execute(
            "INSERT INTO lessons (learner_id, local_date, scenario_id, pattern_id, kind)"
            " VALUES (%s, '2026-11-12', 's-a1', 'pat-a', 'new')",
            (learner,),
        )

    with_conn(clean_db, open_lesson)
    assert len(with_conn(clean_db, lambda conn: due(conn, EVENING_NY))) == 1


def test_sends_once_per_local_day(clean_db):
    add_learner(clean_db, "ny@x.test", "America/New_York")
    outbox = Outbox()
    first = send(clean_db, outbox)
    again = send(clean_db, outbox)
    assert [r.status for r in first] == ["sent"]
    assert again == []
    assert len(outbox.sent) == 1


def test_email_links_to_the_app_and_a_working_unsubscribe(clean_db):
    learner = add_learner(clean_db, "ny@x.test", "America/New_York")
    finish_lesson(clean_db, learner, date(2026, 11, 11))  # yesterday: a 1-day streak
    outbox = Outbox()
    send(clean_db, outbox)
    to, subject, body = outbox.sent[0]
    assert to == "ny@x.test"
    assert "https://app.test" in body and "https://app.test//" not in body
    assert "1-day streak" in body
    link = next(word for word in body.split() if "/api/reminders/unsubscribe?" in word)
    token = parse_qs(urlparse(link).query)["token"][0]
    assert read_unsubscribe_token(token, SECRET) == learner


def test_failed_sends_are_recorded_and_not_retried(clean_db):
    add_learner(clean_db, "bad@x.test", "America/New_York")
    add_learner(clean_db, "good@x.test", "America/New_York")
    outbox = Outbox(fail_for={"bad@x.test"})
    results = send(clean_db, outbox)
    assert sorted(r.status for r in results) == ["failed", "sent"]
    assert "not verified" in next(r.error for r in results if r.status == "failed")
    assert send(clean_db, outbox) == []

    async def statuses(conn):
        cur = await conn.execute("SELECT status FROM reminders ORDER BY learner_id")
        return [r[0] for r in await cur.fetchall()]

    assert with_conn(clean_db, statuses) == ["failed", "sent"]


def test_dry_run_sends_and_records_nothing(clean_db):
    add_learner(clean_db, "ny@x.test", "America/New_York")
    outbox = Outbox()
    assert [r.status for r in send(clean_db, outbox, dry_run=True)] == ["dry-run"]
    assert outbox.sent == []
    assert [r.status for r in send(clean_db, outbox)] == ["sent"]


def test_access_tokens_dont_work_as_unsubscribe_tokens():
    assert read_unsubscribe_token(unsubscribe_token(7, SECRET), SECRET) == 7
    assert read_unsubscribe_token(make_token(7, SECRET), SECRET) is None
    assert read_unsubscribe_token(unsubscribe_token(7, "x" * 32), SECRET) is None
    assert read_unsubscribe_token("garbage", SECRET) is None


@pytest.fixture
def api(clean_db, content_dir):
    app = create_app(two_pattern_content(content_dir), fake_grader, secret=SECRET, database_url=clean_db)
    with TestClient(app) as client:
        yield client


def test_unsubscribe_page_asks_before_turning_reminders_off(api, clean_db):
    learner = add_learner(clean_db, "ny@x.test", "America/New_York")
    token = unsubscribe_token(learner, SECRET)

    page = api.get("/reminders/unsubscribe", params={"token": token})
    assert page.status_code == 200 and "<form" in page.text
    assert len(with_conn(clean_db, lambda conn: due(conn, EVENING_NY))) == 1  # viewing changes nothing

    done = api.post("/reminders/unsubscribe", data={"token": token})
    assert done.status_code == 200 and "Reminders are off" in done.text
    assert with_conn(clean_db, lambda conn: due(conn, EVENING_NY)) == []


def test_learners_read_and_change_their_reminder_time(api):
    token = api.post(
        "/auth/register", json={"email": "me@x.test", "password": "password1", "timezone": "America/New_York"}
    ).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    assert api.get("/me", headers=auth).json()["reminders"] == {"enabled": True, "hour": 19}

    changed = api.put("/me/reminders", headers=auth, json={"enabled": True, "hour": 7})
    assert changed.json() == {"enabled": True, "hour": 7}
    assert api.get("/me", headers=auth).json()["reminders"] == {"enabled": True, "hour": 7}

    assert api.put("/me/reminders", headers=auth, json={"enabled": False, "hour": 7}).json()["enabled"] is False
    assert api.put("/me/reminders", headers=auth, json={"enabled": True, "hour": 24}).status_code == 422
    assert api.put("/me/reminders", json={"enabled": True, "hour": 7}).status_code == 401


def test_unsubscribe_rejects_bad_tokens(api):
    assert api.get("/reminders/unsubscribe", params={"token": "nope"}).status_code == 400
    assert api.post("/reminders/unsubscribe", data={"token": make_token(1, SECRET)}).status_code == 400


def test_ses_sender_uses_aws_region(monkeypatch):
    import boto3

    made = {}
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-east-2")
    monkeypatch.setattr(boto3, "client", lambda service, region_name=None: made.update(region=region_name))
    ses_sender("from@x.test")
    assert made["region"] == "us-east-2"


def test_ses_sender_sends_as_patternly(monkeypatch):
    import boto3

    calls = []

    class Client:
        def send_email(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(boto3, "client", lambda service, region_name=None: Client())
    ses_sender("reminders@x.test", region="us-east-2")("learner@x.test", "Subject", "Body")
    assert calls[0]["FromEmailAddress"] == "Patternly <reminders@x.test>"
    assert calls[0]["Destination"] == {"ToAddresses": ["learner@x.test"]}

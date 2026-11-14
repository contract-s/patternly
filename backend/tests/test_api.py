"""The API end to end, with a fake tutor and a scratch database: the Weekend 5 "Done when" check."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from patternly.service.app import create_app
from patternly.service.lessons import MAX_ATTEMPTS

from .conftest import fake_grader, two_pattern_content

SECRET = "s" * 32


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 11, 15, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def next_day(self) -> None:
        self.now += timedelta(days=1)


@pytest.fixture
def api(clean_db, content_dir):
    clock = Clock()
    app = create_app(two_pattern_content(content_dir), fake_grader, secret=SECRET, database_url=clean_db, clock=clock)
    with TestClient(app) as client:
        token = client.post(
            "/auth/register", json={"email": "Me@X.test", "password": "longenough", "timezone": "America/Detroit"}
        ).json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        yield client, clock


def submit(client, answer):
    r = client.post("/lessons/today/attempts", json={"answer": answer})
    assert r.status_code == 200, r.text
    return r.json()


def test_auth(api):
    client, _ = api
    assert client.get("/me").json()["email"] == "me@x.test"
    anon = {"Authorization": ""}
    assert client.get("/me", headers=anon).status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    bad = {"email": "me@x.test", "password": "nope-nope"}
    assert client.post("/auth/login", json=bad).status_code == 401
    good = client.post("/auth/login", json={"email": "ME@x.test", "password": "longenough"})
    assert good.status_code == 200 and good.json()["token_type"] == "bearer"
    dupe = client.post("/auth/register", json={"email": "me@x.test", "password": "longenough"})
    assert dupe.status_code == 409
    tz = client.post("/auth/register", json={"email": "z@x.test", "password": "longenough", "timezone": "Mars/Base"})
    assert tz.status_code == 422


def test_full_lesson_streak_and_review_queue(api):
    client, clock = api

    # Day 1: a new pattern, solved on the first try (back in 2 days).
    lesson = client.get("/lessons/today").json()
    assert (lesson["kind"], lesson["status"], lesson["attempts_left"]) == ("new", "open", MAX_ATTEMPTS)
    assert "Pattern A" not in str(lesson)
    done = submit(client, "the right idea")
    assert done["lesson"]["status"] == "passed" and done["lesson"]["reveal"]["pattern"] == "Pattern A"
    assert done["lesson"]["next_review"] == "2026-11-13"
    assert done["streak"] == {"current": 1, "longest": 1, "freezes": 0, "done_today": True}
    assert client.post("/lessons/today/attempts", json={"answer": "more"}).status_code == 409

    # Day 2: the next new pattern. Hints get stronger; nothing is revealed until the lesson ends.
    clock.next_day()
    lesson = client.get("/lessons/today").json()
    assert (lesson["kind"], lesson["scenario"]["id"]) == ("new", "s-b1")
    for n in range(1, MAX_ATTEMPTS + 1):
        out = submit(client, "a wrong idea")
        assert out["attempt"]["answer"] == "a wrong idea"
        assert out["attempt"]["hint_level"] == min(n, 3) and out["attempt"]["hint"] == f"Hint {min(n, 3)}."
        assert out["attempt"]["ideas_hit"] == ["First idea."] and out["attempt"]["ideas_total"] == 2
        if n < MAX_ATTEMPTS:
            assert out["lesson"]["reveal"] is None and out["lesson"]["attempts_left"] == MAX_ATTEMPTS - n
    # Out of attempts: revealed, and it still counts for the streak.
    assert out["lesson"]["status"] == "revealed" and out["lesson"]["reveal"]["pattern"] == "Pattern B"
    assert out["lesson"]["next_review"] == "2026-11-13"
    assert out["streak"]["current"] == 2

    # Day 3: both patterns are due; the missed one (lower box) comes back first, with its other scenario.
    clock.next_day()
    reviews = client.get("/reviews").json()
    assert [(r["pattern"], r["last_outcome"]) for r in reviews["due"]] == [("pat-b", "missed"), ("pat-a", "clean")]
    lesson = client.get("/lessons/today").json()
    assert (lesson["kind"], lesson["scenario"]["id"]) == ("review", "s-b2")
    submit(client, "right")
    assert client.get("/me").json()["streak"]["current"] == 3
    assert [r["pattern"] for r in client.get("/reviews").json()["due"]] == ["pat-a"]


def test_requests_are_traced_and_grading_nests_under_them(clean_db, content_dir, spans):
    from opentelemetry.trace import SpanKind

    from patternly.tracing import tracer

    def traced_grader(*args):
        with tracer.start_as_current_span("tutor.attempt"):
            return fake_grader(*args)

    app = create_app(
        two_pattern_content(content_dir), traced_grader, secret=SECRET, database_url=clean_db, clock=Clock()
    )
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        token = client.post("/auth/register", json={"email": "t@x.test", "password": "longenough"}).json()
        client.headers["Authorization"] = f"Bearer {token['access_token']}"
        client.get("/lessons/today")
        submit(client, "an answer")
    finished = spans.get_finished_spans()
    servers = {sp.name: sp for sp in finished if sp.kind == SpanKind.SERVER}
    assert set(servers) == {"POST /auth/register", "GET /lessons/today", "POST /lessons/today/attempts"}
    request = servers["POST /lessons/today/attempts"]
    assert request.attributes["http.route"] == "/lessons/today/attempts"
    (grading,) = [sp for sp in finished if sp.name == "tutor.attempt"]
    assert grading.context.trace_id == request.context.trace_id
    assert grading.parent.span_id == request.context.span_id
    assert not [sp.name for sp in finished if sp.name.endswith((" http send", " http receive"))]
    assert "longenough" not in str([dict(sp.attributes) for sp in finished])

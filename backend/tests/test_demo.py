"""Demo limits: the daily tutor budget, the per-learner cap, guest accounts, and sign-ups per IP."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from patternly.service.app import create_app
from patternly.service.demo import DemoLimits, SignupLimiter, client_ip

from .conftest import fake_grader, two_pattern_content

SECRET = "s" * 32


def costly_grader(scenario, answer, history, learner_id):
    """The fake tutor, charging $0.03 per attempt."""
    r = fake_grader(scenario, answer, history, learner_id)
    r.usages = [SimpleNamespace(cost_usd=0.03)]
    return r


def make_client(clean_db, content_dir, limits):
    content = two_pattern_content(content_dir)
    return TestClient(create_app(content, costly_grader, secret=SECRET, database_url=clean_db, limits=limits))


def sign_up(client, email="me@x.test", **headers):
    return client.post(
        "/auth/register", json={"email": email, "password": "longenough", "timezone": "UTC"}, headers=headers
    )


def login_as(client, response):
    assert response.status_code == 201, response.text
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


def attempt(client, answer="a wrong idea"):
    r = client.post("/lessons/today/attempts", json={"answer": answer})
    assert r.status_code == 200, r.text
    return r.json()["attempt"]


def test_client_ip_reads_the_entry_the_proxies_added():
    assert client_ip("1.1.1.1", "10.0.0.1", 1) == "1.1.1.1"  # nginx alone
    assert client_ip("6.6.6.6, 1.1.1.1, 130.176.0.1", "10.0.0.1", 2) == "1.1.1.1"  # spoofed, client, CloudFront
    assert client_ip(None, "10.0.0.1", 2) == "10.0.0.1"


def test_signup_limiter_slides_over_an_hour():
    now = [0.0]
    limiter = SignupLimiter(2, clock=lambda: now[0])
    assert limiter.allow("a") and limiter.allow("a") and not limiter.allow("a")
    assert limiter.allow("b")
    now[0] = 3600
    assert limiter.allow("a")
    assert SignupLimiter(None).allow("a")


def test_limits_from_env(monkeypatch):
    assert DemoLimits.from_env() == DemoLimits()
    monkeypatch.setenv("PATTERNLY_DAILY_BUDGET_USD", "1.5")
    monkeypatch.setenv("PATTERNLY_TUTOR_ATTEMPTS_PER_LEARNER", "5")
    monkeypatch.setenv("PATTERNLY_PROXY_HOPS", "2")
    assert DemoLimits.from_env() == DemoLimits(1.5, 5, None, 2)


def test_daily_budget_switches_to_the_offline_grader(clean_db, content_dir):
    with make_client(clean_db, content_dir, DemoLimits(daily_budget_usd=0.05)) as client:
        login_as(client, sign_up(client))
        client.get("/lessons/today")
        # $0.00 and $0.03 spent before these two, both under $0.05; then $0.06 is over.
        assert [attempt(client)["graded_by"] for _ in range(3)] == ["tutor", "tutor", "offline"]
        # The budget is shared: another learner gets the offline grader too.
        login_as(client, sign_up(client, "other@x.test"))
        client.get("/lessons/today")
        assert attempt(client)["graded_by"] == "offline"
        lesson = client.get("/lessons/today").json()
        assert [a["graded_by"] for a in lesson["attempts"]] == ["offline"]


def test_per_learner_cap(clean_db, content_dir):
    with make_client(clean_db, content_dir, DemoLimits(tutor_attempts_per_learner=1)) as client:
        login_as(client, sign_up(client))
        client.get("/lessons/today")
        assert [attempt(client)["graded_by"] for _ in range(2)] == ["tutor", "offline"]
        login_as(client, sign_up(client, "other@x.test"))
        client.get("/lessons/today")
        assert attempt(client)["graded_by"] == "tutor"


def test_guest_accounts(clean_db, content_dir):
    with make_client(clean_db, content_dir, DemoLimits()) as client:
        r = client.post("/auth/guest", json={"timezone": "America/Detroit"})
        login_as(client, r)
        me = client.get("/me").json()
        assert me["guest"] is True and me["email"].endswith("@guest.invalid")
        assert me["timezone"] == "America/Detroit" and me["reminders"]["enabled"] is False
        assert client.put("/me/reminders", json={"enabled": True, "hour": 9}).status_code == 403
        assert client.get("/lessons/today").json()["status"] == "open"
        # Each click is a new account; nobody can register on the guest domain.
        assert client.post("/auth/guest", json={}).json()["access_token"] != r.json()["access_token"]
        assert sign_up(client, "x@guest.invalid").status_code == 422
        login_as(client, sign_up(client))
        assert client.get("/me").json()["guest"] is False


@pytest.mark.parametrize("path", ["/auth/register", "/auth/guest"])
def test_signups_per_ip(clean_db, content_dir, path):
    limits = DemoLimits(signups_per_ip_per_hour=2, proxy_hops=2)
    with make_client(clean_db, content_dir, limits) as client:

        def new_account(n, xff):
            body = {"email": f"u{n}@x.test", "password": "longenough"} if path == "/auth/register" else {}
            return client.post(path, json=body, headers={"X-Forwarded-For": xff}).status_code

        assert [new_account(n, f"9.9.9.{n}, 1.1.1.1, 130.176.0.1") for n in range(3)] == [201, 201, 429]
        assert new_account(9, "1.1.1.2, 130.176.0.1") == 201


def test_offline_server_marks_attempts_offline(clean_db, content_dir):
    from patternly.service.offline import offline_grader

    content = two_pattern_content(content_dir)
    app = create_app(content, offline_grader, secret=SECRET, database_url=clean_db, grader_name="offline")
    with TestClient(app) as client:
        login_as(client, sign_up(client))
        client.get("/lessons/today")
        assert attempt(client)["graded_by"] == "offline"


def test_tutor_failure_falls_back_to_the_offline_grader(clean_db, content_dir):
    def failing(scenario, answer, history, learner_id):
        r = fake_grader(scenario, answer, history, learner_id)
        r.error, r.items = "BadRequestError: usage limit reached", None
        return r

    content = two_pattern_content(content_dir)
    with TestClient(create_app(content, failing, secret=SECRET, database_url=clean_db)) as client:
        login_as(client, sign_up(client))
        client.get("/lessons/today")
        a = attempt(client)
        assert a["graded_by"] == "offline" and a["verdict"] == "fail" and a["hint"]

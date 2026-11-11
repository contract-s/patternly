"""Builds throwaway content directories. Fixture text is placeholder, not real lesson content."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

KINDS = ["correct", "partial", "missing_key_idea", "wrong_pattern", "vague", "alternative"]
VERDICT = {
    "correct": "pass",
    "partial": "fail",
    "missing_key_idea": "fail",
    "wrong_pattern": "fail",
    "vague": "fail",
    "alternative": "pass",
}


def scenario(sid: str, pattern: str, prompt: str = "Placeholder prompt text.") -> dict:
    return {
        "id": sid,
        "pattern": pattern,
        "title": f"Placeholder {sid}",
        "prompt": prompt,
        "rubric": [{"id": "idea-a", "idea": "First idea."}, {"id": "idea-b", "idea": "Second idea."}],
        "hints": ["Placeholder nudge.", "Placeholder shape.", "Placeholder clue."],
        "reference_solution": "Placeholder solution.",
        "time_complexity": "O(n)",
        "space_complexity": "O(1)",
    }


def answer_set(sid: str) -> dict:
    answers = []
    for kind in KINDS:
        hit = kind in ("correct", "alternative")
        answers.append(
            {
                "id": kind.replace("_", "-"),
                "kind": kind,
                "verdict": VERDICT[kind],
                "text": f"Placeholder {kind} answer.",
                "labels": {
                    "idea-a": "hit" if hit or kind == "partial" else "miss",
                    "idea-b": "hit" if hit else "miss",
                },
            }
        )
    return {"scenario": sid, "answers": answers}


class ContentDir:
    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "scenarios").mkdir(parents=True)
        (root / "answers").mkdir()
        self.patterns([])

    def _write(self, rel: str, data: object) -> Path:
        path = self.root / rel
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return path

    def patterns(self, items: list[dict]) -> None:
        self._write("patterns.yaml", {"patterns": items})

    def scenario(self, data: dict, filename: str | None = None) -> None:
        self._write(f"scenarios/{filename or data['id']}.yaml", data)

    def answers(self, data: dict) -> None:
        self._write(f"answers/{data['scenario']}.yaml", data)

    def raw(self, rel: str, text: str) -> None:
        (self.root / rel).write_text(text, encoding="utf-8")

    def full(self, n_patterns: int = 5, per_pattern: int = 2) -> None:
        """A complete Weekend 1 set: 5 patterns x 2 scenarios x 6 answers = 60."""
        self.patterns([{"id": f"pat-{p}", "name": f"Pattern {p}"} for p in range(n_patterns)])
        for p in range(n_patterns):
            for i in range(per_pattern):
                sid = f"s-{p}-{i}"
                self.scenario(scenario(sid, f"pat-{p}"))
                self.answers(answer_set(sid))


@pytest.fixture
def content_dir(tmp_path: Path) -> ContentDir:
    return ContentDir(tmp_path / "content")


# ---- Postgres for service tests ----

TEST_DB = "patternly_test"


def _admin_url() -> str:
    from patternly.retrieval.store import database_url

    return database_url()


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """A scratch database next to the dev one, with the service schema. Skips if Postgres isn't running."""
    import asyncio

    import psycopg

    from patternly.service.db import apply_schema

    admin = _admin_url()
    try:
        with psycopg.connect(admin, autocommit=True, connect_timeout=2) as conn:
            if conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)).fetchone() is None:
                conn.execute(f"CREATE DATABASE {TEST_DB}")
    except psycopg.OperationalError:
        pytest.skip("Postgres isn't running (docker compose up -d)")
    url = admin.rsplit("/", 1)[0] + "/" + TEST_DB

    async def setup() -> None:
        async with await psycopg.AsyncConnection.connect(url, autocommit=True) as conn:
            await apply_schema(conn)

    asyncio.run(setup())
    return url


@pytest.fixture
def clean_db(test_db_url: str) -> str:
    import psycopg

    with psycopg.connect(test_db_url, autocommit=True) as conn:
        conn.execute("TRUNCATE learners, lessons, attempts, pattern_progress RESTART IDENTITY CASCADE")
    return test_db_url


def two_pattern_content(content_dir: ContentDir):
    """2 patterns x 2 scenarios, loaded."""
    from patternly.content.loader import load_content

    content_dir.patterns(
        [
            {"id": "pat-a", "name": "Pattern A", "summary": "A summary."},
            {"id": "pat-b", "name": "Pattern B", "summary": "B summary."},
        ]
    )
    for p in ("a", "b"):
        for i in (1, 2):
            content_dir.scenario(scenario(f"s-{p}{i}", f"pat-{p}"))
    return load_content(content_dir.root)


def fake_grader(scenario, answer, history, learner_id):
    """Passes answers containing 'right'; otherwise fails with a hint at the next level."""
    from patternly.tutor.agent import AttemptResult
    from patternly.tutor.baseline import ItemCall
    from patternly.tutor.history import next_hint_level

    previous = history.attempts(learner_id, scenario.id)
    ok = "right" in answer
    level = None if ok else next_hint_level(previous)
    return AttemptResult(
        scenario_id=scenario.id,
        learner_id=learner_id,
        attempt=len(previous) + 1,
        hint_level=level,
        items=[ItemCall(rubric_id=r, evidence="e", hit=ok or n == 0) for n, r in enumerate(scenario.rubric_ids)],
        verdict="pass" if ok else "fail",
        hint="" if ok else f"Hint {level}.",
        hint_source="" if ok else "tutor",
    )

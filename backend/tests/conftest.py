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

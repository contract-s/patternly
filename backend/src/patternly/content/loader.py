"""Load the content directory into typed models, collecting problems instead of failing fast."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from .models import Answer, AnswerSet, Pattern, Scenario, Split, answer_key

PATTERNS_FILE = "patterns.yaml"
SPLIT_FILE = "splits.yaml"
SCENARIOS_DIR = "scenarios"
ANSWERS_DIR = "answers"


@dataclass(frozen=True)
class Issue:
    level: str  # "error" or "warning"
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():7} {self.where}: {self.message}"


@dataclass(frozen=True)
class LabeledAnswer:
    """An answer joined with its scenario, addressed by a global key."""

    key: str
    scenario: Scenario
    answer: Answer


@dataclass
class Content:
    root: Path
    patterns: dict[str, Pattern] = field(default_factory=dict)
    scenarios: dict[str, Scenario] = field(default_factory=dict)
    answer_sets: dict[str, AnswerSet] = field(default_factory=dict)
    split: Split | None = None
    issues: list[Issue] = field(default_factory=list)

    def all_answers(self) -> list[LabeledAnswer]:
        out = []
        for sid in sorted(self.answer_sets):
            scenario = self.scenarios.get(sid)
            if scenario is None:
                continue
            for a in self.answer_sets[sid].answers:
                out.append(LabeledAnswer(answer_key(sid, a.id), scenario, a))
        return out

    def sealed_answers(self) -> list[LabeledAnswer]:
        """Final-metrics answers. Never use these while developing or tuning prompts."""
        sealed = set(self.split.sealed) if self.split else set()
        return [la for la in self.all_answers() if la.key in sealed]

    def dev_answers(self) -> list[LabeledAnswer]:
        """Answers safe to look at and tune against."""
        sealed = set(self.split.sealed) if self.split else set()
        return [la for la in self.all_answers() if la.key not in sealed]


def find_content_dir(start: Path | None = None) -> Path:
    """$PATTERNLY_CONTENT, else the nearest ancestor's content/ folder."""
    env = os.environ.get("PATTERNLY_CONTENT")
    if env:
        return Path(env)
    here = (start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        candidate = d / "content"
        if (candidate / PATTERNS_FILE).is_file():
            return candidate
    raise FileNotFoundError(
        "No content/patterns.yaml found above the current directory; pass --content or set PATTERNLY_CONTENT."
    )


def _read_yaml(path: Path, content: Content) -> object | None:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        content.issues.append(Issue("error", _rel(path, content), f"invalid YAML: {e}"))
        return None


def _parse[M: BaseModel](model: type[M], data: object, path: Path, content: Content) -> M | None:
    try:
        return model.model_validate(data)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "(root)"
            content.issues.append(Issue("error", f"{_rel(path, content)} [{loc}]", err["msg"]))
        return None


def _rel(path: Path, content: Content) -> str:
    try:
        return str(path.relative_to(content.root))
    except ValueError:
        return str(path)


def _yaml_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.iterdir() if p.suffix in {".yaml", ".yml"} and not p.name.startswith("_")
    )


def load_content(root: Path) -> Content:
    content = Content(root=root)

    patterns_path = root / PATTERNS_FILE
    if not patterns_path.is_file():
        content.issues.append(Issue("error", PATTERNS_FILE, "file is missing"))
    else:
        data = _read_yaml(patterns_path, content)
        raw = (data or {}).get("patterns") if isinstance(data, dict) else None
        if data is not None and not isinstance(raw, list | None):
            content.issues.append(Issue("error", PATTERNS_FILE, "'patterns' must be a list"))
            raw = None
        for i, item in enumerate(raw or []):
            p = _parse(Pattern, item, patterns_path, content)
            if p is None:
                continue
            if p.id in content.patterns:
                content.issues.append(
                    Issue("error", f"{PATTERNS_FILE} [{i}]", f"duplicate pattern id '{p.id}'")
                )
            content.patterns[p.id] = p

    for path in _yaml_files(root / SCENARIOS_DIR):
        s = _parse(Scenario, _read_yaml(path, content), path, content)
        if s is None:
            continue
        if path.stem != s.id:
            content.issues.append(Issue("error", _rel(path, content), f"file name must match id '{s.id}'"))
        if s.id in content.scenarios:
            content.issues.append(Issue("error", _rel(path, content), f"duplicate scenario id '{s.id}'"))
        content.scenarios[s.id] = s

    for path in _yaml_files(root / ANSWERS_DIR):
        a = _parse(AnswerSet, _read_yaml(path, content), path, content)
        if a is None:
            continue
        if path.stem != a.scenario:
            content.issues.append(
                Issue("error", _rel(path, content), f"file name must match scenario '{a.scenario}'")
            )
        if a.scenario in content.answer_sets:
            content.issues.append(
                Issue("error", _rel(path, content), f"second answer file for '{a.scenario}'")
            )
        content.answer_sets[a.scenario] = a

    split_path = root / SPLIT_FILE
    if split_path.is_file():
        content.split = _parse(Split, _read_yaml(split_path, content), split_path, content)

    return content

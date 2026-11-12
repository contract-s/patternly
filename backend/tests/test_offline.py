"""The offline grader used by `patternly serve --offline`."""

from __future__ import annotations

from patternly.content.loader import load_content
from patternly.service.offline import offline_grader
from patternly.tutor.history import AttemptRecord, InMemoryHistory

from .conftest import scenario


def test_word_overlap_grading_and_hand_written_hints(content_dir):
    content_dir.patterns([{"id": "p", "name": "P"}])
    s = scenario("s1", "p")
    s["rubric"] = [
        {"id": "count", "idea": "Counts the failures inside the window."},
        {"id": "shrink", "idea": "Shrinks from the left when there are too many."},
    ]
    content_dir.scenario(s)
    sc = load_content(content_dir.root).scenarios["s1"]
    history = InMemoryHistory()

    r = offline_grader(sc, "I count failures in a window", history, "u")
    assert [c.hit for c in r.items] == [True, False]
    assert (r.verdict, r.hint_level, r.hint) == ("fail", 1, sc.hints[0])

    history.add(AttemptRecord("u", "s1", 1, "fail", {}, sc.hints[0], 1))
    r = offline_grader(sc, "count failures in the window; shrink from the left when too many", history, "u")
    assert r.verdict == "pass" and r.hint == "" and r.attempt == 2

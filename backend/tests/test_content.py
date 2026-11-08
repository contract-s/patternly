from __future__ import annotations

from collections import Counter

import pytest
import yaml

from patternly.cli import main
from patternly.content.loader import find_content_dir, load_content
from patternly.content.split import choose_sealed, write_split
from patternly.content.validate import check, weekend1_progress

from .conftest import answer_set, scenario


def errors(content_dir) -> list[str]:
    return [str(i) for i in check(load_content(content_dir.root)) if i.level == "error"]


def warnings(content_dir) -> list[str]:
    return [str(i) for i in check(load_content(content_dir.root)) if i.level == "warning"]


def test_full_set_is_clean_and_counts_as_labeled(content_dir):
    content_dir.full()
    content = load_content(content_dir.root)
    issues = check(content)
    assert issues == []
    progress = weekend1_progress(content, issues)
    assert (progress.patterns_used, progress.scenarios, progress.labeled_answers) == (5, 10, 60)
    assert not progress.done  # not sealed yet


def test_unknown_yaml_key_is_rejected(content_dir):
    content_dir.patterns([{"id": "p", "name": "P"}])
    bad = scenario("s", "p") | {"promt": "typo"}
    content_dir.scenario(bad)
    assert any("promt" in e for e in errors(content_dir))


def test_file_name_must_match_id(content_dir):
    content_dir.patterns([{"id": "p", "name": "P"}])
    content_dir.scenario(scenario("real-id", "p"), filename="other-name")
    assert any("file name must match" in e for e in errors(content_dir))


def test_templates_are_ignored(content_dir):
    content_dir.raw("scenarios/_template.yaml", "id: not valid at all: [")
    assert errors(content_dir) == []


def test_invalid_yaml_reports_file(content_dir):
    content_dir.raw("scenarios/broken.yaml", "id: [unclosed")
    assert any("scenarios/broken.yaml" in e and "invalid YAML" in e for e in errors(content_dir))


def test_unknown_pattern(content_dir):
    content_dir.scenario(scenario("s", "nope"))
    assert any("unknown pattern 'nope'" in e for e in errors(content_dir))


def test_duplicate_rubric_ids(content_dir):
    content_dir.patterns([{"id": "p", "name": "P"}])
    s = scenario("s", "p")
    s["rubric"].append({"id": "idea-a", "idea": "Again."})
    content_dir.scenario(s)
    assert any("duplicate rubric ids: idea-a" in e for e in errors(content_dir))


def test_labels_must_cover_rubric_exactly(content_dir):
    content_dir.patterns([{"id": "p", "name": "P"}])
    content_dir.scenario(scenario("s", "p"))
    aset = answer_set("s")
    del aset["answers"][0]["labels"]["idea-b"]
    aset["answers"][1]["labels"]["idea-z"] = "hit"
    content_dir.answers(aset)
    errs = errors(content_dir)
    assert any("[correct]" in e and "not labeled: idea-b" in e for e in errs)
    assert any("[partial]" in e and "unknown rubric items: idea-z" in e for e in errs)

    content = load_content(content_dir.root)
    assert weekend1_progress(content, check(content)).labeled_answers == 4


def test_answers_for_missing_scenario(content_dir):
    content_dir.answers(answer_set("ghost"))
    assert any("no scenario with id 'ghost'" in e for e in errors(content_dir))


def test_prompt_naming_pattern_warns(content_dir):
    content_dir.patterns([{"id": "p", "name": "Hidden Trick", "aliases": ["the trick"]}])
    content_dir.scenario(scenario("s", "p", prompt="Use THE TRICK to solve this."))
    content_dir.answers(answer_set("s"))
    assert any("names the pattern ('the trick')" in w for w in warnings(content_dir))


def test_alias_matches_whole_words_only(content_dir):
    content_dir.patterns([{"id": "p", "name": "Heap"}])
    content_dir.scenario(scenario("s", "p", prompt="Count the heaped-up boxes cheaply."))
    content_dir.answers(answer_set("s"))
    assert warnings(content_dir) == []


def test_missing_kind_and_inconsistent_verdicts_warn(content_dir):
    content_dir.patterns([{"id": "p", "name": "P"}])
    content_dir.scenario(scenario("s", "p"))
    aset = answer_set("s")
    aset["answers"] = [a for a in aset["answers"] if a["kind"] != "vague"]
    wrong = next(a for a in aset["answers"] if a["kind"] == "wrong_pattern")
    wrong["verdict"] = "pass"
    content_dir.answers(aset)
    ws = warnings(content_dir)
    assert any("missing answer kinds: vague" in w for w in ws)
    assert any("'wrong_pattern' labeled as a pass" in w for w in ws)


def test_sealed_split_is_stratified_and_deterministic(content_dir):
    content_dir.full()
    answers = load_content(content_dir.root).all_answers()
    first = choose_sealed(answers, 20, seed=7)
    assert first == choose_sealed(answers, 20, seed=7)
    assert first != choose_sealed(answers, 20, seed=8)
    assert len(set(first)) == 20

    by_key = {la.key: la for la in answers}
    kinds = Counter(by_key[k].answer.kind for k in first)
    assert set(kinds.values()) <= {3, 4}  # 20 across 6 kinds
    scenarios = Counter(by_key[k].scenario.id for k in first)
    assert max(scenarios.values()) - min(scenarios.values()) <= 1
    assert len(scenarios) == 10


def test_dev_and_sealed_partition(content_dir):
    content_dir.full()
    content = load_content(content_dir.root)
    write_split(content, size=20, seed=1)
    content = load_content(content_dir.root)
    dev = {la.key for la in content.dev_answers()}
    sealed = {la.key for la in content.sealed_answers()}
    assert len(sealed) == 20 and len(dev) == 40 and not dev & sealed
    assert weekend1_progress(content, check(content)).done


def test_write_split_refuses_to_overwrite(content_dir):
    content_dir.full()
    content = load_content(content_dir.root)
    write_split(content, size=20, seed=1)
    with pytest.raises(FileExistsError):
        write_split(content, size=20, seed=2)
    write_split(content, size=20, seed=2, force=True)
    assert yaml.safe_load((content_dir.root / "splits.yaml").read_text())["seed"] == 2


def test_split_with_unknown_ids_is_an_error(content_dir):
    content_dir.full()
    content_dir.raw("splits.yaml", "seed: 1\ncreated: '2026-11-07'\nsealed: [s-0-0/correct, nope/x]\n")
    assert any("sealed ids not found: nope/x" in e for e in errors(content_dir))


def test_cli_seal_requires_complete_labels(content_dir, capsys):
    content_dir.patterns([{"id": "p", "name": "P"}])
    content_dir.scenario(scenario("s", "p"))
    content_dir.answers(answer_set("s"))
    root = str(content_dir.root)
    assert main(["--content", root, "seal"]) == 1
    assert "6/60" in capsys.readouterr().err
    assert main(["--content", root, "seal", "--size", "3", "--allow-incomplete"]) == 0


def test_cli_validate_exit_codes(content_dir):
    root = str(content_dir.root)
    assert main(["--content", root, "validate"]) == 0
    content_dir.patterns([{"id": "p", "name": "P"}])
    content_dir.scenario(scenario("s", "p"))  # no answers file -> warning only
    assert main(["--content", root, "validate"]) == 0
    assert main(["--content", root, "validate", "--strict"]) == 1
    content_dir.scenario(scenario("t", "missing"))
    assert main(["--content", root, "validate"]) == 1


def test_find_content_dir_walks_up(content_dir, monkeypatch):
    monkeypatch.delenv("PATTERNLY_CONTENT", raising=False)
    nested = content_dir.root.parent / "a" / "b"
    nested.mkdir(parents=True)
    assert find_content_dir(nested) == content_dir.root
    monkeypatch.setenv("PATTERNLY_CONTENT", "/elsewhere")
    assert str(find_content_dir(nested)) == "/elsewhere"

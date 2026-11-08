"""`patternly` command line: validate, stats, seal, eval."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from .content.loader import find_content_dir, load_content
from .content.models import AnswerKind, Verdict
from .content.split import write_split
from .content.validate import (
    ANSWERS_PER_SCENARIO,
    TARGET_PATTERNS,
    TARGET_SCENARIOS,
    TARGET_SEALED,
    check,
    weekend1_progress,
)


def _content_dir(args: argparse.Namespace) -> Path:
    return Path(args.content) if args.content else find_content_dir()


def cmd_validate(args: argparse.Namespace) -> int:
    content = load_content(_content_dir(args))
    issues = check(content)
    for issue in issues:
        print(issue)
    errors = sum(1 for i in issues if i.level == "error")
    warnings = len(issues) - errors
    print(f"\n{errors} error(s), {warnings} warning(s)")
    if errors or (args.strict and warnings):
        return 1
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    content = load_content(_content_dir(args))
    issues = check(content)
    progress = weekend1_progress(content, issues)

    print("Scenarios per pattern")
    per_pattern = Counter(s.pattern for s in content.scenarios.values())
    for pid, pattern in sorted(content.patterns.items()):
        print(f"  {pattern.name:30} {per_pattern.get(pid, 0)}")
    if not content.patterns:
        print("  (no patterns yet)")

    answers = [la.answer for la in content.all_answers()]
    if answers:
        kinds = Counter(a.kind for a in answers)
        verdicts = Counter(a.verdict for a in answers)
        print("\nAnswers by kind")
        for k in AnswerKind:
            print(f"  {k.value:30} {kinds.get(k, 0)}")
        print(f"\nVerdicts: {verdicts.get(Verdict.PASS, 0)} pass, {verdicts.get(Verdict.FAIL, 0)} fail")

    def row(label: str, have: int, want: int) -> str:
        mark = "x" if have >= want else " "
        return f"  [{mark}] {label:30} {have}/{want}"

    print("\nWeekend 1 checklist")
    print(row("patterns with scenarios", progress.patterns_used, TARGET_PATTERNS))
    print(row("scenarios", progress.scenarios, TARGET_SCENARIOS))
    print(row("labeled answers", progress.labeled_answers, TARGET_SCENARIOS * ANSWERS_PER_SCENARIO))
    print(row("sealed test answers", progress.sealed, TARGET_SEALED))
    print(f"  [{'x' if progress.errors == 0 else ' '}] {'no validation errors':30} {progress.errors} error(s)")
    print(f"\nWeekend 1 {'DONE' if progress.done else 'not done yet'}")
    return 0


def cmd_seal(args: argparse.Namespace) -> int:
    content = load_content(_content_dir(args))
    issues = check(content)
    progress = weekend1_progress(content, issues)
    if progress.errors:
        print("Fix validation errors before sealing (run `patternly validate`).", file=sys.stderr)
        return 1
    want = TARGET_SCENARIOS * ANSWERS_PER_SCENARIO
    if progress.labeled_answers < want and not args.allow_incomplete:
        print(
            f"Only {progress.labeled_answers}/{want} answers are labeled. Seal once all are labeled, "
            "or pass --allow-incomplete.",
            file=sys.stderr,
        )
        return 1
    try:
        split = write_split(content, size=args.size, seed=args.seed, force=args.force)
    except (FileExistsError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"Sealed {len(split.sealed)} answers (seed {split.seed}) into {content.root / 'splits.yaml'}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    # Imported here so the content commands work without the API packages or a key.
    import anthropic
    from dotenv import load_dotenv

    from .evals.runner import EvalConfig, run_eval

    if args.split == "sealed" and not args.final:
        print(
            "The sealed set is only for final reported numbers. Re-run with --final once you've "
            "stopped changing the tutor.",
            file=sys.stderr,
        )
        return 1
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    content = load_content(_content_dir(args))
    errors = [i for i in check(content) if i.level == "error"]
    if errors:
        print("Fix validation errors first (run `patternly validate`).", file=sys.stderr)
        return 1
    config = EvalConfig(
        label=args.label,
        split=args.split,
        runs=args.runs,
        model=args.model,
        effort=args.effort,
        concurrency=args.concurrency,
        limit=args.limit,
    )
    out_root = Path(args.out) if args.out else content.root.parent / "evals" / "runs"

    def progress(done: int, total: int) -> None:
        print(f"\r{done}/{total} calls", end="", file=sys.stderr, flush=True)

    out_dir, summary = run_eval(anthropic.Anthropic(), content, config, out_root, progress)
    print(file=sys.stderr)
    print((out_dir / "summary.md").read_text())
    print(f"Saved to {out_dir}")
    return 0 if summary["errors"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="patternly", description="Patternly content tools")
    parser.add_argument("--content", help="path to the content directory (default: nearest content/)")
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="check scenarios, answers, and labels")
    v.add_argument("--strict", action="store_true", help="treat warnings as failures")
    v.set_defaults(func=cmd_validate)

    s = sub.add_parser("stats", help="show counts and the Weekend 1 checklist")
    s.set_defaults(func=cmd_stats)

    seal = sub.add_parser("seal", help="choose the sealed test set and write splits.yaml")
    seal.add_argument("--size", type=int, default=TARGET_SEALED)
    seal.add_argument("--seed", type=int, default=2026)
    seal.add_argument("--force", action="store_true", help="overwrite an existing splits.yaml")
    seal.add_argument("--allow-incomplete", action="store_true", help="seal before all answers are labeled")
    seal.set_defaults(func=cmd_seal)

    from .tutor.baseline import DEFAULT_EFFORT, DEFAULT_MODEL

    ev = sub.add_parser("eval", help="grade labeled answers with the tutor and report accuracy")
    ev.add_argument("--split", choices=["dev", "sealed"], default="dev")
    ev.add_argument("--final", action="store_true", help="required to run on the sealed split")
    ev.add_argument("--runs", type=int, default=5, help="passes over every answer (default 5)")
    ev.add_argument("--model", default=DEFAULT_MODEL)
    ev.add_argument("--effort", default=DEFAULT_EFFORT, choices=["low", "medium", "high", "xhigh", "max"])
    ev.add_argument("--concurrency", type=int, default=8)
    ev.add_argument("--limit", type=int, help="only the first N answers (for a quick check)")
    ev.add_argument("--label", default="baseline", help="name for the results folder")
    ev.add_argument("--out", help="results folder (default: evals/runs/ next to content/)")
    ev.set_defaults(func=cmd_eval)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2

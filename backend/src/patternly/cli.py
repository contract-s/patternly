"""`patternly` command line: validate, stats, seal, eval, index, search, retrieval-eval, serve, remind."""

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
        grounding=args.notes,
        batch=args.batch,
    )
    retrieved = None
    if args.notes != "none":
        from .evals.runner import select_answers
        from .retrieval.models import LocalEmbedder
        from .retrieval.search import Retriever, top_patterns
        from .retrieval.store import connect

        method, top = args.notes.rsplit("-top", 1)
        with connect() as conn:
            retriever = Retriever(conn, LocalEmbedder())
            retrieved = {
                la.key: top_patterns(retriever.search(la.answer.text, method, limit=30), int(top))
                for la in select_answers(content, config.split, config.limit)
            }
    out_root = Path(args.out) if args.out else content.root.parent / "evals" / "runs"

    def progress(done: int, total: int) -> None:
        print(f"\r{done}/{total} calls", end="", file=sys.stderr, flush=True)

    out_dir, summary = run_eval(anthropic.Anthropic(), content, config, out_root, progress, retrieved)
    print(file=sys.stderr)
    print((out_dir / "summary.md").read_text())
    print(f"Saved to {out_dir}")
    return 0 if summary["errors"] == 0 else 1


def _checked_content(args: argparse.Namespace):
    content = load_content(_content_dir(args))
    if any(i.level == "error" for i in check(content)):
        print("Fix validation errors first (run `patternly validate`).", file=sys.stderr)
        return None
    return content


def cmd_index(args: argparse.Namespace) -> int:
    from .retrieval.models import LocalEmbedder
    from .retrieval.store import connect, index_notes

    content = _checked_content(args)
    if content is None:
        return 1
    with connect() as conn:
        n = index_notes(conn, content, LocalEmbedder())
    print(f"Indexed {n} note sections from {len(content.notes)} notes")
    return 0


def _retriever(conn):
    from .retrieval.models import LocalEmbedder, LocalReranker
    from .retrieval.search import Retriever

    return Retriever(conn, LocalEmbedder(), LocalReranker())


def cmd_search(args: argparse.Namespace) -> int:
    from .retrieval.store import connect

    with connect() as conn:
        for i, c in enumerate(_retriever(conn).search(args.query, args.method, args.limit), start=1):
            print(f"{i:2}. {c.pattern} / {c.section}")
    return 0


def cmd_retrieval_eval(args: argparse.Namespace) -> int:
    from .evals import retrieval
    from .retrieval.models import EMBED_MODEL, RERANK_MODEL
    from .retrieval.store import connect

    content = _checked_content(args)
    if content is None:
        return 1
    config = {
        "label": args.label,
        "split": "dev",
        "embed_model": EMBED_MODEL,
        "rerank_model": RERANK_MODEL,
        "started_at": retrieval.now(),
    }
    with connect() as conn:
        result = retrieval.run_retrieval_eval(_retriever(conn), content)
    out_root = Path(args.out) if args.out else content.root.parent / "evals" / "runs"
    out_dir = retrieval.save(result, config, out_root)
    print((out_dir / "summary.md").read_text())
    print(f"Saved to {out_dir}")
    return 0


def _load_env() -> None:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _note_search(conn):
    """search_notes backed by hybrid retrieval: the top note sections for a query."""
    from .retrieval.models import LocalEmbedder
    from .retrieval.search import Retriever

    retriever = Retriever(conn, LocalEmbedder())

    def search(query: str) -> list[str]:
        from .tutor.agent import NOTES_PER_SEARCH

        return [c.text for c in retriever.search(query, "hybrid", limit=NOTES_PER_SEARCH)]

    return search


def _checker(content, judge_model: str | None):
    from .tutor.leaks import LeakChecker, ModelJudge

    judge = None
    if judge_model:
        import anthropic

        judge = ModelJudge(anthropic.Anthropic(), judge_model)
    return LeakChecker(content.patterns, judge)


def cmd_leak_check(args: argparse.Namespace) -> int:
    from .evals import leaks

    content = _checked_content(args)
    if content is None:
        return 1
    if args.judge:
        _load_env()
    planted_path = Path(args.planted) if args.planted else content.root.parent / "evals" / "planted-leaks.yaml"
    planted = leaks.load_planted(planted_path)
    records = leaks.run_leak_eval(content, planted, _checker(content, args.judge))
    summary = leaks.summarize(records, judged=bool(args.judge))
    out_root = Path(args.out) if args.out else content.root.parent / "evals" / "runs"
    out_dir = leaks.save(records, summary, out_root, args.label, args.judge)
    print((out_dir / "summary.md").read_text())
    missed = [r for r in records if r["source"] == "planted" and not r["caught"]]
    wrong = [r for r in records if r["source"] != "planted" and r["caught"]]
    for r in missed:
        print(f"MISSED  {r['scenario']} L{r['level']} {r['expected']}: {r['hint']}")
    for r in wrong:
        print(f"FLAGGED {r['scenario']} L{r['level']} ({r['source']}): {r['detail']}")
    print(f"Saved to {out_dir}")
    return 0


def cmd_tutor_eval(args: argparse.Namespace) -> int:
    import contextlib

    import anthropic

    from .evals.agent import AgentEvalConfig, run_agent_eval

    if args.split == "sealed" and not args.final:
        print("The sealed set is only for final reported numbers. Re-run with --final.", file=sys.stderr)
        return 1
    content = _checked_content(args)
    if content is None:
        return 1
    _load_env()
    judge = None if args.judge == "none" else args.judge
    config = AgentEvalConfig(
        label=args.label,
        split=args.split,
        model=args.model,
        effort=args.effort,
        judge_model=judge,
        notes=args.notes,
        attempts=args.attempts,
        concurrency=args.concurrency,
        limit=args.limit,
    )
    out_root = Path(args.out) if args.out else content.root.parent / "evals" / "runs"

    def progress(done: int, total: int) -> None:
        print(f"\r{done}/{total} answers", end="", file=sys.stderr, flush=True)

    with contextlib.ExitStack() as stack:
        search = None
        if args.notes:
            from .retrieval.store import connect

            search = _note_search(stack.enter_context(connect()))
        out_dir, summary = run_agent_eval(
            anthropic.Anthropic(), content, config, _checker(content, judge), out_root, search, progress
        )
    print(file=sys.stderr)
    print((out_dir / "summary.md").read_text())
    print(f"Saved to {out_dir}")
    return 0 if summary["errors"] == 0 else 1


def cmd_try(args: argparse.Namespace) -> int:
    """Try a lesson in the terminal: explain, get graded, get stronger hints, until you pass."""
    import anthropic

    from .tutor.agent import run_attempt
    from .tutor.history import InMemoryHistory

    content = _checked_content(args)
    if content is None:
        return 1
    scenario = content.scenarios.get(args.scenario)
    if scenario is None:
        print(f"No scenario '{args.scenario}'. Scenarios: {', '.join(sorted(content.scenarios))}", file=sys.stderr)
        return 1
    _load_env()
    client, history = anthropic.Anthropic(), InMemoryHistory()
    checker = _checker(content, None if args.judge == "none" else args.judge)
    print(f"{scenario.title}\n\n{scenario.prompt.strip()}\n")
    while True:
        print("Explain your solution (end with an empty line; Ctrl-D to quit):")
        lines = []
        try:
            while (line := input()) != "":
                lines.append(line)
        except EOFError:
            return 0
        if not lines:
            continue
        r = run_attempt(
            client,
            scenario,
            "\n".join(lines),
            learner_id="you",
            history=history,
            checker=checker,
            model=args.model,
            effort=args.effort,
        )
        if r.error:
            print(f"Error: {r.error}", file=sys.stderr)
            continue
        hit = sum(c.hit for c in r.items)
        print(f"\n{hit} of {len(r.items)} key ideas. (${r.cost_usd:.3f}, {r.latency_s:.1f} s)")
        if r.verdict == "pass":
            pattern = content.patterns[scenario.pattern]
            print(f"\nYou've got it. The pattern is {pattern.name}.")
            if pattern.summary:
                print(pattern.summary)
            return 0
        print(f"Hint (level {r.hint_level}): {r.hint}\n")


def cmd_serve(args: argparse.Namespace) -> int:
    import os

    import anthropic
    import uvicorn

    from .service.app import create_app, tutor_grader
    from .service.auth import jwt_secret

    content = _checked_content(args)
    if content is None:
        return 1
    _load_env()
    try:
        secret = jwt_secret()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    from . import tracing

    if tracing.setup("patternly-api"):
        print(f"Tracing on: {os.environ.get(tracing.TRACE_FILE_ENV) or 'OTLP only'}", file=sys.stderr)
    if args.offline:
        from .service.offline import offline_grader

        grader = offline_grader
        print("Offline grader: word matching, no API calls. Not the real tutor.", file=sys.stderr)
    else:
        judge = None if args.judge == "none" else args.judge
        grader = tutor_grader(anthropic.Anthropic(), _checker(content, judge), model=args.model, effort=args.effort)
    uvicorn.run(create_app(content, grader, secret=secret), host=args.host, port=args.port)
    return 0


def cmd_trace_report(args: argparse.Namespace) -> int:
    import os
    from datetime import UTC, datetime

    from .evals.traces import format_report, load, report
    from .tracing import TRACE_FILE_ENV

    path = args.file or os.environ.get(TRACE_FILE_ENV)
    if not path:
        print(f"Pass --file or set {TRACE_FILE_ENV}.", file=sys.stderr)
        return 1
    since = datetime.fromisoformat(args.since).replace(tzinfo=UTC) if args.since else None
    print(format_report(report(load(path, since))))
    return 0


def cmd_remind(args: argparse.Namespace) -> int:
    import asyncio
    import os
    from datetime import UTC, datetime

    import psycopg

    from .retrieval.store import database_url
    from .service.auth import jwt_secret
    from .service.db import apply_schema
    from .service.reminders import send_due, ses_sender

    _load_env()
    try:
        secret = jwt_secret()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    app_url = os.environ.get("APP_URL", "")
    from_address = os.environ.get("REMINDER_FROM", "")
    if args.print:

        def sender(to: str, subject: str, body: str, html: str) -> None:
            print(f"--- learner email, subject: {subject}\n{body}")

    elif not args.dry_run:
        if not app_url or not from_address:
            print("Set APP_URL and REMINDER_FROM (or use --dry-run or --print).", file=sys.stderr)
            return 1
        sender = ses_sender(from_address)
    else:
        sender = None

    async def run():
        async with await psycopg.AsyncConnection.connect(database_url(), autocommit=True) as conn:
            await apply_schema(conn)
            return await send_due(
                conn,
                datetime.now(UTC),
                sender,
                app_url=app_url or "http://localhost:8080",
                secret=secret,
                dry_run=args.dry_run,
            )

    results = asyncio.run(run())
    # Learner ids only: addresses and message bodies stay out of logs.
    for r in results:
        print(f"learner {r.learner.id} {r.local_date}: {r.status}" + (f" ({r.error})" if r.error else ""))
    failed = sum(r.status == "failed" for r in results)
    print(f"{len(results)} due, {len(results) - failed} ok, {failed} failed")
    return 1 if failed else 0


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
    ev.add_argument("--batch", action="store_true", help="use the Message Batches API (half price, slower)")
    ev.add_argument(
        "--notes",
        default="none",
        choices=["none", "hybrid-top3", "vector-top3", "keyword-top3"],
        help="put retrieved pattern notes in the prompt (searched with the learner's answer); needs the database",
    )
    ev.add_argument("--out", help="results folder (default: evals/runs/ next to content/)")
    ev.set_defaults(func=cmd_eval)

    ix = sub.add_parser("index", help="embed the pattern notes into Postgres (run after editing notes)")
    ix.set_defaults(func=cmd_index)

    from .retrieval.search import METHODS

    se = sub.add_parser("search", help="show the note sections retrieved for a query")
    se.add_argument("query")
    se.add_argument("--method", choices=METHODS, default="hybrid-rerank")
    se.add_argument("--limit", type=int, default=5)
    se.set_defaults(func=cmd_search)

    re_ = sub.add_parser("retrieval-eval", help="measure note retrieval hit rate on development answers")
    re_.add_argument("--label", default="retrieval")
    re_.add_argument("--out", help="results folder (default: evals/runs/ next to content/)")
    re_.set_defaults(func=cmd_retrieval_eval)

    from .tutor.leaks import DEFAULT_JUDGE_MODEL

    lc = sub.add_parser("leak-check", help="check that the leak checker catches planted leaky hints")
    lc.add_argument(
        "--judge", metavar="MODEL", help=f"also check revealed steps with this model (e.g. {DEFAULT_JUDGE_MODEL})"
    )
    lc.add_argument("--planted", help="planted leaks file (default: evals/planted-leaks.yaml)")
    lc.add_argument("--label", default="leaks")
    lc.add_argument("--out", help="results folder (default: evals/runs/ next to content/)")
    lc.set_defaults(func=cmd_leak_check)

    te = sub.add_parser("tutor-eval", help="run the tool-using tutor over labeled answers, resubmitting failures")
    te.add_argument("--split", choices=["dev", "sealed"], default="dev")
    te.add_argument("--final", action="store_true", help="required to run on the sealed split")
    te.add_argument("--model", default=DEFAULT_MODEL)
    te.add_argument("--effort", default=DEFAULT_EFFORT, choices=["low", "medium", "high", "xhigh", "max"])
    te.add_argument("--judge", default=DEFAULT_JUDGE_MODEL, help="leak judge model, or 'none'")
    te.add_argument("--notes", action="store_true", help="back search_notes with retrieval (needs the database)")
    te.add_argument("--attempts", type=int, default=3, help="submissions per answer while it fails (default 3)")
    te.add_argument("--concurrency", type=int, default=8)
    te.add_argument("--limit", type=int, help="only the first N answers (for a quick check)")
    te.add_argument("--label", default="tutor-loop")
    te.add_argument("--out", help="results folder (default: evals/runs/ next to content/)")
    te.set_defaults(func=cmd_tutor_eval)

    tr = sub.add_parser("try", help="try a lesson in the terminal with the tutor")
    tr.add_argument("scenario", help="scenario id")
    tr.add_argument("--model", default=DEFAULT_MODEL)
    tr.add_argument("--effort", default=DEFAULT_EFFORT, choices=["low", "medium", "high", "xhigh", "max"])
    tr.add_argument("--judge", default=DEFAULT_JUDGE_MODEL, help="leak judge model, or 'none'")
    tr.set_defaults(func=cmd_try)

    sv = sub.add_parser("serve", help="run the API (needs the database, JWT_SECRET, and an API key)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--model", default=DEFAULT_MODEL)
    sv.add_argument("--effort", default=DEFAULT_EFFORT, choices=["low", "medium", "high", "xhigh", "max"])
    sv.add_argument("--judge", default=DEFAULT_JUDGE_MODEL, help="leak judge model, or 'none'")
    sv.add_argument("--offline", action="store_true", help="grade by word matching instead of the tutor (free)")
    sv.set_defaults(func=cmd_serve)

    trp = sub.add_parser("trace-report", help="p50/p95 latency and cost per graded attempt, from the trace file")
    trp.add_argument("--file", help="JSON Lines trace file (default: $PATTERNLY_TRACE_FILE)")
    trp.add_argument("--since", help="only spans from this UTC date or time on, e.g. 2026-11-14")
    trp.set_defaults(func=cmd_trace_report)

    rm = sub.add_parser("remind", help="email learners whose lesson isn't done (run hourly)")
    rm.add_argument("--dry-run", action="store_true", help="list who is due without sending or recording anything")
    rm.add_argument("--print", action="store_true", help="print the emails instead of sending them through SES")
    rm.set_defaults(func=cmd_remind)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2

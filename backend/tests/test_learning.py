"""Spaced repetition, the daily planner, and streaks."""

from __future__ import annotations

from datetime import date, timedelta

from patternly.learning.planner import pick_scenario, plan
from patternly.learning.scheduler import INTERVAL_DAYS, Outcome, Progress, schedule
from patternly.learning.streaks import compute_streak

D = date(2026, 11, 11)


def days(*offsets: int) -> set[date]:
    return {D + timedelta(days=o) for o in offsets}


# ---- scheduler ----


def test_new_pattern_boxes():
    assert schedule(None, "p", Outcome.CLEAN, D).box == 2
    assert schedule(None, "p", Outcome.HINTED, D).box == 1
    missed = schedule(None, "p", Outcome.MISSED, D)
    assert missed.box == 1 and missed.due == D + timedelta(days=1)


def test_boxes_move_up_stay_and_reset():
    p = Progress("p", 3, D, 4, Outcome.CLEAN)
    up = schedule(p, "p", Outcome.CLEAN, D)
    assert up.box == 4 and up.due == D + timedelta(days=INTERVAL_DAYS[4]) and up.reviews == 5
    assert schedule(p, "p", Outcome.HINTED, D).box == 3
    assert schedule(p, "p", Outcome.MISSED, D).box == 1
    assert schedule(Progress("p", 5, D, 9, Outcome.CLEAN), "p", Outcome.CLEAN, D).box == 5


# ---- planner ----

CURRICULUM = ["a", "b", "c"]
SCENARIOS = {"a": ["a1", "a2"], "b": ["b1", "b2"], "c": []}


def test_new_patterns_in_curriculum_order():
    assert plan(D, CURRICULUM, SCENARIOS, {}, {}).scenario == "a1"
    progress = {"a": Progress("a", 2, D + timedelta(days=2), 1, Outcome.CLEAN)}
    pick = plan(D, CURRICULUM, SCENARIOS, progress, {"a1": D - timedelta(days=1)})
    assert (pick.pattern, pick.kind) == ("b", "new")


def test_due_review_comes_first_with_a_fresh_scenario():
    progress = {"a": Progress("a", 1, D, 1, Outcome.MISSED)}
    pick = plan(D, CURRICULUM, SCENARIOS, progress, {"a1": D - timedelta(days=1)})
    assert (pick.scenario, pick.kind) == ("a2", "review")


def test_most_overdue_review_wins():
    progress = {
        "a": Progress("a", 2, D - timedelta(days=1), 1, Outcome.CLEAN),
        "b": Progress("b", 1, D - timedelta(days=3), 1, Outcome.MISSED),
    }
    assert plan(D, CURRICULUM, SCENARIOS, progress, {}).pattern == "b"


def test_practice_when_nothing_due_or_new():
    progress = {
        "a": Progress("a", 3, D + timedelta(days=4), 2, Outcome.CLEAN),
        "b": Progress("b", 2, D + timedelta(days=2), 1, Outcome.CLEAN),
    }
    pick = plan(D, CURRICULUM, SCENARIOS, progress, {})
    assert (pick.pattern, pick.kind) == ("b", "practice")


def test_pick_scenario_least_recent_when_all_seen():
    seen = {"a1": D, "a2": D - timedelta(days=5)}
    assert pick_scenario(["a1", "a2"], seen) == "a2"


# ---- streaks ----


def test_empty_and_today_only():
    assert compute_streak(set(), D).current == 0
    s = compute_streak(days(0), D)
    assert (s.current, s.longest, s.done_today) == (1, 1, True)


def test_today_not_done_yet_keeps_streak():
    s = compute_streak(days(-3, -2, -1), D)
    assert (s.current, s.done_today) == (3, False)


def test_missed_day_without_freeze_resets():
    s = compute_streak(days(-4, -3, -1, 0), D)
    assert (s.current, s.longest) == (2, 2)
    assert compute_streak(days(-3, -2), D).current == 0  # yesterday missed


def test_freeze_earned_after_seven_covers_one_day():
    done = days(*range(-9, -2), -1, 0)  # 7 days, miss day -2, then 2 more
    s = compute_streak(done, D)
    assert (s.current, s.freezes) == (9, 0)


def test_freezes_cap_at_two_and_long_gap_resets():
    done = days(*range(-30, -9))  # days -30..-10: 21 in a row, 3 freezes earned, capped at 2
    assert compute_streak(done, D - timedelta(days=10)).freezes == 2
    # Two missed days (-9, -8) are covered...
    covered = compute_streak(done | days(-7), D - timedelta(days=7))
    assert (covered.current, covered.freezes) == (22, 0)
    # ...but three (-9, -8, -7) reset the streak.
    reset = compute_streak(done | days(-6), D - timedelta(days=6))
    assert (reset.current, reset.longest) == (1, 21)

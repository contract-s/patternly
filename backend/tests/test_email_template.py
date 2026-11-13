"""The reminder email's text and HTML, without a database."""

from __future__ import annotations

from patternly.service import email_template

APP = "https://app.test"
UNSUB = "https://app.test/api/reminders/unsubscribe?token=a.b.c"


def test_no_streak_line_without_a_streak():
    assert "streak" not in email_template.text(APP, UNSUB, 0)
    assert "streak" not in email_template.html(APP, UNSUB, 0)


def test_streak_line_counts_days():
    assert "1-day streak" in email_template.text(APP, UNSUB, 1)
    assert "5-day streak" in email_template.text(APP, UNSUB, 5)
    assert "5-day streak" in email_template.html(APP, UNSUB, 5)


def test_urls_are_escaped_in_html():
    html = email_template.html('https://app.test/"><script>', UNSUB, 0)
    assert "<script>" not in html
    assert "&quot;&gt;&lt;script&gt;" in html


def test_text_has_both_links():
    text = email_template.text(APP, UNSUB, 0)
    assert APP in text and UNSUB in text

"""The reminder email, as HTML plus a plain-text fallback.

Email clients ignore most CSS, so the HTML uses tables and inline styles. Colors match the web app's light
theme. The logo is a PNG served by the web app (frontend/public/email-logo.png), since Gmail doesn't show SVG.
"""

from __future__ import annotations

from html import escape

ACCENT = "#2f5bea"
TEXT = "#1d1d1b"
MUTED = "#6b6a64"
BORDER = "#e3e1da"
BG = "#f6f5f1"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

PREHEADER = "About 10 minutes: read a short scenario and explain how you'd solve it."


def streak_line(streak: int) -> str | None:
    if streak <= 0:
        return None
    return f"You're on a {streak}-day streak. Finish today's lesson to keep it going."


def text(app_url: str, unsubscribe_url: str, streak: int) -> str:
    lines = ["Hi,", "", f"Today's Patternly lesson isn't done yet. It takes about 10 minutes: {app_url}", ""]
    if line := streak_line(streak):
        lines += [line, ""]
    lines += [f"Don't want these emails? Turn them off: {unsubscribe_url}"]
    return "\n".join(lines) + "\n"


def html(app_url: str, unsubscribe_url: str, streak: int) -> str:
    app, unsub, logo = escape(app_url), escape(unsubscribe_url), escape(f"{app_url}/email-logo.png")
    streak_html = ""
    if line := streak_line(streak):
        streak_html = (
            f'<tr><td style="padding:0 32px 24px">'
            f'<div style="background:#fdf3e2;border-radius:10px;padding:12px 16px;color:#9a5b00;'
            f'font-size:15px;line-height:1.5"><span aria-hidden="true">&#128293;</span>&nbsp; {escape(line)}</div>'
            f"</td></tr>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>Your Patternly lesson for today</title>
</head>
<body style="margin:0;padding:0;background:{BG}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{escape(PREHEADER)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}">
<tr><td align="center" style="padding:32px 16px;font-family:{FONT};color:{TEXT}">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px">
    <tr><td style="padding:0 4px 20px">
      <table role="presentation" cellpadding="0" cellspacing="0"><tr>
        <td style="vertical-align:middle"><img src="{logo}" width="36" height="36" alt=""
          style="display:block;border:0;border-radius:9px"></td>
        <td style="vertical-align:middle;padding-left:10px;font-size:20px;font-weight:700;
          letter-spacing:-0.02em;color:{TEXT}">Patternly</td>
      </tr></table>
    </td></tr>
    <tr><td style="background:#ffffff;border:1px solid {BORDER};border-top:4px solid {ACCENT};border-radius:16px">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="padding:32px 32px 8px">
          <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:{ACCENT};text-transform:uppercase;
            letter-spacing:0.06em">Daily reminder</p>
          <h1 style="margin:0 0 12px;font-size:26px;line-height:1.25;letter-spacing:-0.02em;color:{TEXT}">
            Today's lesson is waiting</h1>
          <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:{TEXT}">It takes about 10 minutes:
            read a short scenario, explain how you'd solve it in plain words, and get feedback that won't
            give the answer away.</p>
        </td></tr>
        {streak_html}
        <tr><td style="padding:0 32px 32px">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            <td style="background:{ACCENT};border-radius:10px">
              <a href="{app}" style="display:inline-block;padding:13px 24px;font-size:16px;font-weight:600;
                color:#ffffff;text-decoration:none;border-radius:10px">Start today's lesson</a>
            </td>
          </tr></table>
          <p style="margin:16px 0 0;font-size:13px;color:{MUTED}">Or open
            <a href="{app}" style="color:{ACCENT}">{app}</a></p>
        </td></tr>
      </table>
    </td></tr>
    <tr><td style="padding:20px 8px 0;font-size:12px;line-height:1.6;color:{MUTED};text-align:center">
      You're getting this because reminders are on for your Patternly account.<br>
      Change the time in the app, or <a href="{unsub}" style="color:{MUTED}">turn reminders off</a>.
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>
"""

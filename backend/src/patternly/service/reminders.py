"""Daily reminder emails: one per learner per local day, only if today's lesson isn't finished.

Each learner picks the local hour their reminder goes out (7 pm unless they change it).

`patternly remind` runs this hourly (a systemd timer on the server). Each reminder is claimed in the
`reminders` table before it's sent, so overlapping or repeated runs never email anyone twice in a day.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import jwt
from psycopg import AsyncConnection

from .auth import ALGORITHM
from .lessons import Learner, get_streak

DEFAULT_HOUR = 19  # matches the reminder_hour column default
SUBJECT = "Your Patternly lesson for today"
SENDER_NAME = "Patternly"  # shown in the inbox instead of the bare address

# Sends one plain-text email: (to, subject, body). Raises on failure.
Sender = Callable[[str, str, str], None]


@dataclass
class Reminder:
    learner: Learner
    local_date: date
    status: str  # "sent", "failed", or "dry-run"
    error: str | None = None


def unsubscribe_token(learner_id: int, secret: str) -> str:
    # No expiry: the link in an old email should still work.
    return jwt.encode({"sub": str(learner_id), "purpose": "unsubscribe"}, secret, algorithm=ALGORITHM)


def read_unsubscribe_token(token: str, secret: str) -> int | None:
    try:
        claims = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return int(claims["sub"]) if claims.get("purpose") == "unsubscribe" else None
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


async def due(conn: AsyncConnection, now: datetime) -> list[tuple[Learner, date]]:
    """Learners past their reminder hour locally, with reminders on, today's lesson unfinished, and no
    reminder yet today. Anyone whose hour passed while the job wasn't running still gets one that day."""
    cur = await conn.execute(
        "SELECT id, email, timezone, reminder_hour FROM learners WHERE reminders_enabled ORDER BY id"
    )
    out = []
    for *row, hour in await cur.fetchall():
        learner = Learner(*row)
        local = now.astimezone(ZoneInfo(learner.timezone))
        if local.hour < hour:
            continue
        cur = await conn.execute(
            """
            SELECT EXISTS (SELECT 1 FROM lessons WHERE learner_id = %(id)s AND local_date = %(day)s
                           AND status <> 'open')
                OR EXISTS (SELECT 1 FROM reminders WHERE learner_id = %(id)s AND local_date = %(day)s)
            """,
            {"id": learner.id, "day": local.date()},
        )
        if not (await cur.fetchone())[0]:
            out.append((learner, local.date()))
    return out


def body(app_url: str, unsubscribe_url: str, streak: int) -> str:
    lines = ["Hi,", "", f"Today's Patternly lesson isn't done yet. It takes about 10 minutes: {app_url}", ""]
    if streak > 0:
        days = "day" if streak == 1 else "days"
        lines += [f"You're on a {streak}-{days} streak. Finish today's lesson to keep it going.", ""]
    lines += [f"Don't want these emails? Turn them off: {unsubscribe_url}"]
    return "\n".join(lines) + "\n"


async def send_due(
    conn: AsyncConnection,
    now: datetime,
    sender: Sender,
    *,
    app_url: str,
    secret: str,
    dry_run: bool = False,
) -> list[Reminder]:
    app_url = app_url.rstrip("/")
    results = []
    for learner, day in await due(conn, now):
        if dry_run:
            results.append(Reminder(learner, day, "dry-run"))
            continue
        cur = await conn.execute(
            "INSERT INTO reminders (learner_id, local_date) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING 1",
            (learner.id, day),
        )
        if await cur.fetchone() is None:
            continue  # another run claimed it
        streak = (await get_streak(conn, learner, now)).current
        unsubscribe_url = f"{app_url}/api/reminders/unsubscribe?token={unsubscribe_token(learner.id, secret)}"
        try:
            sender(learner.email, SUBJECT, body(app_url, unsubscribe_url, streak))
        except Exception as e:  # noqa: BLE001 - one bad address shouldn't stop the others
            error = f"{type(e).__name__}: {e}"[:500]
            await conn.execute(
                "UPDATE reminders SET status = 'failed', error = %s WHERE learner_id = %s AND local_date = %s",
                (error, learner.id, day),
            )
            results.append(Reminder(learner, day, "failed", error))
            continue
        await conn.execute(
            "UPDATE reminders SET status = 'sent' WHERE learner_id = %s AND local_date = %s", (learner.id, day)
        )
        results.append(Reminder(learner, day, "sent"))
    return results


async def get_settings(conn: AsyncConnection, learner_id: int) -> tuple[bool, int]:
    cur = await conn.execute("SELECT reminders_enabled, reminder_hour FROM learners WHERE id = %s", (learner_id,))
    return tuple(await cur.fetchone())


async def set_settings(conn: AsyncConnection, learner_id: int, enabled: bool, hour: int) -> None:
    await conn.execute(
        "UPDATE learners SET reminders_enabled = %s, reminder_hour = %s WHERE id = %s", (enabled, hour, learner_id)
    )


async def unsubscribe(conn: AsyncConnection, learner_id: int) -> bool:
    cur = await conn.execute("UPDATE learners SET reminders_enabled = false WHERE id = %s RETURNING 1", (learner_id,))
    return await cur.fetchone() is not None


def ses_sender(from_address: str, region: str | None = None, name: str = SENDER_NAME) -> Sender:
    """Sends through Amazon SES (v2 API) with the instance role's credentials, as "Patternly <address>"."""
    import os
    from email.utils import formataddr

    import boto3

    # botocore reads AWS_DEFAULT_REGION but not AWS_REGION, which is what the deploy sets.
    region = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    client = boto3.client("sesv2", region_name=region)
    sender = formataddr((name, from_address))

    def send(to: str, subject: str, text: str) -> None:
        client.send_email(
            FromEmailAddress=sender,
            Destination={"ToAddresses": [to]},
            Content={"Simple": {"Subject": {"Data": subject}, "Body": {"Text": {"Data": text}}}},
        )

    return send

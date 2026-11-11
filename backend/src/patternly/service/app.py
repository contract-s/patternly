"""The HTTP API.

POST /auth/register, POST /auth/login     -> bearer token
GET  /me                                  -> learner and streak
GET  /lessons/today                       -> today's lesson (picked on first request of the day)
POST /lessons/today/attempts              -> grade an explanation; returns the critique, hint, or reveal
GET  /reviews                             -> patterns due for review, and upcoming ones
"""

from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

from ..content.loader import Content
from ..learning.streaks import Streak
from . import lessons as L
from .auth import hash_password, make_token, read_token, verify_password
from .db import apply_schema, make_pool

# ---- request and response models ----


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=8, max_length=200)
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def known_zone(cls, tz: str) -> str:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"unknown time zone '{tz}' (use an IANA name like 'America/Detroit')") from None
        return tz


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StreakOut(BaseModel):
    current: int
    longest: int
    freezes: int
    done_today: bool


class MeOut(BaseModel):
    id: int
    email: str
    timezone: str
    streak: StreakOut


class AttemptOut(BaseModel):
    attempt: int
    verdict: str
    ideas_hit: list[str]  # the rubric ideas the learner stated (missed ones stay hidden)
    ideas_total: int
    hint: str
    hint_level: int | None


class RevealOut(BaseModel):
    pattern: str
    summary: str | None
    reference_solution: str
    time_complexity: str
    space_complexity: str


class ScenarioOut(BaseModel):
    id: str
    title: str
    prompt: str


class LessonOut(BaseModel):
    date: date
    kind: str
    status: str
    scenario: ScenarioOut
    attempts: list[AttemptOut]
    attempts_left: int
    reveal: RevealOut | None
    next_review: date | None


class AttemptIn(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)


class SubmitOut(BaseModel):
    attempt: AttemptOut
    lesson: LessonOut
    streak: StreakOut


class ReviewOut(BaseModel):
    pattern: str
    name: str
    box: int
    due: date
    last_outcome: str


class ReviewsOut(BaseModel):
    due: list[ReviewOut]
    upcoming: list[ReviewOut]


# ---- app ----


def create_app(
    content: Content,
    grader: L.Grader,
    *,
    secret: str,
    database_url: str | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    pool = make_pool(database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await pool.open()
        async with pool.connection() as conn:
            await apply_schema(conn)
        yield
        await pool.close()

    app = FastAPI(title="Patternly", lifespan=lifespan)
    bearer = HTTPBearer(auto_error=False)

    async def conn_dep():
        async with pool.connection() as conn:
            yield conn

    Conn = Annotated[psycopg.AsyncConnection, Depends(conn_dep)]

    async def current_learner(
        conn: Conn, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
    ) -> L.Learner:
        learner_id = read_token(creds.credentials, secret) if creds else None
        if learner_id is not None:
            cur = await conn.execute("SELECT id, email, timezone FROM learners WHERE id = %s", (learner_id,))
            row = await cur.fetchone()
            if row:
                return L.Learner(*row)
        raise HTTPException(401, "Not logged in", headers={"WWW-Authenticate": "Bearer"})

    Me = Annotated[L.Learner, Depends(current_learner)]

    @app.exception_handler(L.LessonError)
    async def lesson_error(request: Request, exc: L.LessonError):
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    @app.post("/auth/register", status_code=201)
    async def register(body: RegisterIn, conn: Conn) -> TokenOut:
        try:
            cur = await conn.execute(
                "INSERT INTO learners (email, password_hash, timezone) VALUES (%s, %s, %s) RETURNING id",
                (body.email.lower(), hash_password(body.password), body.timezone),
            )
        except psycopg.errors.UniqueViolation:
            raise HTTPException(409, "That email is already registered") from None
        return TokenOut(access_token=make_token((await cur.fetchone())[0], secret))

    @app.post("/auth/login")
    async def login(body: LoginIn, conn: Conn) -> TokenOut:
        cur = await conn.execute("SELECT id, password_hash FROM learners WHERE email = %s", (body.email.lower(),))
        row = await cur.fetchone()
        if row is None or not verify_password(body.password, row[1]):
            raise HTTPException(401, "Wrong email or password")
        return TokenOut(access_token=make_token(row[0], secret))

    @app.get("/me")
    async def me(learner: Me, conn: Conn) -> MeOut:
        streak = await L.get_streak(conn, learner, clock())
        return MeOut(id=learner.id, email=learner.email, timezone=learner.timezone, streak=_streak(streak))

    async def lesson_out(conn, learner: L.Learner, row: dict) -> LessonOut:
        scenario = content.scenarios[row["scenario_id"]]
        attempts = [_attempt(scenario, a) for a in await L.lesson_attempts(conn, row["id"])]
        reveal = next_review = None
        if row["status"] != "open":
            pattern = content.patterns[scenario.pattern]
            reveal = RevealOut(
                pattern=pattern.name,
                summary=pattern.summary,
                reference_solution=scenario.reference_solution,
                time_complexity=scenario.time_complexity,
                space_complexity=scenario.space_complexity,
            )
            progress = (await L.get_progress(conn, learner.id)).get(scenario.pattern)
            next_review = progress.due if progress else None
        return LessonOut(
            date=row["local_date"],
            kind=row["kind"],
            status=row["status"],
            scenario=ScenarioOut(id=scenario.id, title=scenario.title, prompt=scenario.prompt.strip()),
            attempts=attempts,
            attempts_left=0 if row["status"] != "open" else L.MAX_ATTEMPTS - len(attempts),
            reveal=reveal,
            next_review=next_review,
        )

    @app.get("/lessons/today")
    async def today(learner: Me, conn: Conn) -> LessonOut:
        return await lesson_out(conn, learner, await L.todays_lesson(conn, content, learner, clock()))

    @app.post("/lessons/today/attempts")
    async def attempt(body: AttemptIn, learner: Me, conn: Conn) -> SubmitOut:
        now = clock()
        a, row = await L.submit_attempt(conn, content, learner, body.answer.strip(), now, grader)
        scenario = content.scenarios[row["scenario_id"]]
        return SubmitOut(
            attempt=_attempt(scenario, a),
            lesson=await lesson_out(conn, learner, row),
            streak=_streak(await L.get_streak(conn, learner, now)),
        )

    @app.get("/reviews")
    async def reviews(learner: Me, conn: Conn) -> ReviewsOut:
        today = L.local_today(clock(), learner.timezone)
        items = sorted((await L.get_progress(conn, learner.id)).values(), key=lambda p: (p.due, p.box))
        out = [
            ReviewOut(
                pattern=p.pattern,
                name=content.patterns[p.pattern].name,
                box=p.box,
                due=p.due,
                last_outcome=p.last_outcome.value,
            )
            for p in items
            if p.pattern in content.patterns
        ]
        return ReviewsOut(due=[r for r in out if r.due <= today], upcoming=[r for r in out if r.due > today])

    return app


def _streak(s: Streak) -> StreakOut:
    return StreakOut(current=s.current, longest=s.longest, freezes=s.freezes, done_today=s.done_today)


def _attempt(scenario, a: dict) -> AttemptOut:
    hit = [item.idea for item in scenario.rubric if a["items"].get(item.id)]
    return AttemptOut(
        attempt=a["attempt"],
        verdict=a["verdict"],
        ideas_hit=hit,
        ideas_total=len(scenario.rubric),
        hint=a["hint"],
        hint_level=a["hint_level"],
    )


def tutor_grader(client, checker, *, model: str, effort: str, search=None) -> L.Grader:
    """The real grader: the Weekend 4 tool-using tutor."""
    from ..tutor.agent import run_attempt

    def grade(scenario, answer, history, learner_id):
        return run_attempt(
            client,
            scenario,
            answer,
            learner_id=learner_id,
            history=history,
            checker=checker,
            search=search,
            model=model,
            effort=effort,
        )

    return grade

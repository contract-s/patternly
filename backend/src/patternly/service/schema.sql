-- Learner data. Content (patterns, scenarios, rubrics) stays in content/ YAML and is loaded at startup.
CREATE TABLE IF NOT EXISTS learners (
    id            bigserial PRIMARY KEY,
    email         text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    timezone      text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- One lesson per learner per local day.
CREATE TABLE IF NOT EXISTS lessons (
    id          bigserial PRIMARY KEY,
    learner_id  bigint NOT NULL REFERENCES learners (id) ON DELETE CASCADE,
    local_date  date NOT NULL,
    scenario_id text NOT NULL,
    pattern_id  text NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('new', 'review', 'practice')),
    status      text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'passed', 'revealed')),
    outcome     text CHECK (outcome IN ('clean', 'hinted', 'missed')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    UNIQUE (learner_id, local_date)
);

CREATE TABLE IF NOT EXISTS attempts (
    id          bigserial PRIMARY KEY,
    lesson_id   bigint NOT NULL REFERENCES lessons (id) ON DELETE CASCADE,
    attempt     int NOT NULL,
    answer      text NOT NULL,
    verdict     text NOT NULL CHECK (verdict IN ('pass', 'fail')),
    items       jsonb NOT NULL,          -- rubric id -> hit
    hint        text NOT NULL,
    hint_level  int,
    hint_source text NOT NULL,
    cost_usd    double precision NOT NULL,
    latency_s   double precision NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (lesson_id, attempt)
);

-- Spaced repetition state per pattern.
CREATE TABLE IF NOT EXISTS pattern_progress (
    learner_id   bigint NOT NULL REFERENCES learners (id) ON DELETE CASCADE,
    pattern_id   text NOT NULL,
    box          int NOT NULL,
    due_date     date NOT NULL,
    reviews      int NOT NULL,
    last_outcome text NOT NULL,
    PRIMARY KEY (learner_id, pattern_id)
);

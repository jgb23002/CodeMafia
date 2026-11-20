CREATE TABLE challenge_timers (
    session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    round integer NOT NULL CHECK (round BETWEEN 1 AND 5),
    deadline timestamptz NOT NULL,
    PRIMARY KEY (session_id, round)
);

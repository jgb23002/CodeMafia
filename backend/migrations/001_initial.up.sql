CREATE TABLE sessions (
    id uuid CONSTRAINT sessions_pkey PRIMARY KEY,
    room_code text NOT NULL CONSTRAINT sessions_room_code_key UNIQUE
        CHECK (room_code ~ '^[A-Z0-9]{6}$'),
    host_player_id uuid NOT NULL,
    phase text NOT NULL DEFAULT 'WAITING'
        CHECK (phase IN ('WAITING','SABOTAGE','CHALLENGE','DISCUSSION','VOTING','ROUND_RESULTS','GAME_OVER')),
    round integer NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'waiting',
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    CONSTRAINT sessions_lifecycle_check CHECK (
        (phase = 'WAITING' AND round = 0 AND status = 'waiting' AND started_at IS NULL)
        OR (phase NOT IN ('WAITING','GAME_OVER') AND round BETWEEN 1 AND 5
            AND status = 'active' AND started_at IS NOT NULL)
        OR (phase = 'GAME_OVER' AND round BETWEEN 1 AND 5
            AND status = 'finished' AND started_at IS NOT NULL)
    ),
    CHECK ((status = 'finished') = (completed_at IS NOT NULL))
);

CREATE TABLE players (
    id uuid CONSTRAINT players_pkey PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 40),
    token_hash text NOT NULL CONSTRAINT players_token_hash_key UNIQUE
        CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT players_membership_key UNIQUE (id, session_id)
);
CREATE INDEX players_session_idx ON players(session_id, created_at, id);
ALTER TABLE sessions ADD CONSTRAINT sessions_host_membership_fkey
    FOREIGN KEY (host_player_id, id) REFERENCES players(id, session_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE role_assignments (
    session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    player_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('MAFIA','DETECTIVE','HACKER','CIVILIAN')),
    PRIMARY KEY (session_id, player_id),
    UNIQUE (session_id, role),
    FOREIGN KEY (player_id, session_id) REFERENCES players(id, session_id)
);

CREATE TABLE challenges (
    id text PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('CODING','ESCAPE')),
    round integer NOT NULL CHECK (round BETWEEN 1 AND 5),
    prompt text NOT NULL CHECK (length(prompt) > 0),
    answer_key jsonb NOT NULL CHECK (jsonb_typeof(answer_key) = 'object'),
    UNIQUE (round, kind)
);

CREATE TABLE attempts (
    id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    player_id uuid NOT NULL,
    challenge_id text NOT NULL REFERENCES challenges(id),
    submitted_answer text NOT NULL,
    is_correct boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (player_id, session_id) REFERENCES players(id, session_id)
);
CREATE INDEX attempts_session_idx ON attempts(session_id, challenge_id);

CREATE TABLE challenge_completions (
    session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    challenge_id text NOT NULL REFERENCES challenges(id),
    completed_by uuid NOT NULL,
    completed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, challenge_id),
    FOREIGN KEY (completed_by, session_id) REFERENCES players(id, session_id)
);

CREATE TABLE votes (
    session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    round integer NOT NULL CHECK (round BETWEEN 1 AND 5),
    voter_id uuid NOT NULL,
    target_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, round, voter_id),
    CHECK (voter_id <> target_id),
    FOREIGN KEY (voter_id, session_id) REFERENCES players(id, session_id),
    FOREIGN KEY (target_id, session_id) REFERENCES players(id, session_id)
);

CREATE TABLE results (
    session_id uuid PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    winner text NOT NULL CHECK (winner IN ('NON_MAFIA','MAFIA')),
    reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 80),
    solved_count integer NOT NULL CHECK (solved_count BETWEEN 0 AND 10),
    rounds_played integer NOT NULL CHECK (rounds_played BETWEEN 1 AND 5),
    completed_at timestamptz NOT NULL DEFAULT now()
);

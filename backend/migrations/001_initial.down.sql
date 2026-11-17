DROP TABLE results;
DROP TABLE votes;
DROP TABLE challenge_completions;
DROP TABLE attempts;
DROP TABLE challenges;
DROP TABLE role_assignments;
ALTER TABLE sessions DROP CONSTRAINT sessions_host_membership_fkey;
DROP TABLE players;
DROP TABLE sessions;

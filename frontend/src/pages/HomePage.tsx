import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useApi } from '../api/ApiProvider';
import type { JoinResult } from '../api/types';
import { useMutation } from '../hooks/useMutation';
import { normalizeCode, normalizeName, validateCode, validateName } from '../lib/validation';
import { useSession } from '../session/SessionProvider';

export function HomePage() {
  const api = useApi();
  const { setSeat } = useSession();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [name, setName] = useState('');
  const [code, setCode] = useState(() => normalizeCode(searchParams.get('code') ?? ''));
  const [nameError, setNameError] = useState<string | null>(null);
  const [codeError, setCodeError] = useState<string | null>(null);

  const create = useMutation((playerName: string) => api.createRoom(playerName));
  const join = useMutation((roomCode: string, playerName: string) => api.joinRoom(roomCode, playerName));
  const pending = create.pending || join.pending;

  function enterRoom(result: JoinResult, playerName: string) {
    setSeat({
      roomCode: result.roomCode,
      playerId: result.playerId,
      playerName,
      playerToken: result.playerToken,
    });
    navigate(`/room/${result.roomCode}`);
  }

  function checkName(): string | null {
    const playerName = normalizeName(name);
    const error = validateName(playerName);
    setNameError(error);
    return error ? null : playerName;
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    join.reset();
    const playerName = checkName();
    if (!playerName) return;
    const result = await create.run(playerName);
    if (result.ok) enterRoom(result.data, playerName);
  }

  async function handleJoin(event: FormEvent) {
    event.preventDefault();
    create.reset();
    const playerName = checkName();
    const roomCodeError = validateCode(code);
    setCodeError(roomCodeError);
    if (!playerName || roomCodeError) return;
    const result = await join.run(code, playerName);
    if (result.ok) enterRoom(result.data, playerName);
  }

  return (
    <div className="home">
      <section className="home__intro">
        <h1>Escape the system. Find the mafia.</h1>
        <p>Four players, one room code. Create a room and share the code, or join a friend’s room.</p>
      </section>

      <div className="field">
        <label htmlFor="player-name">Your name</label>
        <input
          id="player-name"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setNameError(null);
          }}
          autoComplete="nickname"
          aria-invalid={nameError ? true : undefined}
          aria-describedby={nameError ? 'player-name-error' : 'player-name-hint'}
        />
        {nameError ? (
          <p id="player-name-error" className="field__error" role="alert">
            {nameError}
          </p>
        ) : (
          <p id="player-name-hint" className="field__hint">
            2–16 letters, numbers, spaces, - or _
          </p>
        )}
      </div>

      <div className="home__actions">
        <form className="card" onSubmit={handleCreate} aria-labelledby="create-heading" noValidate>
          <h2 id="create-heading">Create a room</h2>
          <p className="card__text">Start a new room and become the host.</p>
          <button type="submit" className="button button--primary" disabled={pending}>
            {create.pending ? 'Creating…' : 'Create room'}
          </button>
          {create.error && (
            <p className="form-error" role="alert">
              {create.error.message}
            </p>
          )}
        </form>

        <form className="card" onSubmit={handleJoin} aria-labelledby="join-heading" noValidate>
          <h2 id="join-heading">Join a room</h2>
          <div className="field">
            <label htmlFor="room-code">Room code</label>
            <input
              id="room-code"
              className="input--code"
              value={code}
              onChange={(e) => {
                setCode(normalizeCode(e.target.value));
                setCodeError(null);
                join.reset();
              }}
              placeholder="ABC234"
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              aria-invalid={codeError ? true : undefined}
              aria-describedby={codeError ? 'room-code-error' : undefined}
            />
            {codeError && (
              <p id="room-code-error" className="field__error" role="alert">
                {codeError}
              </p>
            )}
          </div>
          <button type="submit" className="button button--secondary" disabled={pending}>
            {join.pending ? 'Joining…' : 'Join room'}
          </button>
          {join.error && (
            <p className="form-error" role="alert">
              {join.error.message}
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

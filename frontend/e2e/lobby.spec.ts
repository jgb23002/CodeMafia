import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const API = 'http://127.0.0.1:18000';

/** Test credentials stay in the browser; only safe state/error data leaves it. */
async function privateRequest(page: Page, suffix: string, method = 'GET', body?: object) {
  return page.evaluate(async ({ suffix, method, body, base }) => {
    const seat = JSON.parse(sessionStorage.getItem('codemafia.seat')!);
    const response = await fetch(`${base}/api/sessions/${seat.roomCode}${suffix}`, {
      method,
      headers: { Authorization: `Bearer ${seat.playerToken}`, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: 'no-store',
    });
    return { status: response.status, body: await response.json(), playerId: seat.playerId };
  }, { suffix, method, body, base: API });
}

test('four players privately reveal stable roles and rejoin without duplicate seats', async ({ browser }) => {
  const contexts = await Promise.all(Array.from({ length: 5 }, (_, index) =>
    browser.newContext(index === 1 ? { viewport: { width: 390, height: 844 } } : {}),
  ));
  try {
    const pages = await Promise.all(contexts.map((context) => context.newPage()));
    const host = pages[0];
    await host.goto('/');
    await host.getByLabel('Your name').fill('Host');
    await host.getByRole('button', { name: 'Create room', exact: true }).click();
    const codeDisplay = host.locator('.lobby__code-value');
    await expect(codeDisplay).toHaveText(/^[A-Z0-9]{6}$/);
    const code = (await codeDisplay.textContent())!.trim();
    await expect(host.getByRole('button', { name: 'Start game' })).toBeDisabled();

    for (let index = 1; index < 4; index++) {
      const guest = pages[index];
      await guest.goto('/');
      await guest.getByLabel('Your name').fill(`Guest ${index}`);
      await guest.getByLabel('Room code').fill(code);
      await guest.getByRole('button', { name: 'Join room', exact: true }).click();
      await expect(guest.locator('.lobby__code-value')).toHaveText(code);
      await expect(guest.getByRole('button', { name: 'Start game' })).toHaveCount(0);
    }
    await expect(host.getByText('4 of 4 players')).toBeVisible();
    const guestBefore = await privateRequest(pages[1], '/state');
    expect(guestBefore.body.my_role).toBeNull();
    const duplicate = await privateRequest(pages[1], '/join', 'POST', { display_name: 'Duplicate' });
    expect(duplicate.status).toBe(409);
    expect(duplicate.body.error.code).toBe('ALREADY_JOINED');
    const forbidden = await privateRequest(pages[1], '/start', 'POST', {});
    expect(forbidden.status).toBe(403);
    expect(forbidden.body.error.code).toBe('HOST_ONLY');
    await pages[1].reload();
    await expect(pages[1].getByText('4 of 4 players')).toBeVisible();
    expect((await privateRequest(pages[1], '/state')).body.my_player_id).toBe(guestBefore.playerId);

    const fifth = pages[4];
    await fifth.goto('/');
    await fifth.getByLabel('Your name').fill('Fifth');
    await fifth.getByLabel('Room code').fill(code);
    await fifth.getByRole('button', { name: 'Join room', exact: true }).click();
    await expect(fifth.getByRole('alert')).toContainText('already has 4 players');
    const unauthenticated = await contexts[4].request.get(`${API}/api/sessions/${code}/state?player_id=${guestBefore.playerId}`);
    expect(unauthenticated.status()).toBe(401);
    expect(Object.keys(await unauthenticated.json())).toEqual(['error']);

    await expect(host.getByRole('button', { name: 'Start game' })).toBeEnabled();
    await host.getByRole('button', { name: 'Start game' }).click();
    const roles = [];
    const labels: Record<string, string> = { MAFIA: 'Mafia', DETECTIVE: 'Detective', HACKER: 'Hacker', CIVILIAN: 'Civilian' };
    for (const page of pages.slice(0, 4)) {
      await expect(page.getByRole('heading', { name: 'Your role', exact: true })).toBeVisible();
      await expect(page).toHaveURL(new RegExp(`/room/${code}/role$`));
      const privateState = await privateRequest(page, '/state');
      expect(privateState.status).toBe(200);
      expect(Object.keys(privateState.body).sort()).toEqual(['my_player_id', 'my_role', 'phase', 'room_code', 'round']);
      expect(privateState.body.my_player_id).toBe(privateState.playerId);
      await expect(page.getByTestId('private-role')).toHaveCount(0);
      await page.getByRole('button', { name: 'Reveal my role' }).click();
      await expect(page.getByTestId('private-role')).toHaveText(labels[privateState.body.my_role]);
      expect(await page.evaluate(() => Object.keys(sessionStorage))).toEqual(['codemafia.seat']);
      expect(await page.evaluate(() => localStorage.getItem('codemafia.mock.v1'))).toBeNull();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      roles.push(privateState.body.my_role);
    }
    expect(new Set(roles)).toEqual(new Set(['MAFIA', 'DETECTIVE', 'HACKER', 'CIVILIAN']));

    const guest = pages[1];
    const roleBeforeRefresh = (await privateRequest(guest, '/state')).body;
    let registrations = 0;
    guest.on('request', (request) => {
      if (request.method() === 'POST' && request.url().endsWith('/join')) registrations++;
    });
    await guest.reload();
    await expect(guest.getByRole('button', { name: 'Reveal my role' })).toBeVisible();
    await expect(guest.getByTestId('private-role')).toHaveCount(0);
    expect((await privateRequest(guest, '/state')).body).toEqual(roleBeforeRefresh);
    expect(registrations).toBe(0);
    await guest.getByRole('button', { name: 'Reveal my role' }).click();
    await expect(guest.getByTestId('private-role')).toHaveText(labels[roleBeforeRefresh.my_role]);
    if (process.env.CODEMAFIA_ROLE_PREVIEW) {
      await guest.screenshot({ path: process.env.CODEMAFIA_ROLE_PREVIEW, fullPage: true });
    }
    await guest.getByRole('button', { name: 'Hide my role' }).click();
    await expect(guest.getByTestId('private-role')).toHaveCount(0);
    await guest.goto('/');
    await guest.getByRole('button', { name: 'Resume my room' }).click();
    await expect(guest.getByRole('heading', { name: 'Your role', exact: true })).toBeVisible();
    expect((await privateRequest(guest, '/state')).body).toEqual(roleBeforeRefresh);
    expect((await privateRequest(guest, '')).body.player_count).toBe(4);
    expect(registrations).toBe(0);
  } finally {
    await Promise.all(contexts.map((context) => context.close()));
  }
});

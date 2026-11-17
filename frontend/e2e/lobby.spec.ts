import { expect, test } from '@playwright/test';

test('four isolated players create, join, refresh, and start through the real API', async ({ browser }) => {
  const contexts = await Promise.all(Array.from({ length: 5 }, () => browser.newContext()));
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
    await pages[1].reload();
    await expect(pages[1].getByText('4 of 4 players')).toBeVisible();

    const fifth = pages[4];
    await fifth.goto('/');
    await fifth.getByLabel('Your name').fill('Fifth');
    await fifth.getByLabel('Room code').fill(code);
    await fifth.getByRole('button', { name: 'Join room', exact: true }).click();
    await expect(fifth.getByRole('alert')).toContainText('already has 4 players');

    await expect(host.getByRole('button', { name: 'Start game' })).toBeEnabled();
    await host.getByRole('button', { name: 'Start game' }).click();
    for (const page of pages.slice(0, 4)) {
      await expect(page.getByRole('heading', { name: 'Your role' })).toBeVisible();
      await expect(page).toHaveURL(new RegExp(`/room/${code}/role$`));
    }
  } finally {
    await Promise.all(contexts.map((context) => context.close()));
  }
});

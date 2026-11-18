import { expect, test, type Page } from '@playwright/test';

test.skip(!process.env.APP_URL || !process.env.DATABRICKS_TOKEN, 'set APP_URL and DATABRICKS_TOKEN (deployed app)');

async function setPersona(page: Page, persona: 'seller' | 'manager' | 'empty') {
  const res = await page.request.put('/api/persona', { data: { persona } });
  expect(res.status(), await res.text()).toBe(200);
}

test.describe.serial('Fleetwise Seller Hub smoke', () => {
  test.afterAll(async ({ browser }) => {
    const page = await browser.newPage();
    await setPersona(page, 'seller'); // leave the demo on Jordan
    await page.close();
  });

  test('My Week shows Priority deals with at least one deal row for Jordan', async ({ page }) => {
    await setPersona(page, 'seller');
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Priority deals' })).toBeVisible();
    await expect(page.getByTestId('deal-row').first()).toBeVisible();
    await expect(page.getByText('Jordan Rivera', { exact: false }).first()).toBeVisible();
  });

  test('Accept on the first action removes it from the queue', async ({ page }) => {
    await setPersona(page, 'seller');
    await page.goto('/');
    const first = page.getByTestId('action-item').first();
    await expect(first).toBeVisible();
    const actionId = await first.getAttribute('data-action-id');
    expect(actionId).toBeTruthy();
    await first.getByRole('button', { name: 'Accept' }).click();
    await expect(page.locator(`[data-action-id="${actionId}"]`)).toHaveCount(0);
    await page.reload(); // the decision is persisted in Lakebase, not just client state
    await expect(page.getByRole('heading', { name: 'Priority deals' })).toBeVisible();
    await expect(page.getByTestId('action-item').first()).toBeVisible();
    await expect(page.locator(`[data-action-id="${actionId}"]`)).toHaveCount(0);
  });

  test('Deal 360 shows a Next steps section', async ({ page }) => {
    await setPersona(page, 'seller');
    await page.goto('/');
    await page.getByTestId('deal-row').first().getByRole('link').click();
    await expect(page.getByRole('heading', { name: 'Call insights' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Next steps' })).toBeVisible();
  });

  test('Ask Genie answers an open-pipeline question', async ({ page }) => {
    await setPersona(page, 'seller');
    await page.goto('/genie');
    await expect(page.getByRole('heading', { name: 'Ask Genie' })).toBeVisible();
    const input = page.getByPlaceholder('e.g. What is my open pipeline by stage this quarter?');
    await input.fill('What is my open pipeline by stage this quarter?');
    await input.press('Enter');
    // A finished Genie answer renders its generated query / result table.
    await expect(page.getByRole('table').or(page.getByText(/SELECT/i)).first()).toBeVisible({ timeout: 150_000 });
  });

  test('Empty persona shows the No open deals empty state', async ({ page }) => {
    await setPersona(page, 'empty');
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Priority deals' })).toBeVisible();
    await expect(page.getByText('No open deals', { exact: true })).toBeVisible();
  });

  test('Persona switcher rejects admin', async ({ page }) => {
    const res = await page.request.put('/api/persona', { data: { persona: 'admin' } });
    expect(res.status()).toBe(400);
  });
});

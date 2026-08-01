import { expect, test } from '@playwright/test';

test('onboarding, demo workflow, and global pause', async ({ page }) => {
  await page.goto('http://127.0.0.1:8765/portal/');
  const init = page.getByRole('button', { name: 'Initialize first-use account' });
  if (await init.isVisible()) await init.click();
  await page.getByRole('button', { name: 'Run Demo Workflow' }).click();
  await expect(page.getByText('demo completed.')).toBeVisible({ timeout: 120_000 });
  await page.getByRole('button', { name: 'Pause All Automation' }).click();
  await expect(page.getByText('paused')).toBeVisible();
});

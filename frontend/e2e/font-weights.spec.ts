import { test, expect } from '@playwright/test';

test.describe('Issue #211 — Schrift-Weights vollständig geladen', () => {
  test('AC-1: Google-Fonts-Link enthält Inter Tight 400;500;600;700', async ({ page }) => {
    await page.goto('/');
    const linkHref = await page
      .locator('link[rel="stylesheet"][href*="fonts.googleapis.com"]')
      .first()
      .getAttribute('href');
    expect(linkHref).toContain('Inter+Tight:wght@400;500;600;700');
  });

  test('AC-2: Google-Fonts-Link enthält JetBrains Mono 400;500;600', async ({ page }) => {
    await page.goto('/');
    const linkHref = await page
      .locator('link[rel="stylesheet"][href*="fonts.googleapis.com"]')
      .first()
      .getAttribute('href');
    expect(linkHref).toContain('JetBrains+Mono:wght@400;500;600');
  });

  test('AC-3: Google-Fonts-Link enthält display=swap', async ({ page }) => {
    await page.goto('/');
    const linkHref = await page
      .locator('link[rel="stylesheet"][href*="fonts.googleapis.com"]')
      .first()
      .getAttribute('href');
    expect(linkHref).toContain('display=swap');
  });
});

import { test, expect } from '@playwright/test';

test.describe('Epic #133 — Tokens + Topo', () => {
  test('AC-1: --g-text-md = "15px"', async ({ page }) => {
    await page.goto('/');
    const v = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--g-text-md').trim()
    );
    expect(v).toBe('15px');
  });

  test('AC-2: --g-s-4 = "16px"', async ({ page }) => {
    await page.goto('/');
    const v = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--g-s-4').trim()
    );
    expect(v).toBe('16px');
  });

  test('AC-3: --g-track-wide = "0.06em"', async ({ page }) => {
    await page.goto('/');
    const v = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--g-track-wide').trim()
    );
    expect(v).toMatch(/^0?\.06em$/);
  });

  test('AC-4: .g-topo background-image enthält "ellipse"', async ({ page }) => {
    await page.goto('/');
    // .g-topo nur sichtbar wenn TopoBg auf einer Route gemountet ist. Direkt im DOM injizieren:
    const bg = await page.evaluate(() => {
      const el = document.createElement('div');
      el.className = 'g-topo';
      document.body.appendChild(el);
      const result = getComputedStyle(el).backgroundImage;
      el.remove();
      return result;
    });
    expect(bg).toMatch(/radial-gradient\(\s*\d+(?:\.\d+)?(?:px|em|%)\s+\d+(?:\.\d+)?(?:px|em|%)\s+at/);
  });

  test('AC-5: .g-topo backgroundImage enthält 5x radial-gradient', async ({ page }) => {
    await page.goto('/');
    const bg = await page.evaluate(() => {
      const el = document.createElement('div');
      el.className = 'g-topo';
      document.body.appendChild(el);
      const result = getComputedStyle(el).backgroundImage;
      el.remove();
      return result;
    });
    const count = (bg.match(/radial-gradient/g) ?? []).length;
    expect(count).toBe(5);
  });

  test('AC-6: .g-topo opacity-default >= 0.4', async ({ page }) => {
    await page.goto('/');
    const opacity = await page.evaluate(() => {
      const el = document.createElement('div');
      el.className = 'g-topo';
      document.body.appendChild(el);
      const result = parseFloat(getComputedStyle(el).opacity);
      el.remove();
      return result;
    });
    expect(opacity).toBeGreaterThanOrEqual(0.4);
  });
});

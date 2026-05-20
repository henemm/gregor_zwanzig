/**
 * Mobile Audit Screenshot Script
 * Nimmt Screenshots aller Routes bei 4 Viewports.
 * Läuft gegen http://localhost:5173 (dev server).
 */
import { chromium } from 'playwright';
import { readFileSync } from 'fs';
import { mkdir } from 'fs/promises';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dir = dirname(fileURLToPath(import.meta.url));
const BASE_URL = 'http://localhost:5173';

const VIEWPORTS = [
  { name: '375x667', width: 375, height: 667 },
  { name: '390x844', width: 390, height: 844 },
  { name: '414x896', width: 414, height: 896 },
  { name: '768x1024', width: 768, height: 1024 },
];

const ROUTES = JSON.parse(readFileSync(join(__dir, 'routes.json'), 'utf-8'));
const ALL_ROUTES = [...ROUTES.public, ...ROUTES.authenticated];

const STORAGE_STATE = JSON.parse(
  readFileSync(join(__dir, '../frontend/playwright/.auth/admin.json'), 'utf-8')
);

const RESULTS = [];

async function takeScreenshot(page, viewport, route, state = 'default') {
  const dir = join(__dir, 'screenshots', viewport.name);
  await mkdir(dir, { recursive: true });
  const filename = `${route.slug}__${state}.png`;
  const path = join(dir, filename);
  try {
    await page.screenshot({ path, fullPage: false });
    RESULTS.push({ viewport: viewport.name, route: route.slug, state, status: 'ok', path: `screenshots/${viewport.name}/${filename}` });
    console.log(`  ✓ ${viewport.name}/${filename}`);
  } catch (e) {
    RESULTS.push({ viewport: viewport.name, route: route.slug, state, status: 'error', error: e.message });
    console.log(`  ✗ ${viewport.name}/${filename}: ${e.message}`);
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true });

  for (const viewport of VIEWPORTS) {
    console.log(`\n── Viewport ${viewport.name} ──────────────────────────`);

    // Kontext mit Auth-Cookies
    const ctx = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      storageState: STORAGE_STATE,
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
    });

    const page = await ctx.newPage();

    for (const route of ALL_ROUTES) {
      console.log(`\n  Route: ${route.path}`);
      try {
        const url = `${BASE_URL}${route.path}`;
        const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
        const finalUrl = page.url();

        // Wenn Redirect zu /login -> public route, keine Auth
        if (finalUrl.includes('/login') && route.auth) {
          console.log(`  → Redirect zu Login (Auth-Problem oder Session abgelaufen)`);
          await takeScreenshot(page, viewport, route, 'login-redirect');
          continue;
        }

        // Kurz warten bis UI vollständig
        await page.waitForTimeout(800);
        await takeScreenshot(page, viewport, route, 'default');

        // Scrolled-bottom State
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await page.waitForTimeout(300);
        await takeScreenshot(page, viewport, route, 'scrolled-bottom');
        await page.evaluate(() => window.scrollTo(0, 0));

      } catch (e) {
        console.log(`  ✗ Fehler bei ${route.path}: ${e.message}`);
        RESULTS.push({ viewport: viewport.name, route: route.slug, state: 'default', status: 'error', error: e.message });
      }
    }

    await ctx.close();
  }

  await browser.close();

  // Ergebnisse speichern
  import('fs').then(({ writeFileSync }) => {
    writeFileSync(join(__dir, 'screenshot-results.json'), JSON.stringify(RESULTS, null, 2));
  });

  const ok = RESULTS.filter(r => r.status === 'ok').length;
  const err = RESULTS.filter(r => r.status === 'error').length;
  console.log(`\n\nFertig: ${ok} Screenshots OK, ${err} Fehler`);
}

main().catch(console.error);

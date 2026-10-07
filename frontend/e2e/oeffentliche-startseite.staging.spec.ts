// Issue #2520 — oeffentliche Startseite, AC-5/7/9/10 gegen STAGING.
// Spec: docs/specs/modules/oeffentliche_startseite_2520.md
//
// Aufruf (nach Staging-Deploy):
//   cd frontend/e2e && GZ_AUTH_USER=... GZ_AUTH_PASS=... GZ_VALIDATOR_USER=... \
//     GZ_VALIDATOR_PASS=... npx playwright test oeffentliche-startseite.staging.spec.ts
//
// GEHOERT NICHT in `.github/ci_e2e_specs.txt`: braucht Staging (nginx-Schranke,
// Staging-Zugang) und einen echten Service Worker (`serviceWorkers: 'allow'`),
// die isolierte CI-Lane hat beides nicht. Das Suffix `.staging.` schliesst die
// Datei vom Vermessungslauf aus (ci.yml `--exclude='*.staging.spec.ts'`).
import { test, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';

const BASE = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';

test.use({
	baseURL: BASE,
	ignoreHTTPSErrors: true,
	httpCredentials: {
		username: process.env.GZ_VALIDATOR_USER ?? '',
		password: process.env.GZ_VALIDATOR_PASS ?? ''
	},
	storageState: { cookies: [], origins: [] },
	serviceWorkers: 'allow',
	viewport: { width: 375, height: 800 }
});

test.beforeAll(() => assertNotProdBaseURL(BASE));

test('AC-5: Registrieren und Anmelden sichtbar, Klick fuehrt auf /register bzw. /login', async ({ page }) => {
	await page.goto('/');
	await expect(page).toHaveURL(/\/$/);
	const reg = page.getByRole('link', { name: 'Registrieren' });
	const login = page.getByRole('link', { name: 'Anmelden' });
	await expect(reg).toBeVisible();
	await expect(login).toBeVisible();
	await reg.click();
	await expect(page).toHaveURL(/\/register/);
	await page.goto('/');
	await page.getByRole('link', { name: 'Anmelden' }).click();
	await expect(page).toHaveURL(/\/login/);
});

test('AC-7: mindestens drei Bilder laden (naturalWidth > 0) mit nicht leerem Alt-Text', async ({ page }) => {
	await page.goto('/');
	const bilder = page.locator('[data-testid="startseite"] img');
	await expect(bilder).toHaveCount(3);
	for (const img of await bilder.all()) {
		await img.scrollIntoViewIfNeeded();
		await expect.poll(() => img.evaluate((e: HTMLImageElement) => e.naturalWidth)).toBeGreaterThan(0);
		expect((await img.getAttribute('alt'))?.trim().length ?? 0).toBeGreaterThan(5);
	}
});

test('AC-10: kein horizontales Scrollen, kein Navigations-Chrome', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByTestId('startseite')).toBeVisible();
	const breiten = await page.evaluate(() => ({
		scroll: document.documentElement.scrollWidth,
		inner: window.innerWidth
	}));
	expect(breiten.scroll).toBeLessThanOrEqual(breiten.inner);
	for (const id of ['bottom-nav', 'bottom-shell', 'desktop-sidebar', 'konto-kreis']) {
		await expect(page.getByTestId(id)).toHaveCount(0);
	}
});

test('AC-9: ausgeloggt Startseite, Login A Cockpit, Logout Startseite, kein Cache-Eintrag fuer /', async ({ page }) => {
	const user = process.env.GZ_AUTH_USER;
	const pass = process.env.GZ_AUTH_PASS;
	expect(user, 'GZ_AUTH_USER fehlt').toBeTruthy();

	await page.goto('/');
	await expect(page.getByTestId('startseite')).toBeVisible();

	const login = await page.request.post('/api/auth/login', { data: { username: user, password: pass } });
	expect(login.ok()).toBeTruthy();
	await page.goto('/');
	await expect(page.getByTestId('startseite')).toHaveCount(0);
	await expect(page.getByRole('link', { name: 'Registrieren' })).toHaveCount(0);

	// Logout ueber die echte Form-Action.
	await page.evaluate(() => {
		const f = document.createElement('form');
		f.method = 'POST';
		f.action = '/logout';
		document.body.appendChild(f);
		f.submit();
	});
	await page.waitForURL(/\/login/);
	await page.goto('/');
	await expect(page.getByTestId('startseite')).toBeVisible();
	await expect(page.getByRole('link', { name: 'Registrieren' })).toBeVisible();

	const eintraege = await page.evaluate(async () => {
		const out: string[] = [];
		for (const name of await caches.keys()) {
			if (!name.startsWith('gz-daten-')) continue;
			for (const req of await (await caches.open(name)).keys()) {
				const p = new URL(req.url).pathname;
				if (p === '/' || p === '/__data.json') out.push(`${name}:${p}`);
			}
		}
		return out;
	});
	expect(eintraege).toEqual([]);
});

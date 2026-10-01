// TDD RED — E2E (Staging), Issue #2155 S4: Admin-Seite `/admin`.
//
// Spec: docs/specs/modules/admin_ui_s4.md — AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-9.
// Zwei-Nutzer-Test: `gz-staging-admin` (Admin) und ein Nicht-Admin-Konto.
// Gesperrt/umgestuft wird NUR ein Test-Konto (`is_test_user`), nie ein echter Nutzer;
// Tier und Sperre werden am Ende zurueckgestellt.
//
// Vom Frontend vorausgesetzte Testkennungen (Vertrag fuer /50-implement):
//   nav-admin (Sidebar-Eintrag), konto-sheet-admin (Konto-Sheet-Link),
//   admin-user-row (Zeile, Attribut data-user-id), admin-open-request (Antrags-Markierung),
//   admin-tier-select (Tier-Auswahl je Zeile), admin-disable-btn / admin-enable-btn,
//   admin-confirm-disable / admin-cancel-disable (ConfirmDialog), admin-row-error.
//
// RED-Grund: die Seite `/admin` und der Nav-Eintrag existieren nicht.
// Nicht Messbares (Staging-Datenbestand fuer `hem` nicht lesbar) wird als
// NOT_MEASURABLE_ON_STAGING gemeldet, nie als PASS erfunden.
//
// Ausfuehren (aus frontend/, gegen Staging):
//   npx playwright test --config=e2e/playwright.admin-nutzerverwaltung.staging.config.ts

import { test, expect, type Browser, type BrowserContext, type Page } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// Pfade wie im Setup (dort NICHT importierbar: ein Import wuerde dessen setup() im Spec-Projekt registrieren).
const ADMIN_STATE = path.join(__dirname, 'playwright', '.auth', 'staging-2155-s4-admin.json');
const USER_STATE = path.join(__dirname, 'playwright', '.auth', 'staging-2155-s4-user.json');
const BASE = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 375, height: 667 };

async function kontext(browser: Browser, state: string, viewport = DESKTOP): Promise<BrowserContext> {
	return browser.newContext({
		baseURL: BASE,
		storageState: state,
		viewport,
		ignoreHTTPSErrors: true,
		httpCredentials: {
			username: process.env.GZ_VALIDATOR_USER ?? 'admin',
			password: process.env.GZ_VALIDATOR_PASS ?? 'test1234'
		}
	});
}

type AdminUser = { id: string; tier: string; disabled: boolean; is_test_user: boolean; requested_tier: string };

/** Nutzerliste ueber die Go-API des Admin-Kontexts (Testdaten-Auswahl, kein Prueflings-Schritt). */
async function nutzerListe(ctx: BrowserContext): Promise<AdminUser[]> {
	const res = await ctx.request.get('/api/admin/users');
	expect(res.status(), 'Admin-Liste per API').toBe(200);
	return (await res.json()).users;
}

async function testKonto(ctx: BrowserContext): Promise<AdminUser | null> {
	const liste = await nutzerListe(ctx);
	return liste.find((u) => u.is_test_user && !u.disabled) ?? null;
}

const zeileVon = (page: Page, id: string) => page.locator(`[data-testid="admin-user-row"][data-user-id="${id}"]`);

test.describe('#2155 S4 — Admin-Seite', () => {
	test.beforeAll(() => assertNotProdBaseURL(BASE));

	test('AC-1: Nav-Eintrag „Admin" nur fuer Admin (Sidebar + Konto-Sheet), Tabbar unveraendert', async ({ browser }) => {
		const admin = await kontext(browser, ADMIN_STATE);
		const normal = await kontext(browser, USER_STATE);
		try {
			const a = await admin.newPage();
			await a.goto('/');
			await expect(a.getByTestId('desktop-sidebar').getByTestId('nav-admin')).toBeVisible();
			const n = await normal.newPage();
			await n.goto('/');
			await expect(n.getByTestId('desktop-sidebar')).toBeVisible();
			await expect(n.getByTestId('nav-admin')).toHaveCount(0);

			// Mobil: Konto-Sheet
			await a.setViewportSize(MOBILE);
			await a.goto('/');
			const tabsVorher = await a.getByTestId('bottom-nav').locator('a').count();
			await a.getByTestId('konto-kreis').click();
			await expect(a.getByTestId('konto-sheet-admin')).toBeVisible();
			expect(await a.getByTestId('bottom-nav').locator('a').count(), 'Tabbar veraendert').toBe(tabsVorher);
			await n.setViewportSize(MOBILE);
			await n.goto('/');
			await n.getByTestId('konto-kreis').click();
			await expect(n.getByTestId('konto-sheet')).toBeVisible();
			await expect(n.getByTestId('konto-sheet-admin')).toHaveCount(0);
		} finally {
			await admin.close();
			await normal.close();
		}
	});

	test('AC-2: Direktaufruf /admin — Nicht-Admin 403 ohne Nutzerdaten, Admin sieht die Liste', async ({ browser }) => {
		const admin = await kontext(browser, ADMIN_STATE);
		const normal = await kontext(browser, USER_STATE);
		try {
			const n = await normal.newPage();
			const antwort = await n.goto('/admin');
			expect(antwort?.status(), 'Nicht-Admin: Status von /admin').toBe(403);
			await expect(n.getByTestId('admin-user-row')).toHaveCount(0);
			// Go bleibt die echte Sperre
			const api = await normal.request.get('/api/admin/users');
			expect(api.status(), 'Go-API fuer Nicht-Admin').toBe(403);

			const a = await admin.newPage();
			const ok = await a.goto('/admin');
			expect(ok?.status()).toBe(200);
			await expect(a.getByTestId('admin-user-row').first()).toBeVisible();
		} finally {
			await admin.close();
			await normal.close();
		}
	});

	test('AC-3: Zeilen zeigen Kennung, E-Mail, Tier, Sperrstatus, letzten Lauf — keine Geheimnisse', async ({ browser }) => {
		const admin = await kontext(browser, ADMIN_STATE);
		try {
			const liste = await nutzerListe(admin);
			const a = await admin.newPage();
			await a.goto('/admin');
			const zeilen = a.getByTestId('admin-user-row');
			await expect(zeilen).toHaveCount(liste.length);
			const erste = zeileVon(a, liste[0].id);
			await expect(erste).toContainText(/@/);
			await expect(erste).toContainText(/Free|Standard|Premium/);
			await expect(erste).toContainText(/kein Lauf|\d{2}[.:]/);
			const seite = await a.content();
			expect(seite).not.toMatch(/password_hash|passkey|\$2[aby]\$/i);
			// Offener Antrag deutlich hervorgehoben (nur pruefbar, wenn Staging einen hat)
			const mitAntrag = liste.find((u) => u.requested_tier);
			if (mitAntrag) {
				await expect(zeileVon(a, mitAntrag.id).getByTestId('admin-open-request')).toBeVisible();
			} else {
				test.info().annotations.push({ type: 'NOT_MEASURABLE_ON_STAGING', description: 'kein offener Tier-Antrag auf Staging' });
			}
		} finally {
			await admin.close();
		}
	});

	test('AC-4: Tier aendern ersetzt nur die Zeile; Antrag verschwindet', async ({ browser }) => {
		const admin = await kontext(browser, ADMIN_STATE);
		try {
			const ziel = await testKonto(admin);
			test.skip(!ziel, 'NOT_MEASURABLE_ON_STAGING: kein aktives Test-Konto vorhanden');
			const alt = ziel!.tier;
			const neu = alt === 'premium' ? 'standard' : 'premium';
			const a = await admin.newPage();
			await a.goto('/admin');
			const andere = (await nutzerListe(admin)).filter((u) => u.id !== ziel!.id);
			const vorher = await Promise.all(andere.map((u) => zeileVon(a, u.id).innerText()));

			const put = a.waitForResponse((r) => r.url().includes(`/api/admin/users/${ziel!.id}/tier`) && r.request().method() === 'PUT');
			await zeileVon(a, ziel!.id).getByTestId('admin-tier-select').selectOption(neu);
			expect((await put).status()).toBe(200);
			await expect(zeileVon(a, ziel!.id)).toContainText(neu === 'premium' ? 'Premium' : 'Standard');
			await expect(zeileVon(a, ziel!.id).getByTestId('admin-open-request')).toHaveCount(0);
			const nachher = await Promise.all(andere.map((u) => zeileVon(a, u.id).innerText()));
			expect(nachher, 'andere Zeilen veraendert').toEqual(vorher);

			// Zurueckstellen
			await admin.request.put(`/api/admin/users/${ziel!.id}/tier`, { data: { tier: alt } });
		} finally {
			await admin.close();
		}
	});

	test('AC-5: Sperren mit Bestaetigungsdialog, Abbrechen sendet nichts, Entsperren ohne Dialog', async ({ browser }) => {
		const admin = await kontext(browser, ADMIN_STATE);
		try {
			const ziel = await testKonto(admin);
			test.skip(!ziel, 'NOT_MEASURABLE_ON_STAGING: kein aktives Test-Konto vorhanden');
			const a = await admin.newPage();
			await a.goto('/admin');
			const zeile = zeileVon(a, ziel!.id);

			const anfragen: string[] = [];
			a.on('request', (r) => { if (r.url().includes('/disabled') && r.method() === 'PUT') anfragen.push(r.postData() ?? ''); });

			await zeile.getByTestId('admin-disable-btn').click();
			await expect(a.getByTestId('admin-confirm-disable')).toBeVisible();
			await a.getByTestId('admin-cancel-disable').click();
			expect(anfragen, 'Abbrechen hat trotzdem gesendet').toHaveLength(0);

			await zeile.getByTestId('admin-disable-btn').click();
			const put = a.waitForResponse((r) => r.url().includes(`/api/admin/users/${ziel!.id}/disabled`));
			await a.getByTestId('admin-confirm-disable').click();
			expect((await put).status()).toBe(200);
			expect(JSON.parse(anfragen[0])).toEqual({ disabled: true });
			await expect(zeile).toContainText(/gesperrt/i);

			// Entsperren: ohne Dialog
			const put2 = a.waitForResponse((r) => r.url().includes(`/api/admin/users/${ziel!.id}/disabled`));
			await zeile.getByTestId('admin-enable-btn').click();
			await expect(a.getByTestId('admin-confirm-disable')).toHaveCount(0);
			expect((await put2).status()).toBe(200);
			expect(JSON.parse(anfragen[1])).toEqual({ disabled: false });
		} finally {
			// Sicherheitsnetz: nie ein gesperrtes Test-Konto zuruecklassen
			const ziel = (await nutzerListe(admin)).find((u) => u.is_test_user && u.disabled);
			if (ziel) await admin.request.put(`/api/admin/users/${ziel.id}/disabled`, { data: { disabled: false } });
			await admin.close();
		}
	});

	test('AC-6: eigenes Konto sperren wird nicht angeboten bzw. mit Klartext abgelehnt', async ({ browser }) => {
		const admin = await kontext(browser, ADMIN_STATE);
		try {
			const profil = await (await admin.request.get('/api/auth/profile')).json();
			const a = await admin.newPage();
			await a.goto('/admin');
			const eigene = zeileVon(a, profil.id);
			await expect(eigene).toBeVisible();
			const btn = eigene.getByTestId('admin-disable-btn');
			if ((await btn.count()) > 0 && (await btn.isEnabled())) {
				await btn.click();
				await a.getByTestId('admin-confirm-disable').click();
				await expect(eigene.getByTestId('admin-row-error')).toHaveText('Das eigene Konto kann nicht gesperrt werden');
			} else {
				await expect(btn).toBeDisabled();
			}
			const nachher = (await nutzerListe(admin)).find((u) => u.id === profil.id);
			expect(nachher?.disabled, 'Admin hat sich selbst gesperrt').toBe(false);
		} finally {
			await admin.close();
		}
	});
});

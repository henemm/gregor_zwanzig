// E2E (Staging) — Issue #3441 (S5b, Scheibe #2797): „Test-Alarm“ im Menü „Test schicken ▾“, Trip- und Orte-Hub.
// Spec: docs/specs/modules/feat_3441_test_alarm.md — AC-1, AC-2, AC-7, AC-8, AC-16, AC-17.
//
// Läuft NICHT im PR-CI, sondern in /e2e-verify nach Push und Staging-Deploy:
//   cd frontend && npx playwright test --config playwright.3441-test-alarm.staging.config.ts
// Umgebung (nie im Klartext ausgeben): Prüfkonto und Seed-IDs wählt e2e/pruefkontoZugang.ts (GZ_PRUEFKONTO_*
// vor GZ_AUTH_*; ELEMENTLISTE_TRIP_ID/ELEMENTLISTE_ORTE_ID optional, sonst Lookup des Seeds aus
// scripts/staging_pruefkonto_mockupdaten.py), optional GZ_VALIDATOR_* (nginx).
// Echter Versand nur E-Mail und Telegram (Prüfkonto: bestätigte Adresse, verbundener Chat; Staging leitet Mail ins
// Stalwart-Test-Postfach). Den Posteingang (Betreff mit [TEST], X-GZ-Mail-Type: deviation-alert, Anzahl 1 je Klick)
// prüft /e2e-verify im Stalwart-Test-Postfach; SMS/Premium-SMS nie real (Kosten), nur im pytest-Endpunkt-Test.

import { test, expect, type Page, type Locator, type Cookie, type Request } from '@playwright/test';
import { HUB_KINDS, type HubKind } from './helpers';
import { pruefkontoZugang, seedIds } from './pruefkontoZugang.ts';

test.describe.configure({ mode: 'serial' });

const KNOPF = 'subscription-hub-send';
const IDS: Record<HubKind, string> = { route: '', vergleich: '' }; // befüllt in beforeAll (seedIds)
const HUB_PFAD = (kind: HubKind) => (kind === 'route' ? `/trips/${IDS[kind]}` : `/compare/${IDS[kind]}`);
const UNTERTITEL = 'Beispiel-Alarm mit echten Werten an alle Alarm-Kanäle';
const LEER = 'Kein Alarm-Kanal eingerichtet, der Test-Alarm ging nirgends hin.';
let sitzung: Cookie[] = [];

test.beforeAll(async ({ browser }) => {
	const { user, pass } = pruefkontoZugang();
	const ctx = await browser.newContext({ baseURL: test.info().project.use.baseURL, ignoreHTTPSErrors: true });
	const login = await ctx.request.post('/api/auth/login', { data: { username: user, password: pass } });
	expect(login.ok(), `Login HTTP ${login.status()}`).toBeTruthy();
	Object.assign(IDS, await seedIds(ctx.request));
	sitzung = (await ctx.storageState()).cookies as Cookie[];
	await ctx.close();
});

test.beforeEach(async ({ page }) => {
	await page.context().addCookies(sitzung);
	for (const kind of HUB_KINDS) expect(IDS[kind], `Vorbedingung: Seed-ID für ${kind}`).not.toBe('');
});

test.afterAll(async ({ browser }) => {
	const ctx = await browser.newContext({ baseURL: test.info().project.use.baseURL, ignoreHTTPSErrors: true });
	await ctx.addCookies(sitzung);
	await ctx.request.post('/api/auth/logout').catch(() => {});
	await ctx.close();
});

async function oeffneMenue(page: Page, kind: HubKind): Promise<Locator> {
	await page.goto(HUB_PFAD(kind), { waitUntil: 'domcontentloaded' });
	await expect(page.getByTestId(KNOPF)).toBeVisible({ timeout: 20_000 });
	await page.getByTestId(KNOPF).click();
	const m = page.locator('[data-abschnitt="test-menue"]');
	await expect(m).toBeVisible();
	return m;
}

const eintrag = (m: Locator) => m.getByRole('menuitem', { name: /Test-Alarm/ });

async function alarmAbrufe(page: Page, kind: HubKind): Promise<Request[]> {
	const liste: Request[] = [];
	page.on('request', (r) => {
		if (r.method() === 'POST' && r.url().includes(`/api/briefings/${IDS[kind]}/test-alert`)) liste.push(r);
	});
	return liste;
}

for (const kind of HUB_KINDS) {
	for (const breite of [1280, 390]) {
		test(`AC-1 (${kind}, ${breite} px): „Test-Alarm“ mit Untertitel nach „Alle eingerichteten Kanäle“`, async ({ page }) => {
			await page.setViewportSize({ width: breite, height: 900 });
			const m = await oeffneMenue(page, kind);
			const texte = (await m.getByRole('menuitem').allInnerTexts()).map((t) => t.trim());
			const alle = texte.findIndex((t) => t.startsWith('Alle eingerichteten Kanäle'));
			const alarm = texte.findIndex((t) => t.startsWith('Test-Alarm'));
			expect(alle, 'Zeile „Alle eingerichteten Kanäle“ fehlt').toBeGreaterThanOrEqual(0);
			expect(alarm, 'Test-Alarm muss nach „Alle“ stehen').toBe(alle + 1);
			await expect(eintrag(m)).toContainText(UNTERTITEL);
		});
	}
}

for (const kind of HUB_KINDS) {
	test(`AC-2/AC-8/AC-17 (${kind}): echter Versand an E-Mail und Telegram, Doppelklick = ein Request, Rückmeldung 5 s`, async ({ page }) => {
		const abrufe = await alarmAbrufe(page, kind);
		const m = await oeffneMenue(page, kind);
		const antwortP = page.waitForResponse((r) => r.url().includes(`/api/briefings/${IDS[kind]}/test-alert`), { timeout: 150_000 });
		await eintrag(m).dblclick();
		const antwort = await antwortP;
		expect(antwort.status(), await antwort.text()).toBe(200);
		const gesendet = ((await antwort.json()) as { sent_channels?: string[] }).sent_channels ?? [];
		expect([...gesendet].sort()).toEqual(['email', 'telegram']);
		const ok = page.getByTestId('test-schicken-ok');
		await expect(ok).toHaveText(/^Test-Alarm geschickt: E-Mail ✓ · Telegram ✓ .*· \d{2}:\d{2}$/);
		expect(abrufe).toHaveLength(1);
		await expect(ok).toBeHidden({ timeout: 8_000 });
	});
}

for (const kind of HUB_KINDS) {
	test(`AC-7 (${kind}): leere Kanalmenge zeigt den Leer-Text im Fehlerton`, async ({ page }) => {
		// Transportgrenze: die Fehlerform kommt wörtlich wie vom Backend (pytest prüft die Abbildung).
		await page.route(`**/api/briefings/${IDS[kind]}/test-alert**`, (route) =>
			route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ detail: 'x', code: 'keine_alarm_kanaele' }) })
		);
		const m = await oeffneMenue(page, kind);
		await eintrag(m).click();
		await expect(page.getByTestId('test-schicken-fehler')).toHaveText(LEER);
		await expect(page.getByTestId('test-schicken-ok')).toHaveCount(0);
	});
}

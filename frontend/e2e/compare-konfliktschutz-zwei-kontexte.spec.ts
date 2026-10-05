// E2E — Issue #2375 (löst #2381 mit), Epic #2345: Konfliktschutz im
// Ortsvergleich-Hub mit ZWEI Browser-Kontexten desselben Nutzers.
//
// Spec: docs/specs/bugfix/compare_konfliktschutz_teilfelder.md
//   Test 9  / AC-1..AC-4 — A ändert den Namen, B speichert danach je Reiter
//             (Alarme, Wertebereiche, Versand, Wetter-Metriken, Orte): der
//             erste PUT von B trägt If-Match aus dem Seitenaufbau, der Server
//             antwortet 412, nach „Nochmal speichern" stehen Name von A UND
//             Änderung von B auf dem Server.
//   Test 10 / AC-5 (#2381) — selber Tab: Reiter-Wert speichern, danach Name
//             ändern ⇒ beides auf dem Server; der Kopf-PUT ist exakt { name }.
//   Test 11 / AC-6 — Pausieren (a) im Hub, (b) auf der Listenseite /compare:
//             Name von A bleibt, `schedule: "manual"`; der Status-PUT trägt nur
//             { schedule, previous_schedule }.
//
// Warum E2E: „die fremde Änderung überlebt" wirkt erst im Zusammenspiel von
// Seitenaufbau (ETag), Reiter-Nutzlast, 412-Pfad und Go-Merge — nur im
// Browser mit zwei Kontexten messbar. Die Nutzlast-Form sichern die
// Kern-Tests (compare_reiter_nutzlast_nur_eigene_felder.test.ts u. a.).
//
// Zweiter Kontext = weiterer Browser-Kontext mit DEMSELBEN storageState
// (kein zweiter Login ⇒ keine 429-Sperre). Läuft im isolierten CI-Stack
// (frontend/e2e/ci-stack.sh). Presets tragen das Präfix E2E-GZ-, afterEach
// löscht sie direkt, global.teardown.ts räumt Reste.
// Gewartet wird ausschließlich über expect.poll/toHaveAttribute (Filter A der
// CI-Positivliste: keine festen Wartezeiten, keine übersprungenen Fälle).

import { test, expect, type Browser, type BrowserContext, type Page, type Request } from '@playwright/test';
import { E2E_TEST_PREFIX } from './helpers';

let angelegt: string[] = [];
let weitereKontexte: BrowserContext[] = [];

test.afterEach(async ({ page }) => {
	for (const ctx of weitereKontexte) {
		await ctx.close().catch(() => undefined);
	}
	weitereKontexte = [];
	for (const id of angelegt) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Aufräumen ist nicht testkritisch */
		}
	}
	angelegt = [];
});

async function legeVergleichAn(page: Page): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: `${E2E_TEST_PREFIX}Konfliktschutz ${Date.now()}`,
			// Seed-Orte aus global.setup.ts — mit Orten ist der Vergleich „aktiv".
			location_ids: ['e2e-loc-innsbruck', 'e2e-loc-stubai'],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['konfliktschutz@example.com'],
			official_alerts_enabled: true,
			radar_alert_enabled: false,
			send_telegram: true,
			send_sms: false,
			morning_enabled: true,
			morning_time: '06:00:00',
			evening_enabled: false,
			evening_time: '18:00:00',
			alert_cooldown_minutes: 45,
			hourly_enabled: true,
			outlook_enabled: true,
			day_window_start_hour: 4,
			day_window_end_hour: 19,
			corridors: [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }],
			display_config: {
				region: 'Tirol',
				ideal_ranges: { snow_depth_cm: { min: 30, max: 200 } },
				active_metrics: ['snow_depth_cm'],
				hourly_metrics: ['snow_depth_cm'],
				outlook_metrics: ['snow_depth_cm'],
				telegram_style: 'kurzform'
			}
		}
	});
	expect(res.ok(), 'Vergleich-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	angelegt.push(body.id);
	return body.id as string;
}

/** Zweiter Kontext DESSELBEN Nutzers (gleicher storageState, kein neuer Login). */
async function kontextB(browser: Browser, baseURL: string | undefined, storageState: unknown): Promise<Page> {
	const ctx = await browser.newContext({
		baseURL,
		storageState: storageState as string,
		serviceWorkers: 'block',
		viewport: { width: 1280, height: 900 }
	});
	weitereKontexte.push(ctx);
	return ctx.newPage();
}

/** Alle PUTs auf genau diesen Vergleich (Request = abgeschickter Rumpf). */
function zaehlePuts(page: Page, id: string): Request[] {
	const pfad = `/api/compare/presets/${id}`;
	const puts: Request[] = [];
	page.on('request', (r) => {
		if (r.method() === 'PUT' && new URL(r.url()).pathname === pfad) puts.push(r);
	});
	return puts;
}

async function serverStand(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/compare/presets/${id}`);
	expect(res.ok()).toBeTruthy();
	return res.json();
}

const anzeige = (page: Page) => page.locator('[data-testid="save-indicator"]');

async function oeffneHub(page: Page, id: string, reiter?: string): Promise<void> {
	await page.goto(reiter ? `/compare/${id}?tab=${reiter}` : `/compare/${id}`);
	await page.waitForLoadState('networkidle');
	if (reiter) await page.locator(`[data-testid="compare-detail-tab-${reiter}"]:visible`).click();
}

/** Kontext A benennt den Vergleich über den Kopf um und wartet auf den gespeicherten PUT. */
async function benenneUm(page: Page, id: string, name: string): Promise<Request> {
	const puts = zaehlePuts(page, id);
	await page.locator('[data-testid="compare-hub-name-edit-toggle"]:visible').click();
	await page.locator('[data-testid="compare-hub-name-edit"]:visible').fill(name);
	await page.locator('[data-testid="compare-hub-name-save"]:visible').click();
	await expect.poll(async () => (puts.length ? (await puts[0].response())?.status() : 0), { timeout: 10_000 }).toBe(200);
	return puts[0];
}

interface ReiterFall {
	reiter: string;
	/** Tab-Kennung im Hub (`compare-detail-tab-<tab>`) */
	tab: string;
	bereit: (page: Page) => Promise<void>;
	aendern: (page: Page) => Promise<void>;
	pruefe: (stand: Record<string, unknown>) => void;
}

const REITER_FAELLE: ReiterFall[] = [
	{
		reiter: 'Alarme',
		tab: 'alarme',
		bereit: async (p) => {
			await expect(p.locator('[data-testid="alarme-tab"]').first()).toBeVisible({ timeout: 10_000 });
		},
		aendern: async (p) => {
			const radar = p.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first();
			await radar.click();
			await expect(radar).toBeChecked();
		},
		pruefe: (s) => expect(s.radar_alert_enabled, 'Alarme-Änderung von B fehlt auf dem Server').toBe(true)
	},
	{
		reiter: 'Wertebereiche',
		tab: 'wertebereiche',
		bereit: async (p) => {
			const editor = p.locator('[data-testid="corridor-editor-vergleich"]:visible');
			await expect(editor.locator('[data-testid="corridor-row-snow_depth_cm"]')).toBeVisible({ timeout: 10_000 });
		},
		aendern: async (p) => {
			const editor = p.locator('[data-testid="corridor-editor-vergleich"]:visible');
			await editor.locator('.ce-pool-btn').first().click();
			await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(2, { timeout: 5_000 });
		},
		pruefe: (s) =>
			expect((s.corridors as unknown[]).length, 'Wertebereiche-Änderung von B fehlt auf dem Server').toBe(2)
	},
	{
		reiter: 'Versand',
		tab: 'versand',
		bereit: async (p) => {
			await expect(p.locator('[data-testid="versand-tab"]:visible [data-testid="report-morning-time"]')).toBeVisible({
				timeout: 10_000
			});
		},
		aendern: async (p) => {
			await p.locator('[data-testid="versand-tab"]:visible [data-testid="report-morning-time"]').selectOption('08:00');
		},
		pruefe: (s) => expect(s.morning_time, 'Versand-Änderung von B fehlt auf dem Server').toBe('08:00:00')
	},
	{
		reiter: 'Wetter-Metriken',
		tab: 'wetter-metriken',
		bereit: async (p) => {
			await expect(
				p.locator('[data-testid="weather-metrics-tab-vergleich"]:visible [data-testid="report-show-official-alerts"]')
			).toBeVisible({ timeout: 10_000 });
		},
		aendern: async (p) => {
			await p
				.locator(
					'[data-testid="weather-metrics-tab-vergleich"]:visible [data-testid="report-show-official-alerts"] input[type="checkbox"]'
				)
				.click();
		},
		pruefe: (s) => expect(s.official_alerts_enabled, 'Wetter-Metriken-Änderung von B fehlt auf dem Server').toBe(false)
	}
];

test.describe('Issue #2375: Konfliktschutz im Ortsvergleich mit zwei Kontexten', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// Test 9 / AC-1..AC-3 — je Reiter
	for (const fall of REITER_FAELLE) {
		test(`Test 9 (${fall.reiter}): A ändert den Namen, B speichert danach → 412 mit If-Match → „Nochmal speichern" → Name von A UND Änderung von B`, async ({
			page,
			browser,
			baseURL,
			storageState
		}) => {
			const id = await legeVergleichAn(page);
			// B lädt ZUERST — sein Stand ist danach veraltet
			const b = await kontextB(browser, baseURL, storageState);
			const putsB = zaehlePuts(b, id);
			await oeffneHub(b, id, fall.tab);
			await fall.bereit(b);

			// A ändert den Namen
			await oeffneHub(page, id);
			const nameA = `${E2E_TEST_PREFIX}Name von A ${Date.now()}`;
			await benenneUm(page, id, nameA);

			// B speichert seine Reiter-Änderung
			await fall.aendern(b);
			await expect(anzeige(b)).toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });
			expect(putsB.length, 'Vorbedingung: B hat genau einen PUT gesendet').toBe(1);
			expect(
				await putsB[0].headerValue('if-match'),
				'AC-1: der erste PUT nach dem Laden muss If-Match aus dem Seitenaufbau tragen'
			).toBeTruthy();
			expect((await putsB[0].response())?.status(), 'AC-1: der veraltete Stand muss mit 412 abgelehnt werden').toBe(412);

			// „Nochmal speichern"
			await anzeige(b).getByRole('button', { name: 'Nochmal speichern' }).click();
			await expect(anzeige(b)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			expect(putsB.length, 'der Wiederholungs-PUT wurde gesendet').toBe(2);
			expect((await putsB[1].response())?.status()).toBe(200);
			expect(Object.keys(putsB[1].postDataJSON()), 'der Wiederholungs-PUT darf `name` nicht tragen').not.toContain(
				'name'
			);

			const stand = await serverStand(page, id);
			expect(stand.name, 'der Name von A ging beim „Nochmal speichern" von B verloren').toBe(nameA);
			fall.pruefe(stand);
		});
	}

	// Test 9 (Orte) / AC-4. Seit #1433 bleibt nach einem 412 das alte If-Match
	// stehen, bis „Nochmal speichern" läuft (Konflikt-Sperre, kein unbedingtes
	// Schreiben). Der Orte-Pfad meldet seinen 412 deshalb an den Controller: die
	// Liste von B bleibt stehen (kein Rollback), „Nochmal speichern" holt Stand und
	// Stempel frisch und sendet erneut nur { location_ids }.
	test('Test 9 (Orte): A ändert den Namen, B entfernt einen Ort → 412 mit If-Match → „Nochmal speichern" → Name von A UND Ortsliste von B', async ({
		page,
		browser,
		baseURL,
		storageState
	}) => {
		const id = await legeVergleichAn(page);
		const b = await kontextB(browser, baseURL, storageState);
		const putsB = zaehlePuts(b, id);
		await oeffneHub(b, id, 'orte');
		const zeilen = b.locator('[data-testid="hub-orte-row"]');
		await expect(zeilen).toHaveCount(2, { timeout: 10_000 });

		await oeffneHub(page, id);
		const nameA = `${E2E_TEST_PREFIX}Name von A ${Date.now()}`;
		await benenneUm(page, id, nameA);

		const entfernen = b.locator('[data-testid="hub-orte-row"][data-loc-id="e2e-loc-stubai"] [data-testid="hub-orte-remove"]');
		await entfernen.click();
		await expect.poll(async () => (putsB.length ? (await putsB[0].response())?.status() : 0), { timeout: 10_000 }).toBe(412);
		expect(await putsB[0].headerValue('if-match'), 'AC-1: If-Match aus dem Seitenaufbau').toBeTruthy();
		await expect(anzeige(b)).toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });
		await expect(zeilen, 'nach dem 412 bleibt die Ortsliste von B stehen (kein Rollback)').toHaveCount(1, { timeout: 5_000 });

		// „Nochmal speichern"
		await anzeige(b).getByRole('button', { name: 'Nochmal speichern' }).click();
		await expect(anzeige(b)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		expect(putsB.length, 'der Wiederholungs-PUT wurde gesendet').toBe(2);
		expect((await putsB[1].response())?.status()).toBe(200);
		expect(putsB[1].postDataJSON(), 'der Orte-PUT trägt nur { location_ids }').toEqual({ location_ids: ['e2e-loc-innsbruck'] });

		const stand = await serverStand(page, id);
		expect(stand.name, 'der Name von A ging beim Orte-Speichern von B verloren').toBe(nameA);
		expect(stand.location_ids).toEqual(['e2e-loc-innsbruck']);
	});

	// Test 10 / AC-5 (#2381) — selber Tab
	test('Test 10 (#2381): Reiter-Wert speichern, danach im selben Tab den Namen ändern → beides auf dem Server, Kopf-PUT = { name }', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		await oeffneHub(page, id, 'alarme');
		await REITER_FAELLE[0].bereit(page);
		await REITER_FAELLE[0].aendern(page);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		await expect.poll(async () => (await serverStand(page, id)).radar_alert_enabled, { timeout: 10_000 }).toBe(true);

		const neuerName = `${E2E_TEST_PREFIX}Umbenannt ${Date.now()}`;
		const kopfPut = await benenneUm(page, id, neuerName);
		expect(kopfPut.postDataJSON(), 'der Kopf-PUT darf nur { name } tragen').toEqual({ name: neuerName });

		const stand = await serverStand(page, id);
		expect(stand.name).toBe(neuerName);
		expect(stand.radar_alert_enabled, 'der Kopf-Edit hat den eben gespeicherten Alarm-Wert zurückgeschrieben (#2381)').toBe(
			true
		);
	});

	// Test 11a / AC-6 — Hub (Kopf-Kebab → handleToggleActive). B hat einen
	// veralteten Stand: der erste Versuch scheitert mit 412 (If-Match). Seit #1433
	// bleibt das alte If-Match bis „Nochmal speichern" stehen; der Status-Pfad meldet
	// den 412 an den Controller, der Retry holt Stand und Stempel frisch und sendet
	// erneut nur { schedule, previous_schedule }.
	test('Test 11a: A ändert den Namen, B pausiert im Hub → 412 → „Nochmal speichern" → Name von A bleibt, schedule "manual", Status-PUT = { schedule, previous_schedule }', async ({
		page,
		browser,
		baseURL,
		storageState
	}) => {
		const id = await legeVergleichAn(page);
		const b = await kontextB(browser, baseURL, storageState);
		const putsB = zaehlePuts(b, id);
		await oeffneHub(b, id);

		await oeffneHub(page, id);
		const nameA = `${E2E_TEST_PREFIX}Name von A ${Date.now()}`;
		await benenneUm(page, id, nameA);

		await b.getByRole('button', { name: 'Weitere Aktionen' }).first().click();
		await b.getByRole('menuitem', { name: 'Pausieren' }).click();
		await expect.poll(async () => (putsB.length ? (await putsB[0].response())?.status() : 0), { timeout: 10_000 }).toBe(412);
		expect(await putsB[0].headerValue('if-match'), 'AC-1: If-Match aus dem Seitenaufbau').toBeTruthy();
		await expect(anzeige(b)).toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });

		// „Nochmal speichern"
		await anzeige(b).getByRole('button', { name: 'Nochmal speichern' }).click();
		await expect(anzeige(b)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		expect(putsB.length, 'der Wiederholungs-PUT wurde gesendet').toBe(2);
		expect((await putsB[1].response())?.status()).toBe(200);
		expect(Object.keys(putsB[1].postDataJSON()).sort(), 'Status-PUT trägt nur den Status').toEqual([
			'previous_schedule',
			'schedule'
		]);

		const stand = await serverStand(page, id);
		expect(stand.schedule).toBe('manual');
		expect(stand.name, 'Pausieren im Hub hat den Namen von A überschrieben').toBe(nameA);
	});

	// Test 11b / AC-6 — Listenseite /compare (eigener Codepfad, roher fetch ohne If-Match)
	test('Test 11b: A ändert den Namen, B pausiert auf der Listenseite /compare → Name von A bleibt, schedule "manual"', async ({
		page,
		browser,
		baseURL,
		storageState
	}) => {
		const id = await legeVergleichAn(page);
		const b = await kontextB(browser, baseURL, storageState);
		const putsB = zaehlePuts(b, id);
		await b.goto('/compare');
		await b.waitForLoadState('networkidle');
		const kachel = b.locator(`[data-testid="compare-tile-${id}"]:visible`);
		await expect(kachel).toBeVisible({ timeout: 10_000 });

		await oeffneHub(page, id);
		const nameA = `${E2E_TEST_PREFIX}Name von A ${Date.now()}`;
		await benenneUm(page, id, nameA);

		await kachel.locator('button[aria-label="Weitere Aktionen"]').click();
		await b.getByRole('menuitem', { name: 'Pausieren' }).click();
		await expect.poll(async () => (putsB.length ? (await putsB[0].response())?.status() : 0), { timeout: 10_000 }).toBe(200);
		expect(putsB[0].postDataJSON(), 'der Listen-Kebab darf nur den Status senden').toEqual({
			schedule: 'manual',
			previous_schedule: 'daily'
		});

		const stand = await serverStand(page, id);
		expect(stand.schedule).toBe('manual');
		expect(stand.name, 'Pausieren auf der Listenseite hat den Namen von A überschrieben').toBe(nameA);
	});
});

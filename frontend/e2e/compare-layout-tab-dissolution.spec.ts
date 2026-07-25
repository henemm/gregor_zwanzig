// E2E (Staging) — Ortsvergleich: Layout-Reiter aufgelöst, Stundenverlauf zieht in
// den Reiter „Wetter-Metriken" (Issue #1360, Scheibe S1a von Epic #1372).
//
// Spec: docs/specs/modules/compare_layout_tab_dissolution.md § Acceptance Criteria
// Abgedeckt hier: AC-1, AC-2 (Speicher-Anteil), AC-3, AC-4, AC-5, AC-6.
//
// ── Warum Live-Schicht ───────────────────────────────────────────────────────
// Alle sechs Kriterien sind Aussagen über die BEDIENBARE Oberfläche und über den
// Go-Speicherweg:
//   AC-1/AC-4 — was der Nutzer in der Reiterleiste liest.
//   AC-2      — dass eine Bedienung im NEUEN Reiter wirklich einen schreibenden
//               Request auslöst. Bekannte Falle beim Umzug: der Hub speichert
//               über Event-Bubbling am Wrapper (`.hub-layout-hourly-wrap` mit
//               onchange/onfocusout/onclick, CompareTabs.svelte:1339-1348).
//               Wandert die Steuerung ohne ihren Wrapper, speichert sie STUMM
//               nicht mehr — im selben Tab sieht alles korrekt aus. Deshalb ist
//               der PUT-Zähler (> 0) der eigentliche Beweis, nicht der Bildschirm.
//               (Vgl. #1359 Ziehgeste, reference_compare_hub_save_hangs_on_event_bubbling.)
//   AC-3      — die Umleitung alter Deep-Links (`?tab=layout`).
//   AC-5      — Bestandsschutz von `hour_from`/`hour_to` gegen den ECHTEN
//               Go-Handler. Der hat für diese beiden Felder KEINEN Read-Modify-
//               Write-Schutz (Adversary-Fund F003 aus #1268: fehlen sie im PUT,
//               dekodiert Go Zero-Value 0 und schreibt 0 — stiller Datenverlust).
//               Ein Unit-Test auf die Payload-Bau-Funktion beweist das NICHT.
//               Vorbild: compare-legacy-fields-survive-save.spec.ts.
//   AC-6      — die Anlege-Seite zieht identisch mit.
//
// NICHT hier: der Mail-Anteil von AC-2 und AC-7 (Stundentabellen-Spalten in der
// echt zugestellten Mail). Der läuft in `/e2e-verify` über das Stalwart-Test-
// Postfach + `email_spec_validator.py` (Marker `X-GZ-Mail-Type: compare`).
// Die deterministische Struktur-Invarianz der Mail (AC-7) liegt in der
// Kern-Schicht: tests/test_compare_top_n_render_invariance.py.
//
// ── Ausführen (gegen STAGING, aus frontend/, NACH Push + Staging-Deploy) ─────
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.compare-layout-tab-dissolution.staging.config.ts
//
// Die Config `frontend/playwright.compare-layout-tab-dissolution.staging.config.ts`
// liegt daneben (1:1 nach `playwright.compare-metric-order.staging.config.ts`).
// Kein `webServer`-Block: geprüft wird die auf Staging deployte App selbst.
// WICHTIG: `GZ_API_BASE` zeigt per Default auf PRODUKTION (playwright.config.ts).
// Deshalb baseURL in der Config explizit auf `GZ_SVELTE_BASE ??
// 'https://staging.gregor20.henemm.com'`, und `assertNotProdBaseURL` im Setup
// sperrt jeden Lauf gegen die Prod-Domain (#1265).
// Anmeldung über gespeicherten Sitzungszustand (storageState), NICHT per
// Test-Login — der Login ist auf 30/h gedeckelt
// (reference_staging_e2e_storagestate_login_rate_limit).
// Testids kommen doppelt vor (Desktop/Mobil-Zweig) ⇒ durchgängig `:visible`.

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
import {
	cleanupTracked,
	createTestLocation,
	createTestComparePreset,
	registerForCleanup
} from './helpers';

/** Reiterleiste des Hubs nach der Auflösung — Soll aus Spec § Expected Behavior. */
const EXPECTED_HUB_TABS = [
	'Übersicht',
	'Orte',
	'Wetter-Metriken',
	'Wertebereiche',
	'Alarme',
	'Versand',
	'Vorschau'
];

/** Reiter der Anlege-Seite nach der Auflösung (kein „Vorschau", kein „Layout"). */
const EXPECTED_NEW_TABS = [
	'Vergleich',
	'Orte',
	'Wetter-Metriken',
	'Wertebereiche',
	'Alarme',
	'Versand'
];

/**
 * Aussagen, die es im Vergleichs-Editor NICHT mehr geben darf (AC-4).
 * Belegte Renderer-Regel: ALLE drei Kanäle geben ALLE Orte aus — gekappt werden
 * Metrikwerte je Ort bzw. die Nachrichtenlänge, nie die Orts-Spalten.
 * Heutiger Ist-Stand (CompareTabs.svelte:774-775,1303,1319): „Telegram · max 8",
 * „SMS · flach · 0", „Renderer kappt je Kanal".
 */
const FORBIDDEN_CLAIMS: RegExp[] = [
	/Telegram\s*·\s*max\s*\d+/i,
	/kappt\s+je\s+Kanal/i,
	/Spalten\s+pro\s+Kanal/i,
	/Übersicht\s+pro\s+Kanal/i,
	/max\.?\s*\d+\s*(Orte|Spalten)/i
];

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

async function makeThreeLocationIds(page: Page): Promise<string[]> {
	const ids: string[] = [];
	for (let i = 0; i < 3; i++) {
		const loc = await createTestLocation(page.request, { lat: 47.0 + i * 0.1, lon: 11.0 + i * 0.1 });
		ids.push(loc.id);
	}
	return ids;
}

async function makePreset(
	page: Page,
	opts: { hourFrom?: number; hourTo?: number } = {}
): Promise<string> {
	const locationIds = await makeThreeLocationIds(page);
	const preset = await createTestComparePreset(page.request, {
		name: `Layout-Auflösung ${Date.now()}`,
		locationIds,
		hourFrom: opts.hourFrom,
		hourTo: opts.hourTo
	});
	return preset.id;
}

/** Öffnet den Hub und wartet die Hydration ab (SvelteKit-Race, s. #1359). */
async function openHub(page: Page, id: string, query = ''): Promise<void> {
	await page.goto(`/compare/${id}${query}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15_000 });
	// Die Tab-Leiste kommt server-gerendert VOR der Hydration; ein Klick davor
	// geht spurlos verloren (reproduzierbar ~2/3 auf Staging, #1359).
	await page.waitForLoadState('networkidle');
}

async function openHubMetricsTab(page: Page, id: string): Promise<Locator> {
	await openHub(page, id);
	await page.locator('[data-testid="compare-detail-tab-wetter-metriken"]:visible').first().click();
	const panel = page.locator('[data-testid="compare-detail-panel-wetter-metriken"]:visible').first();
	await expect(panel).toBeVisible({ timeout: 10_000 });
	return panel;
}

async function hubTabLabels(page: Page): Promise<string[]> {
	// KORREKTUR gegenüber der RED-Fassung (gemeldet, nicht still geändert):
	// `[data-testid="compare-detail-tab-list"]` umschließt in CompareTabs.svelte
	// NICHT nur die Reiter-Leiste, sondern auch den Panel-Inhalt
	// (`.compare-tabs-bar` + `.compare-tabs-content`). Ein `locator('button')`
	// darauf hätte die „Bearbeiten →"-Knöpfe der Übersichtskarten mitgezählt und
	// AC-1 wäre nie erfüllbar gewesen. Jetzt gezielt über die Reiter-Testids.
	const raw = await page
		.locator('button[data-testid^="compare-detail-tab-"]:visible')
		.allInnerTexts();
	// Der Orte-Reiter trägt eine Zähler-Pille im selben Button — nur die erste
	// Zeile ist die Beschriftung.
	return raw.map((t) => t.split('\n')[0].trim()).filter((t) => t.length > 0);
}

/** Zeichnet jeden PUT auf diesen Vergleich auf (Speicher-Nachweis, AC-2). */
function collectPresetPuts(page: Page, id: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(`/api/compare/presets/${id}`)) {
			puts.push(req);
		}
	});
	return puts;
}

async function readPreset(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/compare/presets/${id}`);
	expect(res.ok(), `GET des Presets fehlgeschlagen: ${res.status()}`).toBeTruthy();
	return (await res.json()) as Record<string, unknown>;
}

test.describe('Issue #1360: Layout-Reiter aufgelöst, Stundenverlauf bei den Wetter-Metriken', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1 ──────────────────────────────────────────────────────────────────
	test('AC-1: der Hub zeigt sieben Reiter und keinen „Layout"', async ({ page }) => {
		const id = await makePreset(page);
		await openHub(page, id);

		const labels = await hubTabLabels(page);
		expect(
			labels,
			'AC-1: Reiterleiste des Ortsvergleichs — Soll aus Spec § Expected Behavior'
		).toEqual(EXPECTED_HUB_TABS);
		expect(labels, 'AC-1: es darf keinen Reiter „Layout" mehr geben').not.toContain('Layout');
		expect(labels.length, 'AC-1: genau sieben Reiter (wie beim Trip)').toBe(7);

		// Kein Panel mehr, das per Deep-Link doch noch erreichbar wäre.
		await expect(page.locator('[data-testid="compare-detail-panel-layout"]')).toHaveCount(0);
	});

	// ── AC-3 ──────────────────────────────────────────────────────────────────
	test('AC-3: der alte Deep-Link ?tab=layout landet in Wetter-Metriken', async ({ page }) => {
		const id = await makePreset(page);
		const consoleErrors: string[] = [];
		page.on('pageerror', (err) => consoleErrors.push(String(err)));

		await openHub(page, id, '?tab=layout');

		await expect(
			page.locator('[data-testid="compare-detail-panel-wetter-metriken"]:visible').first(),
			'AC-3: ein Lesezeichen auf den alten Layout-Reiter muss in Wetter-Metriken landen ' +
				'(resolveCompareTab: layout → wetter-metriken, statt Fallback uebersicht)'
		).toBeVisible({ timeout: 10_000 });
		await expect(page.locator('[data-testid="compare-detail-panel-uebersicht"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="compare-detail-panel-layout"]')).toHaveCount(0);
		expect(consoleErrors, 'AC-3: ohne Fehlermeldung').toEqual([]);

		// Die Stundenverlauf-Steuerung ist genau dort erreichbar.
		await expect(
			page.locator('[data-testid="compare-layout-hourly-metrics"]:visible').first()
		).toBeVisible({ timeout: 10_000 });
	});

	// ── AC-2 ──────────────────────────────────────────────────────────────────
	test('AC-2: Stundengröße im Reiter Wetter-Metriken umschalten löst einen PUT aus und bleibt', async ({
		page
	}) => {
		const id = await makePreset(page);
		const panel = await openHubMetricsTab(page, id);

		const hourlyBlock = panel.locator('[data-testid="compare-layout-hourly-metrics"]').first();
		await expect(
			hourlyBlock,
			'AC-2: die Stundenverlauf-Steuerung muss IM Reiter Wetter-Metriken liegen ' +
				'(Abschnitt „stundenverlauf" zwischen „reihenfolge" und „official_alerts")'
		).toBeVisible({ timeout: 10_000 });
		await expect(
			panel.locator('[data-testid="compare-layout-hourly-enabled-toggle"]').first()
		).toBeVisible({ timeout: 10_000 });

		const puts = collectPresetPuts(page, id);
		const toggle = hourlyBlock
			.locator('[data-testid="compare-layout-hourly-metric-thunder_level"] input')
			.first();
		await expect(toggle).toBeVisible({ timeout: 10_000 });
		const before = await toggle.isChecked();
		await toggle.click();
		await expect(toggle).toBeChecked({ checked: !before });

		// Nachweis 1 — es wurde WIRKLICH gespeichert, nicht nur umgeschaltet.
		// Genau hier bricht ein Umzug ohne den Bubble-Wrapper: stumm kein PUT.
		await expect
			.poll(() => puts.length, {
				message:
					'AC-2: nach der Bedienung muss ein Speichervorgang (PUT) feuern — beim Umzug ' +
					'muss der Bubble-Wrapper (.hub-layout-hourly-wrap) mitwandern',
				timeout: 10_000
			})
			.toBeGreaterThan(0);

		const lastPut = puts[puts.length - 1].postDataJSON() as {
			display_config?: { hourly_metrics?: string[] };
		};
		expect(
			lastPut.display_config?.hourly_metrics,
			'AC-2: der PUT muss die neue Stundengrößen-Auswahl tragen'
		).toBeDefined();

		// Nachweis 2 — der Server hat sie behalten und der Editor zeigt sie nach
		// einem echten Reload weiterhin.
		await expect
			.poll(
				async () => {
					const dc = ((await readPreset(page, id)).display_config ?? {}) as {
						hourly_metrics?: string[];
					};
					return (dc.hourly_metrics ?? []).includes('thunder_level');
				},
				{
					message: 'AC-2: die Auswahl muss serverseitig persistent sein',
					timeout: 10_000
				}
			)
			.toBe(!before);

		const reloaded = await openHubMetricsTab(page, id);
		await expect(
			reloaded
				.locator('[data-testid="compare-layout-hourly-metric-thunder_level"] input')
				.first()
		).toBeChecked({ checked: !before, timeout: 10_000 });
	});

	// ── AC-4 ──────────────────────────────────────────────────────────────────
	test('AC-4: keine Fläche behauptet mehr eine Kappung der Orte je Kanal', async ({ page }) => {
		const id = await makePreset(page);
		await openHub(page, id);

		const collected: string[] = [];
		for (const tab of ['uebersicht', 'orte', 'wetter-metriken', 'idealwerte', 'alarme', 'versand']) {
			await page.locator(`[data-testid="compare-detail-tab-${tab}"]:visible`).first().click();
			const panel = page.locator(`[data-testid="compare-detail-panel-${tab}"]:visible`).first();
			await expect(panel).toBeVisible({ timeout: 10_000 });
			collected.push(await panel.innerText());
		}
		const allText = collected.join('\n---\n');

		for (const claim of FORBIDDEN_CLAIMS) {
			expect(
				allText,
				`AC-4: der Editor behauptet weiterhin eine Orts-Kappung je Kanal (${claim}). ` +
					'Belegte Renderer-Regel: alle drei Kanäle geben ALLE Orte aus.'
			).not.toMatch(claim);
		}
	});

	// ── AC-5 ──────────────────────────────────────────────────────────────────
	test('AC-5: gespeichertes Zeitfenster überlebt eine Änderung im neuen Aufbau', async ({
		page
	}) => {
		const id = await makePreset(page, { hourFrom: 10, hourTo: 14 });

		// Vorbedingung: der Server hat die Werte wirklich übernommen — sonst
		// prüft der Test unten gegen Defaults und wäre wertlos.
		const before = await readPreset(page, id);
		expect(before.hour_from, 'Vorbedingung: hour_from=10 angelegt').toBe(10);
		expect(before.hour_to, 'Vorbedingung: hour_to=14 angelegt').toBe(14);

		const panel = await openHubMetricsTab(page, id);
		const puts = collectPresetPuts(page, id);
		const toggle = panel
			.locator('[data-testid="compare-layout-hourly-metric-uv_index"] input')
			.first();
		await expect(toggle).toBeVisible({ timeout: 10_000 });
		await toggle.click();
		await expect.poll(() => puts.length, { timeout: 10_000 }).toBeGreaterThan(0);

		const after = await readPreset(page, id);
		expect(
			after.hour_from,
			'AC-5: hour_from muss den Speichervorgang bitgleich überleben — der Go-Handler ' +
				'hat für dieses Feld KEINEN Read-Modify-Write-Schutz (#1268 F003), fehlt es im ' +
				'PUT-Body wird still 0 geschrieben'
		).toBe(10);
		expect(after.hour_to, 'AC-5: hour_to muss bitgleich überleben').toBe(14);
	});

	// ── AC-6 ──────────────────────────────────────────────────────────────────
	test('AC-6: die Anlege-Seite hat den Stundenverlauf an derselben Stelle', async ({ page }) => {
		const locA = await createTestLocation(page.request, { lat: 47.6, lon: 11.6 });
		const locB = await createTestLocation(page.request, { lat: 47.7, lon: 11.7 });

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await expect(page.locator('[data-testid="compare-editor"]:visible').first()).toBeVisible({
			timeout: 15_000
		});

		// Reiter der Anlege-Seite: kein „Layout" mehr.
		const newTabLabels = (
			await page.locator('[data-testid^="compare-editor-tab-"]:visible').allInnerTexts()
		)
			.map((t) => t.split('\n')[0].trim())
			.filter((t) => t.length > 0);
		expect(newTabLabels, 'AC-6: Reiter der Anlege-Seite ohne „Layout"').toEqual(
			EXPECTED_NEW_TABS
		);
		await expect(page.locator('[data-testid="compare-editor-tab-layout"]')).toHaveCount(0);

		const vergleichName = `Layout-Auflösung neu ${Date.now()}`;
		await page.locator('[data-testid="compare-editor-name"]:visible').first().fill(vergleichName);

		await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();
		const lib = page.locator('[data-testid="compare-step2-library"]:visible').first();
		await lib.waitFor({ timeout: 10_000 });
		for (const n of [locA.name, locB.name]) {
			await lib.getByText(n, { exact: true }).click();
		}

		// Stundenverlauf liegt jetzt im Reiter Wetter-Metriken — wie im Hub.
		await page.locator('[data-testid="compare-editor-tab-metriken"]:visible').first().click();
		const hourly = page.locator('[data-testid="compare-layout-hourly-metrics"]:visible').first();
		await expect(
			hourly,
			'AC-6: die Stundenverlauf-Steuerung muss auf der Anlege-Seite im Reiter ' +
				'Wetter-Metriken liegen — identisch zur Bearbeitung'
		).toBeVisible({ timeout: 10_000 });

		// Staging-Verifikation 2026-07-25: NICHT 'thunder_level' verwenden -- diese
		// Groesse ist auf der Anlege-Seite bereits vorausgewaehlt (Default-Liste in
		// compareHourlyMetricDefs.ts, #1335 Scheibe 1/F002 -- bewusst kein
		// defaultOff). Ein Klick schaltet sie AB, der Test erwartete AN und wurde
		// dadurch reproduzierbar falsch-rot. 'wind_dir_deg' ist der einzige
		// defaultOff-Eintrag und startet garantiert abgewaehlt.
		const newToggle = hourly
			.locator('[data-testid="compare-layout-hourly-metric-wind_dir_deg"] input')
			.first();
		await expect(newToggle).toBeVisible({ timeout: 10_000 });
		await newToggle.click();

		await page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-alarme"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-versand"]:visible').first().click();

		const [response] = await Promise.all([
			page.waitForResponse(
				(res) => res.url().includes('/api/compare/presets') && res.request().method() === 'POST'
			),
			page.locator('[data-testid="compare-editor-activate"]:visible').first().click()
		]);
		const created = (await response.json()) as { id: string };
		// #1329 Maßnahme B: der über die Oberfläche angelegte Vergleich muss
		// ebenfalls in die Staging-Bereinigung (sonst garantierter Leak).
		registerForCleanup('preset', created.id);

		const preset = await readPreset(page, created.id);
		const dc = (preset.display_config ?? {}) as { hourly_metrics?: string[]; top_n?: number };
		expect(
			dc.hourly_metrics,
			'AC-6: die im Anlegen getroffene Stundengrößen-Auswahl muss im neuen Vergleich stehen'
		).toBeDefined();
		expect(dc.hourly_metrics, 'AC-6: die umgeschaltete Stundengröße ist enthalten').toContain(
			'wind_dir_deg'
		);
		// Issue #1360 AC-8, Restpunkt F002: top_n stammt aus dem abgeschafften
		// Layout-Reiter und darf am Anlege-Pfad nicht wieder auftauchen — sonst
		// unterläuft die Neuanlage die Datenbereinigung (migrate_1360_drop_compare_top_n.py)
		// dauerhaft.
		expect(
			dc.top_n,
			'Issue #1360 F002: über /compare/new angelegter Vergleich darf KEIN display_config.top_n ' +
				'tragen — der Layout-Reiter-Rückbau würde sonst am Anlege-Pfad wieder unterlaufen'
		).toBeUndefined();
	});
});

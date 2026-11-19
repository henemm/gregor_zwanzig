// gz-eigenstaendig: Stundenverlauf-Steuerung existiert nur im Ortsvergleich (COMPARE_ONLY_SECTIONS in weatherMetricsTabSections.ts, #2346 S3: beim Trip ist die Mail-Haupttabelle selbst die Stundentabelle); zusaetzlich Anlege-Seite /compare/new des Alt-Editors
// E2E (Staging) — Reihenfolge der Stundenverlauf-Metriken im Ortsvergleich,
// Issue #1361 Befund 4/5 (S1-Rest von Epic #1372).
//
// Spec: Auftrag "S1-Rest #1361 umsetzen" (kein eigenes Spec-Dokument -- direkte
// Team-Lead-Vorgabe, siehe AC-1..AC-5 dort).
//
// Warum Live-Schicht: analog hub-metrik-reihenfolge-ziehen.spec.ts (#1359) — eine
// Ziehgeste im DnD-Zonen-Widget lässt sich nicht sinnvoll ohne echten Browser
// nachweisen, UND der eigentliche Beweis ist der PUT, nicht die Bildschirm-
// Optik (Fallstrick 1 aus dem Auftrag): der Hub speichert über Event-Bubbling
// am Wrapper `.hub-layout-hourly-wrap` (CompareTabs.svelte) — eine Ziehgeste
// löst `click`/`change` am Wrapper oft NICHT zuverlässig aus. Deshalb ruft
// `handleHourlyDndReorder` in CompareHourlyLayoutControls.svelte den direkten
// `onHourlyCommit`-Callback (analog `onCompareCommit`, #1359) — dieser Test
// beweist, dass dieser Callback tatsächlich beim Hub UND bei der Anlege-Seite
// ankommt (PUT-Zähler > 0), nicht nur, dass sich die Liste optisch verschiebt.
//
// AC-3 → Hub (seit #3154 Karte „Was steht wo“, AC-1/AC-2 gestrichen, s. unten). AC-4 → Anlege-Seite (`/compare/new`). AC-5 (keine
// Regression der An/Aus-Auswahl) ist bereits durch
// hub-wetter-metriken-speichert-selbst.spec.ts MS-2 + compare-stundenverlauf-wertprops.spec.ts
// abgedeckt (Toggle + PUT; vormals compare-layout-tab-dissolution AC-2, #2347 S4) — hier
// nur eine Gegenprobe, dass Ziehen UND Toggle nebeneinander funktionieren.
//
// AC-3 KORRIGIERT (Team-Lead-Gegencheck): KEINE Schnittlinie, da der
// Stundenverlauf laut Backend ausschließlich in der E-Mail erscheint
// (`hourly_metrics` geht nur an `render_compare_email`, comparison.py:230-242;
// `render_compare_telegram`, :360, hat keinen Stundendaten-Bezug; SMS hat
// `max_table_cols: 0`). Eine Telegram-Kappungslinie wäre eine Falschaussage —
// exakt die mit #1360 AC-4 beseitigte Fehlerklasse. Getestet wird stattdessen:
// Linie fehlt, der wahre Hinweis "nur E-Mail" ist da, keine der in
// compare-layout-tab-dissolution.spec.ts (FORBIDDEN_CLAIMS) verbotenen
// Kappungs-Formulierungen taucht auf.
//
// ── Ausführen (gegen STAGING, aus frontend/, NACH Push + Staging-Deploy) ────
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.compare-hourly-metric-order.staging.config.ts
//
// Config `frontend/playwright.compare-hourly-metric-order.staging.config.ts`
// liegt daneben (1:1 nach playwright.compare-layout-tab-dissolution.staging.config.ts).
// Anmeldung über gespeicherten Sitzungszustand (storageState), NICHT per
// Test-Login (Token-Bucket 30/h, reference_staging_e2e_storagestate_login_rate_limit).
// Testids `wm2-reihenfolge-row` kommen im Reiter Wetter-Metriken ZWEIMAL vor
// (Übersichts-Reihenfolge #1359 UND Stundenverlauf-Reihenfolge hier) — deshalb
// überall auf den Container `weather-metrics-stundenverlauf` scopen, NICHT
// pauschal `:visible` (beide Blöcke sind gleichzeitig sichtbar).

import { test, expect, type Page } from '@playwright/test';
// `dragDndZoneItem` ist seit #1771 S1 geteilt (war hier lokal kopiert) und
// wartet auf das echte `finalize`-Ereignis statt auf eine feste Frist.
import { createTestLocation, dragDndZoneItem } from './helpers';
import { oeffneKarte } from './was-steht-wo.helpers';

let createdPresetIds: string[] = [];
let createdLocationIds: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of createdPresetIds) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdPresetIds = [];
	for (const id of createdLocationIds) {
		try {
			await page.request.delete(`/api/locations/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdLocationIds = [];
});

// Drei Stundengrößen (Frontend-Vokabular aus compareHourlyMetricDefs.ts) —
// bewusst OHNE 'wind_dir_deg' (Merge-only, nie Teil der sortierbaren Liste,
// s. orderableHourlyMetricKeys).
const START_ORDER = ['temp_c', 'wind_kmh', 'uv_index'];

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const loc = await createTestLocation(page.request, { name, lat, lon });
	createdLocationIds.push(loc.id);
	return loc.id;
}

async function createPreset(page: Page, name: string, locationIds: string[]): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			display_config: { hourly_metrics: [...START_ORDER], active_metrics: ['temp_max_c', 'wind_max_kmh', 'sunny_hours_h'] }
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	createdPresetIds.push(body.id);
	return body.id as string;
}

test.describe('Issue #1361 Befund 4/5: Reihenfolge des Stundenverlaufs im Ortsvergleich', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14): im Hub gibt es keine eigene
	// Stundenverlauf-Liste mehr. AC-1/AC-2 (Ziehen im Hub speichert die Stundenverlauf-Reihenfolge) sind
	// gestrichen — es gibt EINE Reihenfolge fuer alle Stellen der Karte „Was steht wo“, Ersatz:
	// was-steht-wo-karte.spec.ts WS-2 (Tastatur und Maus, drei Faelle inkl. Orte, Neuladen). AC-3 laeuft an der
	// Karte: die Spalte und der Schalter „Stundenverlauf“ behaupten keine Kanal-Kappung, nur „nur in der E-Mail“.
	const FORBIDDEN_CHANNEL_CLAIMS: RegExp[] = [
		/Telegram\s*·\s*max\s*\d+/i,
		/kappt\s+je\s+Kanal/i,
		/Spalten\s+pro\s+Kanal/i,
		/Übersicht\s+pro\s+Kanal/i,
		/max\.?\s*\d+\s*(Orte|Spalten)/i
	];

	test('AC-3: der Stundenverlauf (Karte im Reiter Wetter) behauptet KEINE Kappung, sondern „nur in der E-Mail“', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1361 CutLine A ${suffix}`, 47.3, 11.3);
		const locB = await createLocation(page, `E2E 1361 CutLine B ${suffix}`, 47.4, 11.4);
		const id = await createPreset(page, `E2E 1361 CutLine ${suffix}`, [locA, locB]);

		const karte = await oeffneKarte(page, 'vergleich', id);
		await expect(karte.locator('[data-slot="et-kopf-stelle"][data-stelle="hourly"]'), 'Spalte Stundenverlauf fehlt').toHaveCount(1);
		await expect(karte, 'AC-3: sichtbarer, wahrer Hinweis, dass der Block nur die E-Mail betrifft').toContainText(/Stunden-Tabelle je Ort unter der Übersicht, nur in der E-Mail/);
		await expect(karte.locator('[data-testid="wm2-cut-line"]'), 'AC-3: keine Schnittlinie').toHaveCount(0);
		const text = await karte.innerText();
		for (const claim of FORBIDDEN_CHANNEL_CLAIMS) {
			expect(text, `AC-3: die Karte darf keine Kanal-Kappungs-Aussage behaupten (${claim})`).not.toMatch(claim);
		}
	});

	// ── AC-4: Anlege-Seite verhält sich identisch ──────────────────────────────
	test('AC-4: auf /compare/new sortiert sich der Stundenverlauf identisch, Reihenfolge landet im neuen Vergleich', async ({
		page
	}) => {
		const suffix = Date.now();
		// Test-Bug (Team-Lead-Fund): `createLocation()` liefert nur die ID
		// (Promise<string>) — für die Orte-Bibliothek wird hier aber der
		// ANZEIGENAME zum Anklicken gebraucht. Deshalb direkt `createTestLocation`
		// (liefert {id, name}), analog hub-anlegen-ablauf.spec.ts (anlegenPflicht, Orte aus der Bibliothek).
		const locA = await createTestLocation(page.request, {
			name: `E2E 1361 New A ${suffix}`,
			lat: 47.5,
			lon: 11.5
		});
		createdLocationIds.push(locA.id);
		const locB = await createTestLocation(page.request, {
			name: `E2E 1361 New B ${suffix}`,
			lat: 47.6,
			lon: 11.6
		});
		createdLocationIds.push(locB.id);

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await expect(page.locator('[data-testid="compare-editor"]:visible').first()).toBeVisible({
			timeout: 15_000
		});
		await page
			.locator('[data-testid="compare-editor-name"]:visible')
			.first()
			.fill(`E2E 1361 New ${suffix}`);

		await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();
		const lib = page.locator('[data-testid="compare-step2-library"]:visible').first();
		await lib.waitFor({ timeout: 10_000 });
		for (const n of [locA.name, locB.name]) {
			await lib.getByText(n, { exact: true }).click();
		}

		// Testfehler (Team-Lead-Fund, zweite Runde): `compare-detail-panel-
		// wetter-metriken` ist ein HUB-Testid (CompareTabs.svelte) — die
		// Anlege-Seite (CompareNewEditor.svelte) hat keinen solchen Panel-
		// Wrapper, sie rendert WeatherMetricsTab direkt im `metriken`-Tab-
		// Zweig. Analog hub-anlegen-ablauf.spec.ts AN-12: direkt
		// auf der Seite scopen, nicht über einen nicht existierenden Panel-Testid.
		// #2794 S3a: Wetter besuchen schaltet Zustellung frei; der Stundenverlauf steht im Schritt Zustellung.
		await page.locator('[data-testid="compare-editor-tab-wetter"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-zustellung"]:visible').first().click();
		const hourly = page.locator('[data-testid="weather-metrics-stundenverlauf"]:visible').first();
		await expect(hourly).toBeVisible({ timeout: 10_000 });

		// Default-Auswahl der Anlege-Seite ist DEFAULT_HOURLY_METRIC_KEYS (9 ohne
		// wind_dir_deg) — die Reihenfolge-Liste ist also von Anfang an gefüllt.
		const rows = hourly.locator('[data-testid="wm2-reihenfolge-row"]');
		await expect(rows).toHaveCount(9, { timeout: 10_000 });

		const before = await rows.evaluateAll((els) => els.map((el) => el.getAttribute('data-metric-id')));
		const first = before[0]!;
		const second = before[1]!;
		const source = hourly.locator(`[data-testid="wm2-reihenfolge-row"][data-metric-id="${first}"]`);
		const target = hourly.locator(`[data-testid="wm2-reihenfolge-row"][data-metric-id="${second}"]`);
		await dragDndZoneItem(page, source, target);

		const expectedOrder = [second, first, ...before.slice(2)];
		await expect
			.poll(
				async () => rows.evaluateAll((els) => els.map((el) => el.getAttribute('data-metric-id'))),
				{ message: 'AC-4: die Ziehgeste muss auf der Anlege-Seite identisch wirken', timeout: 5_000 }
			)
			.toEqual(expectedOrder);
		// Fund (reproduzierbare Flake-Analyse, 3/3 Läufe ohne diese Wartezeit
		// scheiterten am fehlenden `hourly_metrics` im POST-Body): der DOM-Beweis
		// oben (Zeilen zeigen die neue Reihenfolge) kann bereits aus dem
		// `consider`-Event von svelte-dnd-action stammen (Live-Vorschau während
		// der Ziehgeste) — der eigentliche State-Schreibvorgang passiert erst in
		// `handleDndFinalize` -> `onDndReorder` -> `wiz.hourlyMetricKeys = ...`
		// (SortableList.svelte), zeitlich gekoppelt an `flipDurationMs` (200ms,
		// SortableList.svelte:46). Die drei schnellen Tab-Klicks direkt danach
		// (idealwerte/alarme/versand) liefen ohne Wartezeit manchmal schneller ab
		// als dieser Commit — die Anlege-Seite (anders als der Hub, s. AC-1/AC-2)
		// hat keinen sofortigen Speicher-Commit nach dem Drag, sondern liest
		// `wiz.hourlyMetricKeys` erst ganz am Ende bei „Aktivieren". Wartezeit >
		// flipDurationMs schafft hier Verlässlichkeit; 7/7 Läufe seither grün.
		await page.waitForTimeout(400);

		// #2794 S3a: Reiterwechsel Wetter → Zustellung (letzter Schritt) vor dem Aktivieren.
		await page.locator('[data-testid="compare-editor-tab-wetter"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-zustellung"]:visible').first().click();

		const [response] = await Promise.all([
			page.waitForResponse(
				(res) => res.url().includes('/api/compare/presets') && res.request().method() === 'POST'
			),
			page.locator('[data-testid="compare-editor-activate"]:visible').first().click()
		]);
		const created = (await response.json()) as { id: string; display_config?: { hourly_metrics?: string[] } };
		createdPresetIds.push(created.id);

		// Primärnachweis: der POST-Response-Body IST das gerade gespeicherte
		// Preset (Go-Handler antwortet synchron NACH dem Schreiben, s.
		// CreateComparePresetHandler compare_preset.go:253-257) — kein
		// Nachlade-Risiko, da hier keine zweite Anfrage nötig ist.
		expect(
			created.display_config?.hourly_metrics,
			'AC-4: die POST-Antwort beim Anlegen muss bereits die gezogene Reihenfolge tragen'
		).toEqual(expectedOrder);

		// Gegenprobe: ein separater GET direkt danach muss dieselbe Reihenfolge
		// liefern. Beobachtung (2 von 5 Staging-Läufen): ein SOFORTIGER GET
		// direkt nach der POST-Antwort lieferte einmalig `hourly_metrics:
		// undefined`, obwohl die POST-Antwort selbst bereits korrekt war — auf
		// Polling gehärtet, um reinen Übernahme-Zeitversatz von einem echten
		// Persistenz-Fehler zu unterscheiden (an Team-Lead gemeldet, nicht in
		// eigener Verantwortung "stillschweigend" weich gemacht).
		await expect
			.poll(
				async () => {
					const readRes = await page.request.get(`/api/compare/presets/${created.id}`);
					const dc = ((await readRes.json()).display_config ?? {}) as { hourly_metrics?: string[] };
					return dc.hourly_metrics;
				},
				{
					message: 'AC-4: ein GET direkt nach dem Anlegen muss dieselbe Reihenfolge liefern wie die POST-Antwort',
					timeout: 8_000
				}
			)
			.toEqual(expectedOrder);
	});
});

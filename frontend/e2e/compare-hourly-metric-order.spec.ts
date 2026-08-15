// E2E (Staging) — Reihenfolge der Stundenverlauf-Metriken im Ortsvergleich,
// Issue #1361 Befund 4/5 (S1-Rest von Epic #1372).
//
// Spec: Auftrag "S1-Rest #1361 umsetzen" (kein eigenes Spec-Dokument -- direkte
// Team-Lead-Vorgabe, siehe AC-1..AC-5 dort).
//
// Warum Live-Schicht: analog compare-metric-order.spec.ts (#1359) — eine
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
// AC-1/AC-2/AC-3 → Hub. AC-4 → Anlege-Seite (`/compare/new`). AC-5 (keine
// Regression der An/Aus-Auswahl) ist bereits durch
// compare-layout-tab-dissolution.spec.ts AC-2 abgedeckt (Toggle + PUT) — hier
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
// liegt daneben (1:1 nach playwright.compare-metric-order.staging.config.ts).
// Anmeldung über gespeicherten Sitzungszustand (storageState), NICHT per
// Test-Login (Token-Bucket 30/h, reference_staging_e2e_storagestate_login_rate_limit).
// Testids `wm2-reihenfolge-row` kommen im Reiter Wetter-Metriken ZWEIMAL vor
// (Übersichts-Reihenfolge #1359 UND Stundenverlauf-Reihenfolge hier) — deshalb
// überall auf den Container `weather-metrics-stundenverlauf` scopen, NICHT
// pauschal `:visible` (beide Blöcke sind gleichzeitig sichtbar).

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
// `dragDndZoneItem` ist seit #1771 S1 geteilt (war hier lokal kopiert) und
// wartet auf das echte `finalize`-Ereignis statt auf eine feste Frist.
import { createTestLocation, dragDndZoneItem } from './helpers';

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
			display_config: { hourly_metrics: [...START_ORDER] }
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	createdPresetIds.push(body.id);
	return body.id as string;
}

/**
 * Vorbereitungs-Update AUSSERHALB der UI (z.B. um vor einem Test einen
 * bestimmten Ausgangszustand zu setzen). Team-Lead-Fund: ein PUT mit NUR
 * `display_config` wird vom Go-Handler mit HTTP 400 abgewiesen
 * (`validateComparePreset`, compare_preset.go:109-138 — verlangt u.a. `name`,
 * `schedule`, `forecast_hours`, `hour_from`/`hour_to`). Deshalb hier erst der
 * aktuelle Preset-Stand per GET geholt und die volle Struktur zurückgesendet
 * (display_config gemergt) — UND der Rückgabewert geprüft, damit ein
 * fehlgeschlagenes Vorbereiten nicht als inhaltliches Test-Scheitern maskiert
 * wird (genau das ist beim ursprünglichen rohen PUT passiert).
 */
async function updatePresetDisplayConfig(
	page: Page,
	id: string,
	displayConfigPatch: Record<string, unknown>
): Promise<void> {
	const getRes = await page.request.get(`/api/compare/presets/${id}`);
	expect(getRes.ok(), `Vorbereitung: GET Preset fehlgeschlagen: HTTP ${getRes.status()}`).toBeTruthy();
	const preset = await getRes.json();
	const putRes = await page.request.put(`/api/compare/presets/${id}`, {
		data: {
			...preset,
			display_config: { ...(preset.display_config ?? {}), ...displayConfigPatch }
		}
	});
	expect(
		putRes.ok(),
		`Vorbereitung: PUT fehlgeschlagen: HTTP ${putRes.status()} — ${await putRes.text()}`
	).toBeTruthy();
}

/** Zeichnet jeden PUT auf diesen Vergleich auf (Speicher-Nachweis). */
function collectPresetPuts(page: Page, id: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(`/api/compare/presets/${id}`)) {
			puts.push(req);
		}
	});
	return puts;
}

/** Öffnet den Vergleich am Hub und wechselt per Klick auf den Metriken-Tab. */
async function openHubMetricsTab(page: Page, id: string): Promise<Locator> {
	await page.goto(`/compare/${id}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15_000 });
	// SvelteKit-Hydration-Race (#1359): die Tab-Leiste ist server-gerendert VOR
	// der Hydration — ein zu früher Klick geht spurlos verloren.
	await page.waitForLoadState('networkidle');
	await page.getByTestId('compare-detail-tab-wetter-metriken').click();
	const panel = page.getByTestId('compare-detail-panel-wetter-metriken');
	await expect(panel).toBeVisible({ timeout: 10_000 });
	// Issue #1719 S3 (Adversary-Fund F001): "Aus ist ein Zustand" (ADR-0050
	// Regel 4) gilt NUR für den Trip-Kanal-Reiter — weder die Übersichts- noch
	// die Stundenverlauf-Einbettung von WeatherV2Reihenfolge im Ortsvergleich
	// bekommen `offColumns` durchgereicht. Eine Aus-Gruppe darf hier nie
	// entstehen.
	await expect(
		panel.getByTestId('wm2-aus-gruppe'),
		'AC-13 FAIL: eine "Aus in diesem Kanal"-Gruppe darf im Ortsvergleich nicht entstehen'
	).toHaveCount(0);
	return panel;
}

/** Der Stundenverlauf-Container innerhalb des Wetter-Metriken-Panels — grenzt
 *  gegen die Übersichts-Reihenfolge (#1359) ab, die im selben Panel liegt. */
function hourlyBlock(panel: Locator): Locator {
	return panel.locator('[data-testid="weather-metrics-stundenverlauf"]');
}

function hourlyReihenfolgeRows(panel: Locator): Locator {
	return hourlyBlock(panel).locator('[data-testid="wm2-reihenfolge-row"]');
}

async function hourlyOrderInEditor(panel: Locator): Promise<(string | null)[]> {
	return hourlyReihenfolgeRows(panel).evaluateAll((els) =>
		els.map((el) => el.getAttribute('data-metric-id'))
	);
}

test.describe('Issue #1361 Befund 4/5: Reihenfolge des Stundenverlaufs im Ortsvergleich', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1/AC-2: Ziehen im Hub speichert die Reihenfolge und wirkt sich auf ──
	// die Renderer-Reihenfolge aus (AC-2 hier: Speicher-Nachweis; die
	// tatsächliche Spalten-Reihenfolge in der Mail ist Kern-Schicht-getestet,
	// _visible_hour_metrics in compare_html.py folgt display_config.hourly_metrics).
	test('AC-1/AC-2: Stundengröße ziehen speichert die Reihenfolge und überlebt den Reload', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1361 Hourly A ${suffix}`, 47.0, 11.0);
		const locB = await createLocation(page, `E2E 1361 Hourly B ${suffix}`, 47.1, 11.1);
		const locC = await createLocation(page, `E2E 1361 Hourly C ${suffix}`, 47.2, 11.2);
		const id = await createPreset(page, `E2E 1361 Hourly ${suffix}`, [locA, locB, locC]);

		const panel = await openHubMetricsTab(page, id);

		await expect(hourlyReihenfolgeRows(panel)).toHaveCount(START_ORDER.length, { timeout: 10_000 });
		expect(await hourlyOrderInEditor(panel)).toEqual(START_ORDER);

		const puts = collectPresetPuts(page, id);
		const source = hourlyBlock(panel).locator(
			'[data-testid="wm2-reihenfolge-row"][data-metric-id="uv_index"]'
		);
		const target = hourlyBlock(panel).locator(
			'[data-testid="wm2-reihenfolge-row"][data-metric-id="temp_c"]'
		);

		const expectedOrder = ['uv_index', 'temp_c', 'wind_kmh'];

		// Team-Lead-Fund (Flake, reproduzierbar): der sichtbare DOM-Zustand nach
		// der Ziehgeste kann bereits aus `consider` (Live-Vorschau während des
		// Drags) stammen -- VOR dem eigentlichen State-Commit in `finalize`
		// (SortableList.svelte). Anders als auf der Anlege-Seite (AC-4, feste
		// Wartezeit, dort gibt es kein beobachtbares Signal) hat der Hub eins:
		// den PUT selbst (`onHourlyCommit` -> `handleLayoutCommit`, synchron aus
		// `handleDndFinalize` ausgeloest). Der Test haengt deshalb kausal an
		// `page.waitForResponse()` auf genau diesen PUT -- gekoppelt per
		// `Promise.all` an die Ziehgeste selbst, nicht an eine geratene Dauer
		// oder eine reine DOM-Umsortierungs-Pruefung danach.
		const [putResponse] = await Promise.all([
			page.waitForResponse(
				(res) =>
					res.request().method() === 'PUT' &&
					res.url().includes(`/api/compare/presets/${id}`),
				{ timeout: 10_000 }
			),
			dragDndZoneItem(page, source, target)
		]);

		// Nachweis 1 (Fallstrick 1 aus dem Auftrag): es wurde WIRKLICH
		// gespeichert — der Wrapper-Bubble-Handler ist bei einer Ziehgeste kein
		// verlässlicher Speicherweg. `waitForResponse` oben ist bereits der
		// kausale Beweis (kein DOM-Umsortieren allein); die folgende Prüfung
		// verifiziert zusätzlich den INHALT dieses PUT.
		const putBody = putResponse.request().postDataJSON() as {
			display_config?: { hourly_metrics?: string[] };
		};
		expect(
			putBody.display_config?.hourly_metrics,
			'AC-2: der PUT muss die neue Stundenverlauf-Reihenfolge tragen'
		).toEqual(expectedOrder);
		expect(puts.length, 'AC-2: genau der erwartete PUT wurde erfasst').toBeGreaterThan(0);

		// Jetzt, NACH dem bestätigten PUT, muss auch das DOM die neue Position
		// zeigen (kein Wettlauf mehr — der Commit ist bereits durch).
		expect(await hourlyOrderInEditor(panel)).toEqual(expectedOrder);

		// Nachweis 2 — Server behält sie, und der Editor zeigt sie nach echtem Reload.
		await expect
			.poll(
				async () => {
					const r = await page.request.get(`/api/compare/presets/${id}`);
					return ((await r.json()).display_config ?? {}).hourly_metrics as string[];
				},
				{ message: 'AC-1: die Reihenfolge muss serverseitig persistent sein', timeout: 8_000 }
			)
			.toEqual(expectedOrder);

		const reloadedPanel = await openHubMetricsTab(page, id);
		await expect
			.poll(async () => hourlyOrderInEditor(reloadedPanel), {
				message: 'AC-1: nach dem Neuladen muss die gezogene Reihenfolge noch da sein',
				timeout: 10_000
			})
			.toEqual(expectedOrder);
	});

	// ── AC-3 (korrigiert, s. Team-Lead-Gegencheck): KEINE Schnittlinie ────────
	// Ursprüngliche Annahme war fachlich falsch: `hourly_metrics` geht laut
	// Backend ausschließlich an `render_compare_email` (comparison.py:230-242).
	// `render_compare_telegram` (comparison.py:360) kennt keinerlei
	// Stundendaten, SMS hat `max_table_cols: 0` — der Stundenverlauf existiert
	// nur in der E-Mail. Eine "ab hier von Telegram gekappt"-Linie wäre also
	// eine Falschaussage — exakt die Fehlerklasse, die #1360 AC-4 beseitigt hat
	// (keine Fläche behauptet mehr eine Kappung je Kanal). Verbotene Aussagen
	// 1:1 aus compare-layout-tab-dissolution.spec.ts FORBIDDEN_CLAIMS.
	const FORBIDDEN_CHANNEL_CLAIMS: RegExp[] = [
		/Telegram\s*·\s*max\s*\d+/i,
		/kappt\s+je\s+Kanal/i,
		/Spalten\s+pro\s+Kanal/i,
		/Übersicht\s+pro\s+Kanal/i,
		/max\.?\s*\d+\s*(Orte|Spalten)/i
	];

	test('AC-3: die Stundenverlauf-Liste zeigt KEINE Kappungs-Linie, sondern den Hinweis "nur E-Mail"', async ({
		page
	}) => {
		// Alle 9 sortierbaren Stundengrößen auswählen (ohne wind_dir_deg) — auch
		// mit mehr als 8 Einträgen darf keine Schnittlinie erscheinen, da die
		// Telegram-8er-Grenze für den Stundenverlauf gar nicht gilt.
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1361 CutLine A ${suffix}`, 47.3, 11.3);
		const locB = await createLocation(page, `E2E 1361 CutLine B ${suffix}`, 47.4, 11.4);
		const id = await createPreset(page, `E2E 1361 CutLine ${suffix}`, [locA, locB]);
		// Alle 9 orderable Keys nachtragen (Preset startete mit START_ORDER = 3).
		const allNine = ['temp_c', 'wind_chill_c', 'wind_kmh', 'gust_kmh', 'precip_mm', 'uv_index', 'thunder_level', 'pop_pct', 'visibility_m'];
		await updatePresetDisplayConfig(page, id, { hourly_metrics: allNine });

		const panel = await openHubMetricsTab(page, id);
		await expect(hourlyReihenfolgeRows(panel)).toHaveCount(allNine.length, { timeout: 10_000 });

		await expect(
			hourlyBlock(panel).locator('[data-testid="wm2-cut-line"]'),
			'AC-3: KEINE Schnittlinie beim Stundenverlauf — er erscheint ausschließlich in der ' +
				'E-Mail, eine Telegram-Kappungslinie wäre eine Falschaussage (comparison.py:230-242 ' +
				'vs. :360)'
		).toHaveCount(0);

		await expect(
			hourlyBlock(panel).getByTestId('compare-layout-hourly-email-only-hint'),
			'AC-3: sichtbarer, wahrer Hinweis, dass der Block nur die E-Mail betrifft'
		).toContainText(/nur.*E-Mail/i, { timeout: 10_000 });

		const panelText = await panel.innerText();
		for (const claim of FORBIDDEN_CHANNEL_CLAIMS) {
			expect(
				panelText,
				`AC-3: der Stundenverlauf-Block darf keine Kanal-Kappungs-Aussage behaupten (${claim}) — ` +
					'exakt die mit #1360 AC-4 beseitigte Fehlerklasse'
			).not.toMatch(claim);
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
		// (liefert {id, name}), analog compare-layout-tab-dissolution.spec.ts AC-6.
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
		// Zweig. Analog compare-layout-tab-dissolution.spec.ts AC-6: direkt
		// auf der Seite scopen, nicht über einen nicht existierenden Panel-Testid.
		await page.locator('[data-testid="compare-editor-tab-metriken"]:visible').first().click();
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

		await page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-alarme"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-versand"]:visible').first().click();

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

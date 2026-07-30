// E2E (Staging) — Issue #1373, S2 Scheibe B: Speicherformat der Metrik-Auswahl
// eines Ortsvergleichs (`display_config.active_metrics`) ist Größe + Auswertung
// (`[{"metric_id":"temperature","aggregation":"max"}, …]`).
//
// Spec: docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md
//   AC-4  (umgestellte/alte Auswahl zeigt dieselben Größen)
//   AC-9  (Speichern schreibt nur noch das neue Format)
//   AC-12 (Speichern beschädigt die Auswahl nicht)
//
// WARUM DIESE DATEI EXISTIERT (Adversary-Runde 2, F001): die Verdrahtung im
// Component ist unter `node --test` nicht prüfbar — `.svelte`-Dateien sind dort
// nicht importierbar (test-lib-loader.mjs hat keinen Svelte-Transform), und die
// Kern-Tests in
// `src/lib/components/compare/__tests__/compareActiveMetricsStorageFormat.test.ts`
// prüfen deshalb ausdrücklich NUR die reinen Hilfsfunktionen. Der Nachweis der
// Reihenfolge „Katalogantwort abwarten → hydrieren → Grundzustand aufnehmen"
// (CompareTabs.svelte::hydrateWetterMetrikenTab) und des Rücksetzpfads bei
// fehlgeschlagenem PUT ist nur am echten Browser möglich — hier.
//
// Der entscheidende Diskriminator ist der PUT-ZÄHLER auf
// `/api/compare/presets/{id}`:
//   * Der Reiter-Wrapper `.hub-wetter-metriken-wrap` (CompareTabs.svelte)
//     ruft den Commit bei JEDEM `click`/`change`/`focusout` auf; geschrieben
//     wird nur, wenn `flushPendingWeatherMetricsSave` einen Unterschied zum
//     Grundzustand sieht.
//   * Enthielte der Grundzustand die unaufgelöste Rohform (der Bruch aus
//     Fix-Runde 1), erzeugte schon ein Klick, der NICHTS ändert, einen PUT
//     (Scheindiff) — und die Häkchen wären von Anfang an leer, weil
//     `includes(entry.metric)` Zeichenketten gegen Objekte vergleicht.
//
// Ausführen (gegen Staging, aus frontend/, NACH Push + Staging-Deploy):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.compare-active-metrics-format.staging.config.ts
//
// Login über gespeicherten Sitzungszustand (storageState), NICHT per Test —
// der Login ist auf 30/h gedeckelt
// (reference_staging_e2e_storagestate_login_rate_limit).
// Muster: compare-metric-order.spec.ts (PUT-Aufzeichnung, afterEach-Cleanup).

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
import { createTestLocation } from './helpers';

let createdIds: string[] = [];
let createdLocationIds: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of createdIds) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdIds = [];
	for (const id of createdLocationIds) {
		try {
			await page.request.delete(`/api/locations/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdLocationIds = [];
});

// Die drei Verifikationsanker der Spec: Höchst- UND Tiefsttemperatur teilen die
// Größe `temperature` und unterscheiden sich nur in der Auswertung — genau die
// Verschmelzungsfalle. Gespeichert im NEUEN Format (so sieht ein Vergleich nach
// dem Migrationslauf aus).
const STORED_NEW_FORMAT = [
	{ metric_id: 'temperature', aggregation: 'max' },
	{ metric_id: 'temperature', aggregation: 'min' },
	{ metric_id: 'wind_chill', aggregation: 'min' }
];
// Dieselbe Auswahl in der Auswahl-Schlüssel-Sprache der Oberfläche.
const EXPECTED_KEYS = ['temp_max_c', 'temp_min_c', 'wind_chill_min_c'];

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const loc = await createTestLocation(page.request, { name, lat, lon });
	createdLocationIds.push(loc.id);
	return loc.id;
}

/** Legt einen Vergleich an, dessen Metrik-Auswahl bereits im NEUEN Format
 *  gespeichert ist (Go reicht `display_config` untypisiert durch — genau wie
 *  nach `scripts/migrate_1373_compare_active_metrics_format.py`). */
async function createMigratedPreset(page: Page, name: string, locationIds: string[]): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'daily',
			profil: 'wandern',
			empfaenger: ['urlauber@example.com'],
			display_config: { active_metrics: STORED_NEW_FORMAT }
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	createdIds.push(body.id);

	// Vorbedingung hart prüfen: das Backend muss das NEUE Format wirklich
	// gespeichert haben — sonst prüfte der Test den Altformat-Pfad und wäre
	// wertlos.
	const stored = await page.request.get(`/api/compare/presets/${body.id}`);
	const storedJson = await stored.json();
	expect(
		storedJson.display_config?.active_metrics,
		'Vorbedingung: der Vergleich muss im neuen Speicherformat vorliegen'
	).toEqual(STORED_NEW_FORMAT);

	return body.id as string;
}

/** Zeichnet jeden PUT auf diesen Vergleich auf. */
function collectPresetPuts(page: Page, id: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(`/api/compare/presets/${id}`)) {
			puts.push(req);
		}
	});
	return puts;
}

/** Zählt die Abrufe des Metrik-Katalogs (geteilter Promise-Cache: EINE Anfrage
 *  pro Seiten-Load, auch wenn mehrere Reiter sie brauchen). */
function collectCatalogRequests(page: Page): Request[] {
	const reqs: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'GET' && req.url().includes('/api/compare/metrics')) reqs.push(req);
	});
	return reqs;
}

/** Öffnet den Vergleich am Hub und wechselt per KLICK auf den Metriken-Reiter. */
async function openMetricsTab(page: Page, id: string): Promise<Locator> {
	await page.goto(`/compare/${id}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15_000 });
	// SvelteKit liefert die Tab-Leiste server-gerendert VOR der Hydration aus —
	// ein zu früher Klick geht spurlos verloren (Muster aus
	// compare-metric-order.spec.ts).
	await page.waitForLoadState('networkidle');
	await page.getByTestId('compare-detail-tab-wetter-metriken').click();
	const panel = page.getByTestId('compare-detail-panel-wetter-metriken');
	await expect(panel).toBeVisible({ timeout: 10_000 });
	await expect(panel.getByTestId('weather-metrics-vergleich-list')).toBeVisible({ timeout: 15_000 });
	return panel;
}

/** Die tatsächlich ANGEHAKTEN Metriken der Grundauswahl — aus dem DOM-Zustand
 *  der Checkboxen, nicht aus einer Datenquelle (genau das, was der Nutzer
 *  sieht).
 *
 *  Issue #1411 (Epic #1372 S4b Scheibe 1): die Grundauswahl gruppiert seit
 *  dieser Lieferung nach `metric_id` — eine Zeile kann mehrere unabhängige
 *  Kästchen tragen (Temperatur, gefühlte Temperatur). Jedes Kästchen trägt
 *  `data-metric-key` mit dem echten Katalog-Schlüssel (z.B. `temp_max_c`),
 *  unabhängig davon, ob es das einzige Kästchen der Zeile ist oder eines von
 *  mehreren — der Helper liest deshalb direkt diese Kästchen statt den
 *  Zeilen-Test-ID zu parsen (der jetzt `metric_id` statt `key` trägt). */
async function checkedMetrics(panel: Locator): Promise<string[]> {
	return panel
		.locator('[data-testid^="weather-metrics-vergleich-row-"] input[type="checkbox"]')
		.evaluateAll((inputs) =>
			(inputs as HTMLInputElement[])
				.filter((el) => el.checked)
				.map((el) => el.getAttribute('data-metric-key') ?? '')
				.filter(Boolean)
		);
}

/** Zeile ueber die (seit #1411) `metric_id`-basierte Test-ID adressieren —
 *  fuer Groessen mit genau einer Auswertung (hier: `wind`) ist die ganze
 *  Zeile weiterhin klickbar (Label-wrapped Checkbox, unveraendertes Verhalten). */
function metricRow(panel: Locator, metricId: string): Locator {
	return panel.getByTestId(`weather-metrics-vergleich-row-${metricId}`);
}

test.describe('Issue #1373 S2 Scheibe B: umgestellte Metrik-Auswahl im Hub', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('AC-4/AC-9: Häkchen stimmen, ein Klick ohne Änderung schreibt NICHT, eine Änderung genau einmal', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-GZ-1373 A ${suffix}`, 47.0, 11.0);
		const locB = await createLocation(page, `E2E-GZ-1373 B ${suffix}`, 47.1, 11.1);
		const locC = await createLocation(page, `E2E-GZ-1373 C ${suffix}`, 47.2, 11.2);
		const id = await createMigratedPreset(page, `E2E-GZ-1373 Format ${suffix}`, [locA, locB, locC]);

		const catalogRequests = collectCatalogRequests(page);
		const puts = collectPresetPuts(page, id);
		const panel = await openMetricsTab(page, id);

		// (1) Die gespeicherte Auswahl ist SICHTBAR — nicht leer. Das ist der
		// Kern: bei unaufgelöster Rohform wäre hier nichts angehakt.
		await expect
			.poll(async () => (await checkedMetrics(panel)).sort(), {
				message:
					'AC-4: die im neuen Format gespeicherte Auswahl muss im Reiter angehakt sein — ' +
					'leere Häkchen bedeuten, dass die Hydration die Rohform nicht aufgelöst hat',
				timeout: 10_000
			})
			.toEqual([...EXPECTED_KEYS].sort());

		// (2) Ein Klick, der NICHTS ändert (auf den Hinweistext der Karte), läuft
		// durch denselben Wrapper-Commit — darf aber keinen PUT erzeugen.
		// Enthielte der Grundzustand die Rohform, entstünde hier ein Scheindiff-PUT.
		await panel.getByText('Nur angewählte Metriken erscheinen in der Vergleichs-Mail.').click();
		await page.waitForTimeout(1_500);
		expect(
			puts.length,
			'ohne echte Änderung darf kein Speichervorgang laufen (Scheindiff-Nachweis)'
		).toBe(0);

		// (3) EINE echte Geste: eine weitere Größe anhaken → genau EIN PUT, und
		// der Payload trägt die vollständige Auswahl im neuen Format.
		await metricRow(panel, 'wind').click();

		await expect
			.poll(() => puts.length, {
				message: 'eine Änderung MUSS genau einen Speichervorgang auslösen',
				timeout: 8_000
			})
			.toBe(1);
		await page.waitForTimeout(1_500);
		expect(puts.length, 'kein Nachschlag-PUT nach derselben Geste').toBe(1);

		const sent = puts[0].postDataJSON() as {
			display_config?: { active_metrics?: unknown[] };
		};
		expect(
			sent.display_config?.active_metrics,
			'AC-9: geschrieben wird ausschliesslich Groesse + Auswertung, in Auswahl-Reihenfolge'
		).toEqual([...STORED_NEW_FORMAT, { metric_id: 'wind', aggregation: 'max' }]);

		// (4) Serverseitig angekommen — und nach einem echten Reload weiterhin
		// vollständig angehakt (AC-12: nichts beschädigt, nichts verloren).
		await expect
			.poll(
				async () => {
					const r = await page.request.get(`/api/compare/presets/${id}`);
					return ((await r.json()).display_config ?? {}).active_metrics;
				},
				{ message: 'die Auswahl muss serverseitig im neuen Format persistent sein', timeout: 8_000 }
			)
			.toEqual([...STORED_NEW_FORMAT, { metric_id: 'wind', aggregation: 'max' }]);

		const reloaded = await openMetricsTab(page, id);
		await expect
			.poll(async () => (await checkedMetrics(reloaded)).sort(), {
				message: 'nach dem Neuladen muessen alle vier Groessen angehakt sein',
				timeout: 10_000
			})
			.toEqual([...EXPECTED_KEYS, 'wind_max_kmh'].sort());

		// Geteilter Katalog-Cache: pro Seiten-Load genau eine Katalog-Anfrage
		// (zwei Seiten-Loads in diesem Test → maximal zwei).
		expect(
			catalogRequests.length,
			'der Metrik-Katalog darf pro Seiten-Load nur EINMAL geholt werden'
		).toBeLessThanOrEqual(2);
	});

	test('Rücksetzpfad: nach fehlgeschlagenem Speichern stimmen die Häkchen weiterhin', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-GZ-1373 F A ${suffix}`, 46.0, 10.0);
		const locB = await createLocation(page, `E2E-GZ-1373 F B ${suffix}`, 46.1, 10.1);
		const locC = await createLocation(page, `E2E-GZ-1373 F C ${suffix}`, 46.2, 10.2);
		const id = await createMigratedPreset(page, `E2E-GZ-1373 Rollback ${suffix}`, [locA, locB, locC]);

		const panel = await openMetricsTab(page, id);
		await expect
			.poll(async () => (await checkedMetrics(panel)).sort(), { timeout: 10_000 })
			.toEqual([...EXPECTED_KEYS].sort());

		// Speichern serverseitig scheitern lassen (echtes Abfangen, keine
		// Testdaten-Manipulation): der Rücksetzpfad in CompareTabs setzt
		// `wizardState.activeMetricKeys` auf den Grundzustand zurück.
		await page.route(`**/api/compare/presets/${id}`, async (route) => {
			if (route.request().method() === 'PUT') {
				await route.fulfill({
					status: 500,
					contentType: 'application/json',
					body: JSON.stringify({ error: 'E2E: Speichern absichtlich fehlgeschlagen' })
				});
				return;
			}
			await route.continue();
		});

		await metricRow(panel, 'wind').click();
		// Fehlerhinweis abwarten, damit der Rücksetzpfad sicher gelaufen ist.
		await page.waitForTimeout(2_000);

		// DAS ist der Bruch aus Fix-Runde 1: hier standen danach die rohen
		// Objekte im Zustand, kein Häkchen passte mehr.
		await expect
			.poll(async () => (await checkedMetrics(panel)).sort(), {
				message:
					'nach fehlgeschlagenem Speichern muss die gespeicherte Auswahl weiterhin ' +
					'angehakt sein (Ruecksetzen darf nicht auf die Rohform zurueckfallen)',
				timeout: 8_000
			})
			.toEqual([...EXPECTED_KEYS].sort());

		// Serverseitig unverändert — der fehlgeschlagene PUT hat nichts geschrieben.
		const stored = await page.request.get(`/api/compare/presets/${id}`);
		expect(
			(await stored.json()).display_config?.active_metrics,
			'ein fehlgeschlagenes Speichern darf die gespeicherte Auswahl nicht veraendern'
		).toEqual(STORED_NEW_FORMAT);
	});

	test('verzögerte Katalogantwort: Reiterwechsel im Wartefenster beschädigt die Auswahl nicht', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-GZ-1373 D A ${suffix}`, 45.0, 9.0);
		const locB = await createLocation(page, `E2E-GZ-1373 D B ${suffix}`, 45.1, 9.1);
		const locC = await createLocation(page, `E2E-GZ-1373 D C ${suffix}`, 45.2, 9.2);
		const id = await createMigratedPreset(page, `E2E-GZ-1373 Delay ${suffix}`, [locA, locB, locC]);

		// Katalogantwort künstlich verzögern — genau das Fenster, in dem die
		// Hydration früher zu früh lief.
		await page.route('**/api/compare/metrics', async (route) => {
			await new Promise((resolve) => setTimeout(resolve, 3_000));
			await route.continue();
		});

		const catalogRequests = collectCatalogRequests(page);
		const puts = collectPresetPuts(page, id);

		await page.goto(`/compare/${id}`);
		await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 20_000 });
		await page.getByTestId('compare-detail-tab-wetter-metriken').click();

		// Im Wartefenster hin- und herwechseln (Idealwerte braucht denselben
		// Katalog) — es darf nichts geschrieben werden.
		await page.getByTestId('compare-detail-tab-idealwerte').click();
		await page.getByTestId('compare-detail-tab-wetter-metriken').click();
		expect(puts.length, 'im Wartefenster darf kein Speichervorgang laufen').toBe(0);

		// Nach Ankunft der Antwort ist die Auswahl vollständig angehakt.
		await expect(
			page.getByTestId('compare-detail-panel-wetter-metriken').getByTestId('weather-metrics-vergleich-list')
		).toBeVisible({ timeout: 20_000 });
		await expect
			.poll(async () => (await checkedMetrics(page.getByTestId('compare-detail-panel-wetter-metriken'))).sort(), {
				message: 'auch bei spaeter Katalogantwort muss die Auswahl angehakt erscheinen',
				timeout: 15_000
			})
			.toEqual([...EXPECTED_KEYS].sort());

		expect(puts.length, 'auch nach der Hydration kein PUT ohne Nutzergeste').toBe(0);
		expect(
			catalogRequests.length,
			'zwei Reiter, ein Seiten-Load: der Katalog darf nur EINMAL geholt werden'
		).toBe(1);
	});
});

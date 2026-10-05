// E2E — Bug #2454 Fix-Loop 2 (Adversary-Findings F001/F002/F004).
//
// Spec: docs/specs/bugfix/bug_2454_kurzform_gefuehlte_temperatur.md (AC-1/AC-2/AC-3).
//
// Der Adversary hat belegt: die Ableitungs-/Mitnahme-Logik selbst
// (deriveMissingChildMetrics/moveWithDerivedChildren/computeInitialBuckets/
// toggleGlobalMetric) ist solide unit-getestet, aber KEIN Test erreicht den
// echten Wirkort in WeatherMetricsTab.svelte (initFromTrip()/onToggleMetric()/
// onRestoreMetric()/onRemove()) — die Frontend-Unit-Harness ist SSR-only,
// `$effect`/Event-Handler laufen dort nie. Diese Spec schließt genau diese
// Lücke: sie bedient den echten Editor im Browser und prüft die tatsächlich
// gespeicherte PUT-Payload sowie den GET-Rücklese-Stand.
//
// Muster übernommen aus weather-metrics-tab-autosave.spec.ts (collectTripPuts,
// seedMetrics, wm2-grundauswahl-Toggle) + daywindow-schedule-control.spec.ts
// (createTrip mit `id`, openTripOverview/clickWeatherTab).
//
// Lokale Ausführung (Fix-Loop 2, 30.09.2026): isolierter Stack auf freien
// Ports (Go/Python/Vite-Preview), NICHT gegen Staging/Prod. Zwei Fallen des
// lokalen Stacks, die die Runde-2-Adversary-Sitzung noch mit 401 blockierten
// (dort ohne Log-Eintrag im isolierten Go-Server — beide Ursachen liegen
// VOR dem Go-Server, nicht darin):
// (1) `apiProxyTarget.ts` zeigt per Default auf Port 8091 (den echten,
// dauerhaft laufenden Staging-Go-Server) — Browser-`/api`-Traffic ging dort
// hin und wurde dort mangels passender Session abgewiesen.
// `GZ_E2E_API_PROXY_TARGET`/`GZ_API_BASE` auf den eigenen, isolierten Go-Port
// setzen. (2) eine lokale `.env` liefert dem Preview-Server ein FREMDES
// `GZ_SESSION_SECRET` — SvelteKit prüfte Cookies damit gegen ein anderes
// Secret, als der Go-Server zum Signieren benutzte. `GZ_REPO_ENV_FILE` auf
// eine leere Datei setzen, DAMIT ABER `GZ_TEST_FIXTURE_DIR` (sessionSecretGate.ts)
// setzen — ohne eines von beiden bricht der Preview-Start mit
// "GZ_SESSION_SECRET ist nicht gesetzt" ab (fail-closed), MIT
// `GZ_TEST_FIXTURE_DIR` faellt SvelteKit auf dasselbe Default-Secret zurueck,
// das der Go-Server ohne eigenes `GZ_SESSION_SECRET` ebenfalls verwendet —
// GENAU der Weg, den der echte CI-Stack ueber `.env.e2e` geht. Mit beiden
// Fixes: Kontrollmessung (daywindow-schedule-control.spec.ts) UND diese Spec
// liefen lokal echt durch (3 bzw. 4 Szenarien + Setup bestanden, 0 rot).
//
// Mutations-Gegenprobe (Fix-Loop 2, gegen den lokalen Stack, siehe Rückmeldung
// für Artefakte): jede Zeile unten wurde EINZELN durch die Vorher-Fassung
// ersetzt (Backup + sha256-Rückprobe), Frontend neu gebaut, Kontrollspec UND
// diese Spec erneut gelaufen. Kontrollspec blieb in JEDEM Durchlauf gruen
// (3/3) — ein Rot ist also der Mutation zuzuschreiben, nicht dem Stack.
//
//   Mutation                                                | rotes Szenario (Payload-Assertion)
//   --------------------------------------------------------|-------------------------------------
//   A: computeInitialBuckets()-Ergebnis in initFromTrip()    | S1 ("fehlt global"), zusaetzlich
//      (Z. ~474) nachtraeglich um die 3 Kinder bereinigt     | kollateral S2+S4 rot (Kinder fehlen
//                                                             | komplett aus ALLEN Buckets, dadurch
//                                                             | greift move() in nachfolgenden
//                                                             | Aufrufen ins Leere)
//   E: channelOverrideFromMetrics()-Ergebnis in der Kanal-   | S1 ("fehlt in channel_layouts.sms"),
//      Rekonstruktion (Z. ~502) nachtraeglich bereinigt      | kollateral S3 rot (leerer SMS-Bestand
//                                                             | laeuft ueber denselben Pfad)
//   B: toggleGlobalMetric() in onToggleMetric() (Z. ~798)    | S2 ("fehlt in der gespeicherten
//      durch die Vor-#2454-Fassung ersetzt (move() ohne      | Payload nach dem globalen
//      Kind-Mitnahme; die Kanal-Durchschreibung bei Abwahl   | Einschalten") — ISOLIERT, S1/S3/S4 gruen
//      blieb TEIL der Vor-Fassung und damit erhalten)        |
//   D: moveWithDerivedChildren()->move() in onRestoreMetric()| S3 ("fehlt im gespeicherten
//      (Z. ~834)                                             | SMS-Kanal-Layout ... Wiederherstellung")
//                                                             | — ISOLIERT, S1/S2/S4 gruen
//   F004: moveWithDerivedChildren()->move() in onRemove()    | S4 ("ist im SMS-Kanal-Layout nach
//      (Z. ~820)                                             | dem Entfernen noch aktiv")
//                                                             | — ISOLIERT, S1/S2/S3 gruen
//
// Alle 5 Mutationen wurden von mindestens einem Szenario mit einer echten
// Payload-Assertion gefangen (nie nur Timeout/Locator-Fehler). A und E lassen
// zusätzlich Szenarien rot werden, die NICHT ihr eigentlicher Wirkort sind —
// das ist ein Mutations-Formeffekt (fehlende Kinder verschwinden bei A aus
// ALLEN Buckets, nicht nur dem Ziel-Bucket) und kein zusätzlicher Befund.
//
// Reine Funktion statt Wirkort-Test fuer onRemove() bewusst NICHT ergaenzt:
// die einzige Logik dort ist der moveWithDerivedChildren()-Aufruf selbst,
// der schon in metricsEditor.ts unit-getestet ist (kindmetriken_ableitung_
// und_mitnahme.test.ts) — eine weitere reine Funktion würde denselben Pfad
// doppelt pruefen, ohne den Wirkort (das eigentliche Loch) zusaetzlich abzudecken.
//
// Ausführen (gegen einen isolierten lokalen Stack oder Staging):
//   cd frontend && npx playwright test e2e/kurzform-gefuehlte-temperatur-kind-mitnahme.spec.ts

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-2454-kurzform';
const tripId = (suffix: string) => `${TRIP_PREFIX}-${suffix}`;

const WIND_CHILL_KINDER = ['wind_chill_day_low', 'wind_chill_day_high', 'wind_chill_night'];

/** Golden Elter+Kind-fehlt-Fixture: `wind_chill` aktiv (primary), KEINE der
 *  drei Kind-Größen explizit vorhanden -- exakt das eingefrorene KHW-403-
 *  Ausgangsmuster (ohne die Kind-Einträge, die die Migration sonst entfernt),
 *  global UND im SMS-Kanal-Layout. `wind` dient als Ankermetrik für die
 *  "unrelated gesture"-gestützte Save-Auslösung in Szenario 1. */
async function createTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Bug 2454 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe 1',
					date: '2026-08-01',
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			display_config: {
				metrics: [
					{ metric_id: 'wind_chill', enabled: true, bucket: 'primary', order: 0 },
					{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 1 }
				],
				channel_layouts: {
					sms: [{ metric_id: 'wind_chill', enabled: true, order: 0 }]
				}
			}
		}
	});
	expect([200, 201], `Seed HTTP ${res.status()}`).toContain(res.status());
}

/** Golden für Szenario 2 (Toggle-Pfad): `wind_chill` global AUS. */
async function createTripWindChillOff(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Bug 2454 Toggle ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe 1',
					date: '2026-08-01',
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			display_config: {
				metrics: [
					{ metric_id: 'wind_chill', enabled: false, bucket: 'off' },
					{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 0 }
				]
			}
		}
	});
	expect([200, 201], `Seed HTTP ${res.status()}`).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

async function fetchTrip(request: APIRequestContext, id: string) {
	const res = await request.get(`/api/trips/${id}`);
	expect(res.ok(), `GET HTTP ${res.status()}`).toBeTruthy();
	return res.json();
}

async function openWeatherTab(page: Page, id: string): Promise<void> {
	await page.goto(`/trips/${id}`);
	await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible();
	await page.getByTestId('trip-detail-tab-wetter-metriken').first().click();
	await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();
}

async function waitForWeatherConfigPut(page: Page, id: string) {
	return page.waitForResponse(
		(r) => r.url().includes(`/api/trips/${id}/weather-config`) && r.request().method() === 'PUT',
		{ timeout: 10_000 }
	);
}

function activeIds(metrics: Array<{ metric_id: string; enabled: boolean }> = []): Set<string> {
	return new Set(metrics.filter((m) => m.enabled).map((m) => m.metric_id));
}

test.describe('Bug #2454 Fix-Loop 2: WeatherMetricsTab-Wirkort (Findings F001/F002/F004)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// Szenario 1 (Lade-Pfad, faengt Mutation A -- computeInitialBuckets()-
	// Aufruf in initFromTrip() entfernt): wind_chill ist beim Laden bereits
	// aktiv, Kinder fehlen explizit. Eine UNBETEILIGTE Geste (Toggle einer
	// anderen Metrik) loest den Autosave aus -- die Payload muss dabei
	// bereits die vom LADEN abgeleiteten Kinder tragen (nicht erst durch die
	// Geste selbst erzeugt).
	test('Szenario 1 (Laden): fehlende wind_chill-Kinder werden global UND im SMS-Kanal abgeleitet und ueberleben einen unbeteiligten Save', async ({
		page,
		request
	}) => {
		const id = tripId('load');
		await deleteTrip(request, id).catch(() => {});
		await createTrip(request, id);
		try {
			await openWeatherTab(page, id);

			// Unbeteiligte Geste: 'wind' aus- und wieder einschalten loest genau
			// einen weather-config-PUT aus, ohne dass der Nutzer wind_chill anfasst.
			const windToggle = page
				.locator('[data-testid="wm2-grundauswahl"] .toggle-btn')
				.filter({ hasText: 'Wind' })
				.first();
			await expect(windToggle).toBeVisible();
			const [putResponse] = await Promise.all([waitForWeatherConfigPut(page, id), windToggle.click()]);
			expect(putResponse.ok()).toBeTruthy();
			// Zurueckschalten, damit 'wind' im Endstand aktiv bleibt (fuer die
			// Server-Rueckfrage unten unerheblich, haelt den Trip aber konsistent).
			const [putResponse2] = await Promise.all([waitForWeatherConfigPut(page, id), windToggle.click()]);
			expect(putResponse2.ok()).toBeTruthy();

			const trip = await fetchTrip(request, id);
			const globalActive = activeIds(trip.display_config?.metrics);
			for (const kind of WIND_CHILL_KINDER) {
				expect(globalActive.has(kind), `${kind} fehlt global nach dem Save (Ist: ${[...globalActive].join(', ')})`).toBe(
					true
				);
			}
			const smsLayout = trip.display_config?.channel_layouts?.sms as
				| Array<{ metric_id: string; enabled: boolean }>
				| undefined;
			expect(smsLayout, 'channel_layouts.sms fehlt nach dem Save').toBeTruthy();
			const smsActive = activeIds(smsLayout);
			for (const kind of WIND_CHILL_KINDER) {
				expect(
					smsActive.has(kind),
					`${kind} fehlt in channel_layouts.sms nach dem Save (Ist: ${[...smsActive].join(', ')})`
				).toBe(true);
			}
		} finally {
			await deleteTrip(request, id);
		}
	});

	// Szenario 2 (Toggle-Pfad, faengt Mutation B -- toggleGlobalMetric()-Aufruf
	// in onToggleMetric() entfernt): wind_chill ist beim Laden AUS. Der Nutzer
	// schaltet es GLOBAL ein -- die Kinder muessen mitgenommen werden UND die
	// gespeicherte Payload muss sie mit enabled:true tragen.
	test('Szenario 2 (globaler Toggle): wind_chill einschalten nimmt seine drei Kinder mit in die gespeicherte Payload', async ({
		page,
		request
	}) => {
		const id = tripId('toggle');
		await deleteTrip(request, id).catch(() => {});
		await createTripWindChillOff(request, id);
		try {
			await openWeatherTab(page, id);

			const windChillToggle = page
				.locator('[data-testid="wm2-grundauswahl"] .toggle-btn')
				.filter({ hasText: 'Gefühlte Temperatur' });
			await expect(windChillToggle).toBeVisible();
			await expect(windChillToggle).not.toHaveClass(/\bon\b/);

			const [putResponse] = await Promise.all([waitForWeatherConfigPut(page, id), windChillToggle.click()]);
			expect(putResponse.ok()).toBeTruthy();
			const body = putResponse.request().postDataJSON() as { metrics?: Array<{ metric_id: string; enabled: boolean }> };
			const savedActive = activeIds(body.metrics);
			expect(savedActive.has('wind_chill'), 'wind_chill selbst fehlt in der gespeicherten Payload').toBe(true);
			for (const kind of WIND_CHILL_KINDER) {
				expect(
					savedActive.has(kind),
					`${kind} fehlt in der gespeicherten Payload nach dem globalen Einschalten (Ist: ${[...savedActive].join(', ')})`
				).toBe(true);
			}

			const trip = await fetchTrip(request, id);
			const globalActive = activeIds(trip.display_config?.metrics);
			for (const kind of WIND_CHILL_KINDER) {
				expect(globalActive.has(kind), `${kind} fehlt nach Reload-Rueckfrage global`).toBe(true);
			}
		} finally {
			await deleteTrip(request, id);
		}
	});

	// Szenario 3 (Kanal-eigener Restore-Pfad, deckt den direkten
	// moveWithDerivedChildren()-Aufruf in onRestoreMetric() ab -- kein
	// Einheit-Test erreicht diese Aufrufstelle; das Gegenstueck onRemove()
	// deckt Szenario 4 ab): wind_chill ist global aktiv (Kinder bereits
	// vorhanden), im SMS-Kanal aber in der "Aus"-Gruppe.
	// Der Nutzer stellt es im SMS-Reiter wieder her -- die Kinder muessen im
	// Kanal-Layout mitkommen.
	test('Szenario 3 (SMS-Kanal-Restore): wind_chill im SMS-Reiter wiederherstellen nimmt seine Kinder in den Kanal-Override mit', async ({
		page,
		request
	}) => {
		const id = tripId('restore');
		await deleteTrip(request, id).catch(() => {});
		const res = await request.post('/api/trips', {
			data: {
				id,
				name: `Bug 2454 Restore ${id}`,
				stages: [
					{
						id: `${id}-stage-1`,
						name: 'Etappe 1',
						date: '2026-08-01',
						waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
					}
				],
				display_config: {
					metrics: [
						{ metric_id: 'wind_chill', enabled: true, bucket: 'primary', order: 0 },
						{ metric_id: 'wind_chill_day_low', enabled: true, bucket: 'primary', order: 1 },
						{ metric_id: 'wind_chill_day_high', enabled: true, bucket: 'primary', order: 2 },
						{ metric_id: 'wind_chill_night', enabled: true, bucket: 'primary', order: 3 },
						{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 4 }
					],
					// SMS-Kanal fuehrt wind_chill selbst als AUS (0 = 'off'-Bucket-
					// Aequivalent: nicht in der Liste -> aus).
					channel_layouts: { sms: [] }
				}
			}
		});
		expect([200, 201]).toContain(res.status());
		try {
			await openWeatherTab(page, id);
			await page.getByTestId('channel-tab-sms').click();

			// Scoping auf die Kanal-Reihenfolge-Karte (#2049): die "3-Tages-
			// Vorschau" (CompareOutlookLayoutControls) nutzt denselben geteilten
			// WeatherV2Reihenfolge-Baustein mit identischen Testids fuer ihre
			// EIGENE Aus-Gruppe -- ohne Scoping ein strict-mode violation-Risiko.
			const kanalReihenfolge = page.getByTestId('weather-metrics-kanal-reihenfolge');
			const ausRow = kanalReihenfolge.locator('[data-testid="wm2-aus-row"][data-metric-id="wind_chill"]');
			await expect(ausRow).toBeVisible();
			const restoreButton = ausRow.getByRole('button').first();

			const [putResponse] = await Promise.all([waitForWeatherConfigPut(page, id), restoreButton.click()]);
			expect(putResponse.ok()).toBeTruthy();
			const body = putResponse.request().postDataJSON() as {
				channel_layouts?: Record<string, Array<{ metric_id: string; enabled: boolean }>>;
			};
			const smsActive = activeIds(body.channel_layouts?.sms);
			expect(smsActive.has('wind_chill'), 'wind_chill selbst fehlt im gespeicherten SMS-Kanal-Layout').toBe(true);
			for (const kind of WIND_CHILL_KINDER) {
				expect(
					smsActive.has(kind),
					`${kind} fehlt im gespeicherten SMS-Kanal-Layout nach der Wiederherstellung (Ist: ${[...smsActive].join(', ')})`
				).toBe(true);
			}
		} finally {
			await deleteTrip(request, id);
		}
	});

	// Szenario 4 (SMS-Kanal-Entfernen, faengt Finding F004 -- onRemove() ruft
	// moveWithDerivedChildren() direkt auf, primary->off): wind_chill ist
	// global UND im SMS-Kanal aktiv (Kinder ueberall bereits vorhanden). Der
	// Nutzer entfernt wind_chill NUR aus dem SMS-Reiter -- die Kinder muessen
	// im SMS-Kanal-Override mit nach "off" wandern, waehrend sie GLOBAL aktiv
	// bleiben (onRemove wirkt kanal-eigen, nicht global).
	test('Szenario 4 (SMS-Kanal-Entfernen): wind_chill im SMS-Reiter entfernen nimmt seine Kinder in den Kanal-Override mit', async ({
		page,
		request
	}) => {
		const id = tripId('remove');
		await deleteTrip(request, id).catch(() => {});
		const res = await request.post('/api/trips', {
			data: {
				id,
				name: `Bug 2454 Remove ${id}`,
				stages: [
					{
						id: `${id}-stage-1`,
						name: 'Etappe 1',
						date: '2026-08-01',
						waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
					}
				],
				display_config: {
					metrics: [
						{ metric_id: 'wind_chill', enabled: true, bucket: 'primary', order: 0 },
						{ metric_id: 'wind_chill_day_low', enabled: true, bucket: 'primary', order: 1 },
						{ metric_id: 'wind_chill_day_high', enabled: true, bucket: 'primary', order: 2 },
						{ metric_id: 'wind_chill_night', enabled: true, bucket: 'primary', order: 3 },
						{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 4 }
					],
					channel_layouts: {
						sms: [
							{ metric_id: 'wind_chill', enabled: true, order: 0 },
							{ metric_id: 'wind_chill_day_low', enabled: true, order: 1 },
							{ metric_id: 'wind_chill_day_high', enabled: true, order: 2 },
							{ metric_id: 'wind_chill_night', enabled: true, order: 3 },
							{ metric_id: 'wind', enabled: true, order: 4 }
						]
					}
				}
			}
		});
		expect([200, 201]).toContain(res.status());
		try {
			await openWeatherTab(page, id);
			await page.getByTestId('channel-tab-sms').click();

			// Scoping auf die Kanal-Reihenfolge-Karte (#2049, s. Szenario 3): die
			// "3-Tages-Vorschau" rendert denselben Baustein mit identischen
			// Testids fuer wind_chill in ihrer eigenen Grundauswahl -- ohne
			// Scoping resolved der Locator auf zwei Elemente (strict mode).
			const kanalReihenfolge = page.getByTestId('weather-metrics-kanal-reihenfolge');
			const primaryRow = kanalReihenfolge.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind_chill"]');
			await expect(primaryRow).toBeVisible();
			const removeButton = primaryRow.getByRole('button', { name: 'Aus' });

			const [putResponse] = await Promise.all([waitForWeatherConfigPut(page, id), removeButton.click()]);
			expect(putResponse.ok()).toBeTruthy();
			const body = putResponse.request().postDataJSON() as {
				metrics?: Array<{ metric_id: string; enabled: boolean }>;
				channel_layouts?: Record<string, Array<{ metric_id: string; enabled: boolean }>>;
			};
			const smsActive = activeIds(body.channel_layouts?.sms);
			expect(smsActive.has('wind_chill'), 'wind_chill ist im SMS-Kanal-Layout noch aktiv').toBe(false);
			for (const kind of WIND_CHILL_KINDER) {
				expect(
					smsActive.has(kind),
					`${kind} ist im SMS-Kanal-Layout nach dem Entfernen noch aktiv (Ist: ${[...smsActive].join(', ')})`
				).toBe(false);
			}
			const globalActive = activeIds(body.metrics);
			expect(globalActive.has('wind_chill'), 'wind_chill wurde faelschlich auch global entfernt').toBe(true);
			for (const kind of WIND_CHILL_KINDER) {
				expect(
					globalActive.has(kind),
					`${kind} wurde faelschlich auch global entfernt (Ist: ${[...globalActive].join(', ')})`
				).toBe(true);
			}
		} finally {
			await deleteTrip(request, id);
		}
	});
});

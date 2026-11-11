// E2E — Epic #1319 Scheibe B+C, erweitert Issue #1361/#1372 S1b (ADR-0035):
// konfigurierbares Tagesfenster im Trip-Editor, Reiter "Wetter-Metriken"
// (context="route").
//
// Spec: docs/specs/modules/compare_shared_day_window.md (AC-4/AC-5)
// Vorgaenger: docs/specs/modules/daywindow_configurable_window.md (AC-5,
// Epic #1319) — das Control lag dort noch im Versand-Tab; #1361/#1372 S1b
// verschiebt es in den Reiter Wetter-Metriken (Inhalts-, keine Versandfrage)
// und macht ein Fenster ueber Mitternacht gueltig (ADR-0035, Punkt 5).
//
// Muster uebernommen aus versand-tab.spec.ts (createTrip/openTripOverview)
// + weather-metrics-tab-autosave.spec.ts (clickWeatherTab/collectTripPuts).
//
// Ausfuehren (gegen Staging/Preview):
//   cd frontend && npx playwright test e2e/daywindow-schedule-control.spec.ts

import { test, expect, type APIRequestContext, type Locator, type Page, type Request } from '@playwright/test';
import { login } from './helpers.js';
import { setzeStunde, stundeAnzeige, stundeEingabe } from './s3a2794-teil3.helpers';

const TRIP_PREFIX = 'e2e-1319-daywindow';
const tripId = (suffix: string) => `${TRIP_PREFIX}-${suffix}`;

async function createTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 1319 Slice B ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe 1',
					date: '2026-08-01',
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			report_config: {
				enabled: true,
				morning_enabled: true,
				evening_enabled: false,
				morning_time: '07:00',
				send_email: true
			}
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

async function openTripOverview(page: Page, id: string): Promise<void> {
	await page.goto(`/trips/${id}`);
	await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible();
}

async function clickWeatherTab(page: Page): Promise<void> {
	await page.getByTestId('trip-detail-tab-wetter').first().click(); // #2794 S3a: Tagesfenster im Reiter Wetter
	await expect(page.locator('[data-testid="wetter-tab"]:visible').first()).toBeVisible();
}

/**
 * #2913 Scheibe (c): das Tagesfenster steht in der eingeklappten Karte „Anpassen" (Aufklapper) mit zwei
 * Uhrzeitfeldern im Stundenraster (statt DayWindowCard mit Select). Klappt auf und liefert die Karte.
 */
async function oeffneTagesfenster(page: Page): Promise<Locator> {
	const karte = page.locator('[data-testid="wetter-anpassen-karte"]:visible').first();
	await expect(karte).toBeVisible({ timeout: 10_000 });
	await karte.getByTestId('wetter-anpassen-aufklappen').click();
	await expect(karte.getByTestId('day-window-start-hour')).toBeVisible({ timeout: 10_000 });
	return karte;
}

/** Zeichnet jeden PUT-Request auf den Trip auf (Muster: weather-metrics-tab-autosave.spec.ts). */
function collectTripPuts(page: Page, id: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(`/api/trips/${id}`)) {
			puts.push(req);
		}
	});
	return puts;
}

/**
 * Disjunktheit der Trip-Speicherung (feat_2794_s3a_teil3_wetter.md Z.131, AC-38; Isolationsgarantie
 * #1234/#1361): hoechstens `maxWetter` PUTs auf /weather-config, und keiner davon traegt ein
 * Tagesfenster- oder Warn-Feld. Liefert die PUTs auf den Trip selbst (ohne /weather-config).
 */
function pruefeDisjunkteSpeicherung(puts: Request[], maxWetter = 1): Request[] {
	const urls = puts.map((r) => r.url()).join(', ');
	const wetterPuts = puts.filter((r) => r.url().includes('/weather-config'));
	expect(wetterPuts.length, `hoechstens ${maxWetter} PUT(s) auf /weather-config erwartet, getroffene URLs: ${urls}`).toBeLessThanOrEqual(maxWetter);
	for (const r of wetterPuts) {
		const roh = r.postData() ?? '';
		expect(roh, `/weather-config darf kein Tagesfenster tragen (Disjunktheit, #1361): ${roh}`).not.toMatch(/"day_window_/);
		expect(roh, `/weather-config darf keine Warn-Felder tragen (Disjunktheit, AC-38): ${roh}`).not.toMatch(/"(official_alerts_enabled|official_warnings|radar_alert_enabled)"/);
	}
	return puts.filter((r) => !r.url().includes('/weather-config'));
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = any;
/** Metrik-Katalog des Trips am Server: `display_config.metrics` (Reihenfolge) und `display_config.ampel` (Grenzen). */
type Katalog = { metrics: Json[]; ampel: Json };

async function katalogAmServer(request: APIRequestContext, id: string): Promise<Katalog> {
	const res = await request.get(`/api/trips/${id}`);
	expect(res.ok(), `GET /api/trips/${id} fehlgeschlagen: ${res.status()}`).toBeTruthy();
	const dc = ((await res.json()) as Json).display_config ?? {};
	return { metrics: dc.metrics ?? [], ampel: dc.ampel ?? {} };
}

/**
 * Intent der #1361-Zusicherung (Adversary F001, #2913 Scheibe (c)): ein reiner Tagesfenster-Wechsel
 * veraendert den Metrik-Katalog NICHT. Der freigegebene Speicherweg sendet dabei immer auch den
 * /weather-config-PUT (feat_2794_s3a_teil3_wetter.md Z.131, AC-38); dessen Inhalt muss deshalb dem
 * Server-Stand VOR der Aenderung entsprechen: dieselben Metriken in derselben Reihenfolge (keine hinzu,
 * keine weg, nicht umsortiert), jede gesendete Metrik-Angabe wie am Server, Ampel-Grenzen gleich.
 */
function pruefeKatalogUnveraendertGesendet(puts: Request[], vorher: Katalog): void {
	// Leerer Vorher-Katalog machte den Vergleich wertlos (Adversary F001, Low).
	expect(vorher.metrics.length, '#1361: Vorbedingung — der Trip hat am Server einen Metrik-Katalog').toBeGreaterThan(0);
	for (const r of puts.filter((x) => x.url().includes('/weather-config'))) {
		const body = r.postDataJSON() as Json;
		const gesendet: Json[] = body?.metrics ?? [];
		expect(
			gesendet.map((m) => m.metric_id),
			'#1361: /weather-config darf beim Tagesfenster-Wechsel keine Metrik hinzufuegen, entfernen oder umsortieren'
		).toEqual(vorher.metrics.map((m) => m.metric_id));
		gesendet.forEach((m, i) =>
			expect(vorher.metrics[i], `#1361: Metrik ${m.metric_id} wurde beim Tagesfenster-Wechsel veraendert gesendet`).toMatchObject(m)
		);
		expect(body?.ampel ?? {}, '#1361: Ampel-Grenzen duerfen sich beim Tagesfenster-Wechsel nicht aendern').toEqual(vorher.ampel);
	}
}

test.describe('Issue #1361/#1372 S1b: Tagesfenster-Control im Reiter Wetter-Metriken (context=route)', () => {
	test.beforeEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${tripId('ac5')}`).catch(() => {});
		await createTrip(page.request, tripId('ac5'));
	});

	test.afterEach(async ({ page }) => {
		await deleteTrip(page.request, tripId('ac5'));
	});

	// AC-5: Startstunde setzen -> Endstunde-Optionen bieten alle Stunden AUSSER
	// der Startstunde (ADR-0035: ein Fenster ueber Mitternacht ist gueltig, die
	// Endstunde darf also auch VOR der Startstunde liegen); Speichern loest
	// genau EINEN PUT aus, der das Feld-Paar persistiert; Reload behaelt den Wert.
	test('AC-5: Endstunde-Optionen schliessen nur die Startstunde selbst aus, genau 1 PUT, Reload persistiert', async ({
		page
	}) => {
		await login(page);
		await openTripOverview(page, tripId('ac5'));
		await clickWeatherTab(page);

		const control = await oeffneTagesfenster(page);

		const startFeld = control.locator('[data-testid="day-window-start-hour"]:visible').first();
		const endFeld = control.locator('[data-testid="day-window-end-hour"]:visible').first();

		// #2913 Scheibe (c): Stundenraster — die Minute ist kein Eingabesegment (fest 00).
		await expect(startFeld.locator('[data-segment="minute"]')).toHaveCount(0);
		await expect(endFeld.locator('[data-segment="minute"]')).toHaveCount(0);

		await setzeStunde(page, startFeld, 6);

		// ADR-0035: alle Stunden AUSSER der Startstunde sind waehlbar (auch
		// Werte VOR der Startstunde -- das bildet ein Fenster ueber Mitternacht).
		// Uhrzeitfeld statt Optionsliste: die Startstunde als Ende wird auf die
		// naechste Stunde gezogen (clampDayWindowEndHour), jede andere Stunde --
		// auch eine VOR der Startstunde -- bleibt stehen.
		await setzeStunde(page, endFeld, 6);
		await expect(stundeEingabe(endFeld), 'Ende = Start muss ausgeschlossen sein (Klemme auf 07:00)').toHaveText(stundeAnzeige(7));
		await setzeStunde(page, endFeld, 5);
		await expect(stundeEingabe(endFeld), 'eine Stunde VOR der Startstunde muss waehlbar sein').toHaveText(stundeAnzeige(5));
		await page.waitForTimeout(1_500); // Zwischenstaende vor der Messung absetzen lassen

		// Katalog-Stand am Server unmittelbar vor der gemessenen Aenderung (Intent #1361, F001).
		const katalogVorher = await katalogAmServer(page.request, tripId('ac5'));
		const puts = collectTripPuts(page, tripId('ac5'));
		await setzeStunde(page, endFeld, 16);
		await page.waitForTimeout(1_500); // Debounce-Fenster (Autosave-Muster anderer Tabs)

		// Staging-Fund AC-5 (#1361, zweifach live reproduziert): ein reiner
		// Endstunden-Wechsel schrieb den kompletten, unveraenderten Metrik-Katalog
		// mit — Verstoss gegen die #1234-Isolationsgarantie. Die fruehere Zusicherung
		// „0 PUTs auf /weather-config, genau 1 PUT" ist abgeloest durch die
		// freigegebene Entscheidung feat_2794_s3a_teil3_wetter.md (Z.131, AC-38,
		// Changelog Z.316): ein Speichervorgang des Reiters Wetter besteht aus zwei
		// DISJUNKTEN PUTs, kein PUT wiederholt den Inhalt des anderen. Gleichwertig
		// streng uebersetzt (#2913 Scheibe (c)): genau 1 Trip-PUT mit dem Tagesfenster,
		// hoechstens 1 /weather-config-PUT, und der traegt weder Tagesfenster noch
		// Warn-Felder (Disjunktheit = Kern der Isolationsgarantie), dessen Inhalt
		// dem Katalog am Server vor der Aenderung entspricht, und nach dem Neuladen
		// ist der Katalog am Server unveraendert (Intent #1361, Adversary F001).
		const tripPuts = pruefeDisjunkteSpeicherung(puts);
		pruefeKatalogUnveraendertGesendet(puts, katalogVorher);
		expect(tripPuts.length, `Erwartet genau 1 PUT auf den Trip nach Fenster-Aenderung, erhalten ${tripPuts.length}`).toBe(1);
		const body = tripPuts[0].postDataJSON() as {
			report_config?: { day_window_start_hour?: number; day_window_end_hour?: number };
		};
		expect(body.report_config?.day_window_start_hour).toBe(6);
		expect(body.report_config?.day_window_end_hour).toBe(16);

		await page.reload();
		await page.waitForLoadState('networkidle');
		await clickWeatherTab(page);
		const neu = await oeffneTagesfenster(page);

		await expect(stundeEingabe(neu.getByTestId('day-window-start-hour'))).toHaveText(stundeAnzeige(6), { timeout: 10_000 });
		await expect(stundeEingabe(neu.getByTestId('day-window-end-hour'))).toHaveText(stundeAnzeige(16), { timeout: 10_000 });
		expect(await katalogAmServer(page.request, tripId('ac5')), '#1361: Metrik-Katalog am Server nach dem Neuladen unveraendert').toEqual(
			katalogVorher
		);
	});

	// AC-3/AC-5 (ADR-0035, Punkt 5): ein Fenster ueber Mitternacht (Endstunde
	// VOR der Startstunde) ist ueber die Oberfläche waehlbar, persistiert, und
	// die Karte zeigt den Mitternachts-Hinweis.
	test('AC-3: Mitternachts-Fenster (22-2 Uhr) ist waehlbar, zeigt den Hinweis, persistiert nach Reload', async ({
		page
	}) => {
		await login(page);
		await openTripOverview(page, tripId('ac5'));
		await clickWeatherTab(page);

		const control = await oeffneTagesfenster(page);

		const startFeld = control.locator('[data-testid="day-window-start-hour"]:visible').first();
		const endFeld = control.locator('[data-testid="day-window-end-hour"]:visible').first();

		// Vorlauf: eine erste Fenster-Aenderung, damit der Reiter seinen Katalog einmal gespeichert hat
		// (ein frisch per API angelegter Trip traegt noch keine display_config). Danach ist der Server-Stand
		// die Vergleichsbasis fuer den Intent #1361 (Adversary F001).
		await setzeStunde(page, startFeld, 21);
		await page.waitForTimeout(1_500);
		const katalogVorher = await katalogAmServer(page.request, tripId('ac5'));

		const puts = collectTripPuts(page, tripId('ac5'));
		await setzeStunde(page, startFeld, 22);
		await setzeStunde(page, endFeld, 2);
		await page.waitForTimeout(1_500);

		// Zwei Eingaben (Start, Ende) koennen je einen Speichervorgang ausloesen; jeder besteht aus
		// disjunkten PUTs (feat_2794_s3a_teil3_wetter.md Z.131, AC-38), und jeder /weather-config-PUT
		// sendet den unveraenderten Katalog (Intent #1361). Massgeblich ist der letzte Trip-PUT.
		const tripPuts = pruefeDisjunkteSpeicherung(puts, 2);
		pruefeKatalogUnveraendertGesendet(puts, katalogVorher);
		expect(tripPuts.length, `Erwartet mindestens 1 PUT auf den Trip, erhalten ${tripPuts.length}`).toBeGreaterThanOrEqual(1);
		const lastBody = tripPuts[tripPuts.length - 1].postDataJSON() as {
			report_config?: { day_window_start_hour?: number; day_window_end_hour?: number };
		};
		expect(lastBody.report_config?.day_window_start_hour).toBe(22);
		expect(lastBody.report_config?.day_window_end_hour).toBe(2);

		await expect(control.locator('[data-testid="day-window-wrap-hint"]:visible').first()).toBeVisible();

		await page.reload();
		await page.waitForLoadState('networkidle');
		await clickWeatherTab(page);
		const neu = await oeffneTagesfenster(page);

		await expect(stundeEingabe(neu.getByTestId('day-window-start-hour'))).toHaveText(stundeAnzeige(22), { timeout: 10_000 });
		await expect(stundeEingabe(neu.getByTestId('day-window-end-hour'))).toHaveText(stundeAnzeige(2), { timeout: 10_000 });
		expect(await katalogAmServer(page.request, tripId('ac5')), '#1361: Metrik-Katalog am Server nach dem Neuladen unveraendert').toEqual(
			katalogVorher
		);
	});
});

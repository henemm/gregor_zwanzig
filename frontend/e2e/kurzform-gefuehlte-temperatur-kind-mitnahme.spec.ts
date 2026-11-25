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
import { gespeichertAn, haken, oeffneKarte, tabelle, tabelleGespeichert } from './was-steht-wo.helpers';

const TRIP_PREFIX = 'e2e-2454-kurzform';
const tripId = (suffix: string) => `${TRIP_PREFIX}-${suffix}`;

const WIND_CHILL_KINDER = ['wind_chill_day_low', 'wind_chill_day_high', 'wind_chill_night'];

/** Golden Elter+Kind-fehlt-Fixture: `wind_chill` aktiv (primary), KEINE der
 *  drei Kind-Größen explizit vorhanden -- exakt das eingefrorene KHW-403-
 *  Ausgangsmuster (ohne die Kind-Einträge, die die Migration sonst entfernt),
 *  global UND in der SMS. #3359: die SMS-Auswahl steht seit #3277 allein in der
 *  Tabelle „Was steht wo“ (`placements.rows`, `wind_chill` mit `places.sms = true`,
 *  bewusst abweichend von der Grundauswahl: kein Ausblick, Ausblick nur abends).
 *  `wind` dient als Ankermetrik für die "unrelated gesture"-gestützte
 *  Save-Auslösung in Szenario 1. */
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
				placements: {
					version: 1,
					rows: [
						{ metric_id: 'wind_chill', places: { email: true, telegram: true, sms: true, outlook: false } },
						// ohne `places` = überall an: genau die Form, in der „+“ die Zeile zurückschreibt (WS-11 T4)
						{ metric_id: 'wind' }
					],
					outlook_reports: ['evening']
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

	// #2794 Teil 3 (Spec feat_2794_s3a_teil3_wetter.md §4, §6 e, AC-19, AC-37): die GLOBALE Metrik-
	// Auswahl steht jetzt im WetterTab (Reiter Wetter); er schreibt `display_config.metrics[]` als
	// bestehende Liste mit neuem `enabled` (fehlende Einträge hängt er nur für gewählte Metriken an)
	// und die SMS-Auswahl (seit #3277 allein die Tabelle „Was steht wo“, `placements`) nicht abweichend.
	// Die Kind-Größen von „Gefühlte Temperatur" sind im Katalog eigene Zeilen. Die Kernaussage von
	// Bug #2454 bleibt dieselbe und wird am neuen Träger geprüft: der Editor darf fehlende Kind-Größen
	// NIE abgewählt festschreiben (Einfrieren, das die Elter→Kind-Ableitung des Loaders
	// `_DERIVED_METRIC_RULES` dauerhaft blockiert), weder global (`enabled:false`) noch in der
	// SMS-Spalte der Tabelle (`places.sms = false`) — und `wind_chill` selbst bleibt bzw. wird aktiv
	// gespeichert.
	const metrikenIm = (body: { metrics?: Array<{ metric_id: string; enabled: boolean }> } | undefined) => body?.metrics ?? [];
	function keinEingefrorenesKind(liste: Array<{ metric_id: string; enabled: boolean }> = [], wo: string): void {
		for (const kind of WIND_CHILL_KINDER) {
			const eintrag = liste.find((m) => m.metric_id === kind);
			expect(eintrag?.enabled === false, `${kind} ist ${wo} als enabled:false eingefroren (Bug #2454)`).toBe(false);
		}
	}

	async function oeffneWetterTab(page: Page, id: string) {
		await page.goto(`/trips/${id}?tab=wetter`);
		const reiter = page.locator('[data-testid="wetter-tab"]:visible');
		await expect(reiter).toBeVisible({ timeout: 15_000 });
		await expect(reiter.getByTestId('wetter-tab-laden')).toHaveCount(0, { timeout: 15_000 });
		return reiter;
	}

	// Szenario 1 (Lade-Pfad): wind_chill ist beim Laden bereits aktiv, Kinder fehlen explizit.
	// Eine UNBETEILIGTE Geste (Wind „−" und wieder „+") löst Speichervorgänge aus — keiner davon
	// darf die fehlenden Kinder einfrieren, die SMS-Spalte der Tabelle bleibt wie gespeichert.
	test('Szenario 1 (Laden): fehlende wind_chill-Kinder werden bei einem unbeteiligten Save weder global noch im SMS-Kanal eingefroren', async ({
		page,
		request
	}) => {
		const id = tripId('load');
		await deleteTrip(request, id).catch(() => {});
		await createTrip(request, id);
		try {
			const vorher = await fetchTrip(request, id);
			expect(gespeichertAn(vorher.display_config?.placements, 'wind_chill', 'sms'), 'Messaufbau: wind_chill in der SMS-Spalte der Tabelle').toBe(true);
			const reiter = await oeffneWetterTab(page, id);
			await expect(reiter.getByTestId('wetter-zeile-wind_chill'), 'Vorbedingung: wind_chill ist im Briefing').toBeVisible();

			const [putResponse] = await Promise.all([waitForWeatherConfigPut(page, id), reiter.getByTestId('wetter-zeile-entfernen-wind').click()]);
			expect(putResponse.ok()).toBeTruthy();
			keinEingefrorenesKind(metrikenIm(putResponse.request().postDataJSON()), 'in der gespeicherten Payload (1. Save)');
			const [putResponse2] = await Promise.all([waitForWeatherConfigPut(page, id), reiter.getByTestId('wetter-nicht-im-briefing-plus-wind').click()]);
			expect(putResponse2.ok()).toBeTruthy();
			const body2 = putResponse2.request().postDataJSON() as { metrics?: Array<{ metric_id: string; enabled: boolean }> };
			keinEingefrorenesKind(metrikenIm(body2), 'in der gespeicherten Payload (2. Save)');
			expect(activeIds(body2.metrics).has('wind_chill'), 'wind_chill selbst muss aktiv gespeichert bleiben').toBe(true);

			const trip = await fetchTrip(request, id);
			keinEingefrorenesKind(trip.display_config?.metrics, 'global auf dem Server');
			expect(activeIds(trip.display_config?.metrics).has('wind_chill')).toBe(true);
			// #3359: SMS-Teil über die Tabelle „Was steht wo“ (Entscheidung im Spec-Changelog fix_3359).
			const zeilen = trip.display_config?.placements?.rows as Array<{ metric_id: string; places?: Record<string, boolean> }> | undefined;
			expect(zeilen, 'placements.rows fehlt nach dem Save').toBeTruthy();
			for (const kind of WIND_CHILL_KINDER) {
				const zeile = zeilen!.find((r) => r.metric_id === kind);
				expect(zeile?.places?.sms === false, `${kind} ist in der SMS-Spalte der Tabelle abgewählt eingefroren (Bug #2454)`).toBe(false);
			}
			expect(gespeichertAn(trip.display_config?.placements, 'wind_chill', 'sms'), 'wind_chill bleibt in der SMS angehakt').toBe(true);
			const mitHaken = await tabelle(request, 'route', id);
			const sms = (mitHaken.rows as Array<{ metric_id: string; cells: Record<string, { state: string }> }>).find((r) => r.metric_id === 'wind_chill');
			expect(sms?.cells?.sms?.state, 'Server-Tabelle: wind_chill steht in der SMS').toBe('on');
			expect(trip.display_config?.placements, 'die Tabelle ist nach den unbeteiligten Speichervorgängen gleich dem Stand vorher').toEqual(vorher.display_config?.placements);

			// AC-7 (Spec fix_3359): die Kurz-SMS enthält den Wert der gefühlten Temperatur, ohne Haken fehlt er.
			// Geprüft am SMS-Beispiel der Server-Tabelle: es rendert die echte Trip-SMS über feste Beispieldaten
			// (services/placements_beispiel, keine Vorhersage, deterministisch). Kürzel der gefühlten Temperatur
			// selbst: TF (sms_format.md). Die Kind-Größen (FN/FL/FD) sind in der Tabelle eigene Zeilen mit eigenem
			// Haken und bleiben nach Abwahl nur der Elter-Zeile bewusst stehen; geprüft wird deshalb das TF-Token.
			const GEFUEHLT = /(^| )TF\S*/;
			expect(mitHaken.sms_example?.text, 'AC-7: Kurz-SMS mit Haken enthält die gefühlte Temperatur').toMatch(GEFUEHLT);
			const karte = await oeffneKarte(page, 'route', id);
			const abgewaehlt = tabelleGespeichert(page, id);
			await haken(karte, 'wind_chill', 'sms').click();
			await abgewaehlt;
			const ohneHaken = await tabelle(request, 'route', id);
			expect(gespeichertAn(ohneHaken.placements, 'wind_chill', 'sms'), 'Messaufbau: wind_chill in der SMS abgewählt').toBe(false);
			expect(ohneHaken.sms_example?.text, 'AC-7: Kurz-SMS ohne Haken enthält keine gefühlte Temperatur').not.toMatch(GEFUEHLT);
			expect(ohneHaken.sms_example?.text, 'AC-7: Kurz-SMS ohne Haken ist sonst noch da (Wind)').toMatch(/(^| )W\d/);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// Szenario 2 (Hinzufügen-Pfad): wind_chill ist beim Laden AUS. Der Nutzer nimmt es über
	// „Nicht im Briefing" ins Briefing — die gespeicherte Payload trägt wind_chill aktiv und
	// friert keine Kind-Größe ein.
	test('Szenario 2 (globaler Toggle): wind_chill einschalten speichert es aktiv und friert keine Kind-Größe ein', async ({
		page,
		request
	}) => {
		const id = tripId('toggle');
		await deleteTrip(request, id).catch(() => {});
		await createTripWindChillOff(request, id);
		try {
			const reiter = await oeffneWetterTab(page, id);
			await expect(reiter.getByTestId('wetter-zeile-wind_chill'), 'Vorbedingung: wind_chill ist nicht im Briefing').toHaveCount(0);

			const [putResponse] = await Promise.all([
				waitForWeatherConfigPut(page, id),
				reiter.getByTestId('wetter-nicht-im-briefing-plus-wind_chill').click()
			]);
			expect(putResponse.ok()).toBeTruthy();
			const body = putResponse.request().postDataJSON() as { metrics?: Array<{ metric_id: string; enabled: boolean }> };
			expect(activeIds(body.metrics).has('wind_chill'), 'wind_chill selbst fehlt in der gespeicherten Payload').toBe(true);
			keinEingefrorenesKind(metrikenIm(body), 'in der gespeicherten Payload nach dem Einschalten');

			const trip = await fetchTrip(request, id);
			expect(activeIds(trip.display_config?.metrics).has('wind_chill'), 'wind_chill nach Rückfrage nicht aktiv').toBe(true);
			keinEingefrorenesKind(trip.display_config?.metrics, 'nach Rückfrage global');
			const r2 = await oeffneWetterTab(page, id);
			await expect(r2.getByTestId('wetter-zeile-wind_chill'), 'nach Neuladen steht wind_chill im Briefing').toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 14): Szenario 3 (SMS-Kanal-Restore) und
	// Szenario 4 (SMS-Kanal-Entfernen) sind gestrichen. Ihr Wirkort — die Kanal-Listen der Metrik-Oberflaeche
	// im Uebergangsblock des Reiters Zustellung (onRestoreMetric/onRemove in WeatherMetricsTab) — ist entfernt;
	// im Hub bestimmt die Karte „Was steht wo“ je Stelle, was in der SMS steht (Tabelle `placements`, kein
	// Schreiber der alten Kanal-Listen mehr). Die Mitnahme-Logik selbst bleibt unit-getestet
	// (kindmetriken_ableitung_und_mitnahme.test.ts); Szenario 1 sichert weiter (#3359), dass die SMS-Spalte
	// der Tabelle beim Speichern unberuehrt bleibt und keine Kind-Größe darin abgewählt eingefroren wird.
});

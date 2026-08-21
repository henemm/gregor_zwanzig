// Staging-Klickpfad — #1720 Scheibe 1: Abschnitt "3-Tages-Vorschau" im
// Wetter-Metriken-Reiter des Trips (AC-6, AC-7, AC-11, AC-13).
//
// Spec: docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md
// Nacharbeit: docs/specs/fast/fix-1720-s1-playwright-selektoren.md
// Kontext: docs/context/feat-1720-vorschau-metriken.md
//
// Namensregel (CLAUDE.md): nach Verhalten benannt, nicht nach Ticket.
// Muster: compare-outlook-metric-selection.staging.spec.ts — dieselbe
// Bedienflaeche, nur im Trip-Kontext (parametrisiert statt kopiert).
//
// Die Datei entstand in der RED-Phase und war dort strukturell nicht
// ausfuehrbar (der Abschnitt war noch nicht deployt). Zwei Annahmen ueber die
// Oberflaeche hielten dem ersten echten Lauf nicht stand und sind hier
// richtiggestellt — s. `wartetAufAutosave` (kein Speichern-Knopf im Trip) und
// die Gegenprobe in AC-13 (der Ausblick-Schalter lebt im selben Reiter).
//
// Ausfuehren (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   set -a; source /home/hem/gregor_zwanzig_staging/.env; set +a
//   npx playwright test --config=playwright.trip-outlook.staging.config.ts
//
// Zugangsdaten-Hinweis (CLAUDE.md, 2026-08-08): nginx-Schranke =
// GZ_VALIDATOR_*, App-Anmeldung = GZ_AUTH_* aus der STAGING-.env — die .env
// des Arbeitsordners liefert dort 401.

import { test, expect, type Locator, type Page } from '@playwright/test';
import { createTestTrip } from './helpers';

type CatalogEntry = { key: string; label: string; metric_id: string; aggregation: string };

/** Konsolenfehler und pageerror waehrend des ganzen Tests einsammeln (AC-6). */
function sammleKonsolenfehler(page: Page): string[] {
	const fehler: string[] = [];
	page.on('console', (msg) => {
		if (msg.type() === 'error') fehler.push(`console.error: ${msg.text()}`);
	});
	page.on('pageerror', (err) => fehler.push(`pageerror: ${err.message}`));
	return fehler;
}

/** Oeffnet den Trip und wechselt in den Wetter-Metriken-Reiter. */
async function oeffneMetrikenReiter(page: Page, tripId: string): Promise<Locator> {
	await page.goto(`/trips/${tripId}?tab=weather`);
	await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible({ timeout: 15000 });
	await page.getByTestId('trip-detail-tab-weather').first().click();
	const reiter = page.getByTestId('weather-metrics-tab');
	await expect(reiter).toBeVisible({ timeout: 15000 });
	return reiter;
}

/** Der neue Abschnitt. Traegt bewusst DIESELBE Testid wie im Ortsvergleich —
 *  es ist dasselbe, parametrisierte Bauteil, keine zweite Komponente
 *  (Trip/Compare-Teilungs-Invariante, CLAUDE.md). */
function vorschauAbschnitt(reiter: Locator): Locator {
	return reiter.getByTestId('weather-metrics-ausblick');
}

/** Der Trip-Editor hat KEINEN Speichern-Knopf: `TripTabs` reicht einen
 *  `saveController` hinein, und `WeatherMetricsTab.svelte:1451` rendert
 *  `weather-metrics-tab-save` nur `{#if isDirty && !saveController && !createMode}`.
 *  Gespeichert wird per Autosave (700 ms Debounce) — `scheduleAutoSave()`
 *  schreibt die Ausblick-Auswahl per PUT auf `/api/trips/{id}/weather-config`
 *  (WeatherMetricsTab.svelte:960). Der Test wartet deshalb auf die echte
 *  Speicher-Antwort statt auf einen Knopf, den es hier nicht gibt.
 *
 *  Scharfschalten VOR der Geste: der Debounce kann sonst ablaufen, bevor
 *  jemand zuhoert. */
function wartetAufAutosave(page: Page, tripId: string) {
	return page.waitForResponse(
		(r) =>
			r.url().includes(`/api/trips/${tripId}/weather-config`) && r.request().method() === 'PUT',
		{ timeout: 15000 }
	);
}

test.describe('Trip-Vorschau: waehlbare Spalten im Wetter-Metriken-Reiter (#1720 S1, Staging)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-6 ────────────────────────────────────────────────────────────────
	test('AC-6 (#1720 S1): eine abgewaehlte Groesse bleibt nach dem Neuladen abgewaehlt, ohne Konsolenfehler', async ({
		page,
		request
	}) => {
		const fehler = sammleKonsolenfehler(page);
		const trip = await createTestTrip(request, { name: '1720-AC6' });

		const reiter = await oeffneMetrikenReiter(page, trip.id);
		const abschnitt = vorschauAbschnitt(reiter);
		await expect(
			abschnitt,
			'AC-6: der Abschnitt "3-Tages-Vorschau" fehlt im Trip-Reiter'
		).toBeVisible({ timeout: 10000 });
		await expect(abschnitt.getByTestId('compare-layout-outlook-metrics')).toBeVisible({
			timeout: 10000
		});

		// #1848 A3: abgewaehlt wird ueber den "Aus"-Knopf der Reihenfolge-Liste
		// — die Kaestchenliste ist ersatzlos entfallen (Block A, #2029). Die
		// Zusicherung dieses Tests ist davon unberuehrt: der SERVERSTAND nach
		// der Abwahl, und dass der Klickpfad keine Konsolenfehler wirft. Der
		// reine DOM-Weg (Aus-Gruppe, Reload, Zurueckholen) ist in
		// ausblick-erbt-grundauswahl.staging.spec.ts::AC-7 abgedeckt und hier
		// bewusst nur noch angerissen, statt ihn doppelt zu pflegen.
		const boeenZeile = abschnitt.locator(
			'[data-testid="wm2-reihenfolge-row"][data-metric-id="gust"]'
		);
		await expect(boeenZeile, 'Vorbedingung: Böen ist vor der Abwahl aktiv').toBeVisible({
			timeout: 10000
		});
		const gespeichertePut = wartetAufAutosave(page, trip.id);
		await boeenZeile.getByRole('button', { name: 'Aus' }).click();
		await expect(
			abschnitt.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="gust"]')
		).toHaveCount(0);

		await gespeichertePut;
		await page.waitForLoadState('networkidle');

		// Serverstand ist die eigentliche Aussage, nicht nur der DOM.
		const gespeichert = await page.request.get(`/api/trips/${trip.id}`);
		const body = await gespeichert.json();
		// #1848 A2: gespeichert werden reine KENNUNGEN. Ein `m.metric_id`-Zugriff
		// auf eine Zeichenkette liefert `undefined` — der Vergleich waere still
		// immer falsch und die Abwahl-Zusicherung trivial erfuellt. Deshalb hier
		// bewusst der direkte Wert-Vergleich.
		const auswahl = (body.display_config?.outlook_metrics ?? []) as string[];
		expect(
			auswahl.every((m) => typeof m === 'string'),
			`#1848 A2: display_config.outlook_metrics muss reine Kennungen fuehren: ${JSON.stringify(auswahl)}`
		).toBe(true);
		expect(
			auswahl.includes('gust'),
			`AC-6: 'gust' steht nach dem Speichern weiterhin in display_config.outlook_metrics: ${JSON.stringify(auswahl)}`
		).toBe(false);
		expect(
			auswahl.length,
			'AC-6: die uebrigen Groessen muessen erhalten bleiben (nur Böen abgewaehlt)'
		).toBeGreaterThan(0);

		// Neuladen: die Abwahl ueberlebt. #1848 A3: sichtbar daran, dass "gust"
		// NICHT in der aktiven Liste steht — die Aus-Gruppe und das
		// Zurueckholen pruefen wir nicht doppelt (s. o.).
		const reiterNachReload = await oeffneMetrikenReiter(page, trip.id);
		const abschnittNachReload = vorschauAbschnitt(reiterNachReload);
		await expect(
			abschnittNachReload.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="gust"]'),
			'AC-6: nach dem Neuladen ist die Abwahl verloren — Hinweis auf einen fehlenden Lesepfad (initFromTrip ohne normalizeStoredActiveMetrics)'
		).toHaveCount(0);

		await page.screenshot({
			path: '../docs/artifacts/feat-1720-vorschau-metriken/ac-6-abwahl-ueberlebt-reload.png',
			fullPage: true
		});

		expect(fehler, `AC-6: Konsolenfehler waehrend des Klickpfads: ${fehler.join(' | ')}`).toEqual([]);
	});

	// ── AC-7 (S1), fortgeschrieben durch AC-6 der Scheibe 2 ─────────────────
	// Scheibe 1 verlangte hier den Hinweis "Erscheint nur in der E-Mail", weil
	// die Trip-Auswahl damals wirklich nur die E-Mail erreichte. Mit Scheibe 2
	// (Spec: docs/specs/modules/feat_1720_s2_ausblick_kompakt_telegram.md,
	// AC-6) wirkt dieselbe Auswahl in allen vier Ausgabeorten — der Hinweis
	// waere im Trip jetzt schlicht falsch und ist dort abgeschaltet
	// (`showEmailOnlyHint={false}`). Im Ortsvergleich bleibt er unveraendert;
	// das deckt compare-outlook-metric-selection.staging.spec.ts ab.
	test('AC-6 (#1720 S2): der Trip-Abschnitt traegt KEINEN Hinweis "Erscheint nur in der E-Mail"', async ({
		page,
		request
	}) => {
		const trip = await createTestTrip(request, { name: '1720-AC7' });
		const reiter = await oeffneMetrikenReiter(page, trip.id);
		const abschnitt = vorschauAbschnitt(reiter);
		await expect(abschnitt).toBeVisible({ timeout: 10000 });

		// Mindestens eine Groesse aktiv — das ist die Bedingung, unter der der
		// Hinweis im Ortsvergleich erscheint. Nur so ist die Abwesenheit im
		// Trip eine Aussage und kein Nebeneffekt einer leeren Auswahl.
		// #1848 A3: der Ausblick erbt die Grundauswahl, ein frischer Trip hat
		// also von sich aus aktive Zeilen — die Vorbedingung muss nicht mehr
		// per Kaestchen hergestellt werden (die Liste ist entfallen), sie wird
		// nur noch belegt.
		await expect(
			abschnitt.locator('[data-testid="wm2-reihenfolge-row"]').first(),
			'Vorbedingung: mindestens eine Groesse ist im Ausblick aktiv'
		).toBeVisible({ timeout: 10000 });

		await expect(
			abschnitt.getByTestId('compare-layout-outlook-email-only-hint'),
			'AC-6 (S2): der Trip-Abschnitt zeigt weiterhin den E-Mail-only-Hinweis, obwohl die Auswahl dort jetzt Kompakt-Mail und Telegram mitsteuert'
		).toHaveCount(0);
		await expect(
			abschnitt.getByText('Erscheint nur in der E-Mail', { exact: false }),
			'AC-6 (S2): der Hinweistext taucht im Trip-Abschnitt noch auf (ggf. ohne Testid gerendert)'
		).toHaveCount(0);

		await page.screenshot({
			path: '../docs/artifacts/feat-1720-vorschau-metriken/ac-7-kein-email-hinweis.png'
		});
	});

	// ── AC-13 ───────────────────────────────────────────────────────────────
	test('AC-13 (#1720 S1): kein zweiter Ein/Aus-Schalter im Vorschau-Abschnitt', async ({
		page,
		request
	}) => {
		const trip = await createTestTrip(request, { name: '1720-AC13' });
		const reiter = await oeffneMetrikenReiter(page, trip.id);
		const abschnitt = vorschauAbschnitt(reiter);
		await expect(abschnitt).toBeVisible({ timeout: 10000 });

		// Der Ortsvergleich zeigt hier einen ChannelToggle "3-Tages-Ausblick".
		// Der Trip hat mit report_config.show_outlook bereits einen solchen
		// Schalter in der Inhalt-/Versand-Karte — ein zweiter waere eine
		// widerspruechliche Bedienflaeche.
		await expect(
			abschnitt.getByRole('switch'),
			'AC-13: der Vorschau-Abschnitt darf keinen eigenen Ein/Aus-Schalter tragen'
		).toHaveCount(0);
		await expect(
			abschnitt.getByText('3-Tages-Ausblick', { exact: false }),
			'AC-13: kein zweiter Ausblick-Schalter (Beschriftung des Compare-Toggles)'
		).toHaveCount(0);

		// Gegenprobe: der EINE vorhandene Schalter lebt weiterhin in der
		// Mail-Inhalt-Karte — und die sitzt im SELBEN Wetter-Metriken-Reiter,
		// nicht im Versand-Reiter: `WeatherMetricsTab.svelte:1780-1787` bindet
		// `EditReportConfigSection` (Abschnitt 'report_config') inline ein,
		// `BriefingScheduleTab.svelte:117-119` haelt ausdruecklich fest
		// "Mail-Inhalt bleibt unangetastet im Inhalt-Tab". Also ohne Tab-Wechsel.
		await expect(
			reiter.getByTestId('report-show-outlook'),
			'AC-13: der bestehende Ein/Aus-Schalter fuer den Ausblick muss erhalten bleiben'
		).toBeVisible({ timeout: 10000 });

		await page.screenshot({
			path: '../docs/artifacts/feat-1720-vorschau-metriken/ac-13-kein-zweiter-schalter.png',
			fullPage: true
		});
	});

	// ── AC-10/AC-11 ─────────────────────────────────────────────────────────
	// ⚠️ #1848 A3: die Zusicherung "der PICKER bietet jede Katalog-Groesse an"
	// ist ERSATZLOS entfallen — es gibt keinen Picker mehr (Block A, #2029).
	// Welche Groessen der Ausblick zeigt, entscheidet seit A3 die Grundauswahl
	// der Tour, nicht der Katalog; das deckt
	// ausblick-erbt-grundauswahl.staging.spec.ts::AC-5 ab ("eine Groesse
	// ausserhalb der Grundauswahl erscheint weder aktiv noch in der
	// Aus-Gruppe").
	//
	// Was BLEIBT und hier weitergeprueft wird: AC-10 (#710) — der Katalog, aus
	// dem sich die Bedienflaeche speist, darf "confidence" gar nicht erst
	// anbieten. Diese Zusicherung haengt am Endpoint, nicht an der Liste, und
	// waere mit der Datei sonst stillschweigend verschwunden.
	test('AC-10 (#710): der Ausblick-Katalog bietet "Vorhersage-Genauigkeit" nicht an', async ({
		page,
		request
	}) => {
		const trip = await createTestTrip(request, { name: '1720-AC11' });
		const katalogRes = await request.get('/api/compare/metrics');
		expect(katalogRes.ok(), `GET /api/compare/metrics HTTP ${katalogRes.status()}`).toBeTruthy();
		const katalog = (await katalogRes.json()) as { metrics: CatalogEntry[] };
		expect(
			katalog.metrics.some((m) => m.metric_id === 'confidence'),
			'AC-10: der Katalog darf "confidence" nicht anbieten (PO-Entscheid #710)'
		).toBe(false);
		expect(
			katalog.metrics.length,
			'Vakuum-Schutz: ein leerer Katalog machte die Zusicherung oben trivial wahr'
		).toBeGreaterThan(20);

		// Gegenprobe an der Bedienflaeche: "confidence" taucht auch dort nicht
		// auf — weder aktiv noch in der Aus-Gruppe.
		const reiter = await oeffneMetrikenReiter(page, trip.id);
		const abschnitt = vorschauAbschnitt(reiter);
		await expect(abschnitt).toBeVisible({ timeout: 10000 });
		await expect(
			abschnitt.locator('[data-metric-id="confidence"]'),
			'AC-10: "Vorhersage-Genauigkeit" darf im Ausblick nicht auftauchen'
		).toHaveCount(0);
	});
});

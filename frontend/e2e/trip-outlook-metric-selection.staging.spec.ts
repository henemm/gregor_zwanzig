// TDD RED — #1720 Scheibe 1: Abschnitt "3-Tages-Vorschau" im Wetter-Metriken-
// Reiter des Trips (AC-6, AC-7, AC-13).
//
// Spec: docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md
// Kontext: docs/context/feat-1720-vorschau-metriken.md
// Workflow: feat-1720-vorschau-metriken
//
// Namensregel (CLAUDE.md): nach Verhalten benannt, nicht nach Ticket.
// Muster: compare-outlook-metric-selection.staging.spec.ts — dieselbe
// Bedienflaeche, nur im Trip-Kontext (parametrisiert statt kopiert).
//
// 🔴 IN DER RED-PHASE NICHT AUSFUEHRBAR: der Abschnitt existiert auf Staging
// noch nicht ('ausblick' steht in COMPARE_ONLY_SECTIONS,
// weatherMetricsTabSections.ts:56). Der Lauf gehoert in die GREEN-Phase,
// nach dem Staging-Deploy.
//
// Ausfuehren (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   set -a; source /home/hem/gregor_zwanzig_staging/.env; set +a
//   npx playwright test --config=playwright.trip-outlook.staging.config.ts
//
// ⚠️ Die genannte Config `frontend/playwright.trip-outlook.staging.config.ts`
// FEHLT noch: der Edit-Wächter der RED-Phase laesst dort keine Datei zu
// (kein Test-Pfad). Sie ist in der GREEN-Phase anzulegen, 1:1 nach dem
// Muster `playwright.compare-outlook.staging.config.ts` — Projekte `setup`
// (diese `.staging.setup.ts`) und `chromium` mit
// `storageState: 'playwright/.auth/staging-trip-outlook.json'`.
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

async function speichern(page: Page, reiter: Locator, tripId: string): Promise<void> {
	const put = page.waitForResponse(
		(r) => r.url().includes(`/api/trips/${tripId}`) && r.request().method() === 'PUT',
		{ timeout: 10000 }
	);
	await reiter.getByTestId('weather-metrics-tab-save').click();
	await put;
	await page.waitForLoadState('networkidle');
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

		// Eine Groesse abwaehlen, die in der Grundvorbelegung aktiv ist.
		const boeen = abschnitt.getByTestId('compare-layout-outlook-metric-gust').locator('input');
		await expect(boeen, 'Vorbedingung: Böen ist vor der Abwahl angehakt').toBeChecked();
		await boeen.uncheck();
		await expect(boeen).not.toBeChecked();

		await speichern(page, reiter, trip.id);

		// Serverstand ist die eigentliche Aussage, nicht nur der DOM.
		const gespeichert = await page.request.get(`/api/trips/${trip.id}`);
		const body = await gespeichert.json();
		const auswahl = (body.display_config?.outlook_metrics ?? []) as CatalogEntry[];
		expect(
			auswahl.some((m) => m.metric_id === 'gust'),
			`AC-6: 'gust' steht nach dem Speichern weiterhin in display_config.outlook_metrics: ${JSON.stringify(auswahl)}`
		).toBe(false);
		expect(
			auswahl.length,
			'AC-6: die uebrigen Groessen muessen erhalten bleiben (nur Böen abgewaehlt)'
		).toBeGreaterThan(0);

		// Neuladen: die Abwahl ueberlebt.
		const reiterNachReload = await oeffneMetrikenReiter(page, trip.id);
		const abschnittNachReload = vorschauAbschnitt(reiterNachReload);
		await expect(
			abschnittNachReload.getByTestId('compare-layout-outlook-metric-gust').locator('input'),
			'AC-6: nach dem Neuladen ist die Abwahl verloren — Hinweis auf einen fehlenden Lesepfad (initFromTrip ohne normalizeStoredActiveMetrics)'
		).not.toBeChecked();

		await page.screenshot({
			path: '../docs/artifacts/feat-1720-vorschau-metriken/ac-6-abwahl-ueberlebt-reload.png',
			fullPage: true
		});

		expect(fehler, `AC-6: Konsolenfehler waehrend des Klickpfads: ${fehler.join(' | ')}`).toEqual([]);
	});

	// ── AC-7 ────────────────────────────────────────────────────────────────
	test('AC-7 (#1720 S1): der Abschnitt traegt den Hinweis "Erscheint nur in der E-Mail"', async ({
		page,
		request
	}) => {
		const trip = await createTestTrip(request, { name: '1720-AC7' });
		const reiter = await oeffneMetrikenReiter(page, trip.id);
		const abschnitt = vorschauAbschnitt(reiter);
		await expect(abschnitt).toBeVisible({ timeout: 10000 });

		// Mindestens eine Groesse gewaehlt (Bedingung des Hinweises, Muster
		// CompareOutlookLayoutControls.svelte:159-161).
		const niederschlag = abschnitt
			.getByTestId('compare-layout-outlook-metric-precipitation')
			.locator('input');
		if (!(await niederschlag.isChecked())) await niederschlag.check();

		const hinweis = abschnitt.getByTestId('compare-layout-outlook-email-only-hint');
		await expect(
			hinweis,
			'AC-7: Kompakt-Mail und Telegram folgen erst in Scheibe 2 — bis dahin muss der Abschnitt denselben Hinweis tragen wie beim Ortsvergleich'
		).toBeVisible();
		await expect(hinweis).toContainText('Erscheint nur in der E-Mail');

		await page.screenshot({
			path: '../docs/artifacts/feat-1720-vorschau-metriken/ac-7-email-hinweis.png'
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

		// Gegenprobe: der EINE vorhandene Schalter lebt weiterhin im
		// Inhalt-/Versand-Bereich und ist unberuehrt.
		await page.getByTestId('trip-detail-tab-briefings').first().click();
		await expect(
			page.getByTestId('report-show-outlook'),
			'AC-13: der bestehende Ein/Aus-Schalter fuer den Ausblick muss erhalten bleiben'
		).toBeVisible({ timeout: 10000 });

		await page.screenshot({
			path: '../docs/artifacts/feat-1720-vorschau-metriken/ac-13-kein-zweiter-schalter.png',
			fullPage: true
		});
	});

	// ── AC-11 (Oberflaeche gegen Backend-Katalog) ───────────────────────────
	test('AC-11 (#1720 S1): der Picker speist sich aus GET /api/compare/metrics', async ({
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

		const reiter = await oeffneMetrikenReiter(page, trip.id);
		const abschnitt = vorschauAbschnitt(reiter);
		await expect(abschnitt).toBeVisible({ timeout: 10000 });

		const groessen = new Set(katalog.metrics.map((m) => m.metric_id));
		for (const metricId of groessen) {
			const einzel = abschnitt.getByTestId(`compare-layout-outlook-metric-${metricId}`);
			const mehrfach = abschnitt.getByTestId(`compare-layout-outlook-metric-row-${metricId}`);
			expect(
				(await einzel.count()) + (await mehrfach.count()),
				`AC-11: der Picker bietet die Katalog-Groesse ${metricId} nicht an`
			).toBeGreaterThan(0);
		}
		await expect(
			abschnitt.getByTestId('compare-layout-outlook-metric-confidence'),
			'AC-10: "Vorhersage-Genauigkeit" darf im Picker nicht auftauchen'
		).toHaveCount(0);
	});
});

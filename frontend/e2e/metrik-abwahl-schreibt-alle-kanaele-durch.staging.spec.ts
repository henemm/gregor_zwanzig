// E2E (Staging) — Issue #1719 Scheibe 3, AC-10: der Persistenz-Fix. "Das ist
// der wichtigste Test der Scheibe" (Auftrag Team-Lead-Spawn).
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md AC-10,
//   Abschnitt 4 ("Durchschreibung — und der Persistenz-Fix").
// Kontext: docs/context/fix-1719-s3-aus-ist-ein-zustand.md Abschnitt 10.1
//   ("Der Fund, der die Scheibe rettet").
//
// Der gemessene Defekt: `buildWeatherPayload` (WeatherMetricsTab.svelte:754-767)
// serialisiert HEUTE nur `channelBuckets[activeChannel]`. Steht der Nutzer
// beim globalen Abwählen im E-Mail-Reiter, waehrend SMS bereits einen
// eigenstaendigen Kanal-Override traegt, geht dieser SMS-Override beim
// Speichern NIE mit — der Server behaelt den alten, widerspruechlichen
// SMS-Stand (neue ADR-0050-Regel-3-Verletzung, eingebaut von der Scheibe,
// die sie beheben soll). Zwei Zusicherungen zusammen:
//   (1) Durchschreibung: eine globale Abwahl schreibt SOFORT in ALLE
//       vorhandenen Kanal-Overrides (Regel 3, Voraussetzung fuer AC-9).
//   (2) Persistenz: `buildWeatherPayload` serialisiert ALLE nicht-null
//       Kanal-Overrides beim Speichern, nicht nur den aktiven Reiter.
// Dieser Test beweist die END-ZU-END-WIRKUNG beider Fixes zusammen — ueber
// Reload UND die echt zugestellte SMS-Kurzform (`/api/preview`, NICHT der
// Validator-Endpoint).
//
// SCHREIBT NUR — wird in dieser RED-Phase NICHT ausgeführt (Testauflage PO,
// "Das ist KRITISCH!!!!!" — der Lauf gehört in die GREEN-/Verifikationsphase).
//
// Vorbild: metrik-grundauswahl-schneidet-kanal.staging.spec.ts (S2 — derselbe
// Grundmechanismus, dort noch ohne den Persistenz-Fix; dieser Test prueft
// den fehlenden zweiten Teil: das Verhalten NACH Speichern+Reload UND wenn
// der Nutzer NICHT im SMS-Reiter, sondern im E-Mail-Reiter steht).
//
// Ausführen (gegen Staging, aus frontend/, NACH GREEN):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.metrik-abwahl-schreibt-alle-kanaele-durch.staging.config.ts

import { test, expect, type APIRequestContext } from '@playwright/test';

const TRIP_ID = 'e2e-1719-s3-persistenz-fix';

const REPORT_CONFIG = {
	enabled: true,
	morning_enabled: true,
	evening_enabled: true,
	morning_time: '07:00:00',
	evening_time: '18:00:00',
	send_email: true,
	send_telegram: false,
	send_sms: false,
	multi_day_trend_morning: false,
	multi_day_trend_evening: true,
	multi_day_trend_reports: ['evening'],
	show_compact_summary: true,
	show_daylight: true,
	wind_exposition_min_elevation_m: null,
	show_stage_stats: true,
	show_quick_take_tags: true,
	show_stability: true,
	show_highlights: true,
	daily_summary_metrics: ['precipitation', 'wind', 'visibility', 'thunder'],
	show_metrics_summary: false,
	show_outlook: true,
	email_format: 'full',
	show_yesterday_comparison: true
};

async function createTrip(request: APIRequestContext) {
	await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	await request.post('/api/trips', {
		data: {
			id: TRIP_ID,
			name: 'E2E #1719 S3 Persistenz-Fix',
			report_config: REPORT_CONFIG,
			display_config: {
				metrics: [
					{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 },
					{ metric_id: 'precipitation', enabled: true, bucket: 'primary', order: 1 },
					{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 2 }
				]
			},
			stages: [
				{
					id: `${TRIP_ID}-stage-1`,
					name: 'Etappe 1',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [
						{ id: `${TRIP_ID}-wp-1`, name: 'Start', lat: 46.5, lon: 8.1, elevation_m: 1800 },
						{ id: `${TRIP_ID}-wp-2`, name: 'Ziel', lat: 46.6, lon: 8.2, elevation_m: 2400 }
					]
				}
			]
		}
	});
}

test.describe('Issue #1719 S3 AC-10: globale Abwahl im E-Mail-Reiter schreibt auch einen bereits eigenständigen SMS-Kanal durch', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
	});

	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	test('SMS-Reiter geöffnet (Kanal-Ebene existiert) -> zurück zu E-Mail -> dort global abwählen -> speichern -> Reload: SMS-Reiter UND zugestellte SMS-Kurzform sind ohne "gust"', async ({
		page,
		request
	}) => {
		await createTrip(request);
		await page.goto(`/trips/${TRIP_ID}?tab=weather`);
		await page.getByTestId('trip-detail-tab-weather').click();
		const tab = page.getByTestId('weather-metrics-tab');
		await expect(tab).toBeVisible({ timeout: 10_000 });
		await expect(tab.getByTestId('wm2-grundauswahl').locator('.toggle-btn').first()).toBeVisible({
			timeout: 10_000
		});

		// SMS-Reiter öffnen und EDITIEREN ("precipitation" dort abwählen) -> erst
		// eine echte Editier-Geste (nicht der bloße Tab-Wechsel) löst das
		// Copy-on-write aus (editActiveChannel, WeatherMetricsTab.svelte) und legt
		// die SMS-Kanal-Kopie an ("gust" bleibt darin aktiv, "precipitation" wird
		// SMS-eigen abgewählt). Diese Kopie existiert danach eigenständig in
		// channelBuckets.sms — Vorbild: metrik-grundauswahl-schneidet-kanal.staging.spec.ts (S2).
		await tab.getByTestId('channel-tab-sms').click();
		const precipRow = tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="precipitation"]');
		await expect(precipRow).toBeVisible();
		await precipRow.getByRole('button', { name: 'Aus' }).click();
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		// Zurück zum E-Mail-Reiter -- HIER steht der Nutzer beim Abwählen (AC-10-Kern:
		// activeChannel ist "email", NICHT "sms").
		await tab.getByTestId('channel-tab-email').click();

		// Grundauswahl: "gust" (Böen) global abwählen.
		const gustToggle = tab.locator('[data-testid="wm2-grundauswahl"] .toggle-btn[title="Böen"]');
		await expect(gustToggle).toHaveClass(/\bon\b/);
		await gustToggle.click();
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		// 🔴 Mutations-Gegenprobe M1 (Fund aus der GREEN-Phase, 2026-08-11): der
		// RAW gespeicherte Stand muss geprüft werden, NICHT nur die Anzeige. Das
		// Frontend filtert die Kanal-Anzeige defensiv gegen die aktuelle globale
		// Auswahl (channelListSections/splitChannelMetricsForDisplay) — diese
		// Filterung würde einen kaputten Persistenz-Fix (M1: buildWeatherPayload
		// serialisiert wieder nur activeChannel) an der ANZEIGE vollständig
		// maskieren, weil "gust" ohnehin schon über die globale Metrik-Liste
		// herausgefiltert wird. Der einzige Ort, an dem M1 sichtbar wird, ist der
		// GESPEICHERTE `channel_layouts.sms`-Stand selbst — deshalb hier direkt
		// per API prüfen, bevor überhaupt reloaded wird (Vorbild:
		// layout-tab-route.spec.ts:453-463, #1575-Bestandstest).
		const savedTrip = await (await request.get(`/api/trips/${TRIP_ID}`)).json();
		const savedSmsLayout = savedTrip.display_config?.channel_layouts?.sms ?? [];
		const savedSmsActiveIds = savedSmsLayout
			.filter((m: { enabled: boolean }) => m.enabled)
			.map((m: { metric_id: string }) => m.metric_id);
		expect(
			savedSmsActiveIds,
			'AC-10 FAIL (M1): der GESPEICHERTE SMS-Kanal-Layout-Stand enthält "gust" noch als aktiv — ' +
				'buildWeatherPayload hat beim Speichern (Nutzer stand im E-Mail-Reiter) nicht den vollständigen ' +
				'channelBuckets-Stand serialisiert, nur den aktiven Kanal. Die Editor-ANZEIGE würde das durch ' +
				'defensive Filterung gegen die globale Auswahl trotzdem korrekt zeigen — nur der gespeicherte ' +
				'Stand verrät den Fehler.'
		).not.toContain('gust');

		// Reload -> der SMS-Reiter (NICHT der zuletzt aktive E-Mail-Reiter) zeigt
		// "gust" weder aktiv noch in der Aus-Gruppe (AC-8: global abgewählt heisst
		// nirgends mehr erreichbar).
		await page.reload();
		await page.getByTestId('trip-detail-tab-weather').click();
		const reloaded = page.getByTestId('weather-metrics-tab');
		await expect(reloaded.getByTestId('wm2-grundauswahl').locator('.toggle-btn').first()).toBeVisible({
			timeout: 10_000
		});
		await reloaded.getByTestId('channel-tab-sms').click();
		await expect(
			reloaded.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="gust"]'),
			'AC-10 FAIL: "gust" darf nach Reload im SMS-Reiter nicht mehr aktiv sein — ' +
				'ohne den Persistenz-Fix serialisiert buildWeatherPayload nur den aktiven (E-Mail-)Kanal, ' +
				'der SMS-Server-Stand bleibt der alte, widersprüchliche'
		).toHaveCount(0);
		await expect(
			reloaded.getByTestId('wm2-aus-gruppe').locator('[data-testid="wm2-aus-row"][data-metric-id="gust"]'),
			'AC-10 FAIL: "gust" ist GLOBAL abgewählt und darf auch nicht in der SMS-Aus-Gruppe auftauchen'
		).toHaveCount(0);

		// Zugestellte Ausgabe: der echte Versandweg-Renderpfad (api/routers/preview.py),
		// NICHT der Validator-Endpoint. "gust" -> SMS-Kürzel 'G'.
		const res = await request.get(`/api/preview/${TRIP_ID}/sms?type=morning&demo=true`);
		expect(res.ok(), `preview HTTP ${res.status()}`).toBeTruthy();
		const body = (await res.json()) as { token_line: string };
		expect(
			/(^|\s)G\d/.test(body.token_line),
			`AC-10 FAIL: 'gust' (Kürzel 'G') erscheint trotz globaler Abwahl im E-Mail-Reiter in der zugestellten SMS-Vorschau: ${body.token_line}`
		).toBe(false);
	});
});

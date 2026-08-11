// E2E (Staging) — Issue #1719 Scheibe 2 AC-10 Test B: die real erreichbare
// Editor-Sequenz aus K1 (Kontext-Dokument) wird GEKLICKT, nicht konstruiert.
// SMS-Kanal-Reiter editieren (erzeugt die Kanal-Kopie, copy-on-write,
// WeatherMetricsTab.svelte:638) -> zurück zur (immer sichtbaren)
// Grundauswahl -> dort die Ziel-Metrik abwählen -> speichern -> zugestellte
// SMS-Kurzform (api/routers/preview.py, echter format_email()-Renderpfad)
// darf die Metrik nicht mehr führen.
//
// Läuft bewusst gegen den UNVERÄNDERTEN Editor (S3 behebt "Aus ist ein
// Zustand" erst später) — der Klickpfad beweist die S2-Zusicherung (die
// zugestellte Ausgabe folgt der Grundauswahl), nicht ADR-0050 Regel 4.
//
// Vorbilder: weather-metrics-tab-autosave.spec.ts (createTrip/report_config-
// Normalisierung gegen den Mount-Effekt-Autosave), layout-tab-route.spec.ts
// (channel-tab-*, wm2-reihenfolge-row, "Aus"-Button), issue-776-metrics-
// toggle.spec.ts (Testaufbau-Konventionen).
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.metrik-grundauswahl-schneidet-kanal.staging.config.ts

import { test, expect, type APIRequestContext } from '@playwright/test';

const TRIP_ID = 'e2e-1719-s2-kaskade';

// Vorab-normalisierter report_config-Blob (exakt wie layout-tab-route.spec.ts):
// verhindert, dass EditReportConfigSections Mount-Effekt einen Auto-Save mit
// noch-leeren buckets schedult und die Metriken-Seed überschreibt.
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
			name: 'E2E #1719 S2 Kaskade',
			report_config: REPORT_CONFIG,
			display_config: {
				metrics: [
					{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 },
					{ metric_id: 'precipitation', enabled: true, bucket: 'primary', order: 1 }
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

test.describe('Issue #1719 S2 AC-10 Test B: Grundauswahl-Abwahl schneidet SMS-Kanal-Kopie', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
	});

	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	test('SMS-Reiter-Edit + Grundauswahl-Abwahl -> "gust" verschwindet aus der zugestellten SMS-Vorschau', async ({
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

		// SMS-Kanal-Reiter öffnen UND editieren -> copy-on-write legt die
		// SMS-Kanal-Kopie als Snapshot der Grundauswahl an (gust bleibt darin
		// aktiv -- nur precipitation wird IN DIESER Kopie entfernt).
		await tab.getByTestId('channel-tab-sms').click();
		const precipRow = tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="precipitation"]');
		await expect(precipRow).toBeVisible();
		await precipRow.getByRole('button', { name: 'Aus' }).click();
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		// Zurück zur Grundauswahl (kanalunabhängig immer sichtbar) -> Ziel-Metrik
		// dort abwählen ("[title]" statt Text: "Böen" wäre sonst kein Substring-
		// Kollisionsrisiko, aber title ist der robustere, geprüfte Anker).
		const gustToggle = tab.locator('[data-testid="wm2-grundauswahl"] .toggle-btn[title="Böen"]');
		await expect(gustToggle).toHaveClass(/\bon\b/);
		await gustToggle.click();
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		// Zugestellte Ausgabe: der echte Versandweg-Renderpfad (format_email(),
		// api/routers/preview.py), NICHT der Validator-Endpoint.
		const res = await request.get(`/api/preview/${TRIP_ID}/sms?type=morning&demo=true`);
		expect(res.ok(), `preview HTTP ${res.status()}`).toBeTruthy();
		const body = (await res.json()) as { token_line: string };
		expect(
			/(^|\s)G\d/.test(body.token_line),
			`'gust' (Kürzel 'G') erscheint trotz globaler Abwahl in der zugestellten SMS-Vorschau: ${body.token_line}`
		).toBe(false);
	});
});

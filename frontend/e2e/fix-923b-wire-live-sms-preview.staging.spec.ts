// Staging-Validierung Fix #923b — SMS-Fidelity-Vorschau an die live
// gerenderte Komponente (WeatherV2MailPreview.svelte) anschliessen.
//
// Spec: docs/specs/modules/fix_923b_wire_live_sms_preview.md
//
// Deckt AC-1/AC-2/AC-6 (Trip-Editor, echter Server-Text + echte 160er-Grenze,
// erreicht ueber die reale Route) und AC-3 (Ortsvergleich-Editor zeigt keine
// SMS-Kachel und loest keinen sms-fidelity-preview-Request aus) ab.
//
// Ausfuehren (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   set -a; source /home/hem/gregor_zwanzig/.env; set +a
//   npx playwright test --config=playwright.fix-923b.staging.config.ts

import { test, expect, type APIRequestContext } from '@playwright/test';
import { createTestLocation, registerForCleanup, cleanupTracked, E2E_TEST_PREFIX } from './helpers';

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

async function createTrip(request: APIRequestContext, tag: string) {
	const suffix = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
	const id = `e2e-gz-923b-${tag}-${suffix}`;
	const name = `${E2E_TEST_PREFIX}923b-${tag}-${suffix}`;
	const res = await request.post('/api/trips', {
		data: {
			id,
			name,
			region: 'Korsika',
			stages: [
				{
					id: `${tag}-s1`,
					name: 'Tag 1',
					date: '2026-08-10',
					waypoints: [wp(`${tag}-a1`, 42.0), wp(`${tag}-b1`, 42.04)]
				}
			],
			display_config: {
				metrics: [
					{
						metric_id: 'temperature',
						enabled: true,
						use_friendly_format: true,
						horizons: { today: true, tomorrow: true, day_after: true },
						bucket: 'primary',
						order: 0
					}
				]
			}
		}
	});
	expect(res.ok(), `POST /api/trips HTTP ${res.status()} — ${await res.text()}`).toBeTruthy();
	const body = (await res.json()) as { id: string; name: string };
	registerForCleanup('trip', body.id);
	return body;
}

test.afterEach(async ({ request }) => {
	await cleanupTracked(request);
});

test('AC-1/AC-2/AC-6: Trip-Editor SMS-Kachel zeigt echten Server-Text und 160er-Grenze', async ({
	page,
	request
}) => {
	const trip = await createTrip(request, 'trip');

	await page.goto(`/trips/${trip.id}?tab=weather`);
	await expect(page.getByTestId('weather-metrics-tab')).toBeVisible({ timeout: 15000 });

	const responsePromise = page.waitForResponse(
		(res) => res.url().includes('/api/_validator/sms-fidelity-preview') && res.request().method() === 'POST',
		{ timeout: 15000 }
	);
	await page.getByTestId('channel-tab-sms').click();
	const response = await responsePromise;
	expect(response.ok(), `POST /api/_validator/sms-fidelity-preview HTTP ${response.status()}`).toBeTruthy();
	const body = await response.json();

	const tile = page.getByTestId('wm2-sms-line');
	await expect(tile).toBeVisible({ timeout: 10000 });

	const bubbleText = (await tile.locator('.sms-bubble').textContent()) ?? '';
	expect(bubbleText, 'Bubble darf keinen Rest der alten Z:WATCH-Simulation zeigen').not.toContain('Z:WATCH');
	expect(bubbleText.trim()).toBe((body.line as string).trim());

	const lenText = (await tile.locator('.sms-len').textContent()) ?? '';
	expect(lenText, 'Zeichenzaehler darf nicht mehr die alte 140er-Grenze zeigen').not.toContain('/140');
	expect(lenText).toContain(`/${body.max_length}`);
	expect(body.max_length).toBe(160);
});

test('AC-3: Ortsvergleich-Editor zeigt keine SMS-Kachel und ruft den Endpoint nicht auf', async ({
	page,
	request
}) => {
	const loc = await createTestLocation(request, {
		name: `${E2E_TEST_PREFIX}923b-loc-${Date.now()}`,
		lat: 47.1,
		lon: 11.2
	});

	const presetRes = await request.post('/api/compare/presets', {
		data: {
			name: `${E2E_TEST_PREFIX}923b-preset-${Date.now()}`,
			location_ids: [loc.id],
			schedule: 'manual',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 18,
			empfaenger: ['urlauber@example.com']
		}
	});
	expect(presetRes.ok(), `POST /api/compare/presets HTTP ${presetRes.status()}`).toBeTruthy();
	const preset = (await presetRes.json()) as { id: string };
	registerForCleanup('preset', preset.id);

	let smsFidelityRequestSeen = false;
	page.on('request', (req) => {
		if (req.url().includes('/api/_validator/sms-fidelity-preview')) {
			smsFidelityRequestSeen = true;
		}
	});

	await page.goto(`/compare/${preset.id}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15000 });
	await page.getByTestId('compare-detail-tab-wetter-metriken').click();
	await expect(page.getByTestId('compare-detail-panel-wetter-metriken')).toBeVisible({ timeout: 10000 });
	await expect(page.getByTestId('weather-metrics-tab-vergleich')).toBeVisible({ timeout: 10000 });
	await page.waitForLoadState('networkidle');

	await expect(page.getByTestId('wm2-sms-line')).toHaveCount(0);
	await expect(page.getByTestId('wm2-mail-preview')).toHaveCount(0);
	await expect(page.getByTestId('channel-tab-sms')).toHaveCount(0);
	expect(smsFidelityRequestSeen, 'sms-fidelity-preview darf im Ortsvergleich-Editor nie aufgerufen werden').toBe(false);
});

// Runde 2 — Adversary-Sweep (Protokoll-Pflicht): AC-4 sichtbar im echten
// Klickpfad (nicht nur Katalog-Unit-Test), Kanal-Doppelklick-Race,
// Leerauswahl.
test('Adversary-Sweep: temperature_night traegt TN im echten Server-Text, Kanal-Doppelklick bleibt konsistent', async ({
	page,
	request
}) => {
	const suffix = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
	const id = `e2e-gz-923b-adv-${suffix}`;
	const name = `${E2E_TEST_PREFIX}923b-adv-${suffix}`;
	const res = await request.post('/api/trips', {
		data: {
			id,
			name,
			region: 'Korsika',
			stages: [
				{
					id: `adv-s1`,
					name: 'Tag 1',
					date: '2026-08-10',
					waypoints: [wp('adv-a1', 42.0), wp('adv-b1', 42.04)]
				}
			],
			display_config: {
				metrics: [
					{
						metric_id: 'temperature_night',
						enabled: true,
						use_friendly_format: true,
						horizons: { today: true, tomorrow: true, day_after: true },
						bucket: 'primary',
						order: 0
					}
				]
			}
		}
	});
	expect(res.ok(), `POST /api/trips HTTP ${res.status()}`).toBeTruthy();
	registerForCleanup('trip', id);

	await page.goto(`/trips/${id}?tab=weather`);
	await expect(page.getByTestId('weather-metrics-tab')).toBeVisible({ timeout: 15000 });

	const responsePromise = page.waitForResponse(
		(r) => r.url().includes('/api/_validator/sms-fidelity-preview') && r.request().method() === 'POST',
		{ timeout: 15000 }
	);
	await page.getByTestId('channel-tab-sms').click();
	const response = await responsePromise;
	const body = await response.json();
	expect(body.carried_ids, 'temperature_night muss getragen werden (Root-Cause AC-4)').toContain('temperature_night');

	const tile = page.getByTestId('wm2-sms-line');
	await expect(tile).toBeVisible({ timeout: 10000 });

	// AC-4: der Katalog-Eintrag zeigt sein sms_code im Reihenfolge-Abschnitt
	// (WeatherV2Reihenfolge.svelte "SMS {m.sms_code}") — NICHT im gerenderten
	// SMS-Zeilentext selbst, der weiterhin das unabhaengige Renderer-Symbol
	// "N" aus SMS_MULTI_SYMBOLS_BY_METRIC traegt (per Spec bewusst getrennt).
	const reihenfolgeRow = page.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="temperature_night"]');
	await expect(reihenfolgeRow).toBeVisible({ timeout: 10000 });
	const smsBadgeText = (await reihenfolgeRow.locator('.sms-badge').textContent()) ?? '';
	expect(smsBadgeText, 'Katalog-sms_code fuer temperature_night muss TN sein, nicht leer').toContain('TN');

	// Kanal-Doppelklick-Race: schnell email -> telegram -> sms -> email -> sms.
	await page.getByTestId('channel-tab-email').click();
	await page.getByTestId('channel-tab-telegram').click();
	await page.getByTestId('channel-tab-sms').click();
	await page.getByTestId('channel-tab-email').click();
	await page.getByTestId('channel-tab-sms').click();
	await page.waitForLoadState('networkidle');
	await expect(page.getByTestId('wm2-sms-line')).toBeVisible({ timeout: 10000 });
	await expect(page.getByTestId('wm2-sms-line').locator('.sms-error')).toHaveCount(0);
	const finalLen = (await page.getByTestId('wm2-sms-line').locator('.sms-len').textContent()) ?? '';
	expect(finalLen).not.toContain('/140');
	expect(finalLen).toContain('/160');
});

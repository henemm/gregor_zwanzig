// E2E-Tests für Issue #736 — Reiter-Reorganisation "Inhalt" vs. "Versand".
//
// Spec: docs/specs/modules/issue_736_tabs_reorg.md
// Workflow: issue-736-tabs-reorg
//
// Ziel-Oberfläche: /trips/[id]?tab=weather (Inhalt-Reiter) und
//                  /trips/[id]?tab=briefings (Versand-Reiter)
//
// Diese Tests sind RED bis die Reorganisation implementiert ist:
//   - Tab-Labels heißen noch "Wetter-Metriken" / "Briefing-Zeitplan"
//   - Kanal-Toggle liegt noch in ?tab=weather (nicht in ?tab=briefings)
//   - E-Mail-Inhalt liegt noch in ?tab=briefings (nicht in ?tab=weather)
//   - Schwellwerte-Abschnitt heißt noch "SMS-Schwellwerte"

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-issue-736';
const tripId = (suffix: string) => `${TRIP_PREFIX}-${suffix}`;

async function createTrip(
	request: APIRequestContext,
	id: string,
	options: {
		channels?: { email: boolean; telegram: boolean; sms: boolean };
		report_config?: Record<string, unknown>;
	} = {}
) {
	const channels = options.channels ?? { email: true, telegram: false, sms: false };
	const report_config = options.report_config ?? {
		enabled: true,
		morning_time: '07:00',
		evening_time: '18:00',
		send_email: channels.email,
		send_telegram: channels.telegram,
		send_sms: channels.sms
	};
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 736 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [
						{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 },
						{ id: `${id}-wp-2`, name: 'Ziel', lat: 42.2, lon: 9.1, elevation_m: 900 }
					]
				}
			],
			display_config: { channels },
			report_config,
			alert_rules: []
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string) {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

async function openTab(page: Page, id: string, tab: 'weather' | 'briefings') {
	await page.goto(`/trips/${id}?tab=${tab}`);
	await page.locator(`[data-testid="trip-detail-tab-${tab}"]`).waitFor({ state: 'visible' });
}

test.describe('Issue #736: Reiter-Reorganisation "Inhalt" vs. "Versand"', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ── AC-1: Tab-Labels "Inhalt" und "Versand" ──────────────────────────────────
	test('AC-1: Tab weather heißt "Inhalt", Tab briefings heißt "Versand"', async ({
		page,
		request
	}) => {
		const id = tripId('ac1');
		await createTrip(request, id);
		try {
			await page.goto(`/trips/${id}`);
			await page.locator('[data-testid="trip-detail-tab-list"]').waitFor({ state: 'visible' });

			// Labels prüfen
			await expect(page.locator('[data-testid="trip-detail-tab-weather"]')).toContainText('Inhalt');
			await expect(page.locator('[data-testid="trip-detail-tab-briefings"]')).toContainText('Versand');

			// URL-Parameter aktivieren richtigen Reiter
			await page.goto(`/trips/${id}?tab=weather`);
			await expect(page.locator('[data-testid="trip-detail-tab-weather"]')).toHaveAttribute(
				'data-state',
				'active'
			);

			await page.goto(`/trips/${id}?tab=briefings`);
			await expect(page.locator('[data-testid="trip-detail-tab-briefings"]')).toHaveAttribute(
				'data-state',
				'active'
			);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-2: Inhalt-Reiter hat E-Mail-Inhalt, kein Kanal-Toggle ───────────────
	test('AC-2: Inhalt-Reiter zeigt E-Mail-Inhalt-Karte, aber keinen Kanal-Toggle', async ({
		page,
		request
	}) => {
		const id = tripId('ac2');
		await createTrip(request, id);
		try {
			await openTab(page, id, 'weather');
			await page.locator('[data-testid="weather-metrics-tab"]').waitFor({ state: 'visible' });

			// Kein Kanal-Toggle im Inhalt-Reiter
			await expect(page.locator('[data-testid="channel-email"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="channel-telegram"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="channel-sms"]')).toHaveCount(0);

			// E-Mail-Inhalt-Karte vorhanden
			await expect(page.locator('[data-testid="report-mail-content"]')).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-3: Versand-Reiter hat Kanäle genau einmal, kein E-Mail-Inhalt ────────
	test('AC-3: Versand-Reiter hat Kanal-Checkboxen genau einmal, keine E-Mail-Inhalt-Karte', async ({
		page,
		request
	}) => {
		const id = tripId('ac3');
		await createTrip(request, id, { channels: { email: true, telegram: true, sms: false } });
		try {
			await openTab(page, id, 'briefings');
			await page.locator('[data-testid="briefings-save"]').waitFor({ state: 'visible' });

			// Kanal-Checkboxen genau einmal
			await expect(page.locator('[data-testid="channel-email"]')).toHaveCount(1);
			await expect(page.locator('[data-testid="channel-telegram"]')).toHaveCount(1);

			// Keine E-Mail-Inhalt-Karte im Versand-Reiter
			await expect(page.locator('[data-testid="report-mail-content"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-4: Kanal-Toggle setzt display_config + report_config synchron ────────
	test('AC-4: E-Mail aktivieren im Versand-Reiter setzt beide Persistenz-Felder', async ({
		page,
		request
	}) => {
		const id = tripId('ac4');
		// Trip mit E-Mail initial deaktiviert
		await createTrip(request, id, {
			channels: { email: false, telegram: false, sms: false },
			report_config: {
				enabled: false,
				morning_time: '07:00',
				evening_time: '18:00',
				send_email: false,
				send_telegram: false,
				send_sms: false
			}
		});
		try {
			await openTab(page, id, 'briefings');
			await page.locator('[data-testid="briefings-save"]').waitFor({ state: 'visible' });

			// E-Mail-Checkbox aktivieren
			await page.locator('[data-testid="channel-email"]').getByRole('checkbox').check();

			// Speichern
			await page.waitForResponse(
				(r) => r.url().includes(`/api/trips/${id}`) && r.request().method() === 'PUT'
			);
			await page.locator('[data-testid="briefings-save"]').click();
			await page.waitForResponse(
				(r) => r.url().includes(`/api/trips/${id}`) && r.request().method() === 'PUT'
			);

			// Beide Felder prüfen
			const tripRes = await request.get(`/api/trips/${id}`);
			expect(tripRes.ok()).toBeTruthy();
			const trip = await tripRes.json();
			// display_config.channels.email UND report_config.send_email müssen true sein
			expect(trip.display_config?.channels?.email).toBe(true);
			expect(trip.report_config?.send_email).toBe(true);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-5: "Schwellwerte" — nicht "SMS-Schwellwerte" ─────────────────────────
	test('AC-5: Schwellwerte-Abschnitt heißt nicht "SMS-Schwellwerte", sondern "Schwellwerte" mit Hinweis', async ({
		page,
		request
	}) => {
		const id = tripId('ac5');
		await createTrip(request, id);
		try {
			await openTab(page, id, 'weather');
			await page.locator('[data-testid="weather-metrics-tab"]').waitFor({ state: 'visible' });

			// "SMS-Schwellwerte" darf NICHT vorkommen
			await expect(page.getByText('SMS-Schwellwerte', { exact: false })).toHaveCount(0);

			// Issue #872: Eyebrow heißt "04 — Schwellwerte"
			await expect(page.getByText('04 — Schwellwerte', { exact: false })).toBeVisible();

			// Issue #872: Hinweis-Text nennt SMS-Token; alter Text ist weg
			const thresholdsText = await page
				.locator('[data-testid="sms-thresholds"]')
				.textContent();
			await expect(
				page.getByText('Gelten für E-Mail, Telegram und SMS', { exact: false })
			).toHaveCount(0);
			await expect(page.getByText('SMS-Token', { exact: false })).toBeVisible();
			expect(thresholdsText).toContain('SMS-Token');

			// Issue #872: Segmented-Control statt Freitext-Input
			await expect(
				page.locator('[data-testid="threshold-level-wind-standard"]')
			).toBeVisible();
			await expect(
				page.locator('[data-testid="threshold-level-thunder-high"]')
			).toBeVisible();
			// Alter Freitext-Input ist weg
			await expect(page.locator('[data-testid="sms-threshold-wind"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-6: Bestehender Zustand wird beim Öffnen korrekt angezeigt ─────────────
	test('AC-6: gespeicherter Kanal-Zustand wird im Versand-Reiter korrekt initialisiert', async ({
		page,
		request
	}) => {
		const id = tripId('ac6');
		// email=false, telegram=true gespeichert
		await createTrip(request, id, {
			channels: { email: false, telegram: true, sms: false },
			report_config: {
				enabled: true,
				morning_time: '07:00',
				evening_time: '18:00',
				send_email: false,
				send_telegram: true,
				send_sms: false
			}
		});
		try {
			await openTab(page, id, 'briefings');
			await page.locator('[data-testid="briefings-save"]').waitFor({ state: 'visible' });

			// E-Mail-Checkbox muss ungehakt sein
			await expect(
				page.locator('[data-testid="channel-email"]').getByRole('checkbox')
			).not.toBeChecked();

			// Telegram-Checkbox muss gehakt sein
			await expect(
				page.locator('[data-testid="channel-telegram"]').getByRole('checkbox')
			).toBeChecked();
		} finally {
			await deleteTrip(request, id);
		}
	});
});

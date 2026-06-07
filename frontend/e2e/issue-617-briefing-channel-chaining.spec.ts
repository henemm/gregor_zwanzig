// E2E-Tests für Issue #617 — Briefing-Zeitplan: Kanal-Verkettung aus Wetter-Metriken.
//
// Spec: docs/specs/modules/issue_617_briefing_channel_chaining.md
// Workflow: issue-617-kanal-verkettung
//
// Ziel-Oberfläche: /trips/[id]?tab=briefings (BriefingScheduleTab →
// EditReportConfigSection.svelte). Die im Wetter-Metriken-Tab gesetzten Kanäle
// (display_config.channels) steuern, welche Kanäle hier erscheinen.
//
// Erwartete neue TestIDs (aus der Spec):
//   briefings-channel-hint        — Hinweis-Banner mit aktiven Kanälen (AC-2)
//   briefings-channel-empty       — Warnzustand bei 0 aktiven Kanälen (AC-3)
//   briefings-channel-empty-link  — Rücksprung-Link zum Wetter-Metriken-Tab (AC-3)
// Bestehende TestIDs: channel-email / channel-telegram / channel-sms, briefings-save
//
// Diese Tests sind RED bis die Verkettung existiert. Cleanup inline (DELETE).

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-issue-617';
const tripId = (suffix: string) => `${TRIP_PREFIX}-${suffix}`;

type Channels = { email: boolean; telegram: boolean; sms: boolean };

async function createTrip(
	request: APIRequestContext,
	id: string,
	channels: Channels,
	report_config: Record<string, unknown> = {
		enabled: true,
		morning_time: '07:00',
		evening_time: '18:00'
	}
) {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 617 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
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

async function openBriefings(page: Page, id: string) {
	await page.goto(`/trips/${id}?tab=briefings`);
	await page.getByTestId('briefings-save').waitFor({ state: 'visible', timeout: 8000 });
}

test.describe('Issue #617: Briefing-Zeitplan Kanal-Verkettung', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ── AC-1 ───────────────────────────────────────────────────────────────
	test('AC-1: nur Wetter-aktive Kanäle erscheinen, SMS (aus) fehlt', async ({ page, request }) => {
		const id = tripId('ac1');
		await createTrip(request, id, { email: true, telegram: true, sms: false });
		try {
			await openBriefings(page, id);
			await expect(page.getByTestId('channel-email')).toBeVisible();
			await expect(page.getByTestId('channel-telegram')).toBeVisible();
			await expect(page.getByTestId('channel-sms')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-2 ───────────────────────────────────────────────────────────────
	test('AC-2: Hinweis-Banner nennt die aktiven Kanäle', async ({ page, request }) => {
		const id = tripId('ac2');
		await createTrip(request, id, { email: true, telegram: true, sms: false });
		try {
			await openBriefings(page, id);
			const hint = page.getByTestId('briefings-channel-hint');
			await expect(hint).toBeVisible();
			await expect(hint).toContainText('Wetter-Metriken');
			await expect(hint).toContainText('Email');
			await expect(hint).toContainText('Telegram');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-3 ───────────────────────────────────────────────────────────────
	test('AC-3: kein Kanal aktiv → Warnzustand + Rücksprung zu Wetter-Metriken', async ({
		page,
		request
	}) => {
		const id = tripId('ac3');
		await createTrip(request, id, { email: false, telegram: false, sms: false });
		try {
			await openBriefings(page, id);
			await expect(page.getByTestId('briefings-channel-empty')).toBeVisible();
			await expect(page.getByTestId('channel-email')).toHaveCount(0);
			await page.getByTestId('briefings-channel-empty-link').click();
			await expect(page).toHaveURL(/[?&]tab=weather/);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-4 ───────────────────────────────────────────────────────────────
	test('AC-4: verwaister send_sms wird beim Speichern aus, übrige Felder bleiben', async ({
		page,
		request
	}) => {
		const id = tripId('ac4');
		await createTrip(
			request,
			id,
			{ email: true, telegram: true, sms: false },
			{ enabled: true, morning_time: '07:00', evening_time: '18:00', send_sms: true }
		);
		try {
			await openBriefings(page, id);
			await page.getByTestId('briefings-save').click();
			await page.waitForResponse(
				(r) => r.url().includes(`/api/trips/${id}`) && r.request().method() === 'PUT'
			);
			const res = await request.get(`/api/trips/${id}`);
			expect(res.ok()).toBeTruthy();
			const trip = await res.json();
			expect(trip.report_config?.send_sms).toBe(false);
			expect(String(trip.report_config?.evening_time)).toMatch(/^18:00/);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-5 ───────────────────────────────────────────────────────────────
	test('AC-5: Wahl unter aktiven Kanälen bleibt nach Reload erhalten', async ({
		page,
		request
	}) => {
		const id = tripId('ac5');
		await createTrip(
			request,
			id,
			{ email: true, telegram: true, sms: false },
			{ enabled: true, morning_time: '07:00', evening_time: '18:00', send_email: true, send_telegram: true }
		);
		try {
			await openBriefings(page, id);
			// Telegram abwählen (Checkbox innerhalb channel-telegram)
			await page.getByTestId('channel-telegram').getByRole('checkbox').uncheck();
			await page.getByTestId('briefings-save').click();
			await page.waitForResponse(
				(r) => r.url().includes(`/api/trips/${id}`) && r.request().method() === 'PUT'
			);
			await openBriefings(page, id);
			await expect(page.getByTestId('channel-email').getByRole('checkbox')).toBeChecked();
			await expect(page.getByTestId('channel-telegram').getByRole('checkbox')).not.toBeChecked();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-7 (Multi-Trip-Isolation; Cross-User via staging-validator + Account-Scope) ──
	test('AC-7: zwei Trips mit unterschiedlichen Kanälen zeigen je ihre eigenen', async ({
		page,
		request
	}) => {
		const a = tripId('ac7a');
		const b = tripId('ac7b');
		await createTrip(request, a, { email: true, telegram: false, sms: false });
		await createTrip(request, b, { email: false, telegram: true, sms: false });
		try {
			await openBriefings(page, a);
			await expect(page.getByTestId('channel-email')).toBeVisible();
			await expect(page.getByTestId('channel-telegram')).toHaveCount(0);

			await openBriefings(page, b);
			await expect(page.getByTestId('channel-telegram')).toBeVisible();
			await expect(page.getByTestId('channel-email')).toHaveCount(0);
		} finally {
			await deleteTrip(request, a);
			await deleteTrip(request, b);
		}
	});
});

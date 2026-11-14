// E2E — Issue #2069 AC-8: Beispiel-Warnung im Alarme-Reiter.
//
// Spec: docs/specs/modules/alert_preview_echte_segmente.md (AC-8)
// Workflow: fix-2069-alert-preview-echte-segmente
//
// (a) Trip ohne eine einzige Etappe mit mindestens 2 Wegpunkten: AlertPreviewCard
//     zeigt den Hinweis `alert-preview-no-stages` statt eines Fehlertexts und ruft
//     die Alarm-Vorschau NICHT ab (Pendant zu `alert-preview-no-locations`).
// (b) Geplanter Trip (erste Etappe in 5 Tagen, nicht heute): die Beispiel-Warnung
//     erscheint weiterhin, mit echter Ortsangabe statt Platzhalter.
//
// Echter Klick-Pfad wie versand-tab.spec.ts: Trip öffnen → Reiter Zustellung.

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { login } from './helpers.js';

const PREFIX = 'e2e-2069-alarm-vorschau';
const tripId = (s: string) => `${PREFIX}-${s}`;

function isoInTagen(tage: number): string {
	const d = new Date();
	d.setDate(d.getDate() + tage);
	return d.toISOString().slice(0, 10);
}

const ALERT_FELDER = {
	display_config: { metric_alert_levels: { wind_gust: 'standard' } },
	alert_rules: [
		{ id: 'r1', kind: 'absolute', metric: 'wind_gust', threshold: 50, severity: 'warning', enabled: true }
	]
};

async function createTrip(request: APIRequestContext, id: string, waypoints: object[]): Promise<void> {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 2069 ${id}`,
			stages: [{ id: `${id}-T1`, name: 'Etappe 1', date: isoInTagen(5), waypoints }],
			...ALERT_FELDER
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function openZustellung(page: Page, id: string): Promise<void> {
	await page.goto(`/trips/${id}`);
	await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible();
	await page.getByTestId('trip-detail-tab-zustellung').first().click();
	await expect(page.getByTestId('trip-detail-panel-zustellung')).toBeVisible();
}

test.describe('Issue #2069 AC-8 — Beispiel-Warnung mit echten Etappen', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test.afterEach(async ({ page }) => {
		for (const s of ['ohne-etappe', 'geplant']) {
			await page.request.delete(`/api/trips/${tripId(s)}`);
		}
	});

	test('Trip ohne Etappe mit 2 Wegpunkten: Hinweis statt Fehler, kein Abruf', async ({ page }) => {
		await createTrip(page.request, tripId('ohne-etappe'), [
			{ id: 'G1', name: 'Start', lat: 47.0, lon: 11.0, elevation_m: 1000 }
		]);
		const abrufe: string[] = [];
		page.on('request', (r) => {
			if (r.url().includes('/alert-preview')) abrufe.push(r.url());
		});

		await openZustellung(page, tripId('ohne-etappe'));
		const karte = page.getByTestId('alert-preview-card');
		await expect(karte.getByTestId('alert-preview-no-stages')).toBeVisible();
		await expect(karte.getByTestId('alert-preview-load-btn')).toHaveCount(0);
		expect(abrufe).toEqual([]);
	});

	test('Geplanter Trip (nicht heute): Beispiel-Warnung erscheint', async ({ page }) => {
		await createTrip(page.request, tripId('geplant'), [
			{ id: 'G1', name: 'Start', lat: 47.0, lon: 11.0, elevation_m: 1000 },
			{ id: 'G2', name: 'Ziel', lat: 47.1, lon: 11.1, elevation_m: 1400 }
		]);

		await openZustellung(page, tripId('geplant'));
		const karte = page.getByTestId('alert-preview-card');
		await expect(karte.getByTestId('alert-preview-no-stages')).toHaveCount(0);
		await karte.getByTestId('alert-preview-load-btn').click();
		await expect(karte.getByTestId('alert-preview-error')).toHaveCount(0);
		await expect(karte.locator('.channel-section').first()).toBeVisible({ timeout: 130_000 });
	});
});

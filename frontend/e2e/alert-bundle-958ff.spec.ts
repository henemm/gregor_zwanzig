// Fix Alert Bundle — #958/#959/#933/#921/#980/#981/#982/#986
// Spec: docs/specs/modules/fix_alert_bundle_958ff.md
//
// Frontend-ACs (#959/#933): AC-5 (Nullgradgrenze-Konsolidierung),
// AC-6 (Empty-State statt Alle-Metriken-Fallback), AC-7 (Regressionsschutz
// gegen die Fallback-Entfernung, nicht-leerer gemappter Fall).
//
// Echter Klick-Pfad + UI-Zustand: Tab-Navigation via ?tab=alerts (analog
// issue-953-alerts-autosave-tabswitch.spec.ts), Trip-Seed via API,
// Assertions über sichtbare data-testid-Zeilen — kein DB-Read.

import { expect, test, type Page } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-958-alerts';

function tripId(suffix: string) {
	return `${TRIP_PREFIX}-${suffix}`;
}

interface SeedOptions {
	metrics: Array<{ metric_id: string; enabled: boolean }>;
	// Issue #946: metric_alert_levels ist die einzige Alert-Quelle — gesetzt
	// (auch leer {}) verlässt den Onboarding-Zustand der AlertsTab.
	metric_alert_levels: Record<string, string>;
}

async function seedTrip(page: Page, id: string, opts: SeedOptions) {
	await page.request.delete(`/api/trips/${id}`).catch(() => {});
	const res = await page.request.post('/api/trips', {
		data: {
			id,
			name: `Issue 958 ${id}`,
			region: 'Korsika',
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: '2026-08-01',
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			display_config: {
				metrics: opts.metrics,
				metric_alert_levels: opts.metric_alert_levels
			}
		}
	});
	expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
}

async function deleteTrip(page: Page, id: string) {
	await page.request.delete(`/api/trips/${id}`).catch(() => {});
}

test.describe('Fix Alert Bundle #958ff — Nullgradgrenze-Konsolidierung + Alertable-Metriken-Filter', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// AC-5 (#959): "Schneefallgrenze" ist keine eigene wählbare Alert-Metrik
	// mehr — nur noch "Nullgradgrenze" (freezing_level).
	test('AC-5: "Schneefallgrenze" ist keine Alert-Metrik-Zeile mehr, "Nullgradgrenze" genau einmal', async ({
		page
	}) => {
		const id = tripId('ac5');
		// Beide zugrundeliegenden Wetter-Metriken aktiv, damit das Ergebnis
		// unabhängig vom AC-6/#933-Fallback-Verhalten ist (isoliert #959).
		await seedTrip(page, id, {
			metrics: [
				{ metric_id: 'freezing_level', enabled: true },
				{ metric_id: 'snowfall_limit', enabled: true }
			],
			metric_alert_levels: { freezing_level: 'standard', snow_line: 'standard' }
		});
		try {
			await page.goto(`/trips/${id}?tab=alerts`);
			await expect(page.getByTestId('alerts-tab')).toBeVisible();

			// Keine eigene "snow_line"-Zeile mehr im DOM.
			await expect(page.getByTestId('alert-metric-row-snow_line')).toHaveCount(0);
			// "freezing_level" (Nullgradgrenze) erscheint genau einmal.
			await expect(page.getByTestId('alert-metric-row-freezing_level')).toHaveCount(1);
			await expect(page.getByText('Schneefallgrenze')).toHaveCount(0);
		} finally {
			await deleteTrip(page, id);
		}
	});

	// AC-6 (#933): keine der aktiven Wetter-Metriken ist einer Alert-Metrik
	// zugeordnet -> 0 Zeilen + Hinweistext statt Alle-Metriken-Fallback.
	test('AC-6: keine gemappte Wetter-Metrik aktiv -> 0 Metrik-Zeilen + Hinweistext', async ({ page }) => {
		const id = tripId('ac6');
		// uv_index ist eine wählbare Wetter-Metrik OHNE Eintrag in
		// CATALOG_TO_ALERT_METRICS (kein Alert-Mapping vorhanden).
		await seedTrip(page, id, {
			metrics: [{ metric_id: 'uv_index', enabled: true }],
			metric_alert_levels: {}
		});
		try {
			await page.goto(`/trips/${id}?tab=alerts`);
			await expect(page.getByTestId('alerts-tab')).toBeVisible();

			await expect(page.locator('[data-testid="alert-metric-level-table"] tbody tr')).toHaveCount(
				0
			);
			await expect(
				page.getByText('Wähle oben Metriken aus, um Alarm-Schwellen zu konfigurieren')
			).toBeVisible();
		} finally {
			await deleteTrip(page, id);
		}
	});

	// AC-7 (#933, Regressionsschutz): genau eine aktive, gemappte Wetter-Metrik
	// -> Tabelle zeigt weiterhin exakt die zugeordnete(n) Alert-Zeile(n).
	test('AC-7: eine gemappte Wetter-Metrik aktiv -> Tabelle zeigt genau die zugeordnete(n) Alert-Zeile(n)', async ({
		page
	}) => {
		const id = tripId('ac7');
		await seedTrip(page, id, {
			metrics: [{ metric_id: 'gust', enabled: true }],
			metric_alert_levels: {}
		});
		try {
			await page.goto(`/trips/${id}?tab=alerts`);
			await expect(page.getByTestId('alerts-tab')).toBeVisible();

			const rows = page.locator('[data-testid="alert-metric-level-table"] tbody tr');
			await expect(rows).toHaveCount(1);
			await expect(page.getByTestId('alert-metric-row-wind_gust')).toBeVisible();
		} finally {
			await deleteTrip(page, id);
		}
	});
});

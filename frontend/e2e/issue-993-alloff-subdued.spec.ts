// Fix Validator Bundle — #997/#921/#993
// Spec: docs/specs/modules/fix_997_validator_bundle.md
//
// AC-6/AC-7 (#993): AlertsTab.svelte:50 —
//   let allOff = $derived(displayMetrics.every((m) => currentLevels[m] === 'off'));
// `[].every(...)` liefert vacuously `true` fuer eine LEERE displayMetrics-Liste
// (seit #933 erreichbar, wenn keine aktive Wetter-Metrik alert-faehig ist) —
// `.extra-cards` (Cooldown-/QuietHours-Karten) wird dadurch faelschlich
// gedaempft (`subdued`), obwohl gar keine Metrik konfiguriert ist.
//
// AC-6: leere displayMetrics -> .extra-cards OHNE subdued (rot gegen
// aktuelles Staging, da der Ist-Code subdued setzt).
// AC-7 (Regressionsschutz, NUR GESCHRIEBEN — nicht ausgefuehrt, siehe
// Team-Lead-Vorgabe): nicht-leere displayMetrics, alle Stufen 'off' ->
// .extra-cards bleibt weiterhin subdued (bestehendes Verhalten unveraendert).
//
// Muster: alert-bundle-958ff.spec.ts (Seed via API, ?tab=alerts, echter
// Klick-/Navigationspfad ueber Trip-Detailseite, kein DB-Read).

import { expect, test, type Page } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-993-alloff';

function tripId(suffix: string) {
	return `${TRIP_PREFIX}-${suffix}`;
}

interface SeedOptions {
	metrics: Array<{ metric_id: string; enabled: boolean }>;
	// Issue #946: metric_alert_levels ist die einzige Alert-Quelle — gesetzt
	// (auch leer {}) verlaesst den Onboarding-Zustand der AlertsTab.
	metric_alert_levels: Record<string, string>;
}

async function seedTrip(page: Page, id: string, opts: SeedOptions) {
	await page.request.delete(`/api/trips/${id}`).catch(() => {});
	const res = await page.request.post('/api/trips', {
		data: {
			id,
			name: `Issue 993 ${id}`,
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

test.describe('Fix #993 — allOff nicht vacuously true bei leerer displayMetrics', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// AC-6: uv_index hat kein Eintrag in CATALOG_TO_ALERT_METRICS (kein
	// Alert-Mapping) -> activeAlertableMetrics() liefert [] -> .extra-cards
	// darf NICHT subdued sein (Ist-Code: subdued, da `[].every(...)` vacuously
	// true liefert — genau der #993-Bug).
	test('AC-6: keine alert-fähige Metrik aktiv -> .extra-cards ohne subdued-Klasse', async ({
		page
	}) => {
		const id = tripId('ac6');
		await seedTrip(page, id, {
			metrics: [{ metric_id: 'uv_index', enabled: true }],
			metric_alert_levels: {}
		});
		try {
			await page.goto(`/trips/${id}?tab=alerts`);
			await expect(page.getByTestId('alerts-tab')).toBeVisible();
			// Bestaetigt den leeren displayMetrics-Zustand (kein Onboarding, keine Tabelle).
			await expect(page.getByTestId('alerts-no-metrics')).toBeVisible();

			await expect(page.locator('.extra-cards')).not.toHaveClass(/subdued/);
		} finally {
			await deleteTrip(page, id);
		}
	});

	// AC-7 (Regressionsschutz — NICHT ausgeführt, nur geschrieben, siehe
	// Team-Lead-Vorgabe): eine aktive alert-faehige Metrik (gust -> wind_gust)
	// mit Stufe 'off' -> .extra-cards bleibt weiterhin subdued (bestehendes
	// "alles aus"-Verhalten fuer den nicht-leeren Fall unveraendert).
	test('AC-7: eine aktive alert-fähige Metrik auf "off" -> .extra-cards bleibt subdued', async ({
		page
	}) => {
		const id = tripId('ac7');
		await seedTrip(page, id, {
			metrics: [{ metric_id: 'gust', enabled: true }],
			metric_alert_levels: { wind_gust: 'off' }
		});
		try {
			await page.goto(`/trips/${id}?tab=alerts`);
			await expect(page.getByTestId('alerts-tab')).toBeVisible();
			await expect(page.getByTestId('alert-metric-row-wind_gust')).toBeVisible();

			await expect(page.locator('.extra-cards')).toHaveClass(/subdued/);
		} finally {
			await deleteTrip(page, id);
		}
	});
});

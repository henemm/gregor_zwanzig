// Issue #953 — Alerts-Tab: Empfindlichkeits-Änderung geht nach Tab-Klick optisch verloren.
// Reproduktion des Bugs gegen den LIVE-Code auf Staging (kein Mock; der Dialog-Handler
// ist echte Nutzer-Interaktion, keine Verhaltens-Simulation).
// Logik-Vorlage: verifiziertes Repro-Skript (Selektoren/Seed/Ablauf bewiesen).
// Ausführen: cd frontend && npx playwright test e2e/issue-953-alerts-autosave-tabswitch.spec.ts \
//   --config=playwright.953.staging.config.ts --reporter=list

import { test, expect, type Page } from '@playwright/test';

const TRIP_ID = 'e2e-953-alerts';
const TRIP_NAME = 'E2E #953 Alerts Autosave';

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

// Metriken + Alert-Stufen bereits gesetzt (wie in einem real konfigurierten Trip) →
// die Gewitter-Zeile erscheint direkt, kein "Keine Alerts konfiguriert"-Empty-State.
const seedBody = {
	id: TRIP_ID,
	name: TRIP_NAME,
	region: 'Korsika',
	stages: [
		{ id: 's1', name: 'Tag 1', date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] }
	],
	report_config: {
		enabled: true,
		morning_enabled: true,
		evening_enabled: true,
		morning_time: '07:00:00',
		evening_time: '18:00:00'
	},
	display_config: {
		metrics: [
			{ metric_id: 'thunder_level', enabled: true },
			{ metric_id: 'wind_gust', enabled: true },
			{ metric_id: 'precipitation_sum', enabled: true }
		],
		metric_alert_levels: {
			thunder_level: 'standard',
			wind_gust: 'standard',
			precipitation_sum: 'standard'
		}
	}
};

function thunderRow(page: Page) {
	return page.getByTestId('alert-metric-row-thunder_level');
}

test.describe('issue_953 — Alerts-Empfindlichkeit überlebt Tab-Klick', () => {
	test.beforeEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
		const res = await page.request.post('/api/trips', { data: seedBody });
		expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
	});

	test.afterEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	// KERN (aktuell rot): Empfindlichkeit 'sensibel' bleibt nach echtem Tab-Klick sichtbar.
	test('KERN: Empfindlichkeit überlebt Tab-Wechsel in der Anzeige', async ({ page }) => {
		// Ein möglicher confirm-Dialog wird wie vom Nutzer bestätigt (echte Interaktion).
		page.on('dialog', (d) => d.accept());

		await page.goto(`/trips/${TRIP_ID}?tab=alerts`);
		await expect(page.getByTestId('alerts-tab')).toBeVisible();

		// Ausgangszustand: 'standard'.
		await expect(thunderRow(page)).toHaveAttribute('data-level', 'standard');

		// Auf 'sensibel' klicken → lokal sofort sichtbar.
		await page.getByTestId('alert-level-thunder_level-sensibel').click();
		await expect(thunderRow(page)).toHaveAttribute('data-level', 'sensibel');

		// Echter Nutzer-Pfad: Tab-BUTTON klicken (nicht goto/Reload — der Bug tritt
		// nur beim Klick-Pfad auf).
		await page.getByRole('tab', { name: 'Vorschau' }).click();
		await page.getByRole('tab', { name: 'Alerts' }).click();

		// HAUPT-ASSERTION: Die Zeile zeigt weiterhin 'sensibel'. Aktuell rot, weil die
		// UI beim Zurück-Klick den Altwert 'standard' rendert.
		await expect(thunderRow(page)).toHaveAttribute('data-level', 'sensibel');

		// Trennt UI-Bug von Save-Bug: die DB ist korrekt (Wert wurde gespeichert).
		const check = await page.request.get(`/api/trips/${TRIP_ID}`);
		expect(check.ok(), `GET trip HTTP ${check.status()}`).toBeTruthy();
		const trip = await check.json();
		expect(trip.display_config?.metric_alert_levels?.thunder_level).toBe('sensibel');
	});
});

// E2E (Staging) — Issue #1269: Speicher-Status-Anzeige lügt (Trip + Ortsvergleich).
//
// Spec: docs/specs/modules/issue_1269_save_status_lie.md
//   § Acceptance Criteria AC-1, AC-2, AC-3, AC-4
// Kontext: docs/context/fix-1269-save-status-lie.md
//
// Nachweis über abgefangene Netzwerk-Requests (page.on('request')) UND den
// `data-state`-Attribut des SaveIndicator-Chips (`data-testid="save-indicator"`,
// s. frontend/src/lib/components/ui/SaveIndicator.svelte) — nicht über Text-
// Matching (i18n/Formulierungs-fragil). Echter Klick-Pfad (Tab-Klick statt
// goto), keine Mocks. Vorbild: weather-metrics-tab-autosave.spec.ts (#1234) +
// compare-editor-autosave.spec.ts (#1261).
//
// NICHT lokal/gegen Staging ausgeführt in dieser Phase (GREEN) — reine
// Struktur-/Lint-Prüfung. Ausführung erfolgt in der Staging-Verifikation:
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1269.staging.config.ts

import { test, expect, type Page, type Request, type APIRequestContext } from '@playwright/test';

const TRIP_PREFIX = 'e2e-1269';

function tripId(suffix: string): string {
	return `${TRIP_PREFIX}-${suffix}`;
}

// Bewusst OHNE Sekunden ("07:00" statt "07:00:00") — reproduziert exakt die
// Mount-Kanonisierungs-Situation aus der Spec (toHHMMSS-Diff).
async function createTrip(request: APIRequestContext, id: string) {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 1269 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			report_config: { enabled: true, morning_time: '07:00', evening_time: '18:00', send_email: true },
			display_config: { metrics: [] }
		}
	});
	expect([200, 201], `Seed HTTP ${res.status()}`).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string) {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

/** Zeichnet jeden PUT-Request auf den Trip auf (Detail + weather-config getrennt filterbar). */
function collectTripPuts(page: Page, id: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(`/api/trips/${id}`)) {
			puts.push(req);
		}
	});
	return puts;
}

/** Nur PUTs auf exakt /api/trips/{id} (nicht .../weather-config). */
function exactTripDetailPuts(puts: Request[], id: string): Request[] {
	return puts.filter((r) => r.url().endsWith(`/api/trips/${id}`));
}

test.describe('Issue #1269: Speicher-Status-Anzeige lügt', () => {
	// AC-3: Trip-Inhalt-Tab öffnen, nichts anfassen → Anzeige bleibt "gespeichert" (idle).
	test('AC-3: Inhalt-Tab öffnen ohne Eingabe → Speicher-Anzeige bleibt "gespeichert"', async ({ page, request }) => {
		const id = tripId('ac3');
		await createTrip(request, id);
		try {
			await page.goto(`/trips/${id}`);
			await page.getByTestId('trip-detail-tab-weather').click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

			// > 700ms Debounce (saveStatusStore.svelte.ts schedule()).
			await page.waitForTimeout(3_000);

			await expect(
				page.getByTestId('save-indicator'),
				'AC-3: bloßes Öffnen des Inhalt-Tabs darf keinen "Nicht gespeichert"-Zustand erzeugen'
			).toHaveAttribute('data-state', 'idle');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-4: Trip-Versand-Tab öffnen, nichts anfassen, Debounce abwarten, Tab
	// wechseln → NULL PUT auf /api/trips/{id}, kein Fehler-Banner.
	test('AC-4: Versand-Tab öffnen ohne Eingabe → kein PUT auf /api/trips/{id}, kein Fehler-Banner', async ({
		page,
		request
	}) => {
		const id = tripId('ac4');
		await createTrip(request, id);
		const puts = collectTripPuts(page, id);
		try {
			await page.goto(`/trips/${id}`);
			await page.getByTestId('trip-detail-tab-briefings').click();
			await expect(page.getByTestId('versand-tab')).toBeVisible();

			await page.waitForTimeout(3_000);
			await page.getByTestId('trip-detail-tab-stages').click();
			await page.waitForTimeout(500);

			expect(
				exactTripDetailPuts(puts, id).length,
				'AC-4: das bloße Öffnen des Versand-Tabs darf keinen echten PUT auf /api/trips/{id} auslösen'
			).toBe(0);

			await expect(
				page.getByTestId('save-indicator'),
				'kein Fehler-Banner ohne jede Nutzergeste'
			).not.toHaveAttribute('data-state', 'error');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-1/AC-2: Ortsvergleich — Layout- und Versand-Tab öffnen, nichts
	// anfassen → Anzeige bleibt durchgehend "gespeichert" (nie "Nicht
	// gespeichert" durch Mount-Kanonisierung, AC-1) UND es geht über den
	// gesamten Ablauf kein einziger PUT raus (AC-2: kein frischer
	// "Gespeichert HH:MM"-Zeitstempel ohne echten Speichervorgang möglich,
	// wenn schlicht nie ein PUT stattfindet).
	test('AC-1/AC-2 (Compare): Layout- und Versand-Tab öffnen ohne Eingabe → Anzeige bleibt "gespeichert", kein PUT', async ({
		page
	}) => {
		// Epic #1273 S4c: Einstieg am Hub statt am weggeleiteten Editor; fester
		// Desktop-Viewport + :visible-Filter gegen Doppel-Mount im DOM.
		await page.setViewportSize({ width: 1280, height: 900 });
		const suffix = Date.now();
		const locRes = await page.request.post('/api/locations', {
			data: { name: `E2E 1269 ${suffix}`, lat: 47.05, lon: 11.05 }
		});
		expect(locRes.ok(), 'Location-Anlage fehlgeschlagen: ' + locRes.status()).toBeTruthy();
		const locId = (await locRes.json()).id as string;

		const presetRes = await page.request.post('/api/compare/presets', {
			data: {
				name: `E2E 1269 ${suffix}`,
				location_ids: [locId],
				schedule: 'daily',
				profil: 'wandern',
				hour_from: 7,
				hour_to: 16,
				empfaenger: ['urlauber@example.com'],
				morning_time: '07:00'
			}
		});
		expect(presetRes.ok(), 'Preset-Anlage fehlgeschlagen: ' + presetRes.status()).toBeTruthy();
		const presetId = (await presetRes.json()).id as string;

		const puts: Request[] = [];
		page.on('request', (req) => {
			if (req.method() === 'PUT' && req.url().includes(`/api/compare/presets/${presetId}`)) {
				puts.push(req);
			}
		});

		try {
			await page.goto(`/compare/${presetId}`);
			await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });

			await page.locator('[data-testid="compare-detail-tab-layout"]:visible').first().click();
			await expect(
				page.locator('[data-testid="compare-detail-panel-layout"]:visible').first()
			).toBeVisible({ timeout: 10_000 });
			await page.waitForTimeout(2_000);
			await expect(
				page.getByTestId('save-indicator'),
				'AC-1: Layout-Tab öffnen ohne Eingabe darf nicht "Nicht gespeichert" zeigen'
			).toHaveAttribute('data-state', 'idle');

			await page.locator('[data-testid="compare-detail-tab-versand"]:visible').first().click();
			await expect(
				page.locator('[data-testid="report-morning-time"]:visible').first()
			).toBeVisible({ timeout: 10_000 });
			await page.waitForTimeout(2_000);
			await expect(
				page.getByTestId('save-indicator'),
				'AC-1: Versand-Tab öffnen ohne Eingabe darf nicht "Nicht gespeichert" zeigen'
			).toHaveAttribute('data-state', 'idle');

			expect(
				puts.length,
				'AC-2: ohne jede Nutzergeste darf über den gesamten Ablauf kein PUT stattfinden — ' +
					'sonst könnte ein frischer "Gespeichert HH:MM"-Zeitstempel ohne echten Speichervorgang entstehen'
			).toBe(0);
		} finally {
			await page.request.delete(`/api/compare/presets/${presetId}`).catch(() => {});
			await page.request.delete(`/api/locations/${locId}`).catch(() => {});
		}
	});
});

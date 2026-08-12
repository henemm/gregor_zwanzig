// E2E (Staging) — Issue #1719 Scheibe 3, Block A: die Live-Vorschau "So
// kommt es an" wird ersatzlos entfernt (PO-Entscheid).
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md AC-1, AC-2.
// Kontext: docs/context/fix-1719-s3-aus-ist-ein-zustand.md Abschnitt 5 + 10.5
//   ("Die Vorschau-Löschung ist ein Umbau, keine Löschung" — LayoutTab.svelte
//   verliert die rechte Zwei-Spalten-Hälfte, WeatherMetricsTab.svelte den
//   Mobile-FAB + Sheet-Wrapper).
//
// SCHREIBT NUR — wird in dieser RED-Phase NICHT ausgeführt (Staging läuft
// noch auf dem alten Stand mit Vorschau). Der Lauf gehört in die
// GREEN-/Verifikationsphase (Testauflage PO, "Das ist KRITISCH!!!!!").
//
// Vorbilder: metrik-grundauswahl-schneidet-kanal.staging.spec.ts (S2,
// Dreier-Struktur spec+setup+config), layout-tab-route.spec.ts (Testaufbau,
// dragDndZoneItem-Helper, wm2-* Test-IDs), weather-metrics-tab-autosave.spec.ts
// (report_config-Normalisierung gegen den Mount-Effekt-Autosave).
//
// Ausführen (gegen Staging, aus frontend/, NACH GREEN):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.wetter-metriken-vorschau-entfernt.staging.config.ts

import { test, expect, type APIRequestContext, type Locator, type Page } from '@playwright/test';

const TRIP_ID = 'e2e-1719-s3-vorschau-weg';

// Basiert auf layout-tab-route.spec.ts:23-48 — Pointer-basierte
// Drag-Simulation (svelte-dnd-action reagiert nicht auf natives HTML5-Drag).
//
// Diagnose-Fund (2026-08-12, #1719 S3 — Team-Lead-Auftrag "Reihenfolge-
// Persistenz diagnostizieren"): `svelte-dnd-action` feuert das `finalize`-
// CustomEvent auf der Drag-Zone NACH dem `mouseup` unzuverlässig verzögert.
// Messung (4 Läufe gegen Staging, rohes DOM-CustomEvent-Log auf
// `.sortable-zone`, unabhängig vom App-Code): 2× kein `finalize` innerhalb
// der Testlaufzeit, 1× sofort, 1× erst nach ~1,9s. Ohne `finalize` ruft
// `SortableList.svelte::handleDndFinalize` niemals `onDndReorder` auf — kein
// `channelBuckets`-Edit, kein PUT, keine Persistenz. Die vorher hier
// stehende feste `waitForTimeout(120)`-Pause nach dem Drop maskierte das:
// der Test las den DOM-Zwischenstand aus `handleDndConsider` (der lokal
// bereits die neue Reihenfolge zeigt, OHNE dass sie je committet wurde) und
// hielt das fälschlich für einen bestandenen Speichervorgang. Bei tatsächlich
// gefeuertem `finalize` ist die App-Logik nachweislich korrekt (PUT-Body mit
// `precipitation order:0`, GET nach Reload bitgenau identisch) — der Fehler
// liegt ausschließlich in der Test-Simulation, nicht im Produktcode.
//
// Der geteilte Helfer in layout-tab-route.spec.ts (und weiteren Dateien,
// z.B. compare-hub-inline-edit.spec.ts) hat dieselbe Schwäche — reproduziert
// mit layout-tab-route.spec.ts AC-3, 2× hintereinander lokal fehlgeschlagen,
// KEIN S3-Bezug. Der Umbau dort ist bewusst NICHT Teil dieser Scheibe
// (Team-Lead-Entscheid: "nur unseren eigenen Helfer robust machen, nichts
// Geteiltes anfassen") — separat zu buchen.
async function dragDndZoneItem(page: Page, source: Locator, target: Locator): Promise<void> {
	await source.scrollIntoViewIfNeeded();
	await target.scrollIntoViewIfNeeded();
	const sourceBox = await source.boundingBox();
	const targetBox = await target.boundingBox();
	if (!sourceBox || !targetBox) throw new Error('dragDndZoneItem: source/target ohne BoundingBox');

	// Vor dem Drag: Promise auf der Zone verdrahten, die bei `finalize`
	// aufloest. `document.querySelector` genuegt — diese Ansicht zeigt genau
	// EINE Reihenfolge-Zone (die mobile FAB/Sheet-Duplizierung ist mit AC-1
	// dieser Scheibe entfernt).
	await page.evaluate(() => {
		const zone = document.querySelector('.sortable-zone');
		if (!zone) throw new Error('dragDndZoneItem: .sortable-zone nicht im DOM gefunden');
		(window as unknown as { __gzDndFinalize?: Promise<void> }).__gzDndFinalize = new Promise((resolve) => {
			zone.addEventListener('finalize', () => resolve(), { once: true });
		});
	});

	await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2);
	await page.mouse.down();
	await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2 - 12, {
		steps: 6
	});
	await page.waitForTimeout(120);
	await page.mouse.move(targetBox.x + targetBox.width / 2, targetBox.y + targetBox.height / 2, {
		steps: 15
	});
	await page.waitForTimeout(120);
	await page.mouse.up();

	// Großzügiges Zeitfenster ueber dem gemessenen Maximum (~1,9s). Feuert
	// `finalize` nicht, scheitert der Test HIER mit klarer Ursache — statt
	// spaeter unspezifisch an einer Persistenz-Assertion, die faelschlich
	// als Produktfehler gelesen werden koennte.
	const FINALIZE_TIMEOUT_MS = 4_000;
	const fired = await page.evaluate(({ ms }) => {
		const w = window as unknown as { __gzDndFinalize?: Promise<void> };
		if (!w.__gzDndFinalize) return Promise.resolve(false);
		return Promise.race([
			w.__gzDndFinalize.then(() => true),
			new Promise<boolean>((resolve) => setTimeout(() => resolve(false), ms))
		]);
	}, { ms: FINALIZE_TIMEOUT_MS });
	if (!fired) {
		throw new Error(
			`dragDndZoneItem: finalize blieb aus (>${FINALIZE_TIMEOUT_MS}ms) — Ziehgeste hat nicht ` +
			'committet. Bekannte Flakiness des Pointer-Drag-Helfers (svelte-dnd-action), kein ' +
			'Produktfehler — siehe Kommentar ueber dieser Funktion (Diagnose 2026-08-12).'
		);
	}
}

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
	return request.post('/api/trips', {
		data: {
			id: TRIP_ID,
			name: 'E2E #1719 S3 Vorschau weg',
			report_config: REPORT_CONFIG,
			display_config: {
				metrics: [
					{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 0 },
					{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 1 },
					{ metric_id: 'precipitation', enabled: true, bucket: 'primary', order: 2 }
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

async function openMetricsTab(page: Page) {
	await page.goto(`/trips/${TRIP_ID}?tab=weather`);
	const weatherTabBtn = page.getByTestId('trip-detail-tab-weather');
	await expect(weatherTabBtn).toBeVisible({ timeout: 10_000 });
	await weatherTabBtn.click();
	const tab = page.getByTestId('weather-metrics-tab');
	await expect(tab).toBeVisible({ timeout: 10_000 });
	await expect(tab.getByTestId('wm2-grundauswahl').locator('.toggle-btn').first()).toBeVisible({
		timeout: 10_000
	});
	return tab;
}

test.describe('Issue #1719 S3 Block A: Live-Vorschau ist ersatzlos weg', () => {
	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	test('AC-1: weder Vorschau-Spalte noch Mobile-Knopf existieren — Desktop UND Mobil', async ({ page, request }) => {
		// Staging-Fund (2026-08-11): `createTrip` war definiert, aber in BEIDEN
		// Tests dieser Datei nie aufgerufen — der Trip existierte nicht, die
		// Navigation zu `/trips/{id}?tab=weather` fand keinen Reiter
		// ("trip-detail-tab-weather" not found). Test-/Fixture-Fehler, kein
		// Produktfehler (Beleg: derselbe Navigationsweg besteht in
		// kanal-grenzen-und-hinweise.staging.spec.ts, wo der Trip angelegt wird).
		const created = await createTrip(request);
		expect(created.ok(), `Trip-Anlage fehlgeschlagen: HTTP ${created.status()}`).toBeTruthy();
		await page.setViewportSize({ width: 1440, height: 900 });
		const tab = await openMetricsTab(page);

		await expect(
			tab.getByTestId('wm2-mail-preview'),
			'AC-1 FAIL (Desktop): "So kommt es an" darf im DOM nicht mehr existieren'
		).toHaveCount(0);
		await expect(
			page.getByTestId('mobile-mail-fab'),
			'AC-1 FAIL (Desktop): Mobile-FAB darf im DOM nicht mehr existieren'
		).toHaveCount(0);

		await page.setViewportSize({ width: 390, height: 844 });
		await expect(
			tab.getByTestId('wm2-mail-preview'),
			'AC-1 FAIL (Mobil): "So kommt es an" darf auch auf Mobil-Breite nicht existieren'
		).toHaveCount(0);
		await expect(
			page.getByTestId('mobile-mail-fab'),
			'AC-1 FAIL (Mobil): Mobile-FAB darf auf Mobil-Breite nicht existieren'
		).toHaveCount(0);
	});

	test('AC-2: Kanal-Wähler + Ziehen bleiben ohne Vorschau bedienbar, kein horizontaler Scroll', async ({
		page,
		request
	}) => {
		// Staging-Fund (2026-08-11): siehe Kommentar bei AC-1 — createTrip war
		// nie aufgerufen.
		const created = await createTrip(request);
		expect(created.ok(), `Trip-Anlage fehlgeschlagen: HTTP ${created.status()}`).toBeTruthy();
		await page.setViewportSize({ width: 1440, height: 900 });
		const tab = await openMetricsTab(page);
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle');

		// Kanal-Wähler weiterhin bedienbar (Wähler selbst überlebt die
		// Vorschau-Löschung — nur die rechte Spalte/Hülle entfällt).
		await tab.getByTestId('channel-tab-telegram').click();
		await tab.getByTestId('channel-tab-sms').click();
		await tab.getByTestId('channel-tab-email').click();

		// Reihenfolge-Liste weiterhin bedienbar: "precipitation" vor "temperature" ziehen.
		const rows = tab.locator('[data-testid="wm2-reihenfolge-row"]');
		await expect(rows).toHaveCount(3);
		const source = tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="precipitation"]');
		const target = tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="temperature"]');
		await dragDndZoneItem(page, source, target);
		await expect(rows.first()).toHaveAttribute('data-metric-id', 'precipitation');

		// Kappungs-Hinweis (LTCapNote) bleibt sichtbar und bedienbar.
		await expect(page.locator('[data-testid="lt-cap-note"]:visible').first()).toBeVisible();

		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		// Reload: Reihenfolge bleibt.
		await page.reload();
		await page.getByTestId('trip-detail-tab-weather').click();
		const reloadedRows = page
			.getByTestId('weather-metrics-tab')
			.locator('[data-testid="wm2-reihenfolge-row"]');
		await expect(reloadedRows.first()).toHaveAttribute('data-metric-id', 'precipitation', {
			timeout: 5_000
		});

		// Kein horizontaler Scroll ohne die rechte Vorschau-Spalte.
		const overflowsX = await page.evaluate(
			() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 4
		);
		expect(overflowsX, 'AC-2 FAIL: Seite scrollt horizontal ohne die Vorschau-Spalte').toBeFalsy();
	});
});

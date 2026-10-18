// TDD: Issue #153 — Epic #135 Step 2: Trip-Detail Header (Breadcrumb + Status-Badge + Aktionen).
//
// Spec: docs/specs/modules/epic_135_step2_trip_detail_actions.md
//
// Voraussetzung: Test-Trip `e2e-cockpit-test` aus global.setup.ts existiert.

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';

// Hilfsfunktionen, um den Trip-Status zu Beginn jedes Tests zurückzusetzen.
// Vermeidet Test-Reihenfolgen-Abhängigkeit, weil das PATCH /state persistiert.
async function resetTripState(request: import('@playwright/test').APIRequestContext) {
	// Beide Flags löschen — egal in welchem Zustand der Trip vor dem Test war.
	await request.patch(`/api/trips/${TRIP_ID}/state`, {
		data: { paused: false, archived: false }
	});
}

// #2278: Pausieren/Fortsetzen/Archivieren/Reaktivieren sind Eintraege des Hub-Lebenszyklus-Menues
// (`subscription-kebab`); Desktop-Dropdown und mobiles Blatt teilen `subscription-action-<id>`.
type Page = import('@playwright/test').Page;
async function hubAktion(page: Page, id: string) {
	await page.getByTestId('subscription-kebab').click();
	await page.getByTestId(`subscription-action-${id}`).click();
}
/** Oeffnet das Menue, prueft Vorhandensein (true/false) je Aktion und schliesst es wieder. */
async function menueHat(page: Page, erwartet: Record<string, boolean>) {
	await page.getByTestId('subscription-kebab').click();
	for (const [id, da] of Object.entries(erwartet))
		await expect(page.getByTestId(`subscription-action-${id}`)).toHaveCount(da ? 1 : 0);
	await page.keyboard.press('Escape');
}

test.describe('Issue #153 — Trip-Detail Header (Breadcrumb + Status + Aktionen)', () => {
	test.beforeEach(async ({ request }) => {
		await resetTripState(request);
	});

	test.afterAll(async ({ request }) => {
		await resetTripState(request);
	});

	test('AC-10: Breadcrumb-Bar ist sichtbar und zeigt "Trips" + Trip-Name', async ({ page }) => {
		// Issue #699: Die innere Duplikat-Breadcrumb (trip-detail-breadcrumb) wurde
		// entfernt. Die korrekte Breadcrumb ist die äußere Bar in +page.svelte
		// (data-testid="trip-detail-breadcrumb-bar"), die „Trips / <Name>" zeigt.
		await page.goto(`/trips/${TRIP_ID}`);
		const bar = page.getByTestId('trip-detail-breadcrumb-bar');
		await expect(bar).toBeVisible();
		await expect(bar).toContainText('Trips');
		// Akzeptiert sowohl Shortcode als auch Name — die genaue Logik ist in AC-11.
	});

	test('AC-11: Breadcrumb-Bar zeigt Trip-Name (Original-Schreibweise, nicht uppercase)', async ({
		page
	}) => {
		// e2e-cockpit-test hat keinen Shortcode → Fallback auf Name.
		// Issue #699: Die äußere Bar rendert den Namen NICHT uppercase
		// (anders als die entfernte innere nav).
		await page.goto(`/trips/${TRIP_ID}`);
		const bar = page.getByTestId('trip-detail-breadcrumb-bar');
		await expect(bar).toContainText('E2E Cockpit Test Trip');
	});

	test('AC-12: Status-Badge zeigt "Aktiv" für trip mit Stages umschliessend heute', async ({
		page
	}) => {
		// e2e-cockpit-test hat Stages 2026-05-11 + 2026-05-12 (gestern/heute) → aktiv
		await page.goto(`/trips/${TRIP_ID}`);
		const badge = page.getByTestId('trip-detail-status-badge');
		await expect(badge).toBeVisible();
		await expect(badge).toContainText(/Aktiv|Geplant/); // 'Aktiv' wenn heute innerhalb, sonst 'Geplant'
		// Pill-Tone laut TripStatusBadge.svelte TONE_MAP: active -> 'accent',
		// planned -> 'info'. 'accent' ist gewollt und eigens in app.css
		// gestylt (Regel [data-slot="pill"][data-outlined][data-tone="accent"],
		// bewacht von TripStatusBadge.atomic.test.ts AC-4) — die frühere
		// Erwartung 'success' stammt aus der Zeit vor diesem Mapping.
		const tone = await badge.getAttribute('data-tone');
		expect(['accent', 'info']).toContain(tone);
	});

	test('AC-13: Klick auf "Pausieren" → PATCH + Badge wechselt zu "Pausiert" ohne Reload', async ({
		page
	}) => {
		// Issue #302 / #581: Pause-Button lebt jetzt in der Breadcrumb-Bar und hat
		// das Label "Pausieren" (bzw. "Fortsetzen" im pausierten Zustand).
		await page.goto(`/trips/${TRIP_ID}`);
		await menueHat(page, { pause: true, resume: false });

		// Klick → PATCH
		await hubAktion(page, 'pause');

		// Nach Response: Badge zeigt 'Pausiert' (data-tone=warning)
		const badge = page.getByTestId('trip-detail-status-badge');
		await expect(badge).toContainText('Pausiert');
		await expect(badge).toHaveAttribute('data-tone', 'warning');

		// Menue-Eintrag wechselt auf 'Fortsetzen'
		await menueHat(page, { pause: false, resume: true });
	});

	test('AC-14: Klick auf "Archivieren" öffnet Confirm-Dialog, sendet noch nichts', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await menueHat(page, { archive: true });

		await hubAktion(page, 'archive');

		const dialog = page.getByTestId('trip-detail-archive-confirm-dialog');
		await expect(dialog).toBeVisible();

		// Badge ist NOCH unverändert (kein PATCH gesendet)
		const badge = page.getByTestId('trip-detail-status-badge');
		await expect(badge).not.toContainText('Archiviert');
	});

	test('AC-15: Cancel im Confirm-Dialog → keine Statusänderung', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await hubAktion(page, 'archive');
		await page.getByTestId('trip-detail-archive-confirm-cancel').click();

		// Dialog geschlossen
		await expect(page.getByTestId('trip-detail-archive-confirm-dialog')).not.toBeVisible();

		// Badge unverändert (nicht 'Archiviert')
		const badge = page.getByTestId('trip-detail-status-badge');
		await expect(badge).not.toContainText('Archiviert');
		await menueHat(page, { archive: true, unarchive: false });
	});

	test('AC-16: Confirm im Dialog → PATCH gesendet + Badge "Archiviert" + kein Pausieren mehr im Menü', async ({
		page
	}) => {
		// #2278: ein archivierter Trip bietet im Lebenszyklus-Menue nur noch Reaktivieren/Löschen.
		await page.goto(`/trips/${TRIP_ID}`);
		await hubAktion(page, 'archive');
		await page.getByTestId('trip-detail-archive-confirm-yes').click();

		// Dialog geschlossen
		await expect(page.getByTestId('trip-detail-archive-confirm-dialog')).not.toBeVisible();

		// Badge zeigt 'Archiviert'
		const badge = page.getByTestId('trip-detail-status-badge');
		await expect(badge).toContainText('Archiviert');

		await menueHat(page, { pause: false, resume: false, unarchive: true });
	});

	test('AC-17: Archivierter Trip → Menü bietet "Reaktivieren", kein Pausieren/Fortsetzen', async ({
		page,
		request
	}) => {
		await request.patch(`/api/trips/${TRIP_ID}/state`, { data: { archived: true } });

		await page.goto(`/trips/${TRIP_ID}`);
		await menueHat(page, { unarchive: true, pause: false, resume: false });
	});

	test('AC-18: Pausierter Trip → Menü bietet "Fortsetzen", Archivieren bleibt sichtbar', async ({
		page,
		request
	}) => {
		await request.patch(`/api/trips/${TRIP_ID}/state`, { data: { paused: true } });

		await page.goto(`/trips/${TRIP_ID}`);
		await menueHat(page, { resume: true, archive: true });
	});

	test('AC-19: Reload zeigt persistierten Status (paused → Fortsetzen-Button)', async ({
		page,
		request
	}) => {
		// Setup via UI: pausieren
		await page.goto(`/trips/${TRIP_ID}`);
		await hubAktion(page, 'pause');
		await expect(page.getByTestId('trip-detail-status-badge')).toContainText('Pausiert');

		// Page-Reload
		await page.reload();

		// Status + Menüeintrag bleiben persistent
		await expect(page.getByTestId('trip-detail-status-badge')).toContainText('Pausiert');
		await menueHat(page, { resume: true });
	});

	test('AC-20: Tab-Navigation aus Step 1 bleibt unverändert sichtbar und funktional', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const tabList = page.getByTestId('trip-detail-tab-list');
		await expect(tabList).toBeVisible();

		for (const tab of ['uebersicht', 'etappen', 'wetter-metriken', 'versand', 'wertebereiche', 'vorschau']) {
			const trigger = page.getByTestId(`trip-detail-tab-${tab}`);
			await expect(trigger).toBeVisible();
		}

		// Tab-Wechsel funktioniert nach wie vor
		await page.getByTestId('trip-detail-tab-wertebereiche').click();
		await expect(page.getByTestId('trip-detail-tab-wertebereiche')).toHaveAttribute('data-state', 'active');
	});

	test('Toggle-Roundtrip: Pause → Resume → wieder aktiv', async ({ page }) => {
		// Issue #302 / #581: Pause-Button-Label ist "Pausieren" / "Fortsetzen".
		await page.goto(`/trips/${TRIP_ID}`);
		await hubAktion(page, 'pause');
		await expect(page.getByTestId('trip-detail-status-badge')).toContainText('Pausiert');

		// Resume
		await hubAktion(page, 'resume');
		await expect(page.getByTestId('trip-detail-status-badge')).not.toContainText('Pausiert');
		await menueHat(page, { pause: true });
	});

	test('Screenshot der Trip-Header-Komponente für visuelle Verifikation', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.waitForSelector('[data-testid="trip-detail-breadcrumb-bar"]');
		await page.screenshot({
			path: '../docs/artifacts/epic-135-step2-trip-detail-actions/screenshot-trip-header.png',
			fullPage: false
		});
	});
});

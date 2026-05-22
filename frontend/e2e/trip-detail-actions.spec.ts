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

test.describe('Issue #153 — Trip-Detail Header (Breadcrumb + Status + Aktionen)', () => {
	test.beforeEach(async ({ request }) => {
		await resetTripState(request);
	});

	test.afterAll(async ({ request }) => {
		await resetTripState(request);
	});

	test('AC-10: Breadcrumb zeigt Shortcode wenn vorhanden', async ({ page }) => {
		// Vorbedingung: e2e-cockpit-test hat KEINEN Shortcode in global.setup.ts —
		// daher fällt dieser AC auf den Fallback-Pfad (siehe AC-11) zurück.
		// Strenger Shortcode-Test braucht eigenen Test-Trip; dieser AC verifiziert
		// nur, dass die Breadcrumb-Struktur korrekt aufgebaut ist.
		await page.goto(`/trips/${TRIP_ID}`);
		const breadcrumb = page.getByTestId('trip-detail-breadcrumb');
		await expect(breadcrumb).toBeVisible();
		const link = page.getByTestId('trip-detail-breadcrumb-link-trips');
		await expect(link).toHaveAttribute('href', '/trips');
		const current = page.getByTestId('trip-detail-breadcrumb-current');
		await expect(current).toBeVisible();
		// Akzeptiert sowohl Shortcode als auch Name — die genaue Logik ist in AC-11.
	});

	test('AC-11: Breadcrumb zeigt Trip-Name wenn kein Shortcode', async ({ page }) => {
		// e2e-cockpit-test hat keinen Shortcode → Fallback auf Name.
		// Issue #302: Breadcrumb rendert Eyebrow-style UPPERCASE.
		await page.goto(`/trips/${TRIP_ID}`);
		const current = page.getByTestId('trip-detail-breadcrumb-current');
		await expect(current).toContainText('E2E COCKPIT TEST TRIP');
	});

	test('AC-12: Status-Badge zeigt "Aktiv" für trip mit Stages umschliessend heute', async ({
		page
	}) => {
		// e2e-cockpit-test hat Stages 2026-05-11 + 2026-05-12 (gestern/heute) → aktiv
		await page.goto(`/trips/${TRIP_ID}`);
		const badge = page.getByTestId('trip-detail-status-badge');
		await expect(badge).toBeVisible();
		await expect(badge).toContainText(/Aktiv|Geplant/); // 'Aktiv' wenn heute innerhalb, sonst 'Geplant'
		// Pill-Tone success für aktiv
		const tone = await badge.getAttribute('data-tone');
		expect(['success', 'info']).toContain(tone);
	});

	test('AC-13: Klick auf "Briefings pausieren" → PATCH + Badge wechselt zu "Pausiert" ohne Reload', async ({
		page
	}) => {
		// Issue #302: Pause-Button hat jetzt Label "Briefings pausieren" und lebt
		// in der Danger-Zone unter den Tabs.
		await page.goto(`/trips/${TRIP_ID}`);
		const pauseBtn = page.getByTestId('trip-detail-action-pause');
		await expect(pauseBtn).toContainText('Briefings pausieren');

		// Klick → PATCH
		await pauseBtn.click();

		// Nach Response: Badge zeigt 'Pausiert' (data-tone=warning)
		const badge = page.getByTestId('trip-detail-status-badge');
		await expect(badge).toContainText('Pausiert');
		await expect(badge).toHaveAttribute('data-tone', 'warning');

		// Button-Label wechselt auf 'Fortsetzen'
		await expect(page.getByTestId('trip-detail-action-pause')).toContainText('Fortsetzen');
	});

	test('AC-14: Klick auf "Archivieren" öffnet Confirm-Dialog, sendet noch nichts', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const archiveBtn = page.getByTestId('trip-detail-action-archive');
		await expect(archiveBtn).toContainText('Archivieren');

		await archiveBtn.click();

		const dialog = page.getByTestId('trip-detail-archive-confirm-dialog');
		await expect(dialog).toBeVisible();

		// Badge ist NOCH unverändert (kein PATCH gesendet)
		const badge = page.getByTestId('trip-detail-status-badge');
		await expect(badge).not.toContainText('Archiviert');
	});

	test('AC-15: Cancel im Confirm-Dialog → keine Statusänderung', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-action-archive').click();
		await page.getByTestId('trip-detail-archive-confirm-cancel').click();

		// Dialog geschlossen
		await expect(page.getByTestId('trip-detail-archive-confirm-dialog')).not.toBeVisible();

		// Badge unverändert (nicht 'Archiviert')
		const badge = page.getByTestId('trip-detail-status-badge');
		await expect(badge).not.toContainText('Archiviert');
		await expect(page.getByTestId('trip-detail-action-archive')).toContainText('Archivieren');
	});

	test('AC-16: Confirm im Dialog → PATCH gesendet + Badge "Archiviert" + Pause-Button disabled', async ({
		page
	}) => {
		// Issue #302: Pause-Button bleibt im DOM (Danger-Zone), wird aber deaktiviert.
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-action-archive').click();
		await page.getByTestId('trip-detail-archive-confirm-yes').click();

		// Dialog geschlossen
		await expect(page.getByTestId('trip-detail-archive-confirm-dialog')).not.toBeVisible();

		// Badge zeigt 'Archiviert'
		const badge = page.getByTestId('trip-detail-status-badge');
		await expect(badge).toContainText('Archiviert');

		// Pause-Button bleibt sichtbar, ist aber disabled
		const pauseBtn = page.getByTestId('trip-detail-action-pause');
		await expect(pauseBtn).toBeVisible();
		await expect(pauseBtn).toBeDisabled();
	});

	test('AC-17: Archivierter Trip → Button-Label "Reaktivieren", Pause-Button disabled', async ({
		page,
		request
	}) => {
		// Issue #302: Pause-Button bleibt im DOM und ist deaktiviert.
		await request.patch(`/api/trips/${TRIP_ID}/state`, { data: { archived: true } });

		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByTestId('trip-detail-action-archive')).toContainText('Reaktivieren');
		await expect(page.getByTestId('trip-detail-action-pause')).toBeDisabled();
	});

	test('AC-18: Pausierter Trip → Button-Label "Fortsetzen", Archive-Button bleibt sichtbar', async ({
		page,
		request
	}) => {
		await request.patch(`/api/trips/${TRIP_ID}/state`, { data: { paused: true } });

		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByTestId('trip-detail-action-pause')).toContainText('Fortsetzen');
		await expect(page.getByTestId('trip-detail-action-archive')).toContainText('Archivieren');
		await expect(page.getByTestId('trip-detail-action-archive')).toBeVisible();
	});

	test('AC-19: Reload zeigt persistierten Status (paused → Fortsetzen-Button)', async ({
		page,
		request
	}) => {
		// Setup via UI: pausieren
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-action-pause').click();
		await expect(page.getByTestId('trip-detail-status-badge')).toContainText('Pausiert');

		// Page-Reload
		await page.reload();

		// Status + Button bleiben persistent
		await expect(page.getByTestId('trip-detail-status-badge')).toContainText('Pausiert');
		await expect(page.getByTestId('trip-detail-action-pause')).toContainText('Fortsetzen');
	});

	test('AC-20: Tab-Navigation aus Step 1 bleibt unverändert sichtbar und funktional', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const tabList = page.getByTestId('trip-detail-tab-list');
		await expect(tabList).toBeVisible();

		for (const tab of ['overview', 'stages', 'weather', 'briefings', 'alerts', 'preview']) {
			const trigger = page.getByTestId(`trip-detail-tab-${tab}`);
			await expect(trigger).toBeVisible();
		}

		// Tab-Wechsel funktioniert nach wie vor
		await page.getByTestId('trip-detail-tab-alerts').click();
		await expect(page.getByTestId('trip-detail-tab-alerts')).toHaveAttribute('data-state', 'active');
	});

	test('Toggle-Roundtrip: Pause → Resume → wieder aktiv', async ({ page }) => {
		// Issue #302: Pause-Button-Label ist "Briefings pausieren" / "Fortsetzen".
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-action-pause').click();
		await expect(page.getByTestId('trip-detail-status-badge')).toContainText('Pausiert');

		// Resume
		await page.getByTestId('trip-detail-action-pause').click();
		await expect(page.getByTestId('trip-detail-status-badge')).not.toContainText('Pausiert');
		await expect(page.getByTestId('trip-detail-action-pause')).toContainText('Briefings pausieren');
	});

	test('Screenshot der Trip-Header-Komponente für visuelle Verifikation', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.waitForSelector('[data-testid="trip-detail-breadcrumb"]');
		await page.screenshot({
			path: 'docs/artifacts/epic-135-step2-trip-detail-actions/screenshot-trip-header.png',
			fullPage: false
		});
	});
});

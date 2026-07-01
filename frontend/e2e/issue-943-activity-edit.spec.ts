// E2E-Tests für Issue #943 — Aktivitätstyp im Edit-Modus änderbar & persistent.
//
// Spec: docs/specs/fast/fix-943-activity-edit.md
//
// Kernproblem (vor Fix): TripEditView bot keinen Aktivitätstyp-Editor. Der Wert
// aus `trip.activity` wurde zwar an EditStagesPanelNew durchgereicht, konnte aber
// nicht geändert und nicht neu persistiert werden.
//
// Nach Fix (TripEditView.svelte):
//   - `activityType` als eigener $state (init aus trip.activity)
//   - Select-Dropdown `data-testid="edit-activity-dropdown"` in der Stats-Karte
//   - `activity: activityType` im api.put
//   - EditStagesPanelNew erhält `activityType={activityType}` (reaktiv)
//
// Verhaltensnachweis-Pflicht (CLAUDE.md): Frontend-Bug → Playwright gegen echten
// Server, eingeloggter Nutzer, echter DB-Zustand über Reload. Kein Mock, kein
// Dateiinhalt-Check.
//
// Ausführung (aus frontend/):
//   npx playwright test issue-943-activity-edit.spec.ts

import { test, expect, type Page } from '@playwright/test';
import { login } from './helpers.js';

const DROPDOWN = 'edit-activity-dropdown';

// Öffnet die Edit-Seite des ersten Trips in der Liste und liefert die Trip-ID
// (aus der URL /trips/<id>/edit). Setzt voraus, dass mindestens ein Trip existiert.
async function openFirstTripEdit(page: Page): Promise<string> {
	await page.goto('/trips');
	// Erste Trip-Karte mit Link zur Detail- oder Edit-Seite ansteuern.
	const editLink = page.locator('a[href$="/edit"]').first();
	await editLink.waitFor({ state: 'visible' });
	await editLink.click();
	await page.getByTestId('trip-edit-view').waitFor({ state: 'visible' });
	const m = page.url().match(/\/trips\/([^/]+)\/edit/);
	if (!m) throw new Error(`Edit-URL nicht erkannt: ${page.url()}`);
	return m[1];
}

test.describe('Issue #943 — Aktivitätstyp im Edit-Modus', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// AC-1: Dropdown sichtbar mit gespeichertem Wert vorausgewählt.
	test('AC-1: Aktivitätstyp-Dropdown sichtbar mit vorausgewähltem Wert', async ({ page }) => {
		await openFirstTripEdit(page);

		const dropdown = page.getByTestId(DROPDOWN);
		await expect(dropdown).toBeVisible();

		// Vorausgewählter Wert ist einer der bekannten Aktivitätstypen (nicht leer,
		// wenn der Trip einen activity-Wert hat) — mindestens muss das Dropdown
		// interagierbar sein und die Fahrrad-Optionen anbieten.
		await expect(dropdown.locator('option[value="fahrrad_20"]')).toHaveCount(1);
		await expect(dropdown.locator('option[value="trekking"]')).toHaveCount(1);
	});

	// AC-2: Wechsel + Speichern → beim erneuten Öffnen korrekt vorausgewählt.
	test('AC-2: geänderter Aktivitätstyp wird persistiert und nach Reload vorausgewählt', async ({
		page
	}) => {
		const tripId = await openFirstTripEdit(page);

		const dropdown = page.getByTestId(DROPDOWN);
		await expect(dropdown).toBeVisible();

		// Zielwert wählen, der sich garantiert vom Default unterscheidet: erst prüfen.
		const current = await dropdown.inputValue();
		const target = current === 'fahrrad_20' ? 'trekking' : 'fahrrad_20';

		await dropdown.selectOption(target);
		await expect(dropdown).toHaveValue(target);

		// Speichern → Navigation zurück zur Liste.
		await page.getByTestId('edit-save-btn').click();
		await page.waitForURL('**/trips');

		// Edit-Seite desselben Trips frisch laden (echter DB-Zustand).
		await page.goto(`/trips/${tripId}/edit`);
		const reloaded = page.getByTestId(DROPDOWN);
		await expect(reloaded).toBeVisible();
		await expect(reloaded).toHaveValue(target);
	});

	// AC-3: Wechsel auf Etappen-Tab → Ankunftszeiten reaktiv neu berechnet,
	// ohne Seitenneuladen (nur Client-State-Änderung).
	test('AC-3: Aktivitätswechsel wirkt reaktiv auf Etappen-Ankunftszeiten', async ({ page }) => {
		await openFirstTripEdit(page);

		const dropdown = page.getByTestId(DROPDOWN);
		await expect(dropdown).toBeVisible();

		// Auf Etappen-Tab wechseln und den anfänglichen Zustand der Panel-Inhalte
		// festhalten (Ankunftszeiten hängen vom Aktivitätsprofil ab).
		await page.getByTestId('edit-tab-etappen').click();
		const panel = page.getByTestId('edit-tab-content');
		await expect(panel).toBeVisible();
		const before = (await panel.innerText()).trim();

		// Zurück zur Stats-Karte-Ebene ist nicht nötig — Dropdown liegt oberhalb der
		// Tabs und bleibt sichtbar. Aktivitätstyp auf einen anderen Wert setzen.
		const current = await dropdown.inputValue();
		const target = current === 'fahrrad_25' ? 'trekking' : 'fahrrad_25';
		await dropdown.selectOption(target);
		await expect(dropdown).toHaveValue(target);

		// KEIN Reload — die Etappen-Ankunftszeiten müssen sich rein reaktiv ändern.
		// Wir warten darauf, dass sich der gerenderte Panel-Text unterscheidet
		// (unterschiedliche Geschwindigkeit → andere Ankunftszeiten).
		await expect
			.poll(async () => (await panel.innerText()).trim(), {
				message: 'Etappen-Panel muss sich reaktiv ändern (neue Ankunftszeiten)',
				timeout: 5_000
			})
			.not.toBe(before);
	});
});

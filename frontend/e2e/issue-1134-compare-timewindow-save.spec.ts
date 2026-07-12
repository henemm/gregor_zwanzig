// E2E — Issue #1134: Zeitfenster im Compare-Edit-Pfad speichern (AC-3 / AC-3a)
//
// Spec: docs/specs/modules/issue_1134_compare_mail_formatting.md
//
// Bug (AC-3): Der Edit-Save (`CompareEditor.handleSave` -> `buildComparePresetSavePayload`,
// Issue #758 ohne Redirect) traegt weder `hour_from` noch `hour_to` in den PUT-Body.
// Ein im Versand-Tab (Step 5) geaendertes Zeitfenster wird deshalb NICHT persistiert;
// stattdessen ueberschreibt der Round-Trip-Spread `...original` es mit dem alten Wert.
// Beim erneuten Oeffnen liest die Edit-Seite `state.timeWindowStart = preset.hour_from`
// -> wieder der alte Wert.
//
// RED-Erwartung (vor Fix):
//   AC-3:  FAIL — nach Aenderung auf 07-14 + Speichern liefert GET des Presets
//          weiterhin 09/16, und das erneute Oeffnen zeigt 09/16 (nicht persistiert).
//   AC-3a: PASS (Nicht-Regressions-Waechter) — eine reine Namensaenderung darf das
//          bestehende Zeitfenster (07-14) und die Empfaenger nicht auf einen Default
//          zuruecksetzen; der Round-Trip-Spread erhaelt sie bereits heute.
//
// Der Save navigiert NICHT weg (Issue #758): der Abschluss wird ueber den
// `save-indicator` (data-state=idle -> „Gespeichert") abgewartet, danach wird
// per API-GET und erneutem Oeffnen der Edit-Seite verifiziert.
//
// Base-URL: playwright.config.ts (Default localhost:4173 Preview; Staging via
// GZ_SVELTE_BASE analog bestehender Compare-E2E-Tests).
//
// Ausfuehren:
//   cd frontend && npx playwright test e2e/issue-1134-compare-timewindow-save.spec.ts \
//     --config playwright.config.ts

import { test, expect, type Page, type Locator } from '@playwright/test';
import { login } from './helpers.js';

// ── Hilfsfunktion: legt einen Compare-Preset an (echte Mandanten-Bindung) ─────
async function createPreset(
	page: Page,
	overrides: Record<string, unknown> = {}
): Promise<{ id: string; empfaenger: string[] }> {
	const empfaenger = ['tw-1134@example.com'];
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: 'Zeitfenster-E2E 1134 ' + Date.now(),
			location_ids: [],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 9,
			hour_to: 16,
			empfaenger,
			...overrides
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	return { id: body.id, empfaenger: body.empfaenger ?? empfaenger };
}

const saveIndicator = (page: Page): Locator => page.getByTestId('save-indicator');

// Step5Versand wird zweimal gerendert (Desktop + Mobile) -> beide binden an
// denselben Wizard-State. Bei 1280px ist der Desktop-Block (DOM-Reihenfolge
// zuerst) sichtbar; `.first()` trifft den sichtbaren, editierbaren Input.
const twStart = (page: Page): Locator =>
	page.getByTestId('compare-step5-time-window-start').first();
const twEnd = (page: Page): Locator =>
	page.getByTestId('compare-step5-time-window-end').first();

// ── Oeffnet das Zeitfenster-Feld im Edit-Modus. Issue #1232 Scheibe 2b: das
// Zeitfenster zog vom Versand-Tab in den Layout-Tab um (CompareReportContentSection);
// die Testids compare-step5-time-window-* selbst bleiben unveraendert. ────────
async function openVersandTab(page: Page, id: string): Promise<void> {
	await page.goto(`/compare/${id}/edit`);
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-editor-tab-layout"]').click();
	await expect(page.locator('[data-testid="compare-editor-tab-layout"]')).toHaveAttribute(
		'data-active',
		'true'
	);
	await expect(twStart(page)).toBeVisible({ timeout: 8_000 });
}

test.describe('Issue #1134: Zeitfenster im Compare-Edit-Pfad speichern', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-3: geaendertes Zeitfenster wird persistiert ───────────────────────
	test('AC-3: Zeitfenster 07-14 wird gespeichert und nach Reload angezeigt', async ({ page }) => {
		const { id } = await createPreset(page);

		// Edit oeffnen, Zeitfenster von 09-16 auf 07-14 aendern.
		await openVersandTab(page, id);
		await twStart(page).fill('7');
		await twEnd(page).fill('14');

		// Speichern -> kein Redirect (Issue #758); auf „Gespeichert" (idle) warten.
		await page.locator('[data-testid="compare-editor-save"]').click();
		await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 8_000 });

		// RED-Beweis via API: Persistenz muss die neuen Werte tragen.
		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.hour_from, 'hour_from muss 7 sein (persistiert)').toBe(7);
		expect(preset.hour_to, 'hour_to muss 14 sein (persistiert)').toBe(14);

		// RED-Beweis aus Nutzersicht: erneutes Oeffnen der Edit-Seite zeigt 07-14.
		await openVersandTab(page, id);
		await expect(twStart(page)).toHaveValue('7');
		await expect(twEnd(page)).toHaveValue('14');
	});

	// ── AC-3a: Round-Trip ohne Zeitfenster-Aenderung erhaelt das Zeitfenster ──
	// Nicht-Regressions-Waechter: heute gruen (Round-Trip-Spread erhaelt 07-14),
	// MUSS nach dem Fix gruen bleiben (kein Reset auf Default).
	test('AC-3a: Namensaenderung erhaelt Zeitfenster und Empfaenger (Round-Trip)', async ({
		page
	}) => {
		const { id, empfaenger } = await createPreset(page, { hour_from: 7, hour_to: 14 });

		// Edit oeffnen, NUR den Namen aendern, Zeitfenster nicht anfassen.
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		const neuerName = 'Nur-Name-1134 ' + Date.now();
		await page.locator('[data-testid="compare-editor-name"]').fill(neuerName);
		await page.locator('[data-testid="compare-editor-save"]').click();
		await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 8_000 });

		// Zeitfenster + Empfaenger duerfen NICHT auf einen Default zurueckfallen.
		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.name).toBe(neuerName);
		expect(preset.hour_from, 'hour_from muss 7 bleiben').toBe(7);
		expect(preset.hour_to, 'hour_to muss 14 bleiben').toBe(14);
		expect(preset.empfaenger, 'Empfaenger duerfen nicht verloren gehen').toEqual(empfaenger);

		// Aus Nutzersicht: Edit-Seite zeigt weiterhin 07-14.
		await openVersandTab(page, id);
		await expect(twStart(page)).toHaveValue('7');
		await expect(twEnd(page)).toHaveValue('14');
	});
});

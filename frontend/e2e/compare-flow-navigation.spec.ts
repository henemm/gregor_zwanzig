// E2E (Staging) — Issue #1256 Scheibe 2: Fluss-Verdrahtung Create→Detail-Redirect,
// Back-Nav, Abbrechen (AC-25–AC-29).
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 2
//
// Ist-Analyse (Spec-Phase + diese Scheibe): alle vier Übergänge sind BEREITS
// implementiert (reine Regressionsabsicherung, kein Neubau) — s. Abschnitt
// „Verifizierte Ausgangslage" in der Spec. Dieser Test sichert sie mit
// ECHTEN Klickpfaden ab (kein goto() wo ein Klick gefordert ist), Desktop UND
// Mobile (AC-25 „Desktop oder Mobile", AC-28 Zurück-Pfeil, Testplan „plus
// Mobile-Äquivalent").
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1256-s2.staging.config.ts

import { test, expect, type Page } from '@playwright/test';

// Staging-Hygiene (Fix-Loop F003): jeder in einem Test angelegte Preset wird
// hier gesammelt und im file-weiten afterEach wieder gelöscht.
let createdIds: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of createdIds) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdIds = [];
});

async function createPreset(page: Page, name: string): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: [],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: []
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdIds.push(id);
	return id;
}

test.describe('Issue #1256 Scheibe 2: Compare-Fluss Klickpfade Desktop (AC-25–AC-29)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-25: Kachel-Klick → /compare/{id} (Detail-Hub) ─────────────────────
	test('AC-25: Klick auf eine Compare-Kachel in der Liste navigiert auf das Detail (Desktop)', async ({
		page
	}) => {
		const name = `E2E Fluss-Kachel ${Date.now()}`;
		const id = await createPreset(page, name);

		await page.goto('/compare');
		await page.waitForLoadState('networkidle');

		// Sowohl Desktop (CompareGrid) als auch Mobile-Stack rendern die Kachel mit
		// data-testid="compare-tile-{id}" (nur einer der beiden ist :visible,
		// analog issue-1080-Spec-Konvention gegen strict-mode-Konflikte).
		const tile = page.locator(`[data-testid="compare-tile-${id}"]:visible`);
		await expect(tile).toBeVisible({ timeout: 10_000 });
		await tile.click();

		await expect(page).toHaveURL(new RegExp(`/compare/${id}$`), { timeout: 10_000 });
	});

	// ── AC-28: Hub-Breadcrumb/Zurück → /compare (Liste) ──────────────────────
	test('AC-28: Breadcrumb "Orts-Vergleiche" im Detail-Hub navigiert zurück zur Liste (Desktop)', async ({
		page
	}) => {
		const name = `E2E Fluss-Zurueck ${Date.now()}`;
		const id = await createPreset(page, name);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const breadcrumb = page.locator('a:has-text("ORTS-VERGLEICHE"):visible');
		await expect(breadcrumb).toBeVisible({ timeout: 10_000 });
		await breadcrumb.click();

		await expect(page).toHaveURL(/\/compare$/, { timeout: 10_000 });
	});

	// ── AC-27: Create-Abbrechen → /compare (Liste) ───────────────────────────
	test('AC-27: "Abbrechen" im Create-Editor navigiert zurück zur Liste', async ({ page }) => {
		await page.goto('/compare');
		await page.waitForLoadState('networkidle');

		// Echter Klick auf "+ Neuer Vergleich" statt goto('/compare/new').
		const newBtn = page.locator('a:has-text("Neuer Vergleich"):visible');
		await expect(newBtn).toBeVisible({ timeout: 10_000 });
		await newBtn.click();
		await expect(page).toHaveURL(/\/compare\/new$/, { timeout: 10_000 });

		const cancelBtn = page.locator('a:has-text("Abbrechen"):visible');
		await expect(cancelBtn).toBeVisible({ timeout: 10_000 });
		await cancelBtn.click();

		await expect(page).toHaveURL(/\/compare$/, { timeout: 10_000 });
	});

	// ── AC-26/AC-29: kompletter Fluss Liste→Neu→Editor→Aktivieren→Detail (kein Zwischen-Screen) ──
	test('AC-26/AC-29: kompletter Fluss endet nach "Briefing aktivieren" im Detail des NEUEN Vergleichs (nicht Liste, nicht Editor)', async ({
		page
	}) => {
		await page.goto('/compare');
		await page.waitForLoadState('networkidle');

		const newBtn = page.locator('a:has-text("Neuer Vergleich"):visible');
		await newBtn.click();
		await expect(page).toHaveURL(/\/compare\/new$/, { timeout: 10_000 });

		const uniqueName = `E2E Fluss-Aktivieren ${Date.now()}`;
		await page.locator('[data-testid="compare-editor-name"]:visible').fill(uniqueName);
		await page.locator('[data-testid="compare-editor-continue-orte"]:visible').click();

		// Zwei Orte per Smart-Import/Koordinaten hinzufügen (deterministisch, kein
		// externer Google/Nominatim-Aufruf nötig — analog issue-1080-compare-new-url.spec.ts).
		const coords: Array<[string, string]> = [
			['47.2692', '11.4041'],
			['47.1015', '11.2958']
		];
		for (const [lat, lon] of coords) {
			const importInput = page.locator('[data-testid="compare-step2-smart-import-input"]:visible');
			await importInput.fill(`${lat}, ${lon}`);
			await page.locator('[data-testid="compare-step2-resolve-btn"]:visible').click();
			const addBtn = page.locator('button:has-text("Zum Vergleich hinzufügen"):visible');
			await expect(addBtn).toBeVisible({ timeout: 15_000 });
			await addBtn.click();
		}

		// Tab-Fortschritt: Idealwerte → Layout → Versand (echte Klicks, schaltet
		// versandVisited frei — Voraussetzung für "Briefing aktivieren").
		await page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible').click();
		await page.locator('[data-testid="compare-editor-tab-layout"]:visible').click();
		await page.locator('[data-testid="compare-editor-tab-versand"]:visible').click();

		const activateBtn = page.locator('[data-testid="compare-editor-activate"]:visible');
		await expect(activateBtn).toBeEnabled({ timeout: 10_000 });
		await activateBtn.click();

		// AC-26: Redirect auf /compare/{neue-id} (Detail), NICHT auf /compare
		// (Liste ohne ID) und KEIN Verbleib im Editor (/compare/new).
		await expect(page).toHaveURL(/\/compare\/[^/]+$/, { timeout: 15_000 });
		await expect(page).not.toHaveURL(/\/compare\/new$/);
		await expect(page).not.toHaveURL(/^.*\/compare\/?$/);

		// AC-29: kein Zwischen-Screen (insbesondere nicht /compare/{id}/edit) im
		// Fluss selbst — die finale URL landet direkt im Hub.
		await expect(page).not.toHaveURL(/\/edit$/);

		// Gegenprobe: der neu angelegte Vergleich ist tatsächlich im Detail-Hub sichtbar.
		await expect(
			page.locator(`text=${uniqueName}`).locator(':visible').first()
		).toBeVisible({ timeout: 10_000 });

		// F003: Staging-Hygiene — die per UI (nicht per createPreset()) angelegte
		// ID aus der finalen Detail-URL extrahieren und zum Cleanup vormerken.
		const finalUrl = page.url();
		const newId = finalUrl.replace(/\/$/, '').split('/').pop();
		if (newId) createdIds.push(newId);
	});
});

// ── Mobile-Äquivalent (Fix-Loop F001) — AC-25 "Desktop oder Mobile", AC-28 ──
// Zurück-Pfeil, Spec-Testplan "plus Mobile-Äquivalent". Viewport 390×844
// (iPhone-Klasse) schaltet auf den CSS-only Mobile-Zweig (<900px) — Desktop-
// Markup bleibt gleichzeitig im DOM, daher :visible-Disambiguierung wie im
// Desktop-Block.
test.describe('Issue #1256 Scheibe 2: Compare-Fluss Klickpfade Mobile (AC-25, AC-28)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
	});

	// ── AC-25 Mobile: Kachel-Tipp im Mobile-Stack → /compare/{id} ────────────
	test('AC-25: Tipp auf eine Compare-Kachel im Mobile-Stack navigiert auf das Detail', async ({
		page
	}) => {
		const name = `E2E Fluss-Kachel-Mobile ${Date.now()}`;
		const id = await createPreset(page, name);

		await page.goto('/compare');
		await page.waitForLoadState('networkidle');

		// Unter 900px rendert routes/compare/+page.svelte den mobilen
		// Kachel-Stack (<a href="/compare/{id}">), das Desktop-Grid bleibt via
		// CSS ausgeblendet, aber im DOM vorhanden — :visible ist Pflicht.
		const tile = page.locator(`[data-testid="compare-tile-${id}"]:visible`);
		await expect(tile).toBeVisible({ timeout: 10_000 });
		await tile.click();

		await expect(page).toHaveURL(new RegExp(`/compare/${id}$`), { timeout: 10_000 });
	});

	// ── AC-28 Mobile: Zurück-Pfeil im Hub → /compare (Liste) ─────────────────
	test('AC-28: Mobiler Zurück-Pfeil im Detail-Hub navigiert zurück zur Liste', async ({
		page
	}) => {
		const name = `E2E Fluss-Zurueck-Mobile ${Date.now()}`;
		const id = await createPreset(page, name);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		// routes/compare/[id]/+page.svelte:172-178 — mobiler Zurück-Pfeil,
		// aria-label="Zurück zur Übersicht" (Desktop-Breadcrumb bleibt via CSS
		// ausgeblendet, aber im DOM vorhanden).
		const backArrow = page.locator('a[aria-label="Zurück zur Übersicht"]:visible');
		await expect(backArrow).toBeVisible({ timeout: 10_000 });
		await backArrow.click();

		await expect(page).toHaveURL(/\/compare$/, { timeout: 10_000 });
	});
});

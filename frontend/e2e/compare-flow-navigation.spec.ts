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
// Fix-Loop 2 (F004-Nachfund): der AC-26/29-Test legt zusätzlich Locations per
// Smart-Import an — auch die werden getrackt und aufgeräumt (Root Cause s. u.).
let createdLocationIds: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of createdIds) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdIds = [];
	for (const id of createdLocationIds) {
		try {
			await page.request.delete(`/api/locations/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdLocationIds = [];
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
		//
		// Fix-Loop 2 Root Cause (Trace-Beleg, s. Bericht): mit reinen
		// Koordinaten-Defaultnamen kollidiert die serverseitige ID
		// (toKebab(Name), internal/handler/location.go:19+91-99) bei jedem
		// Wiederholungslauf mit denselben Koordinaten → HTTP 409 "Ort mit dieser
		// ID existiert bereits", addLocation() bricht in den catch-Zweig ab, ohne
		// die ID zu pickedIds hinzuzufügen. Reproduziert per --trace on: beide
		// POST /api/locations dieses Testlaufs kamen mit Status 409 zurück.
		// Fix: expliziter, pro Lauf eindeutiger Name im "Erkannt"-Namensfeld
		// (compare-step2-name-input) statt des Koordinaten-Defaultnamens.
		const uniqueSuffix = Date.now();
		const coords: Array<[string, string, string]> = [
			['47.2692', '11.4041', `E2E Fluss-Ort-A ${uniqueSuffix}`],
			['47.1015', '11.2958', `E2E Fluss-Ort-B ${uniqueSuffix}`]
		];
		for (let i = 0; i < coords.length; i++) {
			const [lat, lon, locName] = coords[i];
			const importInput = page.locator('[data-testid="compare-step2-smart-import-input"]:visible');
			await importInput.fill(`${lat}, ${lon}`);
			await page.locator('[data-testid="compare-step2-resolve-btn"]:visible').click();

			const nameInput = page.locator('[data-testid="compare-step2-name-input"]:visible');
			await expect(nameInput).toBeVisible({ timeout: 15_000 });
			await nameInput.fill(locName);

			const addBtn = page.locator('button:has-text("Zum Vergleich hinzufügen"):visible');
			await expect(addBtn).toBeVisible({ timeout: 15_000 });
			await addBtn.click();

			// Härtung (Fix-Loop 2, Coordinator-Punkt 3): auf den tatsächlich
			// erhöhten Picked-Zähler warten statt sofort in die nächste
			// Iteration zu springen — verhindert stille Fehlschläge (z. B. den
			// obigen 409) unbemerkt bis zum viel späteren Aktivieren-Timeout.
			await expect(
				page
					.locator('[data-testid="compare-step2-picked-list"]')
					.locator('[data-testid^="compare-step2-picked-item-"]')
			).toHaveCount(i + 1, { timeout: 10_000 });
		}

		// Staging-Hygiene: IDs der per UI angelegten Orte aus den
		// Picked-Item-Testids extrahieren, damit afterEach sie löschen kann.
		const pickedItemTestIds = await page
			.locator('[data-testid="compare-step2-picked-list"]')
			.locator('[data-testid^="compare-step2-picked-item-"]')
			.evaluateAll((els) => els.map((el) => el.getAttribute('data-testid')));
		for (const tid of pickedItemTestIds) {
			const locId = tid?.replace('compare-step2-picked-item-', '');
			if (locId) createdLocationIds.push(locId);
		}

		// Tab-Fortschritt: Idealwerte → Layout → Versand (echte Klicks, schaltet
		// versandVisited frei — Voraussetzung für "Briefing aktivieren"). Nach
		// jedem Klick wird geprüft, dass der Tab wirklich aktiv wurde (Härtung
		// Coordinator-Punkt 3), statt blind weiterzuspringen.
		const idealwerteTab = page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible');
		await idealwerteTab.click();
		await expect(idealwerteTab).toHaveAttribute('data-active', 'true', { timeout: 5_000 });

		const layoutTab = page.locator('[data-testid="compare-editor-tab-layout"]:visible');
		await layoutTab.click();
		await expect(layoutTab).toHaveAttribute('data-active', 'true', { timeout: 5_000 });

		const versandTab = page.locator('[data-testid="compare-editor-tab-versand"]:visible');
		await versandTab.click();
		await expect(versandTab).toHaveAttribute('data-active', 'true', { timeout: 5_000 });

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

		// F003: Staging-Hygiene — die per UI (nicht per createPreset()) angelegte
		// ID aus der finalen Detail-URL extrahieren und SOFORT zum Cleanup
		// vormerken (Fix-Loop 2 Nachfund: vorher stand dieser Block NACH der
		// Gegenprobe unten — schlug die Gegenprobe fehl, wurde die ID nie
		// getrackt und der Preset blieb als Orphan auf Staging liegen, obwohl
		// er längst real angelegt war. Jetzt direkt nach der URL-Bestätigung).
		const finalUrl = page.url();
		const newId = finalUrl.replace(/\/$/, '').split('/').pop();
		if (newId) createdIds.push(newId);

		// Gegenprobe: der neu angelegte Vergleich ist tatsächlich im Detail-Hub sichtbar.
		//
		// Fix-Loop 2 Nachfund: `.locator(':visible')` VOM Text-Match aus sucht nur
		// unter dessen NACHFAHREN (hier: die h1-Überschrift hat keine Kind-Elemente
		// -> "element(s) not found", obwohl die Überschrift selbst sichtbar im DOM
		// stand — s. Trace-Beleg im Bericht). `.filter({ visible: true })` prüft
		// dagegen die getroffenen Elemente selbst (Desktop-Hub UND Mobile-Hub
		// rendern denselben Namen gleichzeitig im DOM, CSS blendet einen aus).
		await expect(
			page.getByText(uniqueName).filter({ visible: true }).first()
		).toBeVisible({ timeout: 10_000 });
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

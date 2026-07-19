// E2E (Staging) — Issue #1256 Scheibe 2: Fluss-Verdrahtung Create→Detail-Redirect,
// Back-Nav, Abbrechen (AC-25–AC-29).
// Issue #1256 Scheibe 3 (ergänzt): Hub-Header-Kebab auf Lifecycle
// (AC-5/KL-7) + Übersicht-Tab bleibt reiner Ansehen-Tab (AC-30). Ergänzt
// statt neuer Datei, damit der bestehende testMatch der
// playwright.1256-s2.staging.config.ts (matcht exakt diesen Dateinamen)
// unverändert bleibt.
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 2 + 3
//
// Ist-Analyse (Spec-Phase + diese Scheibe): alle vier Übergänge sind BEREITS
// implementiert (reine Regressionsabsicherung, kein Neubau) — s. Abschnitt
// „Verifizierte Ausgangslage" in der Spec. Dieser Test sichert sie mit
// ECHTEN Klickpfaden ab (kein goto() wo ein Klick gefordert ist), Desktop UND
// Mobile (AC-25 „Desktop oder Mobile", AC-28 Zurück-Pfeil, Testplan „plus
// Mobile-Äquivalent").
//
// Scheibe 3 RED-Erwartung (aktueller Stand, vor Phase 6): der Hub-Header-
// Kebab speist sich noch aus `compareActions()` (Listen-Vertrag, KEIN
// "Archivieren" mehr seit Scheibe 1 — s. KL-7) statt der neuen
// `compareLifecycleActions()`. Die AC-5/KL-7-Tests unten schlagen daher heute
// fehl: "Archivieren" ist im Hub-Kebab nicht auffindbar (KL-7-Zwischenzustand,
// PO-abgesegnet), und das Menü zeigt 5 statt 3 Einträge.
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

// ── Scheibe 3 Fixtures (AC-5/KL-7/AC-30): Preset MIT Ort, damit
//    deriveStatusFromPreset() nicht auf "draft" fällt (location_ids darf
//    für den Lifecycle-Status nicht leer sein). ────────────────────────────
async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
	expect(res.ok(), 'Location-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdLocationIds.push(id);
	return id;
}

async function createPresetWithLocation(
	page: Page,
	name: string,
	schedule: 'daily' | 'manual',
	locationId: string
): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: [locationId],
			schedule,
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com']
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdIds.push(id);
	return id;
}

// Fix-Loop 1 (F001): Preset MIT bereits gesetzten channel_layouts anlegen —
// simuliert einen bestehenden Vergleich, dessen Layout-Tab schon einmal
// gespeichert wurde. Metrik-IDs müssen nicht im aktuellen Katalog existieren
// (dieser Test besucht den Layout-Tab absichtlich NICHT — es geht nur darum,
// dass display_config.channel_layouts server-seitig bereits einen Wert trägt).
async function createPresetWithChannelLayouts(
	page: Page,
	name: string,
	locationId: string
): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: [locationId],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			display_config: {
				channel_layouts: {
					email: [{ metric_id: 'wind_max_kmh', enabled: true, bucket: 'primary', order: 0 }],
					telegram: [{ metric_id: 'wind_max_kmh', enabled: true, bucket: 'primary', order: 0 }],
					sms: [{ metric_id: 'wind_max_kmh', enabled: true, bucket: 'primary', order: 0 }]
				}
			}
		}
	});
	expect(res.ok(), 'Preset-Anlage (mit channel_layouts) fehlgeschlagen: ' + res.status()).toBeTruthy();
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

		// Sowohl Desktop (geteiltes ListTable-Organism, Issue #1277) als auch
		// Mobile-Stack rendern die Zeile/Kachel mit data-testid="compare-tile-{id}"
		// (nur einer der beiden ist :visible, analog issue-1080-Spec-Konvention
		// gegen strict-mode-Konflikte).
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
		// Epic #1301 F2a: neue Freischalt-Kette — Wertebereiche ist erst nach Besuch
		// des NEUEN Wetter-Metriken-Tabs frei (echter Klick, kein goto).
		await page.locator('[data-testid="compare-editor-tab-metriken"]:visible').click();
		const idealwerteTab = page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible');
		await idealwerteTab.click();
		await expect(idealwerteTab).toHaveAttribute('data-active', 'true', { timeout: 5_000 });

		const layoutTab = page.locator('[data-testid="compare-editor-tab-layout"]:visible');
		await layoutTab.click();
		await expect(layoutTab).toHaveAttribute('data-active', 'true', { timeout: 5_000 });

		// Issue #1258 Scheibe S4 (E1/E2, AC-28): "alarme" ist reguläre Station
		// zwischen "layout" und "versand" — "versand" bleibt ohne Alarme-Besuch
		// gesperrt.
		const alarmeTab = page.locator('[data-testid="compare-editor-tab-alarme"]:visible');
		await alarmeTab.click();
		await expect(alarmeTab).toHaveAttribute('data-active', 'true', { timeout: 5_000 });

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

// ── Scheibe 3 (AC-5, KL-7, AC-30): Hub-Header-Kebab auf Lifecycle ───────────
//
// Ist (Issue #1261, löst den bewusst editier-losen #1256-S3-Desktop-Zustand
// auf — der Nutzer fand "Bearbeiten" hier nicht (Bug #1261)): Der Hub-Header-
// Kebab speist sich aus compareDetailActions(status) (subscriptionHelpers.ts)
// = Lifecycle-Liste (Pausieren/Aktivieren, Archivieren, Löschen) PLUS
// "Bearbeiten" für active/paused — macht den Editor auf der Desktop-
// Detailseite wieder auffindbar, während "Vorschau öffnen"/"Briefing jetzt
// senden" weiterhin exklusiv über Tabs/Primäraktion laufen (nicht im
// Hub-Kebab). "Archivieren" bleibt erreichbar (KL-7 unverändert).
test.describe('Issue #1256 Scheibe 3: Hub-Header-Kebab Lifecycle (AC-5, KL-7, AC-30)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-5: Hub-Kebab bei pausiertem Vergleich = [Aktivieren, Archivieren, Bearbeiten, Löschen] ──
	test('AC-5: Hub-Header-Kebab (pausierter Vergleich) zeigt Aktivieren/Archivieren/Bearbeiten/Löschen', async ({
		page
	}) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S3 Ort ${suffix}`, 47.05, 11.32);
		const name = `E2E S3 Paused ${suffix}`;
		const id = await createPresetWithLocation(page, name, 'manual', locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const kebabTrigger = page.locator('button[aria-label="Weitere Aktionen"]:visible').first();
		await expect(kebabTrigger).toBeVisible({ timeout: 10_000 });
		await kebabTrigger.click();

		// Lifecycle-Vertrag: "Archivieren" erreichbar (KL-7), "Bearbeiten" seit #1261 ergänzt.
		await expect(page.getByRole('menuitem', { name: 'Aktivieren' })).toBeVisible({ timeout: 5_000 });
		await expect(page.getByRole('menuitem', { name: 'Archivieren' })).toBeVisible({ timeout: 5_000 });
		await expect(page.getByRole('menuitem', { name: 'Löschen' })).toBeVisible({ timeout: 5_000 });
		await expect(page.getByRole('menuitem', { name: 'Bearbeiten' })).toBeVisible({ timeout: 5_000 });

		// Listen-exklusive Aktionen dürfen im Hub-Header weiterhin NICHT auftauchen.
		await expect(page.getByRole('menuitem', { name: 'Vorschau öffnen' })).not.toBeVisible();
		await expect(page.getByRole('menuitem', { name: 'Briefing jetzt senden' })).not.toBeVisible();

		await expect(page.getByRole('menuitem')).toHaveCount(4);

		await page.keyboard.press('Escape');
	});

	// ── AC-5/KL-7: "Archivieren" im Hub-Kebab entfernt den Vergleich aus der aktiven Liste ──
	test('KL-7-Auflösung: "Archivieren" im Hub-Header-Kebab archiviert per PATCH /state und verlässt die aktive Liste', async ({
		page
	}) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S3 Ort-Archiv ${suffix}`, 46.98, 11.1);
		const name = `E2E S3 Archivieren ${suffix}`;
		const id = await createPresetWithLocation(page, name, 'daily', locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const kebabTrigger = page.locator('button[aria-label="Weitere Aktionen"]:visible').first();
		await expect(kebabTrigger).toBeVisible({ timeout: 10_000 });
		await kebabTrigger.click();

		const archiveItem = page.getByRole('menuitem', { name: 'Archivieren' });
		await expect(archiveItem).toBeVisible({ timeout: 5_000 });

		const patchPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}/state`) && res.request().method() === 'PATCH'
		);
		await archiveItem.click();
		const patchRes = await patchPromise;
		expect(patchRes.ok(), 'PATCH .../state (archive) fehlgeschlagen: ' + patchRes.status()).toBeTruthy();

		// Archivieren navigiert zurück auf die Liste (analog archivePreset(),
		// +page.svelte:99-111) — der archivierte Vergleich darf dort NICHT
		// mehr als aktive Kachel auftauchen.
		await expect(page).toHaveURL(/\/compare$/, { timeout: 10_000 });
		await page.waitForLoadState('networkidle');
		await expect(page.locator(`[data-testid="compare-tile-${id}"]`)).toHaveCount(0, { timeout: 10_000 });
	});

	// ── AC-30: Übersicht-Tab bleibt reiner Ansehen-Tab (SummaryCard-Sprung wechselt nur den Tab) ──
	test('AC-30: SummaryCard "Bearbeiten →" (Orte) wechselt den Tab inline, keine volle Seiten-Navigation', async ({
		page
	}) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S3 Ort-Uebersicht ${suffix}`, 47.4, 10.9);
		const name = `E2E S3 Uebersicht ${suffix}`;
		const id = await createPresetWithLocation(page, name, 'daily', locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const uebersichtTab = page.locator('[data-testid="compare-detail-tab-uebersicht"]:visible');
		await expect(uebersichtTab).toBeVisible({ timeout: 10_000 });

		// "Bearbeiten →" auf der Orte-SummaryCard im Übersicht-Tab.
		const editJump = page
			.locator('button:has-text("Bearbeiten →")')
			.filter({ visible: true })
			.first();
		await expect(editJump).toBeVisible({ timeout: 10_000 });

		// Kein voller Reload: eine SPA-Navigation über history.replaceState()
		// löst KEIN 'framenavigated' mit Haupt-Dokument-Neuladen aus — als
		// Nachweis prüfen wir, dass die Übersicht-Tab-Leiste (identisches
		// DOM-Element) den Klick unverändert überlebt (kein Full-Page-Reload).
		await editJump.click();

		const orteTab = page.locator('[data-testid="compare-detail-tab-orte"]:visible');
		await expect(orteTab).toHaveAttribute('data-testid', 'compare-detail-tab-orte');
		await expect(page).toHaveURL(/\?tab=orte/, { timeout: 5_000 });

		// Der Übersicht-Tab bleibt im DOM erreichbar (kein Redirect zu
		// /compare/{id}/edit) — Klick zurück auf "Übersicht" muss funktionieren,
		// ohne dass die Seite zwischenzeitlich neu geladen wurde.
		await expect(page).not.toHaveURL(/\/edit/);
	});
});

// ── Scheibe 4 (AC-8, AC-9, AC-10): Editor-Tab "Layout" = geteilter
// LayoutTab-Organism (context="vergleich") ───────────────────────────────
//
// WICHTIGER IST-BEFUND (s. Bericht + compare_editor_layout_tab_wiring.test.ts):
// der Organism ist HEUTE bereits ueber die Step4Layout-Huelle intern
// gemountet (Step4Layout.svelte:293-338 rendert <LayoutTab context="vergleich">
// + <LTComparePreview>). Auf DOM-Ebene sind die folgenden drei Tests daher
// schon VOR Phase 6 grün erwartet (Regressionsanker) — sie sichern ab, dass
// beim Entfernen der Step4Layout-Huelle (Scheibe 4, CompareEditor.svelte
// mountet LayoutTab direkt) die Orte-/Kanal-Datenanbindung erhalten bleibt.
// Der eigentliche RED-Befund liegt auf Quelltext-Ebene (Komponenten-Identitaet
// CompareEditor.svelte -> Step4Layout statt LayoutTab), s. Kern-Test-Datei.
test.describe('Issue #1256 Scheibe 4: Editor-Layout-Tab = geteilter LayoutTab-Organism (AC-8, AC-9, AC-10)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	async function reachLayoutTabWithTwoLocations(page: Page, namePrefix: string): Promise<void> {
		await page.goto('/compare');
		await page.waitForLoadState('networkidle');

		const newBtn = page.locator('a:has-text("Neuer Vergleich"):visible');
		await newBtn.click();
		await expect(page).toHaveURL(/\/compare\/new$/, { timeout: 10_000 });

		const uniqueName = `${namePrefix} ${Date.now()}`;
		await page.locator('[data-testid="compare-editor-name"]:visible').fill(uniqueName);
		await page.locator('[data-testid="compare-editor-continue-orte"]:visible').click();

		// Zwei Orte per Smart-Import (deterministisch, Muster AC-26/29 oben).
		const uniqueSuffix = Date.now();
		const coords: Array<[string, string, string]> = [
			['47.2692', '11.4041', `${namePrefix}-Ort-A ${uniqueSuffix}`],
			['47.1015', '11.2958', `${namePrefix}-Ort-B ${uniqueSuffix}`]
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

			await expect(
				page
					.locator('[data-testid="compare-step2-picked-list"]')
					.locator('[data-testid^="compare-step2-picked-item-"]')
			).toHaveCount(i + 1, { timeout: 10_000 });
		}

		const pickedItemTestIds = await page
			.locator('[data-testid="compare-step2-picked-list"]')
			.locator('[data-testid^="compare-step2-picked-item-"]')
			.evaluateAll((els) => els.map((el) => el.getAttribute('data-testid')));
		for (const tid of pickedItemTestIds) {
			const locId = tid?.replace('compare-step2-picked-item-', '');
			if (locId) createdLocationIds.push(locId);
		}

		// Epic #1301 F2a: neue Freischalt-Kette — Wertebereiche ist erst nach Besuch
		// des NEUEN Wetter-Metriken-Tabs frei (echter Klick, kein goto).
		await page.locator('[data-testid="compare-editor-tab-metriken"]:visible').click();
		const idealwerteTab = page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible');
		await idealwerteTab.click();
		await expect(idealwerteTab).toHaveAttribute('data-active', 'true', { timeout: 5_000 });

		const layoutTab = page.locator('[data-testid="compare-editor-tab-layout"]:visible');
		await layoutTab.click();
		await expect(layoutTab).toHaveAttribute('data-active', 'true', { timeout: 5_000 });
	}

	// ── AC-8 (Epic #1301 F2a): Editor-Layout-Tab = geteilte Stundenverlauf-Steuerung ──
	// Umgeschrieben vom entfernten LayoutTab-/channel_layouts-Organism auf den neuen
	// Layout-Tab-Inhalt: die geteilte Komponente CompareHourlyLayoutControls
	// (Stundenverlauf-Toggle + Metrik-Auswahl). Die alte Attrappe
	// (layout-tab-Organism, compare-step4-layout-preview, channel-tab-*) wurde vom
	// Compare-Renderpfad nie gelesen (#1301-Grundbefund) und entfällt ersatzlos.
	test('AC-8: Editor-Layout-Tab zeigt die geteilte Stundenverlauf-Steuerung', async ({ page }) => {
		await reachLayoutTabWithTwoLocations(page, 'E2E S4 Hourly');

		await expect(
			page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible').first()
		).toBeVisible({ timeout: 10_000 });
		await expect(
			page.locator('[data-testid="compare-layout-hourly-metrics"]:visible').first()
		).toBeVisible();
	});

	// ── AC-9 (F2a): die alte channel_layouts-Attrappe ist verschwunden ──────────
	test('AC-9: kein Layout-Preview / kein Channel-Tab im Editor-Layout-Tab mehr', async ({ page }) => {
		await reachLayoutTabWithTwoLocations(page, 'E2E S4 NoAttrappe');

		await expect(page.locator('[data-testid="compare-step4-layout-preview"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="channel-tab-telegram"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="layout-tab"][data-context="vergleich"]')).toHaveCount(0);
	});
});

// ── Fix-Loop 1 (Adversary F001, HIGH): Zukunfts-Wächter gegen den behobenen
// Bug ─────────────────────────────────────────────────────────────────────
//
// Root Cause (Code-Timing-Diff gegen HEAD 3e2c17af): der Katalog-Fetch +
// channelLayouts-Rewrite-$effect hingen kurzzeitig an einem unbedingten
// onMount() im Editor-Top-Level statt (wie im ursprünglichen Step4Layout.svelte)
// am LAZY MOUNT des Layout-Tab-Inhalts. Dadurch wurde bei JEDEM Öffnen eines
// bestehenden Vergleichs (unabhängig vom besuchten Tab) wiz.channelLayouts mit
// einer strukturell abweichenden JSON-Fassung überschrieben → falscher
// "Ungespeichert"-Zustand direkt beim Öffnen. Behoben: Fetch + Rewrite-Effect
// sind jetzt an activeTab === 'layout' gekoppelt (einmalig, Start-Guard
// ltCatalogLoadStarted) — s. compare_editor_layout_tab_wiring.test.ts für den
// lokalen ROT→GRÜN-Beleg auf Quelltext-Ebene.
//
// Dieser Test läuft NUR sinnvoll gegen einen bereits deployten S4-Stand
// (Staging hatte zum Zeitpunkt des Fix-Loops noch 3e2c17af, also weder Bug
// noch Fix — ein ROT-Beleg gegen Staging ist hier strukturell unmöglich,
// s. PO-Korrektur). Er ist der Zukunfts-Wächter für /e2e-verify nach dem
// nächsten Push: grün dort bestätigt, dass das Fehlverhalten nicht live geht.
test.describe('Issue #1256 Fix-Loop 1 (F001): Editor öffnet bestehenden Vergleich ohne falsches "Ungespeichert"', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('Bestehender Vergleich mit gesetzten channel_layouts öffnet im Standard-Tab ohne Dirty-Indikator', async ({
		page
	}) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E FixLoop1 Ort ${suffix}`, 47.15, 11.05);
		const name = `E2E FixLoop1 Dirty ${suffix}`;
		const id = await createPresetWithChannelLayouts(page, name, locId);

		// Standard-Tab (kein ?tab=-Query) — der Bug betraf JEDEN Tab, daher
		// bewusst NICHT der Layout-Tab, um zu beweisen, dass der Fetch nicht
		// mehr unbedingt bei Editor-Mount läuft.
		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		// Kurz warten (Katalog-Fetch-Fenster) — falls der Fetch fälschlich
		// unbedingt liefe, hätte der channelLayouts-Rewrite-Effect in diesem
		// Fenster bereits geschrieben.
		await page.waitForTimeout(2_500);

		const saveIndicator = page.locator('[data-testid="save-indicator"]:visible');
		await expect(saveIndicator).toBeVisible({ timeout: 10_000 });
		await expect(saveIndicator).not.toHaveAttribute('data-state', 'dirty');
		await expect(saveIndicator).not.toContainText('Nicht gespeichert');
	});
});

// ── Scheibe 4 (Hub, Aufgabenstellung 3c): Layout-Tab im Hub ─────────────
//
// KLÄRUNGSBEDARF (im Bericht markiert): die Spec selbst (Zeilen 214-216,
// "Zielmodell") legt fest, dass der Hub-Layout-Tab bewusst ein reiner
// Ansehen-/Summary-Tab OHNE Editier-Affordanzen bleibt ("Layout ist im JSX
// ein reiner Summary-Tab") — NICHT der volle LayoutTab-Organism wie im
// Editor. Dieser Test prüft daher Daten-Konsistenz (keine Organism-
// Duplizierung, Panel bleibt erreichbar), NICHT Komponenten-Identität mit
// dem Editor-Organism. Sollte der PO "denselben Organism" im Hub wörtlich
// meinen, widerspricht das dem aktuellen Spec-Text und braucht eine
// Spec-Klarstellung vor Phase 6 (s. Bericht).
test.describe('Issue #1256 Scheibe 4 (Hub): Layout-Tab bleibt daten-konsistenter Summary-Tab', () => {
	test('Hub-Layout-Tab bleibt erreichbar und rendert KEIN Organism-Duplikat (Ansehen-only laut Spec-Zielmodell)', async ({
		page
	}) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S4 Hub-Ort ${suffix}`, 47.3, 11.0);
		const name = `E2E S4 Hub-Layout ${suffix}`;
		const id = await createPresetWithLocation(page, name, 'daily', locId);

		await page.goto(`/compare/${id}?tab=layout`);
		await page.waitForLoadState('networkidle');

		const panel = page.locator('[data-testid="compare-detail-panel-layout"]:visible');
		await expect(panel).toBeVisible({ timeout: 10_000 });
		// Summary-Tab bleibt Ansehen-only laut Spec-Zielmodell — kein
		// eingebetteter LayoutTab-Organism im Hub (Unterschied zu Orte/
		// Idealwerte/Versand, die ab Scheibe 6/7 inline editierbar werden).
		await expect(page.locator('[data-testid="layout-tab"]')).toHaveCount(0);
	});
});

// ── Scheibe 5 (AC-12, AC-13): Editor-Tab "Orte" — Fidelity-Verifikation ────
//
// AC-12 (Regressionsanker, bereits heute grün): Smart-Import, min-2-
// Validierung und nummerierte Auswahlliste sind unverändert funktionsfähig.
// AC-13 (GREEN seit Phase 6): die Bibliothek gruppierte vor Phase 6 nach
// `loc.region` (Lawinenwarnregion, vom Smart-Import-Resolver nie befüllt)
// statt nach der App-eigenen Group-Entity (`group_id`/`GET /api/groups`,
// Issue #301) — s. step2_orte_library_grouping.test.ts für den
// Quelltext-Beleg. Der Test unten beweist die Behebung auf DOM-Ebene: ein
// Ort mit gesetzter group_id erscheint jetzt unter seiner Gruppen-Kopfzeile.
test.describe('Issue #1256 Scheibe 5: Editor-Tab "Orte" Fidelity (AC-12, AC-13)', () => {
	let createdGroupIds: string[] = [];

	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test.afterEach(async ({ page }) => {
		for (const id of createdGroupIds) {
			try {
				await page.request.delete(`/api/groups/${id}`);
			} catch {
				/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
			}
		}
		createdGroupIds = [];
	});

	async function openNewCompareOrteTab(page: Page, editorName: string): Promise<void> {
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-name"]:visible').fill(editorName);
		await page.locator('[data-testid="compare-editor-continue-orte"]:visible').click();
		await expect(page.locator('[data-testid="compare-wizard-step-2"]:visible')).toBeVisible({
			timeout: 10_000
		});
	}

	// ── AC-12: Smart-Import-Flow + Picked-Nummerierung sichtbar ─────────────
	test('AC-12: Smart-Import legt einen Ort an, der nummeriert (1) in der Picked-Liste erscheint', async ({
		page
	}) => {
		const suffix = Date.now();
		await openNewCompareOrteTab(page, `E2E S5 SmartImport ${suffix}`);

		const locName = `E2E S5 SmartImport-Ort ${suffix}`;
		await page.locator('[data-testid="compare-step2-smart-import-input"]:visible').fill('47.2692, 11.4041');
		await page.locator('[data-testid="compare-step2-resolve-btn"]:visible').click();

		const nameInput = page.locator('[data-testid="compare-step2-name-input"]:visible');
		await expect(nameInput).toBeVisible({ timeout: 15_000 });
		await nameInput.fill(locName);
		await page.locator('button:has-text("Zum Vergleich hinzufügen"):visible').click();

		const pickedList = page.locator('[data-testid="compare-step2-picked-list"]:visible');
		const pickedItem = pickedList.locator('[data-testid^="compare-step2-picked-item-"]');
		await expect(pickedItem).toHaveCount(1, { timeout: 10_000 });
		// Nummerierung "1" ist Teil des Picked-Items (Soll: screen-compare-editor.jsx:258).
		await expect(pickedItem.first()).toContainText('1');
		await expect(pickedItem.first()).toContainText(locName);

		const locId = await pickedItem
			.first()
			.getAttribute('data-testid')
			.then((tid) => tid?.replace('compare-step2-picked-item-', ''));
		if (locId) await page.request.delete(`/api/locations/${locId}`);
	});

	// ── AC-12: min-2-Validierungs-Copy bei genau 1 gewähltem Ort ─────────────
	test('AC-12: Counter zeigt "min. 2 erforderlich" solange nur 1 Ort gewählt ist', async ({ page }) => {
		const suffix = Date.now();
		await openNewCompareOrteTab(page, `E2E S5 MinTwo ${suffix}`);

		const locName = `E2E S5 MinTwo-Ort ${suffix}`;
		await page.locator('[data-testid="compare-step2-smart-import-input"]:visible').fill('47.1015, 11.2958');
		await page.locator('[data-testid="compare-step2-resolve-btn"]:visible').click();
		const nameInput = page.locator('[data-testid="compare-step2-name-input"]:visible');
		await expect(nameInput).toBeVisible({ timeout: 15_000 });
		await nameInput.fill(locName);
		await page.locator('button:has-text("Zum Vergleich hinzufügen"):visible').click();

		const pickedItem = page
			.locator('[data-testid="compare-step2-picked-list"]:visible')
			.locator('[data-testid^="compare-step2-picked-item-"]');
		await expect(pickedItem).toHaveCount(1, { timeout: 10_000 });

		const counter = page.locator('[data-testid="compare-step2-counter"]:visible');
		await expect(counter).toHaveText('min. 2 erforderlich');

		const locId = await pickedItem
			.first()
			.getAttribute('data-testid')
			.then((tid) => tid?.replace('compare-step2-picked-item-', ''));
		if (locId) await page.request.delete(`/api/locations/${locId}`);
	});

	// ── AC-13 (GREEN seit Phase 6): Bibliothek gruppiert nach Group-Entity ──
	test('AC-13: Bibliothek zeigt einen gespeicherten Ort unter seiner Gruppen-Kopfzeile (group_id), NICHT unter "Weitere"', async ({
		page
	}) => {
		const suffix = Date.now();
		const groupName = `E2E S5 Gruppe ${suffix}`;

		const groupRes = await page.request.post('/api/groups', { data: { name: groupName } });
		expect(groupRes.ok(), 'Gruppen-Anlage fehlgeschlagen: ' + groupRes.status()).toBeTruthy();
		const group = await groupRes.json();
		createdGroupIds.push(group.id);

		const locName = `E2E S5 Gruppen-Ort ${suffix}`;
		const locRes = await page.request.post('/api/locations', {
			data: { name: locName, lat: 47.05, lon: 11.05, group_id: group.id }
		});
		expect(locRes.ok(), 'Location-Anlage fehlgeschlagen: ' + locRes.status()).toBeTruthy();
		const loc = await locRes.json();

		await openNewCompareOrteTab(page, `E2E S5 GruppenLib ${suffix}`);

		const libraryPanel = page.locator('[data-testid="compare-step2-library"]:visible');
		await expect(libraryPanel).toBeVisible({ timeout: 10_000 });

		// Gruppen-Kopfzeile "Gruppe · N" (Soll: screen-compare-editor.jsx:277)
		// mit dem ECHTEN Gruppennamen unseres Test-Orts — vor Phase 6 landete der
		// Ort stattdessen ungruppiert unter "Weitere" (loc.region wird nie gesetzt).
		await expect(libraryPanel.getByText(`${groupName} · 1`)).toBeVisible({ timeout: 10_000 });

		await page.request.delete(`/api/locations/${loc.id}`);
	});
});

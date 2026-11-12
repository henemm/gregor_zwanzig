// E2E — Issue #680 (Epic #677): Compare-Editor Slice 3 — Orte + Idealwerte Fidelity
//
// Spec: docs/specs/modules/issue_680_compare_editor_slice3.md
//
// Epic #1273 S4c: Orte-/Idealwerte-UI lebt nur im Create-Wizard; Einstieg ab
// /compare/new (Edit = 307-Redirect), Tabs progressiv frei (Name → ≥2 Orte → …).
// BEFUND: Step3Idealwerte (compare-step3-*) wurde von #1231 durch den geteilten
// CorridorEditor ersetzt — die Idealwerte-Tests prüfen gegen corridor-row-*.
//
// gz-eigenstaendig: Anlege-Wizard /compare/new hat kein Trip-Pendant mit denselben Kennungen (compare-editor-*, compare-step2-*); die Datei bleibt eigenständig (Create-POST mit 5 Slot-Feldern und official_warnings, in hub-anlegen-ablauf nicht abgedeckt), Wertebereiche je kind decken hub-wertebereiche-*.spec.ts ab.
//
// #2347 S3b: der Fall „Create-Flow sendet die 5 Slot-Felder + official_warnings"
// (Alt versand-tab-vergleich.spec.ts AC-6) steht hier, weil er zum Alt-Wizard gehört.
// Übergabe an S4: die Nachfolge-Anlegeseite /compare/new (Trip-Muster) übernimmt
// diese Zusicherung (Spec feat_2347_s3b_paritaets_e2e.md AC-11).

import { test, expect, type Page } from '@playwright/test';
import { createTestLocation } from './helpers';

// ── Create-Wizard-Klickpfad-Helper ──────────────────────────────────────────
// #1329 Maßnahme B: zentralisiert über den geteilten Helfer (helpers.ts) —
// diese Datei hatte zuvor GAR kein Cleanup (garantierter Leak, Kontext-Dok.).
async function createLoc(
	page: Page,
	name: string,
	lat: number,
	lon: number,
	region?: string
): Promise<string> {
	const loc = await createTestLocation(page.request, { name, lat, lon, region });
	return loc.id;
}

async function newWizard(page: Page, name: string, profil?: string): Promise<void> {
	await page.goto('/compare/new');
	await page.waitForLoadState('networkidle');
	await expect(page.locator('[data-testid="compare-editor"]:visible')).toBeVisible();
	await page.locator('[data-testid="compare-editor-name"]').fill(name);
	if (profil) {
		await page.locator(`[data-testid="compare-editor-profile-${profil}"]:visible`).first().click();
	}
}

async function pickInOrteTab(page: Page, namen: string[]): Promise<void> {
	await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();
	const lib = page.locator('[data-testid="compare-step2-library"]:visible').first();
	await lib.waitFor({ timeout: 8_000 });
	for (const n of namen) {
		await lib.getByText(n, { exact: true }).click();
	}
}

async function openIdealwerte(page: Page): Promise<void> {
	// Epic #1301 F2a (AC-4/AC-5): neue Freischalt-Kette — Wertebereiche ist erst
	// nach Besuch des NEUEN Wetter-Metriken-Tabs frei (Orte → Wetter-Metriken →
	// Wertebereiche). Echter Klick auf den Metriken-Tab, kein goto.
	// #2794 S3a: Metrik-Auswahl und Wertebereiche stehen gemeinsam im Schritt Wetter.
	// #2794 Teil 3 (Spec feat_2794_s3a_teil3_wetter.md §4, Known Limitations): der Schritt Wetter
	// zeigt den WetterTab (Ampel-Zeilen mit „Grenzen ändern") statt des CorridorEditors.
	await page.locator('[data-testid="compare-editor-tab-wetter"]:visible').first().click();
	const reiter = page.locator('[data-testid="wetter-tab"][data-context="vergleich"]:visible').first();
	await expect(reiter).toBeVisible({ timeout: 8_000 });
	await expect(reiter.getByTestId('wetter-tab-laden')).toHaveCount(0, { timeout: 8_000 });
}

/** Legt 2 Orte an und baut im Create-Wizard bis zum Idealwerte-Tab auf. */
async function seedTwoAndOpenIdealwerte(
	page: Page,
	profil: string,
	label: string
): Promise<{ idA: string; idB: string }> {
	const suffix = Date.now();
	const nameA = `E2E-GZ-${label}-A-${suffix}`;
	const nameB = `E2E-GZ-${label}-B-${suffix}`;
	const idA = await createLoc(page, nameA, 47.4, 13.0);
	const idB = await createLoc(page, nameB, 47.1, 12.8);
	await newWizard(page, `Slice3 ${label} ${suffix}`, profil);
	await pickInOrteTab(page, [nameA, nameB]);
	await openIdealwerte(page);
	return { idA, idB };
}

/** Sichtbare Wertebereich-Zeilen (#2794 Teil 3: Metrik-Zeilen des WetterTab, ohne „−"-Knöpfe). */
function corridorRows(page: Page) {
	return page.locator('[data-testid="wetter-tab"]:visible [data-testid^="wetter-zeile-"]:not([data-testid^="wetter-zeile-entfernen-"])');
}

/** Erste sichtbare Wertebereich-Zeile. */
function firstCorridorRow(page: Page) {
	return corridorRows(page).first();
}

test.describe('Issue #680: Compare-Editor Slice 3 — Orte + Idealwerte', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1: Nummerierte Picked-Liste mit ✕ ─────────────────────────────────
	test('AC-1: Picked-Liste zeigt Nummern und ✕-Entfernen-Buttons', async ({ page }) => {
		const suffix = Date.now();
		const nameA = 'E2E-GZ-Ort-Region-A-' + suffix;
		const nameB = 'E2E-GZ-Ort-kein-Region-' + suffix;
		const locIdA = await createLoc(page, nameA, 47.4, 13.0, 'Hochkönig');
		const locIdB = await createLoc(page, nameB, 47.1, 12.8);

		await newWizard(page, 'Slice3 E2E ' + suffix, 'wintersport');
		await pickInOrteTab(page, [nameA, nameB]);

		// Picked-Liste sichtbar
		const pickedList = page.locator('[data-testid="compare-step2-picked-list"]:visible').first();
		await expect(pickedList).toBeVisible({ timeout: 8_000 });

		// Beide Orte als Items vorhanden
		const itemA = page.locator(`[data-testid="compare-step2-picked-item-${locIdA}"]:visible`).first();
		const itemB = page.locator(`[data-testid="compare-step2-picked-item-${locIdB}"]:visible`).first();
		await expect(itemA).toBeVisible();
		await expect(itemB).toBeVisible();

		// ✕-Button entfernt Ort: locIdA entfernen
		const removeA = page.locator(`[data-testid="compare-step2-picked-remove-${locIdA}"]:visible`).first();
		await expect(removeA).toBeVisible();
		await removeA.click();

		// Nach Entfernen: Item A weg, Item B noch da
		await expect(page.locator(`[data-testid="compare-step2-picked-item-${locIdA}"]`)).toHaveCount(0);
		await expect(itemB).toBeVisible();
	});

	// ── AC-2: Counter Warn/OK ────────────────────────────────────────────────
	test('AC-2: Counter zeigt "min. 2 erforderlich" unter 2 Orten', async ({ page }) => {
		const suffix = Date.now();
		const nameA = 'E2E-GZ-Ort-Solo-A-' + suffix;
		await createLoc(page, nameA, 47.4, 13.0, 'Hochkönig');

		await newWizard(page, 'Slice3 Counter ' + suffix);
		// Nur EINEN Ort wählen → Counter warnt.
		await pickInOrteTab(page, [nameA]);

		const counter = page.locator('[data-testid="compare-step2-counter"]:visible').first();
		await expect(counter).toBeVisible();
		await expect(counter).toContainText('min. 2 erforderlich');
	});

	// ── AC-3: Bibliotheks-Grid gruppiert (Sammelgruppe "Weitere") ────────────
	// Issue #301: Bibliothek gruppiert nach group_id, NICHT nach loc.region — ein
	// Ort ohne Gruppe landet in "Weitere" (kein "Hochkönig"-Header mehr).
	test('AC-3: Bibliothek gruppiert Orte (Sammelgruppe "Weitere" als Überschrift)', async ({ page }) => {
		const suffix = Date.now();
		await createLoc(page, 'E2E-GZ-Ort-Region-A-' + suffix, 47.4, 13.0, 'Hochkönig');
		await createLoc(page, 'E2E-GZ-Ort-kein-Region-' + suffix, 47.1, 12.8);

		await newWizard(page, 'Slice3 Library ' + suffix);
		await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();

		// Bibliotheks-Grid vorhanden
		const library = page.locator('[data-testid="compare-step2-library"]:visible').first();
		await expect(library).toBeVisible({ timeout: 8_000 });

		// Sammelgruppe "Weitere" für Orte ohne group_id (beide Testorte).
		await expect(library.locator('text=/weitere/i').first()).toBeVisible();
	});

	// ── AC-4: Idealwerte-Tab rendert den geteilten Wertebereich-Editor (#1231) ──
	test('AC-4: Idealwerte-Tab öffnet den Wertebereich-Editor mit Metrik-Zeilen', async ({ page }) => {
		await seedTwoAndOpenIdealwerte(page, 'wintersport', 'Ideal');
		await expect(firstCorridorRow(page)).toBeVisible({ timeout: 5_000 });
	});

	// ── AC-6: Wertebereich-Editor ist interaktiv (Metrik-Zeile vorhanden) ────
	// Issue #1231: Slider → CorridorEditor-Band-Griff (Drag in Unit-Tests).
	test('AC-6: Wertebereich-Editor zeigt eine bearbeitbare Metrik-Zeile', async ({ page }) => {
		await seedTwoAndOpenIdealwerte(page, 'wintersport', 'Slider');
		const zeile = page.locator('[data-testid="wetter-tab"]:visible [data-testid^="wetter-zeile-"]:has([data-testid^="wetter-grenzen-aendern-"])').first();
		await expect(zeile).toBeVisible({ timeout: 5_000 });
		// bearbeitbar: „Grenzen ändern" öffnet die Felder der Zeile (AC-16)
		const knopf = zeile.locator('[data-testid^="wetter-grenzen-aendern-"]');
		await knopf.click();
		await expect(knopf).toHaveText('Fertig');
		await expect(zeile.locator('[data-testid^="wetter-grenze-"]').first()).toBeEditable();
	});

	// ── AC-7: SUMMER_TREKKING-Profil rendert seine Metrik-Zeilen ─────────────
	// Issue #1231: Enum-Segmented-Control entfällt; geprüft: CorridorEditor-Zeilen da.
	test('AC-7: SUMMER_TREKKING-Profil zeigt Metrik-Zeilen im Wertebereich-Editor', async ({ page }) => {
		await seedTwoAndOpenIdealwerte(page, 'summer_trekking', 'Enum');
		await expect(firstCorridorRow(page)).toBeVisible({ timeout: 5_000 });
	});

	// ── AC-8: Wertebereich-Editor mit mehreren Metrik-Zeilen ─────────────────
	// Issue #1231: "＋ Metrik hinzufügen" entfällt; geprüft: mehrere Zeilen.
	test('AC-8: Wertebereich-Editor zeigt mehrere Metrik-Zeilen', async ({ page }) => {
		await seedTwoAndOpenIdealwerte(page, 'wintersport', 'Add');
		const rows = corridorRows(page);
		await expect(rows.first()).toBeVisible({ timeout: 5_000 });
		expect(await rows.count()).toBeGreaterThanOrEqual(2);
	});

	// ── AC-9: Metrik-Zeile trägt ihren Metrik-Schlüssel ──────────────────────
	// Issue #1231: ✕-Entfernen im CorridorEditor; Zeilen bleiben adressierbar.
	// #2794 Teil 3: Zeilen heißen `wetter-zeile-<metric>` (Katalog-Kennung), „−" entfernt (AC-19).
	test('AC-9: Metrik-Zeilen sind über wetter-zeile-<metric> adressierbar und entfernbar', async ({ page }) => {
		await seedTwoAndOpenIdealwerte(page, 'wintersport', 'Remove');
		const firstRow = firstCorridorRow(page);
		await expect(firstRow).toBeVisible({ timeout: 5_000 });
		const testid = (await firstRow.getAttribute('data-testid')) ?? '';
		expect(testid.startsWith('wetter-zeile-')).toBeTruthy();
		const metrik = testid.replace('wetter-zeile-', '');
		await page.locator(`[data-testid="wetter-tab"]:visible [data-testid="wetter-zeile-entfernen-${metrik}"]`).click();
		await expect(page.locator(`[data-testid="wetter-tab"]:visible [data-testid="wetter-zeile-${metrik}"]`)).toHaveCount(0);
		await expect(page.locator(`[data-testid="wetter-tab"]:visible [data-testid="wetter-nicht-im-briefing-plus-${metrik}"]`)).toBeVisible();
	});

	// ── AC-10: Gewählte Orte landen im Aktivierungs-POST ─────────────────────
	// #1273 S4c: Create-Wizard persistiert erst beim Aktivieren → POST-Body-Nachweis.
	test('AC-10: Wizard-Konfiguration wird beim Aktivieren an den Server gesendet', async ({ page }) => {
		const { idA, idB } = await seedTwoAndOpenIdealwerte(page, 'wintersport', 'Persist');

		// Bis zum Alarme-Tab durchklicken (schaltet den Aktivieren-Button frei).
		// Issue #1360 (Epic #1372 S1a): der Reiter `layout` ist aufgeloest.
		// Issue #1743: der Schritt `versand` ist aufgeloest (Versand steht unten im
		// Schritt wetter-metriken) — Anlegen wird nach dem Besuch von `alarme` frei.
		// #2794 S3a: letzter Schritt ist `zustellung`.
		await page.locator('[data-testid="compare-editor-tab-zustellung"]:visible').first().click();

		const [request] = await Promise.all([
			page.waitForRequest(
				(req) => req.url().includes('/api/compare/presets') && req.method() === 'POST'
			),
			page.locator('[data-testid="compare-editor-activate"]:visible').first().click()
		]);
		const body = request.postDataJSON() as Record<string, unknown>;
		const locationIds = (body.location_ids ?? []) as string[];
		expect(locationIds).toContain(idA);
		expect(locationIds).toContain(idB);
	});

	// ── Alt versand-tab-vergleich AC-6 (#2347 S3b): Create-Flow — POST-Body enthält
	// die 5 Slot-Felder + official_warnings. Issue #1258 S4 (E1/E2, AC-28): die
	// Tab-Kette enthält die reguläre Station "alarme".
	test('Create-Flow sendet die 5 Slot-Felder + official_warnings im POST-Body an /api/compare/presets', async ({
		page
	}) => {
		const suffix = Date.now();
		const [locA, locB] = await Promise.all([
			createTestLocation(page.request, { lat: 47.0, lon: 13.0, region: 'VersandVergleich-Region' }),
			createTestLocation(page.request, { lat: 47.1, lon: 13.1, region: 'VersandVergleich-Region' })
		]);

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		const d = page.locator('.cm-desktop');

		await d.locator('[data-testid="compare-editor-name"]').fill('E2E-GZ-AC-6-Create-Flow-' + suffix);
		await d.locator('[data-testid="compare-editor-tab-orte"]').click();
		await d.locator('[data-testid="compare-step2-library"]').waitFor({ timeout: 8_000 });
		await d.locator('[data-testid="compare-step2-library"]').getByText(locA.name, { exact: true }).click();
		await d.locator('[data-testid="compare-step2-library"]').getByText(locB.name, { exact: true }).click();
		// Epic #1301 F2a: Wetter-Metriken-Tab besuchen schaltet Wertebereiche frei (echter Klick).
		// #2794 S3a: Schritte Wetter (Metriken + Wertebereiche) und Zustellung (Versand + Alarme).
		await d.locator('[data-testid="compare-editor-tab-wetter"]').click();
		await d.locator('[data-testid="compare-editor-tab-zustellung"]').click();

		const [antwort] = await Promise.all([
			page.waitForResponse(
				(res) => new URL(res.url()).pathname === '/api/compare/presets' && res.request().method() === 'POST'
			),
			d.locator('[data-testid="compare-editor-activate"]').click()
		]);
		// Aufräumen des angelegten Vergleichs (Kontingent 2 aktive Vergleiche je Nutzer;
		// die Datei steht auf der Positivliste, Folgefälle dürfen nicht an 409 scheitern).
		const angelegt = ((await antwort.json().catch(() => ({}))) as { id?: string }).id;
		try {
			const body = antwort.request().postDataJSON() as Record<string, unknown>;

			expect(body.morning_enabled).toBe(true);
			expect(body.morning_time).toBe('07:00:00');
			expect(body.evening_enabled).toBe(false);
			expect(body.evening_time).toBe('18:00:00');
			expect(body.end_date == null, 'end_date darf beim Create ohne Laufzeit-Auswahl fehlen/null sein').toBeTruthy();
			// Issue #1258 S4 (AC-27, E3): official_warnings wird unconditional gesendet, kein
			// sources-Key ohne Bestand.
			// #2794 Teil 3: AC-20 (Spec feat_2794_s3a_teil3_wetter.md) — der Schritt Wetter führt EINEN
			// Schalter „Amtliche Warnungen" mit ODER-Lese-Regel und schreibt `official_alerts_enabled`
			// und `official_warnings.enabled` immer gleich („bei an beide true"). Der Entwurf startet mit
			// Bericht an (official_alerts_enabled) ⇒ Schalter an ⇒ beide Felder true im Anlege-POST.
			expect(body.official_warnings).toEqual({ enabled: true });
			expect(body.official_alerts_enabled, 'AC-20: beide Warn-Felder tragen denselben Wert').toBe(true);
		} finally {
			if (angelegt) await page.request.delete(`/api/compare/presets/${angelegt}`).catch(() => {});
		}
	});
});

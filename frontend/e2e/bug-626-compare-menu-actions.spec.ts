// E2E — Bug #626: Ortsvergleiche Listen-Menü-Aktionen
//
// Spec: docs/specs/bugfix/bug_626_compare_menu_actions.md
//
// Issue #1256 Scheibe 1 (2026-07-13): AC-6 und AC-7 wurden auf den neuen
// Listen-Kebab-Vertrag korrigiert (Soll molecules.jsx:1018-1027) —
// "Archivieren" ist kein Bestandteil des Listen-Kebabs mehr (wandert in die
// Hub-Header-Lifecycle-Liste, Scheibe 3); "Briefing jetzt senden" ist seit
// #627 fester Bestandteil (die ursprüngliche AC-6-Annahme "kein send" war
// bereits vor dieser Scheibe stale). Siehe docs/specs/modules/issue_1256_compare_ui_rewire.md AC-1/AC-2.
//
// Verifikation der 7 ACs als eingeloggter Nutzer gegen Staging.
// Voraussetzung: mindestens ein aktiver Compare-Preset und ein pausierter
// Compare-Preset existieren im Test-Account.
//
// Base-URL: GZ_SVELTE_BASE (Default: playwright.config.ts baseURL = Staging)
//
// Ausführen:
//   cd frontend && E2E_USER=admin E2E_PASS=test1234 \
//     npx playwright test e2e/bug-626-compare-menu-actions.spec.ts \
//     --config playwright.config.ts

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

// Hilfsfunktion: Öffnet das Kebab-Menü der ersten Kachel mit einem bestimmten Status-Label
async function openKebabForStatus(page: import('@playwright/test').Page, statusLabel: string) {
	// Finde eine Kachel, die den gesuchten Status-Label enthält
	const tile = page.locator('[data-testid^="compare-tile-"]:visible').filter({ hasText: statusLabel }).first();
	await expect(tile).toBeVisible({ timeout: 10_000 });
	// Klick auf den Kebab-Button (⋯) innerhalb der Kachel
	const kebab = tile.locator('button[aria-label="Weitere Aktionen"]');
	await kebab.click();
	// Warte auf Dropdown
	await page.waitForTimeout(500);
	return tile;
}

// ── Isolierte Test-Fixtures (AC-2/AC-3) ────────────────────────────────────
//
// AC-2/AC-3 verließen sich zuvor auf zufällig vorhandene Presets aus
// Alt-Testläufen (`.filter({ hasText: 'aktiv' })`). Das ist doppelt fragil:
// (1) läuft nur, wenn überhaupt ein aktiver/pausierter Preset im Konto liegt,
// (2) der lebende Locator matcht nach dem Status-Wechsel plötzlich eine ANDERE
// Zeile (bei mehreren aktiven Presets auf Staging), sodass die Pill-Prüfung an
// der falschen Kachel scheitert, obwohl die App korrekt umschaltet.
//
// Abhilfe: jeder Test legt sein EIGENES Preset (inkl. Test-Location, weil
// `deriveStatusFromPreset` `location_ids.length > 0` für Nicht-Draft braucht,
// subscriptionHelpers.ts:72-77) per API an, referenziert die Kachel danach
// über die STABILE `data-testid="compare-tile-<id>"` und räumt in `finally`
// wieder auf. Muster: createPreset/createLocation aus
// compare-mobile-vervollstaendigung.spec.ts:42-68.

async function createLocation(
	page: import('@playwright/test').Page,
	name: string,
	lat: number,
	lon: number
): Promise<string> {
	const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
	await expect(res, 'Location-Anlage fehlgeschlagen: ' + res.status()).toBeOK();
	return (await res.json()).id as string;
}

async function createPresetWithLocation(
	page: import('@playwright/test').Page,
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
	await expect(res, 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeOK();
	return (await res.json()).id as string;
}

// Draft-Preset: `location_ids: []` ⇒ `deriveStatusFromPreset` (subscriptionHelpers.ts)
// faellt auf Status 'draft' zurueck — keine Location noetig, das ist gerade
// der Witz an einem Draft (Setup noch nicht abgeschlossen).
async function createDraftPreset(page: import('@playwright/test').Page, name: string): Promise<string> {
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
	await expect(res, 'Draft-Preset-Anlage fehlgeschlagen: ' + res.status()).toBeOK();
	return (await res.json()).id as string;
}

async function cleanupFixture(
	page: import('@playwright/test').Page,
	presetId: string | null,
	locationId: string | null
): Promise<void> {
	// Staging-Hygiene: nur die selbst angelegten Artefakte entfernen, unabhängig
	// vom Test-Ausgang. Cleanup-Fehler sind nicht test-kritisch.
	if (presetId) {
		await page.request.delete(`/api/compare/presets/${presetId}`).catch(() => {});
	}
	if (locationId) {
		await page.request.delete(`/api/locations/${locationId}`).catch(() => {});
	}
}

test.describe('Bug #626: Compare Listen-Menü-Aktionen (#626)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
		await page.goto('/compare');
		await page.waitForLoadState('networkidle');
	});

	// ── AC-1: Bearbeiten → /compare/{id}/edit ────────────────────────────────

	test('AC-1: "Bearbeiten" navigiert zu /compare/{id}/edit', async ({ page }) => {
		// Finde die erste aktive oder pausierte Kachel
		const tile = page.locator('[data-testid^="compare-tile-"]:visible').first();
		await expect(tile).toBeVisible({ timeout: 10_000 });

		// Preset-ID vor dem Klick sichern (Locator kann nach der Navigation
		// nicht mehr zuverlässig abgefragt werden).
		const tileTestId = await tile.getAttribute('data-testid');
		const id = (tileTestId ?? '').replace('compare-tile-', '');

		// Hole Preset-ID aus dem tile-Link oder data-Attribut
		const kebab = tile.locator('button[aria-label="Weitere Aktionen"]');
		await kebab.click();
		await page.waitForTimeout(500);

		// Klick auf "Bearbeiten"
		const editItem = page.getByRole('menuitem', { name: 'Bearbeiten' });
		await expect(editItem).toBeVisible();
		await editItem.click();

		// Epic #1273 S3: /compare/{id}/edit ist reiner Redirect auf den Hub —
		// die finale URL landet auf /compare/{id} ohne /edit.
		await expect(page).toHaveURL(new RegExp(`/compare/${id}(\\?|$)`), { timeout: 10_000 });
	});

	// ── AC-4: Vorschau → /compare/{id}?tab=vorschau ──────────────────────────

	test('AC-4: "Vorschau öffnen" navigiert zu ?tab=vorschau', async ({ page }) => {
		const tile = page.locator('[data-testid^="compare-tile-"]:visible').first();
		await expect(tile).toBeVisible({ timeout: 10_000 });

		const kebab = tile.locator('button[aria-label="Weitere Aktionen"]');
		await kebab.click();
		await page.waitForTimeout(500);

		// Klick auf "Vorschau öffnen"
		const previewItem = page.getByRole('menuitem', { name: 'Vorschau öffnen' });
		await expect(previewItem).toBeVisible();
		await previewItem.click();

		// Prüfe URL enthält ?tab=vorschau
		await expect(page).toHaveURL(/\?tab=vorschau/, { timeout: 10_000 });
	});

	// ── AC-2: Aktiver Vergleich pausieren → schedule='manual' ────────────────

	test('AC-2: "Pausieren" wechselt aktiven Vergleich zu pausiert', async ({ page }) => {
		// Eigenes, isoliertes aktives Preset anlegen (schedule='daily' + eine
		// Location ⇒ Status 'aktiv'), statt auf Fremd-Presets zu bauen.
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E 626 AC-2 Ort ${suffix}`, 47.11, 11.21);
		const presetId = await createPresetWithLocation(page, `E2E 626 AC-2 aktiv ${suffix}`, 'daily', locId);

		try {
			await page.goto('/compare');
			await page.waitForLoadState('networkidle');

			// STABILE Referenz über die Preset-ID — der Locator matcht auch nach
			// dem Status-Wechsel weiterhin genau DIESE Kachel (nicht per hasText,
			// das nach dem Klick auf eine andere aktive Zeile umspringen würde).
			const tile = page.locator(`[data-testid="compare-tile-${presetId}"]:visible`);
			await expect(tile).toBeVisible({ timeout: 10_000 });

			const statusPill = tile.locator('[data-testid="compare-status-pill"]');
			await expect(statusPill).toContainText('aktiv', { timeout: 10_000 });

			// Öffne Kebab-Menü
			const kebab = tile.locator('button[aria-label="Weitere Aktionen"]');
			await kebab.click();
			await page.waitForTimeout(500);

			// Prüfe: Menü enthält "Pausieren" (nicht "Aktivieren")
			const pauseItem = page.getByRole('menuitem', { name: 'Pausieren' });
			await expect(pauseItem).toBeVisible();

			// Klick auf "Pausieren"
			await pauseItem.click();

			// Warte auf Reaktivität — Status-Pill soll auf "pausiert" wechseln
			await page.waitForTimeout(1000);

			// Prüfe: dieselbe Kachel (per ID) zeigt jetzt "pausiert"
			// (Die Kachel bleibt in der Liste, Pausieren entfernt sie nicht.)
			await expect(statusPill).toContainText('pausiert', { timeout: 5_000 });

			// Prüfe: Kebab-Menü zeigt jetzt "Aktivieren"
			const kebab2 = tile.locator('button[aria-label="Weitere Aktionen"]');
			await kebab2.click();
			await page.waitForTimeout(500);
			await expect(page.getByRole('menuitem', { name: 'Aktivieren' })).toBeVisible();
			await page.keyboard.press('Escape');
		} finally {
			await cleanupFixture(page, presetId, locId);
		}
	});

	// ── AC-3: Pausierten Vergleich aktivieren → schedule='daily' ─────────────

	test('AC-3: "Aktivieren" wechselt pausierten Vergleich zu aktiv', async ({ page }) => {
		// Eigenes, isoliertes pausiertes Preset anlegen (schedule='manual' + eine
		// Location ⇒ Status 'pausiert'), statt auf Fremd-Presets zu bauen.
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E 626 AC-3 Ort ${suffix}`, 46.98, 11.08);
		const presetId = await createPresetWithLocation(page, `E2E 626 AC-3 pausiert ${suffix}`, 'manual', locId);

		try {
			await page.goto('/compare');
			await page.waitForLoadState('networkidle');

			// STABILE Referenz über die Preset-ID.
			const tile = page.locator(`[data-testid="compare-tile-${presetId}"]:visible`);
			await expect(tile).toBeVisible({ timeout: 10_000 });

			const statusPill = tile.locator('[data-testid="compare-status-pill"]');
			await expect(statusPill).toContainText('pausiert', { timeout: 10_000 });

			const kebab = tile.locator('button[aria-label="Weitere Aktionen"]');
			await kebab.click();
			await page.waitForTimeout(500);

			// Prüfe: Menü enthält "Aktivieren" (nicht "Pausieren")
			const activateItem = page.getByRole('menuitem', { name: 'Aktivieren' });
			await expect(activateItem).toBeVisible();

			// Klick auf "Aktivieren"
			await activateItem.click();
			await page.waitForTimeout(1000);

			// Prüfe: dieselbe Kachel (per ID) wechselt auf "aktiv"
			await expect(statusPill).toContainText('aktiv', { timeout: 5_000 });

			// Prüfe: Kebab-Menü zeigt jetzt "Pausieren"
			const kebab2 = tile.locator('button[aria-label="Weitere Aktionen"]');
			await kebab2.click();
			await page.waitForTimeout(500);
			await expect(page.getByRole('menuitem', { name: 'Pausieren' })).toBeVisible();
			await page.keyboard.press('Escape');
		} finally {
			await cleanupFixture(page, presetId, locId);
		}
	});

	// ── AC-5: Draft → "Setup fortsetzen" → /compare/{id}/edit ───────────────
	//
	// Ehemals: verließ sich auf ZUFÄLLIG vorhandene Draft-Vergleiche
	// (`.filter({ hasText: 'draft' })`) und übersprang sich per `test.skip`,
	// wenn keiner existierte — im aktuellen Testkonto lief der Fall nie
	// "scharf", nur "skipped" (Adversary-Fund F002). Abhilfe wie AC-2/AC-3:
	// eigenes, isoliertes Draft-Preset per API anlegen, über die STABILE
	// `data-testid="compare-tile-<id>"` referenzieren, in `finally` aufräumen.

	test('AC-5: "Setup fortsetzen" navigiert Draft zu /compare/{id}/edit', async ({ page }) => {
		const suffix = Date.now();
		const presetId = await createDraftPreset(page, `E2E 626 AC-5 draft ${suffix}`);

		try {
			await page.goto('/compare');
			await page.waitForLoadState('networkidle');

			// STABILE Referenz über die Preset-ID.
			const draftTile = page.locator(`[data-testid="compare-tile-${presetId}"]:visible`);
			await expect(draftTile).toBeVisible({ timeout: 10_000 });

			const statusPill = draftTile.locator('[data-testid="compare-status-pill"]');
			await expect(statusPill).toContainText('draft', { timeout: 10_000 });

			const kebab = draftTile.locator('button[aria-label="Weitere Aktionen"]');
			await kebab.click();
			await page.waitForTimeout(500);

			const setupItem = page.getByRole('menuitem', { name: 'Setup fortsetzen' });
			await expect(setupItem).toBeVisible();
			await setupItem.click();

			// Epic #1273 S3: /compare/{id}/edit ist reiner Redirect auf den Hub —
			// die finale URL landet auf /compare/{id} ohne /edit.
			await expect(page).toHaveURL(new RegExp(`/compare/${presetId}(\\?|$)`), { timeout: 10_000 });
		} finally {
			await cleanupFixture(page, presetId, null);
		}
	});

	// ── AC-6 (korrigiert #1256 S1): "Briefing jetzt senden" IST Teil des Menüs ──
	//
	// #1256 S1: Korrigiert — die ursprüngliche bug-626-Annahme "kein 'Briefing
	// jetzt senden'" wurde bereits durch #627 (Einzel-Sofortversand) überholt;
	// "send" ist seit #627 fester Bestandteil des 5er-Vertrags (Soll
	// molecules.jsx:1018-1027). Assertion auf den aktuellen Vertrag umgestellt.

	test('AC-6 (korrigiert #1256 S1): Menü enthält "Briefing jetzt senden"', async ({ page }) => {
		const tile = page.locator('[data-testid^="compare-tile-"]:visible').first();
		await expect(tile).toBeVisible({ timeout: 10_000 });

		const kebab = tile.locator('button[aria-label="Weitere Aktionen"]');
		await kebab.click();
		await page.waitForTimeout(500);

		// Prüfe: "Briefing jetzt senden" ist vorhanden (#627, seit #1256 S1 fester Bestandteil der 5 Aktionen)
		const sendItem = page.getByRole('menuitem', { name: 'Briefing jetzt senden' });
		await expect(sendItem).toBeVisible();

		await page.keyboard.press('Escape');
	});

	// ── AC-7 (korrigiert #1256 S1): Listen-Kebab = genau 5 Aktionen, KEIN Archivieren ──
	//
	// #1256 S1: Archivieren aus Listen-Kebab entfernt (Soll molecules.jsx:1018-1027);
	// Hub-Lifecycle folgt in S3. Listen-Kebab active/paused = genau
	// [Pausieren|Aktivieren, Briefing jetzt senden, Vorschau öffnen, Bearbeiten, Löschen].

	test('AC-7 (korrigiert #1256 S1): Listen-Kebab zeigt genau 5 Aktionen ohne Archivieren', async ({
		page
	}) => {
		const tile = page.locator('[data-testid^="compare-tile-"]:visible').first();
		await expect(tile).toBeVisible({ timeout: 10_000 });

		const kebab = tile.locator('button[aria-label="Weitere Aktionen"]');
		await kebab.click();
		await page.waitForTimeout(500);

		// Pflicht-Aktionen: Löschen und Bearbeiten müssen weiterhin vorhanden sein.
		await expect(page.getByRole('menuitem', { name: 'Löschen' })).toBeVisible();
		await expect(page.getByRole('menuitem', { name: 'Bearbeiten' })).toBeVisible();
		await expect(page.getByRole('menuitem', { name: 'Vorschau öffnen' })).toBeVisible();
		await expect(page.getByRole('menuitem', { name: 'Briefing jetzt senden' })).toBeVisible();
		// Genau eine der beiden Toggle-Varianten (status-abhängig) muss vorhanden sein.
		const pauseOrActivate = page.getByRole('menuitem', { name: /^(Pausieren|Aktivieren)$/ });
		await expect(pauseOrActivate).toHaveCount(1);

		// #1256 S1: "Archivieren" darf im Listen-Kebab NICHT mehr vorkommen.
		await expect(page.getByRole('menuitem', { name: 'Archivieren' })).not.toBeVisible();

		// Exakt 5 Menüeinträge insgesamt (kein Archivieren, kein sechster Eintrag).
		const menuItems = page.getByRole('menuitem');
		await expect(menuItems).toHaveCount(5);

		// Schließe Menü per Escape
		await page.keyboard.press('Escape');
	});
});

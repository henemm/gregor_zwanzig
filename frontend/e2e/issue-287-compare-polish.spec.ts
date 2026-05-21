// TDD RED — Issue #287: Compare-Screen Polish
//
// Spec: docs/specs/modules/issue_287_compare_polish.md (AC-1 bis AC-7)
//
// Diese Tests prüfen die Ziel-Zustände nach dem Refactoring.
// Alle Tests schlagen in der RED-Phase fehl, weil:
//   - Emoji-Spans noch vorhanden sind (AC-1, AC-2)
//   - "Preset laden" noch outline-Variante hat (AC-3)
//   - Datum-Input kein font-mono hat (AC-4)
//   - bg-green-500/bg-gray-300 noch in CompareSubscriptionsPanel (AC-5)
//   - Raw-Tailwind-Badge-Spans noch vorhanden sind (AC-6)
//   - Kein Bearbeiten-Button vorhanden (AC-7)
//
// Nach der Implementierung müssen alle Tests grün sein.
//
// Ausführen (Preview-Server muss laufen):
//   cd frontend && npx playwright test e2e/issue-287-compare-polish.spec.ts

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Compare Polish #287', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
		await page.goto('/compare');
		await page.waitForSelector('[data-testid="compare-rail"]', { timeout: 10_000 });
	});

	// ── AC-1: Kein Emoji in Location-Listeneinträgen ─────────────────────────
	test('AC-1: Location-Items zeigen colored dot statt Emoji', async ({ page }) => {
		// Mindestens eine Gruppe öffnen (toggle first group header)
		const groupHeaders = page.getByTestId('compare-rail-group-header');
		const count = await groupHeaders.count();
		if (count > 0) {
			await groupHeaders.first().locator('button').click();
		}

		// Im Rail darf kein Emoji-Zeichen aus profileSignature (🥾, ❄, 🏔) vorkommen
		const rail = page.getByTestId('compare-rail');
		const railText = await rail.textContent();
		// Emoji-Charaktere aus profileSignature.ts: wandern=🥾 (U+1F97E), wintersport=❄ (U+2744),
		// summer_trekking=🏔 (U+1F3D4)
		expect(railText).not.toMatch(/\u{1F97E}|\u{2744}|\u{1F3D4}/u);

		// Stattdessen muss ein [data-slot="dot"] span mit inline-background vorhanden sein
		const profileDots = page.locator('[data-testid="compare-rail"] [data-slot="dot"][style*="background"]');
		await expect(profileDots.first()).toBeVisible();
	});

	// ── AC-2: Profil-Filter-Pills zeigen Dot + Eyebrow-Text, kein Emoji ──────
	test('AC-2: Profil-Filter-Pills haben farbigen Dot statt Emoji', async ({ page }) => {
		const profileChips = page.getByTestId('compare-rail-profile-chip');
		const chipCount = await profileChips.count();

		if (chipCount === 0) {
			// Wenn keine Profil-Chips vorhanden sind (keine profilierten Locations),
			// Test als bedingt bestanden markieren
			test.skip();
			return;
		}

		const firstChip = profileChips.first();
		const chipText = await firstChip.textContent();

		// Kein Emoji in Chip-Text
		expect(chipText).not.toMatch(/\u{1F97E}|\u{2744}|\u{1F3D4}/u);

		// Chip enthält einen [data-slot="dot"] mit inline background
		const dot = firstChip.locator('[data-slot="dot"][style*="background"]');
		await expect(dot).toBeVisible();
	});

	// ── AC-3: "Preset laden" hat ghost-Variante ───────────────────────────────
	test('AC-3: "Preset laden"-Button hat data-variant="ghost"', async ({ page }) => {
		// Suche nach dem "Preset laden" Button
		const presetLadenBtn = page.locator('button:has-text("Preset laden"), a:has-text("Preset laden")');
		await expect(presetLadenBtn).toBeVisible();

		// Muss ghost-Variante haben (data-variant="ghost" oder entsprechende Klasse)
		// Btn-Komponente setzt data-variant als Attribut
		const dataVariant = await presetLadenBtn.getAttribute('data-variant');
		expect(dataVariant).toBe('ghost');
	});

	// ── AC-4: Datum-Input hat Mono-Schrift ────────────────────────────────────
	test('AC-4: Datum-Input (cmp-date) hat font-mono oder var(--g-font-data)', async ({ page }) => {
		const dateInput = page.locator('#cmp-date');
		await expect(dateInput).toBeVisible();

		// Prüfe class-Attribut auf font-mono
		const className = await dateInput.getAttribute('class') ?? '';
		// Prüfe computed style für font-family (Mono-Schrift)
		const fontFamily = await dateInput.evaluate((el) => getComputedStyle(el).fontFamily);

		const hasFontMonoClass = className.includes('font-mono');
		const hasMonoFont = fontFamily.toLowerCase().includes('mono') || fontFamily.includes('JetBrains');

		expect(hasFontMonoClass || hasMonoFont).toBe(true);
	});

	// ── AC-5: Auto-Report-Karten nutzen Dot-Komponente ───────────────────────
	test('AC-5: Status-Dots in Auto-Report-Karten sind Dot-Komponenten mit Token-Farben', async ({ page }) => {
		// Auto-Reports-Sektion ist nur sichtbar wenn kein Vergleich läuft und kein Wetter angezeigt wird
		// (laut +page.svelte: {#if !result && !loading && !weatherLocationId})
		const subscriptionsPanel = page.locator('.space-y-3:has(h3:has-text("Auto-Reports"))');

		// Wenn keine Subscriptions vorhanden, Skip
		const emptyMsg = page.locator('text=Noch keine Auto-Reports gespeichert');
		const isEmpty = await emptyMsg.isVisible().catch(() => false);
		if (isEmpty) {
			test.skip();
			return;
		}

		await expect(subscriptionsPanel).toBeVisible();

		// Kein roher Tailwind-Dot (h-2 w-2 bg-green-500 / bg-gray-300) darf im DOM sein
		const rawDot = page.locator('.bg-green-500, .bg-gray-300').filter({ hasAncestor: subscriptionsPanel });
		await expect(rawDot).toHaveCount(0);

		// Stattdessen muss [data-slot="dot"] vorhanden sein
		const tokenDot = subscriptionsPanel.locator('[data-slot="dot"]');
		await expect(tokenDot.first()).toBeVisible();
	});

	// ── AC-6: Status-Badges nutzen Pill-Komponente ───────────────────────────
	test('AC-6: "ok" und "Fehler"-Badges in Auto-Report-Karten sind Pill-Komponenten', async ({ page }) => {
		const subscriptionsPanel = page.locator('.space-y-3:has(h3:has-text("Auto-Reports"))');

		const emptyMsg = page.locator('text=Noch keine Auto-Reports gespeichert');
		const isEmpty = await emptyMsg.isVisible().catch(() => false);
		if (isEmpty) {
			test.skip();
			return;
		}

		await expect(subscriptionsPanel).toBeVisible();

		// Kein roher Badge-Span mit bg-green-50 / bg-red-50 darf vorhanden sein
		const rawBadge = page.locator('.bg-green-50, .bg-red-50').filter({ hasAncestor: subscriptionsPanel });
		await expect(rawBadge).toHaveCount(0);

		// Falls ein "ok"- oder "Fehler"-Text vorhanden ist, muss er als [data-slot="pill"] gerendert sein
		const okText = subscriptionsPanel.locator('text=ok');
		const errorText = subscriptionsPanel.locator('text=Fehler');

		const hasOk = await okText.count() > 0;
		const hasError = await errorText.count() > 0;

		if (hasOk) {
			const okPill = subscriptionsPanel.locator('[data-slot="pill"]:has-text("ok")');
			await expect(okPill).toBeVisible();
		}

		if (hasError) {
			const errorPill = subscriptionsPanel.locator('[data-slot="pill"]:has-text("Fehler")');
			await expect(errorPill).toBeVisible();
		}
	});

	// ── AC-7: Bearbeiten-Button in Auto-Report-Karten vorhanden ──────────────
	test('AC-7: Jede Auto-Report-Karte hat einen Bearbeiten-Icon-Button', async ({ page }) => {
		const emptyMsg = page.locator('text=Noch keine Auto-Reports gespeichert');
		const isEmpty = await emptyMsg.isVisible().catch(() => false);
		if (isEmpty) {
			test.skip();
			return;
		}

		// Suche nach Bearbeiten-Buttons in der Auto-Reports-Sektion
		// Btn variant="ghost" size="icon-sm" title="Bearbeiten"
		const editBtns = page.locator('button[title="Bearbeiten"]').filter({
			hasAncestor: page.locator('.space-y-3:has(h3:has-text("Auto-Reports"))'),
		});

		await expect(editBtns.first()).toBeVisible();
	});
});

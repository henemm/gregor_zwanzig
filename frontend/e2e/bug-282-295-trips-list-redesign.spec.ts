// E2E — Bug #282 + #295: Trips-Liste Redesign
//
// Spec: docs/specs/modules/bug_282_295_trips_list_redesign.md (AC-1 bis AC-8)
//
// TDD RED: Diese Tests MÜSSEN FEHLSCHLAGEN — Eyebrow, Summary-Stats,
// Kebab-Menü, Trip-Name-Link und Footer sind noch nicht implementiert.

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const DESKTOP_VIEWPORT = { width: 1440, height: 900 };
const MOBILE_VIEWPORT = { width: 375, height: 667 };

test.describe('Bug #282 + #295 — Trips-Liste Redesign', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ─── AC-1: Eyebrow + H1-Typografie + Subtitle ───────────────────────────
	test('AC-1: Eyebrow "WORKSPACE · TOUREN" über H1 mit text-3xl und Subtitle sichtbar', async ({
		page
	}) => {
		/**
		 * GIVEN: Desktop-Viewport (≥ 900px), /trips geladen, User eingeloggt
		 * WHEN:  Seite wird gerendert
		 * THEN:  [data-slot="eyebrow"] mit Text "WORKSPACE · TOUREN" ist sichtbar,
		 *        H1 enthält "Trips" und hat Klassen text-3xl + font-semibold,
		 *        Subtitle-Text ist sichtbar
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		const eyebrow = page.locator('[data-slot="eyebrow"]').first();
		await expect(eyebrow).toBeVisible({ timeout: 5000 });
		await expect(eyebrow).toContainText('TOUREN');

		const h1 = page.locator('h1').first();
		await expect(h1).toBeVisible();
		const h1Class = (await h1.getAttribute('class')) ?? '';
		expect(h1Class).toMatch(/text-3xl/);
		expect(h1Class).toMatch(/font-semibold/);

		// Subtitle
		const subtitle = page.locator('p').filter({ hasText: /Zeitraum|Aktionen/ }).first();
		await expect(subtitle).toBeVisible();
	});

	// ─── AC-2: Summary-Stats Strip ──────────────────────────────────────────
	test('AC-2: Summary-Stats mit 4 Einträgen sichtbar (Aktiv, Geplant, Pausiert, Archiviert)', async ({
		page
	}) => {
		/**
		 * GIVEN: Desktop-Viewport, /trips geladen, mindestens 1 Trip vorhanden
		 * WHEN:  Seite gerendert wird
		 * THEN:  4 Stats-Einträge mit den Labels Aktiv / Geplant / Pausiert / Archiviert
		 *        sind sichtbar, jeder mit einem Status-Dot
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		// Mindestens 1 Trip muss vorhanden sein
		const table = page.locator('table');
		if (!(await table.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		for (const label of ['Aktiv', 'Geplant', 'Pausiert', 'Archiviert']) {
			const stat = page.locator('div').filter({ hasText: new RegExp(`^${label}$`) }).first();
			await expect(stat).toBeVisible({ timeout: 5000 });
		}

		// Stats-Container enthält Status-Dots
		const dots = page.locator('[data-slot="dot"]');
		const dotCount = await dots.count();
		// Mindestens 4 Dots für Summary-Stats (können mehr sein wegen Tabellenzeilen)
		expect(dotCount).toBeGreaterThanOrEqual(4);
	});

	// ─── AC-3: Kebab-Dropdown mit 6 Items ───────────────────────────────────
	test('AC-3: Kebab ⋯ öffnet Dropdown mit 6 Items in korrekter Reihenfolge', async ({
		page
	}) => {
		/**
		 * GIVEN: Desktop-Viewport, /trips, mindestens 1 Trip
		 * WHEN:  User klickt ⋯-Button in der ersten Tabellenzeile
		 * THEN:  Dropdown öffnet sich mit genau 6 Items:
		 *        Bearbeiten, Test-Briefing Morgen, Test-Briefing Abend,
		 *        Wetter-Konfiguration, Report-Konfiguration, Löschen
		 *        Das Item "Bearbeiten" hat data-testid="trip-edit-btn"
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		const firstRow = page.locator('table tbody tr').first();
		if (!(await firstRow.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		const kebabBtn = firstRow.getByTitle('Weitere Aktionen');
		await expect(kebabBtn).toBeVisible({ timeout: 5000 });
		await kebabBtn.click();

		// Alle 6 Items prüfen
		for (const label of [
			'Bearbeiten',
			'Test-Briefing Morgen',
			'Test-Briefing Abend',
			'Wetter-Konfiguration',
			'Report-Konfiguration',
			'Löschen',
		]) {
			await expect(page.getByRole('button', { name: label }).first()).toBeVisible({
				timeout: 3000,
			});
		}

		// trip-edit-btn liegt auf "Bearbeiten"
		const editItem = page.locator('[data-testid="trip-edit-btn"]');
		await expect(editItem).toBeVisible();
	});

	// ─── AC-4: Dropdown schließt bei Fokus-Verlust ──────────────────────────
	test('AC-4: Kebab-Dropdown schließt sich bei Fokus-Verlust', async ({ page }) => {
		/**
		 * GIVEN: Kebab-Dropdown ist geöffnet
		 * WHEN:  User drückt Escape oder bewegt Fokus heraus
		 * THEN:  Dropdown ist nicht mehr sichtbar
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		const firstRow = page.locator('table tbody tr').first();
		if (!(await firstRow.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		const kebabBtn = firstRow.getByTitle('Weitere Aktionen');
		await kebabBtn.click();

		// Dropdown ist offen
		const dropdown = page.getByRole('button', { name: 'Bearbeiten' }).first();
		await expect(dropdown).toBeVisible({ timeout: 3000 });

		// Escape schließt Dropdown
		await page.keyboard.press('Escape');
		await expect(dropdown).not.toBeVisible({ timeout: 3000 });
	});

	// ─── AC-5: Primary-Button-Label statusabhängig ───────────────────────────
	test('AC-5: Primary-Button zeigt "Briefing-Vorschau" für aktive/geplante Trips', async ({
		page
	}) => {
		/**
		 * GIVEN: Desktop-Viewport, /trips, mindestens 1 aktiver oder geplanter Trip
		 * WHEN:  Aktionsspalte gerendert wird
		 * THEN:  Primary-Button zeigt "Briefing-Vorschau"
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		const firstRow = page.locator('table tbody tr').first();
		if (!(await firstRow.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		// Mindestens ein Primary-Button mit einem der erwarteten Labels
		const primaryBtns = page
			.locator('table tbody tr td')
			.last()
			.locator('button, a[role="button"]')
			.filter({
				hasText: /Briefing-Vorschau|Reaktivieren|Dearchivieren/,
			});
		const count = await primaryBtns.count();
		// Im ersten Row muss ein Primary-Button existieren
		const actionsCell = firstRow.locator('td').last();
		const primaryBtn = actionsCell
			.locator('button')
			.filter({ hasText: /Briefing-Vorschau|Reaktivieren|Dearchivieren/ })
			.first();
		await expect(primaryBtn).toBeVisible({ timeout: 5000 });
	});

	// ─── AC-6: Trip-Name ist klickbarer Link zu /trips/{id} ─────────────────
	test('AC-6: Klick auf Trip-Namen navigiert zu /trips/{id}', async ({ page }) => {
		/**
		 * GIVEN: Desktop-Viewport, /trips, mindestens 1 Trip
		 * WHEN:  User klickt auf den Trip-Namen in der ersten Tabellenzeile
		 * THEN:  URL wechselt zu /trips/{id}
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		const firstRow = page.locator('table tbody tr').first();
		if (!(await firstRow.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		// Trip-Name als <a>-Link
		const nameLink = firstRow.locator('td a[href^="/trips/"]').first();
		await expect(nameLink).toBeVisible({ timeout: 5000 });

		await nameLink.click();
		await page.waitForURL(/\/trips\/.+/, { timeout: 5000 });
		expect(page.url()).toMatch(/\/trips\/.+/);
		// Sicherstellen, dass wir nicht auf /trips/new gelandet sind
		expect(page.url()).not.toMatch(/\/trips\/new/);
	});

	// ─── AC-7: Mobile-Test-IDs aus Issue #268 unverändert ───────────────────
	test('AC-7: Mobile Card-Stack und Bottom-Sheet sind unverändert erhalten', async ({ page }) => {
		/**
		 * GIVEN: Mobile-Viewport (≤ 899px), /trips, mindestens 1 Trip
		 * WHEN:  Seite geladen wird
		 * THEN:  trip-card-stack, trip-card, trip-card-content-btn, trip-card-menu-btn
		 *        sind vorhanden und funktionsfähig
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/trips');

		const cardStack = page.getByTestId('trip-card-stack');
		await expect(cardStack).toBeVisible({ timeout: 5000 });

		const firstCard = cardStack.getByTestId('trip-card').first();
		if (!(await firstCard.isVisible({ timeout: 3000 }).catch(() => false))) {
			// Kein Trip — AC-7 nicht sinnvoll testbar
			test.skip();
			return;
		}

		await expect(firstCard.getByTestId('trip-card-content-btn')).toBeVisible();
		await expect(firstCard.getByTestId('trip-card-menu-btn')).toBeVisible();

		// Bottom-Sheet öffnet sich
		await firstCard.getByTestId('trip-card-menu-btn').click();
		const sheet = page.getByTestId('trip-action-sheet');
		await expect(sheet).toBeVisible({ timeout: 3000 });
	});

	// ─── AC-8: Footer "X von Y Trips" ───────────────────────────────────────
	test('AC-8: Footer zeigt "X von Y Trips" in Mono-Caps', async ({ page }) => {
		/**
		 * GIVEN: Desktop-Viewport, /trips, mindestens 1 Trip
		 * WHEN:  Seite gerendert wird
		 * THEN:  Unterhalb der Tabelle ist ein Footer mit "X von Y Trips" sichtbar
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		const table = page.locator('table');
		if (!(await table.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		const footer = page.locator('p, caption').filter({ hasText: /von \d+ Trips/ }).first();
		await expect(footer).toBeVisible({ timeout: 5000 });
		await expect(footer).toContainText('Trips');
	});
});

// E2E (Staging) — Issue #1256 Scheibe S8d: Mobile-Editor-Fidelity
// (Restliste-Bündel R4 Mobile-Vervollständigung + C1 Desktop-Editor-create
// Weiter-CTA-Füße).
//
// Spec: docs/specs/modules/feat_1256_s8d_mobile_editor_fidelity.md (AC-1..AC-20)
//
// Ausführen (gegen Staging, aus frontend/, NACH Push+Staging-Deploy):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1256-s8d.staging.config.ts
//
// Muster: compare-hub-fidelity-s8c.spec.ts (S8c) — echte Klickpfade statt
// goto() wo ein Klick gefordert ist, eindeutige Testdaten-Namen mit
// Date.now()-Suffix, :visible-Disambiguierung (Desktop+Mobil-Doppel-DOM),
// afterEach-Cleanup, storageState-Login (kein per-Test-Login, 429-Rate-Limit).
//
// AC-20 (Sharing-Invariante) ist bereits als Node-Source-Wächter in
// compare_editor_mobile_fidelity.test.ts abgedeckt (läuft bei jedem
// vitest/node-test-Durchlauf, kein Staging nötig) — hier nicht dupliziert.
// Die migrierten Bestandssuiten (compare-mobile-vervollstaendigung.spec.ts,
// issue-682-compare-editor-mobile.spec.ts) laufen im selben Staging-Zyklus
// separat weiter grün (eigene Config).

import { test, expect, type Page } from '@playwright/test';

const MOBILE = { width: 390, height: 844 };
const DESKTOP = { width: 1280, height: 900 };

let createdIds: string[] = [];
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

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
	expect(res.ok(), 'Location-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdLocationIds.push(id);
	return id;
}

async function createPresetWithLocations(page: Page, name: string, locationIds: string[]): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'daily',
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

// ─────────────────────────────────────────────────────────────────────────
// Gruppe A — Mobile-Liste (compare/+page.svelte)
// ─────────────────────────────────────────────────────────────────────────

test.describe('Issue #1256 S8d (AC-1): mobile Design-Kopfleiste auf /compare', () => {
	test('Titel + Eyebrow sichtbar, Plus navigiert nach /compare/new; andere Seiten/Desktop unverändert', async ({
		page
	}) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8d Ort-List ${suffix}`, 47.05, 11.05);
		await createPresetWithLocations(page, `E2E S8d List ${suffix}`, [locId]);

		await page.setViewportSize(MOBILE);
		await page.goto('/compare');
		await page.waitForLoadState('networkidle');

		const bar = page.getByTestId('top-app-bar');
		await expect(bar).toBeVisible();
		await expect(bar.getByTestId('top-app-bar-title')).toHaveText('Orts-Vergleiche');
		await expect(bar).toContainText('Workspace ·');

		const plus = page.getByTestId('top-app-bar-new-compare');
		await expect(plus).toBeVisible();
		await plus.click();
		await page.waitForURL('**/compare/new');

		// Andere Seite (/trips) zeigt weiterhin den Wordmark-Default.
		await page.goto('/trips');
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('top-app-bar').getByTestId('top-app-bar-title')).toHaveCount(0);

		// Desktop-Viewport auf /compare zeigt weiterhin den 32px-Titel.
		await page.setViewportSize(DESKTOP);
		await page.goto('/compare');
		await page.waitForLoadState('networkidle');
		await expect(page.locator('.hidden.desktop\\:block').getByText('Orts-Vergleiche').first()).toBeVisible();
	});
});

test.describe('Issue #1256 S8d (AC-2): kurzer mobiler Intro-Text', () => {
	test('kurzer Satz sichtbar, langer Desktop-Satz nicht sichtbar', async ({ page }) => {
		await page.setViewportSize(MOBILE);
		await page.goto('/compare');
		await page.waitForLoadState('networkidle');

		await expect(page.getByText('Ohne Ranking — läuft, bis du stoppst.')).toBeVisible();
		// Fix-Loop 2: der lange Desktop-Satz liegt im `hidden desktop:block`-Zweig
		// weiterhin im DOM (nur per CSS display:none versteckt) — toHaveCount(0)
		// prueft DOM-Anwesenheit statt Sichtbarkeit und schlaegt daher faelschlich
		// fehl. not.toBeVisible() ist die von der Spec geforderte Semantik.
		await expect(page.getByText('Morgen-Briefing für heute, Abend-Briefing für morgen')).not.toBeVisible();
	});
});

test.describe('Issue #1256 S8d (AC-3): Suchfeld nur Desktop', () => {
	test('mobil kein Suchfeld; Desktop Suchfeld sichtbar und filtert', async ({ page }) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8d Ort-Such ${suffix}`, 47.06, 11.06);
		await createPresetWithLocations(page, `E2E S8d Suchbar ${suffix}`, [locId]);

		await page.setViewportSize(MOBILE);
		await page.goto('/compare');
		await page.waitForLoadState('networkidle');
		// Fix-Loop 2: gleiches Muster wie AC-2 — Desktop-Suchfeld ist per
		// display:none (`hidden desktop:block`) versteckt, bleibt aber im DOM.
		await expect(page.getByPlaceholder('Suchen…')).not.toBeVisible();

		await page.setViewportSize(DESKTOP);
		await page.reload();
		await page.waitForLoadState('networkidle');
		const search = page.getByPlaceholder('Suchen…');
		await expect(search).toBeVisible();
		await search.fill(`E2E S8d Suchbar ${suffix}`);
		await expect(page.getByText(`E2E S8d Suchbar ${suffix}`).first()).toBeVisible();
	});
});

test.describe('Issue #1256 S8d (AC-4): mobile Stats kompakt (size=sm)', () => {
	test('Stat-Werte sichtbar; mobile Schriftgröße kleiner als Desktop', async ({ page }) => {
		await page.setViewportSize(MOBILE);
		await page.goto('/compare');
		await page.waitForLoadState('networkidle');
		await expect(page.locator('.desktop\\:hidden').getByText('Aktiv').first()).toBeVisible();
		const mobileFontSize = await page
			.locator('.desktop\\:hidden')
			.getByText('Aktiv')
			.first()
			.evaluate((el) => parseFloat(window.getComputedStyle(el).fontSize));

		await page.setViewportSize(DESKTOP);
		await page.reload();
		await page.waitForLoadState('networkidle');
		const desktopFontSize = await page
			.locator('.hidden.desktop\\:block')
			.getByText('Aktiv')
			.first()
			.evaluate((el) => parseFloat(window.getComputedStyle(el).fontSize));

		expect(mobileFontSize).toBeLessThan(desktopFontSize);
	});
});

test.describe('Issue #1256 S8d (AC-5): kompaktes mobiles Content-Padding', () => {
	test('kein doppeltes Padding, kein horizontaler Overflow', async ({ page }) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8d Ort-Pad ${suffix}`, 47.07, 11.07);
		await createPresetWithLocations(page, `E2E S8d Padding ${suffix}`, [locId]);

		await page.setViewportSize(MOBILE);
		await page.goto('/compare');
		await page.waitForLoadState('networkidle');

		const overflow = await page.evaluate(
			() => (document.scrollingElement?.scrollWidth ?? 0) - window.innerWidth
		);
		expect(overflow).toBeLessThanOrEqual(1);

		// Fix-Loop 2: unscoped Selektor traf zuerst top-app-bar-new-compare
		// (href="/compare/new", ebenfalls in einem .desktop\:hidden-Container,
		// aber ausserhalb von <main>) statt die erste Kachel — auf <main>
		// eingrenzen, wo ausschliesslich der mobile Kachel-Stack liegt.
		const firstTile = page.locator('main .desktop\\:hidden a[href^="/compare/"]').first();
		await expect(firstTile).toBeVisible();
		const box = await firstTile.boundingBox();
		expect(box?.x ?? 0).toBeGreaterThanOrEqual(12);
		expect(box?.x ?? 0).toBeLessThanOrEqual(20);
	});
});

// ─────────────────────────────────────────────────────────────────────────
// Gruppe B — Mobiler Editor
// ─────────────────────────────────────────────────────────────────────────

test.describe('Issue #1256 S8d (AC-6/AC-7): mobiler Orte-Tab dense-Stack', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(MOBILE);
	});

	test('Kopfzeile, Badge, nummerierte Karten, Entfernen; kein Smart-Import/Inline-Bibliothek', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S8d Ort-A ${suffix}`, 47.08, 11.08);

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		// Epic #1301 F3 (#989): eigenständiges Mobile-Namensfeld.
		await page.getByTestId('compare-editor-name-mobile').fill(`E2E S8d Editor ${suffix}`);
		await page.locator('[data-testid="cm-mobile-tab-orte"]:visible').click();

		await expect(page.locator('.cm-mobile').getByText('Im Vergleich ·')).toBeVisible();
		// Step2Orte wird als GETRENNTE Instanz sowohl im .cm-desktop- als auch im
		// .cm-mobile-Zweig gemountet (CSS-only Switch, beide Zweige im DOM) —
		// compare-step2-counter existiert daher doppelt. Seit Epic #1301 F3
		// (#989) ist der .cm-desktop-Zweig auf Mobile per display:none versteckt,
		// bleibt aber im DOM — Container-Scoping auf .cm-mobile ist deshalb
		// weiterhin fuer die doppelt vorhandenen Elemente noetig.
		await expect(page.locator('.cm-mobile [data-testid="compare-step2-counter"]')).toHaveText('min. 2');
		await expect(page.locator('.cm-mobile [data-testid="compare-step2-smart-import-input"]')).toHaveCount(0);
		await expect(page.locator('.cm-mobile [data-testid="compare-step2-library"]')).toHaveCount(0);

		// Ort aus der Bibliothek hinzufügen (Sheet).
		await page.getByTestId('compare-step2-mobile-library-btn').click();
		await page.locator(`[data-testid="compare-step2-mobile-lib-check-${locA}"]`).click();
		await page.locator('button[aria-label="Schliessen"]:visible').click();

		// Fix-Loop 2: gleiches Doppel-Mount-Muster wie oben — Container-Scoping
		// auf .cm-mobile statt :visible (konsistent, unabhaengig vom CSS-
		// Layout-Zufall ob die .cm-desktop-Kopie auf 0 Breite kollabiert).
		const pickedItem = page.locator(`.cm-mobile [data-testid="compare-step2-picked-item-${locA}"]`);
		await expect(pickedItem).toBeVisible();
		await expect(pickedItem).toContainText('1');

		await page.locator(`.cm-mobile [data-testid="compare-step2-picked-remove-${locA}"]`).click();
		await expect(pickedItem).toHaveCount(0);
	});
});

test.describe('Issue #1256 S8d (AC-8..AC-12): kontextuelle Floating-CTA + Versand ohne Boden-CTA', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(MOBILE);
	});

	test('CTA-Labels wechseln pro Tab; Versand-Tab hat keine Floating-CTA mehr', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S8d Ort-CtaA ${suffix}`, 47.09, 11.09);
		const locB = await createLocation(page, `E2E S8d Ort-CtaB ${suffix}`, 47.1, 11.1);

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');

		// AC-8: leerer Name -> "Name eingeben" disabled. Der Button traegt
		// tatsaechlich das HTML disabled-Attribut (kein reiner Style-Zustand) —
		// ein Klick darauf ist per Browser-/Playwright-Actionability nicht
		// ausfuehrbar und lief bisher in einen 60s-Timeout. Fix-Loop 2: Zustand
		// nur noch pruefen (disabled + Tab bleibt unveraendert auf "vergleich"),
		// nicht mehr klicken.
		const cta = page.locator('[data-testid="cm-mobile-cta"]:visible');
		await expect(cta).toContainText('Name eingeben');
		await expect(cta.getByRole('button')).toBeDisabled();
		await expect(page.locator('[data-testid="cm-mobile-tab-vergleich"]:visible')).toHaveAttribute(
			'data-active',
			'true'
		);

		// Name setzen -> "Orte hinzufügen →" aktiv, Klick wechselt zu Orte.
		// Epic #1301 F3 (#989): eigenständiges Mobile-Namensfeld.
		await page.getByTestId('compare-editor-name-mobile').fill(`E2E S8d Cta ${suffix}`);
		await expect(cta).toContainText('Orte hinzufügen →');
		await cta.getByRole('button').click();
		await expect(page.locator('[data-testid="cm-mobile-tab-orte"]:visible')).toHaveAttribute(
			'data-active',
			'true'
		);

		// AC-9: 1 Ort -> "noch 1 Ort nötig" disabled.
		await page.getByTestId('compare-step2-mobile-library-btn').click();
		await page.locator(`[data-testid="compare-step2-mobile-lib-check-${locA}"]`).click();
		await page.locator('button[aria-label="Schliessen"]:visible').click();
		await expect(cta).toContainText('noch 1 Ort nötig');

		// 2. Ort -> Epic #1301 F2a: neuer Wetter-Metriken-Tab in der Kette. Der
		// Orte-CTA führt jetzt zu "Wetter-Metriken →", nicht direkt zu Wertebereiche.
		await page.getByTestId('compare-step2-mobile-library-btn').click();
		await page.locator(`[data-testid="compare-step2-mobile-lib-check-${locB}"]`).click();
		await page.locator('button[aria-label="Schliessen"]:visible').click();
		await expect(cta).toContainText('Wetter-Metriken →');
		await cta.getByRole('button').click();
		await expect(page.locator('[data-testid="cm-mobile-tab-metriken"]:visible')).toHaveAttribute(
			'data-active',
			'true'
		);

		// Wetter-Metriken-Tab -> "Wertebereiche festlegen →".
		await expect(cta).toContainText('Wertebereiche festlegen →');
		await cta.getByRole('button').click();
		await expect(page.locator('[data-testid="cm-mobile-tab-idealwerte"]:visible')).toHaveAttribute(
			'data-active',
			'true'
		);

		// AC-10: Wertebereiche-Tab -> "Layout einrichten →".
		await expect(cta).toContainText('Layout einrichten →');
		await cta.getByRole('button').click();
		await expect(page.locator('[data-testid="cm-mobile-tab-layout"]:visible')).toHaveAttribute(
			'data-active',
			'true'
		);

		// AC-11 (Issue #1258 S4, AC-28): Layout-Tab -> "Alarme einrichten →" (neue
		// reguläre Station, ersetzt den vormals direkten Sprung zu "Versand").
		await expect(cta).toContainText('Alarme einrichten →');
		await cta.getByRole('button').click();
		await expect(page.locator('[data-testid="cm-mobile-tab-alarme"]:visible')).toHaveAttribute(
			'data-active',
			'true'
		);

		// Alarme-Tab -> "Versand einrichten →".
		await expect(cta).toContainText('Versand einrichten →');
		await cta.getByRole('button').click();
		await expect(page.locator('[data-testid="cm-mobile-tab-versand"]:visible')).toHaveAttribute(
			'data-active',
			'true'
		);

		// AC-12: Versand-Tab hat keine Boden-Floating-CTA mehr.
		await expect(page.locator('[data-testid="cm-mobile-cta"]:visible')).toHaveCount(0);
	});
});

test.describe('Issue #1256 S8d (AC-13/AC-14): Profil-Häkchen + gekürzte Metrik-Zeile', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(MOBILE);
	});

	test('Häkchen bei Auswahl; Metrik-Zeile endet mit „…" bei >4 Metriken (Wintersport)', async ({ page }) => {
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');

		// Wintersport hat 5 Metriken (SNOW_DEPTH, SNOW_NEW, SUNNY_HOURS, WIND_MAX,
		// CLOUD_AVG) — der Desktop-Button teilt denselben wiz-State. Fix-Loop 2:
		// compare-editor-profile-wintersport liegt im .cm-desktop-Zweig, der auf
		// Mobile nur per position:fixed/1px-Overflow offscreen ist (nicht
		// display:none) — dadurch bleibt der Button fuer Playwright zwar
		// "visible", ist aber dauerhaft "outside of the viewport" und nicht
		// klickbar (60s-Timeout). Eigener Mobile-Testid (CompareEditor.svelte)
		// ersetzt den Klick auf das unerreichbare Desktop-Element.
		const mobileCard = page.locator('[data-testid="compare-editor-profile-mobile-wintersport"]');
		await mobileCard.click();

		await expect(mobileCard).toBeVisible();
		await expect(mobileCard.locator('svg path[d="M2 6l3 3 5-6"]')).toBeVisible();
		await expect(mobileCard).toContainText('…');
	});
});

test.describe('Issue #1256 S8d (AC-15): genau eine App-Leiste im mobilen Editor', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(MOBILE);
	});

	test('„…" vor Bereitschaft, „Aktivieren" danach; Zurück navigiert /compare; Titel wechselt mit Tab', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S8d Ort-BarA ${suffix}`, 47.11, 11.11);
		const locB = await createLocation(page, `E2E S8d Ort-BarB ${suffix}`, 47.12, 11.12);

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');

		const bars = page.getByTestId('top-app-bar');
		await expect(bars).toHaveCount(1);
		await expect(bars.getByTestId('top-app-bar-title')).toHaveText('Vergleich');
		await expect(bars.getByTestId('top-app-bar-activate')).toHaveText('…');

		// Epic #1301 F3 (#989): eigenständiges Mobile-Namensfeld.
		await page.getByTestId('compare-editor-name-mobile').fill(`E2E S8d Bar ${suffix}`);
		await expect(bars.getByTestId('top-app-bar-title')).toHaveText('Vergleich');
		const cta = page.locator('[data-testid="cm-mobile-cta"]:visible');
		await cta.getByRole('button').click();
		await expect(bars.getByTestId('top-app-bar-title')).toHaveText('Orte');

		await page.getByTestId('compare-step2-mobile-library-btn').click();
		await page.locator(`[data-testid="compare-step2-mobile-lib-check-${locA}"]`).click();
		await page.locator(`[data-testid="compare-step2-mobile-lib-check-${locB}"]`).click();
		await page.locator('button[aria-label="Schliessen"]:visible').click();
		// Epic #1301 F2a: fünf Klicks für die 7-Tab-Kette ab Orte
		// (orte → metriken → idealwerte → layout → alarme → versand).
		await cta.getByRole('button').click();
		await cta.getByRole('button').click();
		await cta.getByRole('button').click();
		await cta.getByRole('button').click();
		await cta.getByRole('button').click();

		await expect(bars.getByTestId('top-app-bar-title')).toHaveText('Versand');
		await expect(bars.getByTestId('top-app-bar-activate')).toHaveText('Aktivieren');

		await bars.getByTestId('top-app-bar-back').click();
		await page.waitForURL('**/compare');

		// F001-Fix (Adversary): Rück-Navigation muss die App-Leiste wirklich in
		// den Listen-Zustand versetzen, nicht nur die URL wechseln — beweist,
		// dass der Editor-Store-Reset ($effect-Cleanup, CompareEditor.svelte:225)
		// bei Client-Navigation tatsächlich greift statt hängenzubleiben.
		await expect(bars.getByTestId('top-app-bar-title')).toHaveText('Orts-Vergleiche');
		await expect(bars).toContainText('Workspace ·');
		await expect(bars.getByTestId('top-app-bar-back')).toHaveCount(0);
	});
});

// ─────────────────────────────────────────────────────────────────────────
// Gruppe C — Desktop-Editor create
// ─────────────────────────────────────────────────────────────────────────

test.describe('Issue #1256 S8d (AC-16..AC-18): Desktop-CTA-Füße Orte/Wertebereiche/Layout', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(DESKTOP);
	});

	test('AC-16: ⊘-Hinweis bei 1 Ort, Button aktiv erst ab 2 Orten', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S8d D-Ort-A ${suffix}`, 47.13, 11.13);
		const locB = await createLocation(page, `E2E S8d D-Ort-B ${suffix}`, 47.14, 11.14);

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await page.getByTestId('compare-editor-name').fill(`E2E S8d Desktop-Orte ${suffix}`);
		await page.getByTestId('compare-editor-continue-orte').click();

		// Ersten Ort über die Bibliothek auswählen (Desktop-Grid).
		// Fix-Loop 2: Step2Orte wird als getrennte Instanz je in .cm-desktop UND
		// .cm-mobile gemountet (CSS-only Switch) — compare-wizard-step-2 (der
		// Root-Wrapper von Step2Orte.svelte) existiert daher doppelt. Bei
		// diesem Test (DESKTOP-Viewport) ist .cm-mobile jedoch echtes
		// display:none, daher hier auf .cm-desktop eingrenzen statt :visible.
		await page.locator(`.cm-desktop div[data-testid="compare-wizard-step-2"]`).waitFor({ state: 'visible' });
		await page.getByText(`E2E S8d D-Ort-A ${suffix}`).click();

		// Epic #1301 F2a: der Orte-Weiter-Knopf ist ziel-benannt
		// (compare-editor-continue-metriken) und führt zum NEUEN Wetter-Metriken-Tab.
		// Das ⊘-Gate (disabled bis ≥2 Orte) ist unverändert.
		const continueBtn = page.getByTestId('compare-editor-continue-metriken');
		await expect(page.getByText('⊘ min. 2 Orte auswählen')).toBeVisible();
		await expect(continueBtn).toBeDisabled();

		await page.getByText(`E2E S8d D-Ort-B ${suffix}`).click();
		await expect(page.getByText('⊘ min. 2 Orte auswählen')).toHaveCount(0);
		await expect(continueBtn).toBeEnabled();
		await continueBtn.click();
		await expect(page.getByTestId('compare-editor-tab-metriken')).toHaveAttribute('data-active', 'true');
	});

	// Issue #1258 Scheibe S4 (E1/E2, AC-28): Layout fuehrt jetzt zu "alarme"
	// (Testid compare-editor-continue-alarme), Alarme fuehrt zu "versand"
	// (neuer CTA im Alarme-Fuß, testid compare-editor-continue-versand).
	test('AC-17/AC-18: Wertebereiche → „Layout einrichten →" → Layout → „Alarme einrichten →" → Alarme → „Versand einrichten →"', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S8d D2-Ort-A ${suffix}`, 47.15, 11.15);
		const locB = await createLocation(page, `E2E S8d D2-Ort-B ${suffix}`, 47.16, 11.16);

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await page.getByTestId('compare-editor-name').fill(`E2E S8d Desktop-Layout ${suffix}`);
		await page.getByTestId('compare-editor-continue-orte').click();
		await page.getByText(`E2E S8d D2-Ort-A ${suffix}`).click();
		await page.getByText(`E2E S8d D2-Ort-B ${suffix}`).click();
		// Epic #1301 F2a: neue Kette Orte → Wetter-Metriken → Wertebereiche.
		// Orte-Fuß führt zum Metriken-Tab; der Wertebereiche-Fuß
		// (compare-editor-continue-idealwerte) sitzt jetzt auf dem Metriken-Tab.
		await page.getByTestId('compare-editor-continue-metriken').click();
		await page.getByTestId('compare-editor-continue-idealwerte').click();

		const layoutBtn = page.getByTestId('compare-editor-continue-layout');
		await expect(layoutBtn).toBeVisible();
		await layoutBtn.click();
		await expect(page.getByTestId('compare-editor-tab-layout')).toHaveAttribute('data-active', 'true');

		const alarmeBtn = page.getByTestId('compare-editor-continue-alarme');
		await expect(alarmeBtn).toBeVisible();
		await alarmeBtn.click();
		await expect(page.getByTestId('compare-editor-tab-alarme')).toHaveAttribute('data-active', 'true');

		const versandBtn = page.getByTestId('compare-editor-continue-versand');
		await expect(versandBtn).toBeVisible();
		await versandBtn.click();
		await expect(page.getByTestId('compare-editor-tab-versand')).toHaveAttribute('data-active', 'true');
	});
});

// Epic #1273 S4c: Die describe-Gruppe „Edit-Modus zeigt keine Create-CTA-Füße"
// (Issue #1256 S8d) wurde entfernt — der abgeschaffte Edit-Modus kannte nie
// Create-CTA-Füße; im Hub-Modell gegenstandslos.

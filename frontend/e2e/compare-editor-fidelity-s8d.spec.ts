// gz-eigenstaendig: nur noch Anlege-Fälle des Ortsvergleichs ohne Trip-Pendant — Orte-Tab mobil (AC-6/AC-7), Vergleichs-Profilkachel mit gekürzter Metrik-Zeile (AC-13/AC-14; der Trip wählt die Aktivität per Dropdown, Pendant hub-kopf-bearbeiten KB-3), ⊘-Orte-Gate am Desktop-Fuß (AC-16) und die mobile CTA-Kette mit dem Zwischenstand „noch 1 Ort nötig" (AC-9..AC-12; ein einzelner Ort hat beim Trip kein Gegenstück, Etappen zählen GPX). Wortlaut je Pflichtschritt und gesperrte CTA ohne Namen (AC-8) prüft hub-anlegen-ablauf AN-14 je kind, die Desktop-Weiter-Füße (AC-17/AC-18) AN-15 je kind — #2347 S4 „Nachträge Teil E".
//
// E2E (Staging) — Issue #1256 Scheibe S8d: Mobile-Editor-Fidelity
// (Restliste-Bündel R4 Mobile-Vervollständigung + C1 Desktop-Editor-create
// Weiter-CTA-Füße).
//
// Spec: docs/specs/modules/feat_1256_s8d_mobile_editor_fidelity.md (AC-1..AC-20)
// #2347 S4 (feat_2347_s4_paritaets_e2e.md): AC-1..AC-5 → hub-liste-seitenrahmen
// HL-1..HL-5, AC-15 → hub-anlegen-ablauf AN-9 (je kind); AC-8..AC-12 teilweise →
// AN-14 (Wortlaut je Pflichtschritt, gesperrte CTA ohne Namen, Punkte-Gate),
// AC-17/AC-18 → AN-15; Rest bleibt hier (Kopfzeile).
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
// Die migrierten Bestandssuiten (hub-list-menu.spec.ts/hub-tab-bar.spec.ts,
// issue-682-compare-editor-mobile.spec.ts) laufen im selben Staging-Zyklus
// separat weiter grün (eigene Config).

import { test, expect, type Page } from '@playwright/test';
import { createTestLocation } from './helpers';

const MOBILE = { width: 390, height: 844 };
const DESKTOP = { width: 1280, height: 900 };

let createdLocationIds: string[] = [];

test.afterEach(async ({ page }) => {
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
	// #1329 Maßnahme B: zentralisiert über den geteilten Helfer (helpers.ts).
	const loc = await createTestLocation(page.request, { name, lat, lon });
	createdLocationIds.push(loc.id);
	return loc.id;
}

// Gruppe A (AC-1..AC-5, mobile Liste) → #2347 S4: hub-liste-seitenrahmen HL-1..HL-5 je kind.

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

test.describe('Issue #1256 S8d (AC-9..AC-12): kontextuelle Floating-CTA + Versand mit Aktivieren im Sticky-Footer', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(MOBILE);
	});

	test('CTA-Labels wechseln pro Tab; Versand-Tab zeigt Aktivieren im Sticky-Footer', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S8d Ort-CtaA ${suffix}`, 47.09, 11.09);
		const locB = await createLocation(page, `E2E S8d Ort-CtaB ${suffix}`, 47.1, 11.1);

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');

		// AC-8 (leerer Name ⇒ gesperrte CTA „Name eingeben", Schritt bleibt) →
		// #2347 S4 Teil E: hub-anlegen-ablauf AN-14 je kind.
		const cta = page.locator('[data-testid="cm-mobile-cta"]:visible');

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
		await expect(page.locator('[data-testid="cm-mobile-tab-wetter-metriken"]:visible')).toHaveAttribute(
			'data-active',
			'true'
		);

		// Wetter-Metriken-Tab -> "Wertebereiche festlegen →".
		await expect(cta).toContainText('Wertebereiche festlegen →');
		await cta.getByRole('button').click();
		await expect(page.locator('[data-testid="cm-mobile-tab-wertebereiche"]:visible')).toHaveAttribute(
			'data-active',
			'true'
		);

		// AC-10/AC-11 (Issue #1258 S4, AC-28; Layout-Reiter per #1360 aufgelöst):
		// Wertebereiche-Tab -> "Alarme einrichten →" (reguläre Station vor "Versand").
		await expect(cta).toContainText('Alarme einrichten →');
		await cta.getByRole('button').click();
		await expect(page.locator('[data-testid="cm-mobile-tab-alarme"]:visible')).toHaveAttribute(
			'data-active',
			'true'
		);

		// Issue #1743: kein Schritt „Versand" mehr — Alarme ist der letzte Schritt,
		// der Sticky-Footer traegt dort „Briefing aktivieren" (derselbe Baustein, den
		// AC-15 prueft).
		await expect(page.locator('[data-testid="cm-mobile-tab-versand"]')).toHaveCount(0);
		await expect(page.getByTestId('cm-mobile-activate')).toBeVisible();
		await expect(cta).not.toContainText('Versand einrichten →');
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

// AC-15 (genau ein Kopf, Titel je Schritt, Aktivieren erst im letzten Schritt im
// Footer, Zurück ⇒ Liste mit Listen-Kopf) → #2347 S4: hub-anlegen-ablauf AN-9 je kind.

// ─────────────────────────────────────────────────────────────────────────
// Gruppe C — Desktop-Editor create
// ─────────────────────────────────────────────────────────────────────────

test.describe('Issue #1256 S8d (AC-16): Desktop-CTA-Fuß Orte', () => {
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
		// (compare-editor-continue-wetter-metriken) und führt zum NEUEN Wetter-Metriken-Tab.
		// Das ⊘-Gate (disabled bis ≥2 Orte) ist unverändert.
		const continueBtn = page.getByTestId('compare-editor-continue-wetter-metriken');
		await expect(page.getByText('⊘ min. 2 Orte auswählen')).toBeVisible();
		await expect(continueBtn).toBeDisabled();

		await page.getByText(`E2E S8d D-Ort-B ${suffix}`).click();
		await expect(page.getByText('⊘ min. 2 Orte auswählen')).toHaveCount(0);
		await expect(continueBtn).toBeEnabled();
		await continueBtn.click();
		await expect(page.getByTestId('compare-editor-tab-wetter-metriken')).toHaveAttribute('data-active', 'true');
	});

	// AC-17/AC-18 (Desktop-Weiter-Füße Wetter-Metriken ⇒ Wertebereiche ⇒ Alarme, danach
	// kein weiterer Schritt, Aktivieren frei) → #2347 S4 Teil E: hub-anlegen-ablauf AN-15 je kind.
});

// Epic #1273 S4c: Die describe-Gruppe „Edit-Modus zeigt keine Create-CTA-Füße"
// (Issue #1256 S8d) wurde entfernt — der abgeschaffte Edit-Modus kannte nie
// Create-CTA-Füße; im Hub-Modell gegenstandslos.

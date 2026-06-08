// E2E — Issue #661: Mobile-Parität /trips/new (Progressive Tab Editor, #622 AC-9).
//
// Spec: docs/specs/modules/issue_661_trip_new_mobile.md (AC-1 bis AC-9)
// Design-Quelle: docs/design-requests/trip-anlegen-2026-06-06/screen-trip-new-v2-mobile.jsx
//
// Reine responsive/Layout-Arbeit — die Logik (tripNewLogic.ts) bleibt unverändert.
// Diese Tests prüfen das mobile Verhalten aus Nutzerperspektive (≤899px) und den
// Desktop-Regressionsschutz (≥900px). Sie sind RED, solange das Mobile-Layout fehlt.
//
// TestID-Inventar (in TripNewEditor.svelte zu implementieren):
//   tn-mobile-appbar        — obere App-Leiste (nur ≤899px)
//   tn-mobile-save          — "Speichern"-Aktion in der App-Leiste
//   tn-desktop-breadcrumb   — Desktop-Breadcrumb-Zeile (nur ≥900px sichtbar)
//   tn-lock-toast           — Toast-Hinweis bei Tap auf gesperrten Tab (mobil)
//   tn-mobile-route-cta      — Floating-CTA im Route-Tab (mobil)
//   tn-mobile-stage-card     — Etappen-Karte (mobil, vertikal gestapelt)
//   tn-mobile-stage-name     — antippbares Etappen-Namensfeld (öffnet Sheet)
//   tn-mobile-stage-sheet    — Bottom-Sheet zur Etappenname-Eingabe
//   tn-mobile-stage-sheet-input  — Eingabe im Etappenname-Sheet
//   tn-mobile-stage-sheet-apply  — "Übernehmen" im Etappenname-Sheet
//
// Breakpoints: Mobile ≤ 899px · Desktop ≥ 900px (app.css @custom-variant).

import { test, expect, type Page } from '@playwright/test';

const MOBILE = { width: 375, height: 667 };
const DESKTOP = { width: 1280, height: 900 };

// Auth läuft über storageState (Projekt-Setup), nicht per Test-Login — vermeidet
// Auth-Rate-Limits bei parallelen Workern (Memory-Muster #586/#609).

// Pflicht-Eingaben Route-Tab, um Etappen freizuschalten.
async function fillRoute(page: Page, name = 'Mobile Testtour', date = '2026-07-01') {
	await page.getByTestId('trip-new-name-input').fill(name);
	await page.getByTestId('trip-new-date-input').fill(date);
}

test.describe('Issue #661 — /trips/new Mobile-Parität', () => {

	// AC-1: App-Leisten-Kopf mobil, Desktop-Breadcrumb verborgen.
	test('AC-1: Mobile zeigt App-Leiste mit Speichern, Desktop-Breadcrumb verborgen', async ({ page }) => {
		await page.setViewportSize(MOBILE);
		await page.goto('/trips/new');

		const appbar = page.getByTestId('tn-mobile-appbar');
		await expect(appbar).toBeVisible();
		await expect(page.getByTestId('tn-mobile-save')).toBeVisible();

		const breadcrumb = page.getByTestId('tn-desktop-breadcrumb');
		await expect(breadcrumb).toBeHidden();
	});

	// AC-2: Gesperrter Tab-Tap → Toast, kein Wechsel; Touch-Höhe ≥44px.
	test('AC-2: Gesperrter Tab zeigt Toast statt zu wechseln, Touch-Targets ≥44px', async ({ page }) => {
		await page.setViewportSize(MOBILE);
		await page.goto('/trips/new');

		// "Etappen" ist ohne Tour-Name/Datum gesperrt.
		// Explizit den mobilen Tab ansteuern (Desktop-Tab ist ebenfalls im DOM, aber
		// display:none — nutzt anderen Handler ohne Toast).
		const mobileTabbar = page.getByTestId('tn-mobile-tabbar');
		const etappenTab = mobileTabbar.getByRole('tab', { name: /Etappen/ });
		const box = await etappenTab.boundingBox();
		expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);

		await etappenTab.click({ force: true });
		// Toast-Wrapper hat position:absolute Kind → zero-height → toBeVisible auf
		// dem inneren role="status" prüfen (beweist Toast tatsächlich gerendert).
		await expect(page.getByTestId('tn-lock-toast').getByRole('status')).toBeVisible();
		// Route-Tab bleibt aktiv (Route-Eingabe weiterhin sichtbar).
		await expect(page.getByTestId('trip-new-name-input')).toBeVisible();
	});

	// AC-3: Route-Tab gestapelt, kein H-Overflow, Floating-CTA führt weiter.
	test('AC-3: Route-Tab gestapelt ohne H-Overflow, Floating-CTA aktiviert sich', async ({ page }) => {
		await page.setViewportSize(MOBILE);
		await page.goto('/trips/new');

		// Kein horizontaler Overflow.
		const overflow = await page.evaluate(
			() => document.scrollingElement!.scrollWidth - window.innerWidth
		);
		expect(overflow).toBeLessThanOrEqual(1);

		const cta = page.getByTestId('tn-mobile-route-cta');
		await expect(cta).toBeVisible();

		await fillRoute(page);
		await cta.click();
		// Etappen-Tab nun aktiv → mobile Etappen-Karte sichtbar.
		await expect(page.getByTestId('tn-mobile-stage-card').first()).toBeVisible();
	});

	// AC-4: Etappen als vertikale Karten, Name-Edit per Sheet schreibt zurück.
	test('AC-4: Etappen-Karten + Sheet-Namenseingabe schreibt Namen zurück', async ({ page }) => {
		await page.setViewportSize(MOBILE);
		await page.goto('/trips/new');
		await fillRoute(page);
		await page.getByTestId('tn-mobile-route-cta').click();

		const card = page.getByTestId('tn-mobile-stage-card').first();
		await expect(card).toBeVisible();

		await card.getByTestId('tn-mobile-stage-name').click();
		const sheet = page.getByTestId('tn-mobile-stage-sheet');
		await expect(sheet.getByTestId('tn-mobile-stage-sheet-input')).toBeVisible();

		await sheet.getByTestId('tn-mobile-stage-sheet-input').fill('Hütte A → Hütte B');
		await sheet.getByTestId('tn-mobile-stage-sheet-apply').click();

		await expect(card).toContainText('Hütte A → Hütte B');
	});

	// AC-6: Mobile rendert die mobile TabBar-Variante ohne H-Overflow.
	// (Per-Tab-Overflow für Wetter/Zeitplan/Alerts + Wetter-FAB benötigen den
	//  GPX-Upload-Flow → vollständig im staging-validator. Hier: mobile Struktur.)
	test('AC-6: Mobile TabBar-Variante gerendert, kein H-Overflow', async ({ page }) => {
		await page.setViewportSize(MOBILE);
		await page.goto('/trips/new');

		const overflow = await page.evaluate(
			() => document.scrollingElement!.scrollWidth - window.innerWidth
		);
		expect(overflow).toBeLessThanOrEqual(1);
		// Mobile-spezifischer Container (existiert erst nach Implementierung).
		await expect(page.getByTestId('tn-mobile-tabbar')).toBeVisible();
	});

	// AC-8: Desktop-Regression — Breadcrumb sichtbar, Mobile-App-Leiste verborgen.
	test('AC-8: Desktop (≥900px) unverändert, kein Mobile-Element', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await page.goto('/trips/new');

		await expect(page.getByTestId('tn-desktop-breadcrumb')).toBeVisible();
		await expect(page.getByTestId('tn-mobile-appbar')).toBeHidden();
	});
});

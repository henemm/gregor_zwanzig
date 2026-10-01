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
import * as path from 'node:path';
import { E2E_TEST_PREFIX } from './helpers';

const MOBILE = { width: 375, height: 667 };
const DESKTOP = { width: 1280, height: 900 };

// Auth läuft über storageState (Projekt-Setup), nicht per Test-Login — vermeidet
// Auth-Rate-Limits bei parallelen Workern (Memory-Muster #586/#609).

// Pflicht-Eingaben Route-Tab, um Etappen freizuschalten.
async function fillRoute(page: Page, name = 'Mobile Test-Trip', date = '2026-07-01') {
	await page.getByTestId('trip-new-name-input-mobile').fill(name);
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

		// "Etappen" ist ohne Trip-Name/Datum gesperrt.
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
		await expect(page.getByTestId('trip-new-name-input-mobile')).toBeVisible();
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

	// ── Issue #2277 S2b (docs/specs/modules/fix_2277_s2b_mobile_rahmen_angleichung.md) ──
	// Zurück (PageHeader) und Speichern (EditorStickyFooter) je Viewport-Zweig.
	// Der Autosave in beforeNavigate greift nur bei `ready` (Zeitplan-Reiter
	// besucht) — ohne diesen Zustand wären die Zurück-Fälle auch bei der Mutation
	// „<a href> statt onclick" grün. Gespeichert wird per POST /api/trips (nicht
	// PUT …/__new__, wie die Spec vermutet), daher wird JEDER schreibende
	// Request auf /api/trips abgefangen.
	const ZWEIGE = [
		{
			name: 'mobil',
			viewport: MOBILE,
			zweig: '.tn-mobile',
			kopf: 'tn-mobile-appbar',
			speichern: 'tn-mobile-save',
			nameInput: (page: Page) => page.getByTestId('trip-new-name-input-mobile'),
			datumInput: (page: Page) => page.getByTestId('trip-new-date-input'),
		},
		{
			name: 'desktop',
			viewport: DESKTOP,
			zweig: '.tn-desktop',
			kopf: 'tn-desktop-breadcrumb',
			speichern: 'trip-new-save-btn',
			nameInput: (page: Page) => page.getByTestId('trip-new-name-input-desktop'),
			datumInput: (page: Page) => page.locator('.tn-desktop input[type="date"]'),
		},
	] as const;

	async function bisSpeicherbereit(page: Page, z: (typeof ZWEIGE)[number], name: string) {
		await page.setViewportSize(z.viewport);
		await page.goto('/trips/new');
		await z.nameInput(page).fill(name);
		await z.datumInput(page).fill(new Date().toISOString().slice(0, 10));

		// getByRole blendet den unsichtbaren Zweig aus — es trifft die sichtbare Tab-Leiste.
		await page.getByRole('tab', { name: /Etappen/ }).click({ force: true });
		const gpx = path.resolve('./e2e/fixtures/test-trip.gpx');
		const gpxInputs = page.locator(`${z.zweig} input[type="file"][accept=".gpx"]`);
		const stageCount = await gpxInputs.count();
		for (let i = 0; i < stageCount; i++) {
			await Promise.all([
				page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 }).catch(() => null),
				gpxInputs.first().setInputFiles(gpx),
			]);
			await page.waitForTimeout(600);
		}
		// Issue #2277 S3: Kette Wetter-Metriken → Wertebereiche → Alarme → Versand;
		// „Speichern" wird erst nach dem Besuch von Versand aktiv.
		for (const reiter of ['Wetter-Metriken', 'Wertebereiche', 'Alarme', 'Versand']) {
			await page.getByRole('tab', { name: new RegExp(reiter) }).click({ force: true });
		}
		// Positivkontrolle: `ready` ist erreicht — sonst gäbe es gar keinen Autosave zu vermeiden.
		await expect(page.getByTestId(z.speichern)).toBeEnabled();
	}

	function schreibendeTripRequests(page: Page): string[] {
		const schreibend: string[] = [];
		page.on('request', (req) => {
			const url = new URL(req.url());
			if (['POST', 'PUT', 'PATCH'].includes(req.method()) && url.pathname.startsWith('/api/trips')) {
				schreibend.push(`${req.method()} ${url.pathname}`);
			}
		});
		return schreibend;
	}

	for (const z of ZWEIGE) {
		test(`S2b AC-5 (${z.name}): Zurück navigiert zu /trips ohne Autosave-Request`, async ({ page }) => {
			await bisSpeicherbereit(page, z, `S2b Zurück ohne Autosave ${z.name}`);
			const schreibend = schreibendeTripRequests(page);

			const zurueck = page.getByTestId(z.kopf).getByTestId('back-link');
			await expect(zurueck).toBeVisible();
			expect(await zurueck.evaluate((el) => el.tagName)).toBe('BUTTON');
			await zurueck.click();

			await expect(page).toHaveURL(/\/trips$/);
			expect(schreibend, `Autosave beim bewussten Zurück ausgelöst: ${schreibend.join(', ')}`).toEqual([]);
		});

		test(`S2b AC-4 (${z.name}): Speichern im Footer legt den Trip an und öffnet ihn`, async ({ page }) => {
			await bisSpeicherbereit(page, z, `${E2E_TEST_PREFIX}S2b Speichern ${z.name}`);
			const schreibend = schreibendeTripRequests(page);

			const speichern = page.getByTestId(z.speichern);
			await expect(speichern).toBeVisible();
			const [antwort] = await Promise.all([
				page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/trips'),
				speichern.click(),
			]);
			expect(antwort.ok(), `POST /api/trips scheiterte: ${antwort.status()}`).toBe(true);

			// Wächter gegen „Speichern ruft onCancel": das führte ohne POST nach /trips.
			const id = ((await antwort.json()) as { id?: string }).id;
			expect(id, 'POST /api/trips lieferte keine id').toBeTruthy();
			await expect(page).toHaveURL(new RegExp(`/trips/${id}$`));
			expect(schreibend).toContain('POST /api/trips');
		});
	}

	// Der Speichern-Footer klebt am Viewport-Unterrand — ungescrollt UND gescrollt.
	// Scroll-Container ist das <main> des App-Layouts; auf Anlege-Seiten reserviert
	// es unten keinen BottomNav-Platz (nur Safe-Area = 0 im Test-Browser).
	test('S2b AC-4 (mobil): Speichern-Footer sitzt ungescrollt und gescrollt am Viewport-Unterrand', async ({ page }) => {
		await page.setViewportSize(MOBILE);
		await page.goto('/trips/new');
		const footer = page.getByTestId('tn-mobile-footer');
		await expect(footer).toBeVisible();

		const unterkante = async () => (await footer.boundingBox())!.y + (await footer.boundingBox())!.height;
		expect(Math.abs((await unterkante()) - MOBILE.height), 'ungescrollt').toBeLessThanOrEqual(1);

		const scrollTop = await page.evaluate(() => {
			const el = document.querySelector('main.mobile-scroll-pad') as HTMLElement;
			el.scrollTop = 120;
			return el.scrollTop;
		});
		expect(scrollTop, 'Messaufbau: der Layout-Scroller hat sich nicht bewegt').toBeGreaterThan(0);
		expect(Math.abs((await unterkante()) - MOBILE.height), `gescrollt (scrollTop ${scrollTop})`).toBeLessThanOrEqual(1);
	});

	// Die Karte rechnet ihre Hoehe gegen den unten belegten Platz — auf /trips/new
	// ist das der Speichern-Footer, nicht die BottomNav. Sonst verdeckt der Footer
	// die (lizenzrechtlich verpflichtende) Karten-Attribution.
	test('S2b AC-4 (mobil): Wegpunkte-Karte samt Attribution endet über dem Speichern-Footer', async ({ page }) => {
		await page.setViewportSize(MOBILE);
		await page.goto('/trips/new');
		await fillRoute(page, 'S2b Karte über Footer', new Date().toISOString().slice(0, 10));
		await page.getByRole('tab', { name: /Etappen/ }).click({ force: true });
		const gpxInputs = page.locator('.tn-mobile input[type="file"][accept=".gpx"]');
		const stageCount = await gpxInputs.count();
		for (let i = 0; i < stageCount; i++) {
			await Promise.all([
				page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 }).catch(() => null),
				gpxInputs.first().setInputFiles(path.resolve('./e2e/fixtures/test-trip.gpx')),
			]);
			await page.waitForTimeout(600);
		}
		await page.getByRole('tab', { name: /Wegpunkte/ }).click({ force: true });

		const karte = page.locator('.tn-mobile [data-testid="mobile-editor"]');
		const attribution = karte.locator('.leaflet-control-attribution');
		const footer = page.getByTestId('tn-mobile-footer');
		await expect(karte).toBeVisible();
		await expect(attribution).toBeVisible();

		const footerOben = (await footer.boundingBox())!.y;
		const k = (await karte.boundingBox())!;
		const a = (await attribution.boundingBox())!;
		expect(k.y + k.height, 'Karten-Unterkante liegt unter der Footer-Oberkante').toBeLessThanOrEqual(footerOben + 0.5);
		expect(a.y + a.height, 'Attribution vom Footer verdeckt').toBeLessThanOrEqual(footerOben + 0.5);
	});

	test('S2b AC-4 (desktop): Speichern-Footer sitzt am unteren Rand des Scrollbereichs', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await page.goto('/trips/new');
		const footer = page.getByTestId('tn-desktop-footer');
		await expect(footer).toBeVisible();
		const box = (await footer.boundingBox())!;
		const scrollerUnten = await page.evaluate(() => {
			const el = document.querySelector('main.mobile-scroll-pad') as HTMLElement;
			return el.getBoundingClientRect().bottom - parseFloat(getComputedStyle(el).paddingBottom);
		});
		expect(Math.abs(box.y + box.height - scrollerUnten)).toBeLessThanOrEqual(1);
	});
});

// Regressionstest — Mobile Etappen-Editor: Steuerelemente müssen im Viewport bleiben.
//
// Bug (#963): `.mobile-map-wrap` setzt `height: calc(100dvh - 56px)` und nimmt an,
// direkt unter der 56px-TopAppBar zu sitzen. Tatsächlich liegt davor variabel hoher
// Chrome-Content (Breadcrumb, TripHeader, Tab-Leiste, EtappenStrip, Etappen-Header,
// optional Cascade-Strip). Die absolut positionierten Steuerelemente
// (`stage-switcher-pill`, `add-waypoint`) erben den fehlerhaften Offset und landen
// unterhalb des sichtbaren Viewports.
//
// WICHTIG: Playwrights `.click()` scrollt automatisch in den sichtbaren Bereich —
// das würde den Bug verschleiern. Daher wird die Bounding-Box IMMER VOR jedem Klick
// explizit gegen die Viewport-Grenzen geprüft (TopAppBar 56px, BottomNav 64px, siehe
// app.css:190-205). Kein `scrollIntoViewIfNeeded` vor der Prüfung.
//
// Ausführen: cd frontend && npx playwright test e2e/mobile-editor-controls-viewport.spec.ts

import { test, expect, type Page, type Locator } from '@playwright/test';

const MOBILE = { width: 390, height: 844 };
const TOP_APP_BAR = 56; // fixe TopAppBar-Höhe (app.css .mobile-scroll-pad padding-top)
const BOTTOM_NAV = 64; // fixe BottomNav-Höhe (app.css .mobile-scroll-pad padding-bottom)

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

const LONG_STAGE_NAME =
	'Refuge de Tighjettu → Auberge U Vallone über Bocca di Stagnu und Brèche de Capitellu (Wetterscheiden-Kammlinie mit Exponierung nach Nordwest)';

function makeSeed(id: string, name: string, firstStageName: string) {
	return {
		id,
		name,
		region: 'Korsika',
		stages: [
			{ id: 's1', name: firstStageName, date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] },
			{ id: 's2', name: 'Tag 2', date: '2026-08-02', waypoints: [wp('c', 42.1), wp('d', 42.14)] },
			{ id: 's3', name: 'Tag 3', date: '2026-08-03', waypoints: [wp('e', 42.2), wp('f', 42.24)] }
		],
		report_config: {
			enabled: true,
			morning_enabled: true,
			evening_enabled: true,
			morning_time: '07:00:00',
			evening_time: '18:00:00'
		}
	};
}

async function openMobileStagesEditor(page: Page, tripId: string) {
	await page.setViewportSize(MOBILE);
	await page.goto(`/trips/${tripId}?tab=stages`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expect(page.getByTestId('mobile-editor')).toBeVisible();
}

async function openMobileStagesEditorAtViewport(
	page: Page,
	tripId: string,
	viewport: { width: number; height: number }
) {
	await page.setViewportSize(viewport);
	await page.goto(`/trips/${tripId}?tab=stages`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expect(page.getByTestId('mobile-editor')).toBeVisible();
}

function control(page: Page, testid: string): Locator {
	return page.getByTestId('mobile-editor').getByTestId(testid);
}

/**
 * Prüft, dass die Bounding-Box eines Steuerelements vollständig innerhalb des
 * sichtbaren Viewports liegt (unterhalb TopAppBar, oberhalb BottomNav) — OHNE
 * vorheriges Auto-Scroll. Gibt die Box für Folge-Assertions zurück.
 */
async function expectWithinViewport(page: Page, testid: string, scope: 'editor' | 'page' = 'editor') {
	// #1375: der Kaskaden-Streifen liegt außerhalb von `.mobile-editor` — für ihn
	// wird seitenweit gesucht, sonst unverändert im Editor-Teilbaum.
	const el = scope === 'page' ? page.getByTestId(testid) : control(page, testid);
	await expect(el).toBeVisible();
	const box = await el.boundingBox();
	expect(box, `${testid}: keine boundingBox`).not.toBeNull();
	// Viewport-Höhe aus der Seite lesen statt der MOBILE-Konstante — die Fälle
	// unten laufen bewusst auch mit engerem Viewport (Staging-Chrome-Emulation).
	const viewportHeight = page.viewportSize()?.height ?? MOBILE.height;
	const top = box!.y;
	const bottom = box!.y + box!.height;
	expect(
		top,
		`${testid}: Oberkante y=${top.toFixed(0)}px liegt über der TopAppBar-Grenze (${TOP_APP_BAR}px)`
	).toBeGreaterThanOrEqual(TOP_APP_BAR);
	expect(
		bottom,
		`${testid}: Unterkante y=${bottom.toFixed(0)}px liegt unter der BottomNav-Grenze (${viewportHeight - BOTTOM_NAV}px, Viewport ${viewportHeight}px)`
	).toBeLessThanOrEqual(viewportHeight - BOTTOM_NAV);
	return box!;
}

/** Bestätigt, dass das Element am Mittelpunkt seiner Box tatsächlich das oberste
 * Element ist (also nicht verdeckt / offscreen) — echter Klickbarkeits-Nachweis. */
async function expectTopmostAt(
	page: Page,
	testid: string,
	box: { x: number; y: number; width: number; height: number }
) {
	const hit = await page.evaluate(
		([x, y, id]) => {
			const el = document.elementFromPoint(x as number, y as number);
			return !!el?.closest(`[data-testid="${id}"]`);
		},
		[box.x + box.width / 2, box.y + box.height / 2, testid] as const
	);
	expect(hit, `${testid}: am Klickpunkt nicht das oberste Element (verdeckt/offscreen)`).toBe(true);
}

test.describe('Mobile-Editor — Steuerelemente im Viewport (#963)', () => {
	const trips: string[] = [];
	async function seed(page: Page, id: string, name: string, firstStageName: string) {
		trips.push(id);
		await page.request.delete(`/api/trips/${id}`).catch(() => {});
		const res = await page.request.post('/api/trips', { data: makeSeed(id, name, firstStageName) });
		expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
	}
	test.afterEach(async ({ page }) => {
		for (const id of trips.splice(0)) {
			await page.request.delete(`/api/trips/${id}`).catch(() => {});
		}
	});

	test('AC-1: Etappenwechsel-Pille liegt im Viewport und ist klickbar', async ({ page }) => {
		const id = 'e2e-963-pill';
		await seed(page, id, 'E2E #963 Pill', 'Tag 1');
		await openMobileStagesEditor(page, id);

		const box = await expectWithinViewport(page, 'stage-switcher-pill');
		await expectTopmostAt(page, 'stage-switcher-pill', box);

		// Funktionsnachweis: Klick öffnet das Etappen-Auswahl-Sheet.
		await control(page, 'stage-switcher-pill').click();
		await expect(page.locator('div[role="presentation"]')).toBeVisible();
	});

	test('AC-2: Wegpunkt-Hinzufügen-Button liegt im Viewport und ist klickbar', async ({ page }) => {
		const id = 'e2e-963-add';
		await seed(page, id, 'E2E #963 Add', 'Tag 1');
		await openMobileStagesEditor(page, id);

		const box = await expectWithinViewport(page, 'add-waypoint');
		await expectTopmostAt(page, 'add-waypoint', box);

		// Klick darf ohne Auto-Scroll-Fehler ausführbar sein.
		await control(page, 'add-waypoint').click();
	});

	test('AC-3: langer Etappenname (mehr Chrome-Höhe) — beide Steuerelemente im Viewport', async ({
		page
	}) => {
		const id = 'e2e-963-long';
		await seed(page, id, 'E2E #963 Long', LONG_STAGE_NAME);
		await openMobileStagesEditor(page, id);

		await expectWithinViewport(page, 'stage-switcher-pill');
		await expectWithinViewport(page, 'add-waypoint');
	});

	// #1375 (Fix 2026-07-25): Dieser Fall prüfte früher NUR `toBeVisible()` direkt
	// nach einem `.fill()` — und war deshalb falsch-grün: Playwright scrollt beim
	// `.fill()` automatisch zum Datumsfeld, `toBeVisible()` sagt nichts über die
	// Lage im Bildschirmausschnitt aus. Real lag der Rückfrage-Streifen bei
	// y≈1102px auf einem 844px hohen Viewport — der Nutzer sah ihn nie. Jetzt wird
	// die echte Bounding-Box gemessen (`expectWithinViewport`), und zwar in BEIDEN
	// Zuständen: direkt nach der Datumsänderung UND nach dem Zurückscrollen zur
	// Karte. Ein erneutes Verstecken des Streifens unter der Karte lässt den Test
	// wieder rot werden.
	test('AC-4: Kaskaden-Rückfrage liegt im Viewport — mitsamt beider Steuerelemente', async ({ page }) => {
		const id = 'e2e-963-cascade';
		await seed(page, id, 'E2E #963 Cascade', 'Tag 1');
		await openMobileStagesEditor(page, id);

		// Cascade-Strip erzwingen: Tourstart-Datum der ersten Etappe verschieben.
		// handleDateChange(Δ≠0, Etappen mit Datum dahinter) setzt `cascade` → Strip erscheint.
		const headerDate = page.locator('[data-testid="stage-date-field"] input[type="date"]').first();
		await headerDate.fill('2026-08-05');
		await headerDate.press('Tab'); // löst echten blur/change aus (zuverlässiger als dispatchEvent)
		await expect(page.getByTestId('cascade-strip')).toBeVisible();

		// Zustand 1 — unmittelbar nach der Änderung (Scroll steht dort, wohin das
		// `.fill()` gescrollt hat): der Nutzer muss die Rückfrage JETZT sehen,
		// ohne selbst zu scrollen. Kein `scrollTo` vor dieser Messung.
		const promptBox = await expectWithinViewport(page, 'cascade-strip', 'page');
		await expectTopmostAt(page, 'cascade-strip', promptBox);
		await expect(page.getByRole('button', { name: /Lückenlos anschließen/ })).toBeVisible();
		await expect(page.getByRole('button', { name: /Nur diese Etappe/ })).toBeVisible();

		// Zustand 2 — Nutzer betrachtet die Karte (Scroll oben, wie beim Öffnen des
		// Tabs): Rückfrage bleibt sichtbar UND verdeckt die #963-Steuerelemente nicht.
		await page.evaluate(() => document.querySelector('main')?.scrollTo(0, 0));
		const topBox = await expectWithinViewport(page, 'cascade-strip', 'page');
		await expectTopmostAt(page, 'cascade-strip', topBox);
		const pillBox = await expectWithinViewport(page, 'stage-switcher-pill');
		await expectTopmostAt(page, 'stage-switcher-pill', pillBox);
		const addBox = await expectWithinViewport(page, 'add-waypoint');
		await expectTopmostAt(page, 'add-waypoint', addBox);
	});

	// #1375 Fix-Loop 1 (Staging-Befund 2026-07-25) — „im Ausschnitt" ist NICHT
	// „klickbar". `expectWithinViewport` misst nur die Bounding-Box; auf Staging
	// überlappte der fixierte Kaskaden-Banner (y=670.6–772.0) die Steuerelemente
	// (stage-switcher-pill y=656.8–690.3, add-waypoint y=656.8–701.1) — beide
	// formal im Viewport, per echtem `click()` aber blockiert („subtree intercepts
	// pointer events"). Ursache: Staging hat mehr Chrome über der Karte, die Karte
	// beginnt dort erst bei y≈645 statt lokal y≈553. Der zweite Viewport unten
	// emuliert diese Enge lokal (gleiche Rest-Höhe zwischen Kartenoberkante und
	// BottomNav) — ohne ihn wäre der Regress lokal unsichtbar geblieben.
	// Geprüft wird per echtem Playwright-`click()` (volle Actionability inkl.
	// Hit-Target), NICHT per Bounding-Box, und in BEIDE Richtungen: Kartensteuerung
	// UND die beiden Schaltflächen der Rückfrage selbst.
	for (const vp of [
		{
			// Trifft die Staging-Geometrie: der längere Tourname schiebt den
			// Kartenblock auf y≈644.8 — gemessen auf Staging: 644.8, add-waypoint
			// dort 656.8–701.1, hier 656.8–700.8. Das alte, starr unten verankerte
			// Banner-Band lag bei 670.6–772.0 und schnitt beide Steuerelemente.
			label: 'Staging-Geometrie 390×844 (Kartenblock bei y≈645)',
			size: { width: 390, height: 844 },
			tripName: 'E2E GR20 Nordabschnitt Etappenplan'
		},
		{
			// Zweiter, unabhängiger Weg in dieselbe Kollision: kurzer Viewport zieht
			// das untere Banner-Band nach oben statt die Karte nach unten.
			label: 'kurzer Viewport 390×700',
			size: { width: 390, height: 700 },
			tripName: 'E2E Kurz'
		}
	]) {
		test(`AC-2-Klick (${vp.label}): Kartensteuerung und Kaskaden-Rückfrage sind gleichzeitig klickbar`, async ({
			page
		}) => {
			const id = `e2e-1375-click-${vp.size.height}`;
			await seed(page, id, vp.tripName, 'Tag 1');
			await openMobileStagesEditorAtViewport(page, id, vp.size);

			// Vorbedingung OHNE Rückfrage: in dieser Geometrie sind beide
			// Steuerelemente klickbar. Schlägt schon das fehl, prüft der Fall die
			// dokumentierte #963-Grenze (Karte zu flach, Sheet überlappt) statt der
			// Banner-Verdeckung — dann ist das Szenario untauglich, nicht der Fix.
			await expectTopmostAt(
				page,
				'stage-switcher-pill',
				await expectWithinViewport(page, 'stage-switcher-pill')
			);
			await expectTopmostAt(page, 'add-waypoint', await expectWithinViewport(page, 'add-waypoint'));

			const headerDate = page.locator('[data-testid="stage-date-field"] input[type="date"]').first();
			await headerDate.fill('2026-08-05');
			await headerDate.press('Tab');
			await expect(page.getByTestId('cascade-strip')).toBeVisible();

			// Nutzer schaut auf die Karte (Scroll oben) — genau der Staging-Zustand.
			await page.evaluate(() => document.querySelector('main')?.scrollTo(0, 0));

			// Geometrie protokollieren, damit der Befund im Artefakt nachvollziehbar ist.
			const geo: Record<string, string> = {};
			for (const [key, loc] of [
				['cascade-strip', page.getByTestId('cascade-strip')],
				['stage-switcher-pill', control(page, 'stage-switcher-pill')],
				['add-waypoint', control(page, 'add-waypoint')],
				['mobile-editor', page.getByTestId('mobile-editor')]
			] as const) {
				const b = await loc.boundingBox();
				geo[key] = b ? `y=${b.y.toFixed(1)}–${(b.y + b.height).toFixed(1)}` : 'keine Box';
			}
			console.log(`GEOMETRIE ${vp.label}:`, JSON.stringify(geo));

			// Vorbedingung: dieser Fall ist nur aussagekräftig, solange beide
			// Steuerelemente überhaupt im Ausschnitt liegen — sonst prüfte er die
			// dokumentierte #963-Grenze (Karte zu flach) statt der Banner-Verdeckung.
			const pillBox = await expectWithinViewport(page, 'stage-switcher-pill');
			const addBox = await expectWithinViewport(page, 'add-waypoint');

			// 1a) Verdeckung scroll-immun prüfen: am Mittelpunkt beider Steuerelemente
			//     muss das Steuerelement selbst das oberste sein. Playwrights `click()`
			//     scrollt vor dem Hit-Test automatisch und kann eine Verdeckung dadurch
			//     zufällig auflösen — diese Messung kann das nicht.
			await expectTopmostAt(page, 'stage-switcher-pill', pillBox);
			await expectTopmostAt(page, 'add-waypoint', addBox);

			// 1b) Kartensteuerung: echte Klicks, kein force, kurzer Timeout — damit die
			//     Fehlermeldung die Verdeckung benennt statt ins Test-Timeout zu laufen.
			await control(page, 'add-waypoint').click({ timeout: 5000 });
			await control(page, 'stage-switcher-pill').click({ timeout: 5000 });
			const overlay = page.locator('div[role="presentation"]');
			await expect(overlay).toBeVisible();
			await overlay.click({ position: { x: 5, y: 5 } });
			await expect(overlay).toHaveCount(0);

			// 2) Gegenrichtung: die Rückfrage selbst muss bedienbar bleiben.
			await expect(page.getByRole('button', { name: /Lückenlos anschließen/ })).toBeVisible();
			await page.getByRole('button', { name: /Nur diese Etappe/ }).click({ timeout: 5000 });
			await expect(page.getByTestId('cascade-strip')).toHaveCount(0);
		});
	}

	// Fix-Loop 2 (Adversary-Findings F001/F002) — Mindesthöhen-Schutz.
	//
	// Geometrische Realität: In diesen beiden Extremfällen übersteigt der fixe,
	// von diesem Fix unberührte Chrome-Block ÜBER `.mobile-editor` (Breadcrumb +
	// TripHeader + Tab-Leiste + Aktivitäts-Select, ~458-526px, siehe
	// docs/context/fix-963-mobile-editor-controls.md) die komplette Viewport-Höhe.
	// Das macht "Pille ohne jedes Scrollen sichtbar" geometrisch unerreichbar, ohne
	// diesen Chrome-Block selbst umzubauen (out of scope, siehe Spec §Known
	// Limitations). Der hier geprüfte, ohne diesen Umbau erreichbare Fix-Umfang:
	// Karte + Steuerelemente kollabieren NICHT mehr auf 0px (F001) und überlappen
	// NICHT mehr mit der Sheet-Griffleiste (F002) — nach Scrollen zur Karte sind
	// beide Steuerelemente vollständig sichtbar UND klickbar (keine Nullgröße,
	// keine gegenseitige Verdeckung).
	test('F001-Regression: schmales Querformat (844×390) — Karte kollabiert nicht, Steuerelemente bleiben real und klickbar', async ({
		page
	}) => {
		const id = 'e2e-963-landscape';
		await seed(page, id, 'E2E #963 Landscape', 'Tag 1');
		const viewport = { width: 844, height: 390 };
		await openMobileStagesEditorAtViewport(page, id, viewport);

		const editorBox = await page.getByTestId('mobile-editor').boundingBox();
		expect(editorBox, 'mobile-editor: keine boundingBox').not.toBeNull();
		// F001 (vor Fix): height kollabierte auf 0px. Jetzt greift der Mindesthöhen-
		// Clamp (MOBILE_EDITOR_MIN_HEIGHT_PX in EditStagesPanelNew.svelte — 200px seit
		// Fix-Loop 3/F004: kleinstmöglicher Wert, der Pille/add-waypoint weiterhin vor
		// Überlappung mit der Sheet-Griffleiste schützt, aber im Standardfall
		// 390×844 NICHT mehr in die reservierte BottomNav-Zone hineinragt).
		expect(editorBox!.height, `mobile-editor: nur ${editorBox!.height}px hoch (F001-Kollaps)`).toBeGreaterThanOrEqual(
			150
		);

		// Zur Karte scrollen (unvermeidlich bei dieser Seitenverhältnis-Extreme,
		// s. Kommentar oben) und danach Sichtbarkeit + Klickbarkeit nachweisen.
		await control(page, 'stage-switcher-pill').scrollIntoViewIfNeeded();
		const pillBox = await control(page, 'stage-switcher-pill').boundingBox();
		expect(pillBox, 'stage-switcher-pill: keine boundingBox').not.toBeNull();
		expect(pillBox!.height, 'stage-switcher-pill: Nullgröße statt realer Höhe').toBeGreaterThan(20);
		await expectTopmostAt(page, 'stage-switcher-pill', pillBox!);
		await control(page, 'stage-switcher-pill').click();
		const overlay = page.locator('div[role="presentation"]');
		await expect(overlay).toBeVisible();
		await overlay.click({ position: { x: 5, y: 5 } }); // Overlay-Klick schließt das Sheet (StageSelectSheet onClose)
		await expect(overlay).toHaveCount(0);

		const addBox = await control(page, 'add-waypoint').boundingBox();
		expect(addBox, 'add-waypoint: keine boundingBox').not.toBeNull();
		expect(addBox!.height, 'add-waypoint: Nullgröße statt realer Höhe').toBeGreaterThan(20);
		await expectTopmostAt(page, 'add-waypoint', addBox!);
	});

	test('F002-Regression: kurzer Portrait-Viewport (320×568, iPhone SE) — Pille/MapControl überlappen nicht mit der Sheet-Griffleiste', async ({
		page
	}) => {
		const id = 'e2e-963-shortportrait';
		await seed(page, id, 'E2E #963 ShortPortrait', 'Tag 1');
		const viewport = { width: 320, height: 568 };
		await openMobileStagesEditorAtViewport(page, id, viewport);

		const editorBox = await page.getByTestId('mobile-editor').boundingBox();
		expect(editorBox, 'mobile-editor: keine boundingBox').not.toBeNull();
		// F002 (vor Fix): height schrumpfte auf ~41.5px, Pille/Griffleiste überlappten.
		expect(editorBox!.height, `mobile-editor: nur ${editorBox!.height}px hoch (F002-Schrumpf)`).toBeGreaterThanOrEqual(
			150
		);

		await control(page, 'stage-switcher-pill').scrollIntoViewIfNeeded();
		const pillBox = await control(page, 'stage-switcher-pill').boundingBox();
		const addBox = await control(page, 'add-waypoint').boundingBox();
		const handleBox = await page.getByTestId('sheet-handle').boundingBox();
		expect(pillBox, 'stage-switcher-pill: keine boundingBox').not.toBeNull();
		expect(addBox, 'add-waypoint: keine boundingBox').not.toBeNull();
		expect(handleBox, 'sheet-handle: keine boundingBox').not.toBeNull();

		// Kein vertikaler Überlapp zwischen Pille/Add-Waypoint (oben, top:12px) und
		// der Sheet-Griffleiste (Default-Snap 'half', am oberen Rand des Sheets).
		expect(
			pillBox!.y + pillBox!.height,
			`Pille (bottom=${pillBox!.y + pillBox!.height}) überlappt Sheet-Griffleiste (top=${handleBox!.y})`
		).toBeLessThanOrEqual(handleBox!.y);
		expect(
			addBox!.y + addBox!.height,
			`add-waypoint (bottom=${addBox!.y + addBox!.height}) überlappt Sheet-Griffleiste (top=${handleBox!.y})`
		).toBeLessThanOrEqual(handleBox!.y);

		// Echter Klickbarkeits-Nachweis (F002 war explizit: "echter Klick schlägt fehl").
		await expectTopmostAt(page, 'stage-switcher-pill', pillBox!);
		await control(page, 'stage-switcher-pill').click();
		await expect(page.locator('div[role="presentation"]')).toBeVisible();
	});

	// Fix-Loop 3 (Adversary-Fund F004, CRITICAL) — echte Kernnavigations-Regression:
	// im STANDARD-Fall (390×844, kein Rand-Fall, scrollY=0) reichte `.mobile-editor`
	// bis in die fixe BottomNav-Zone hinein (Sheet z-index:61 > BottomNav z-index:50),
	// wodurch ein Klick auf die untere Navigationsleiste fehlschlug. Root-Cause-Fix:
	// Höhenformel reserviert jetzt explizit die BottomNav-Höhe (siehe
	// BOTTOM_NAV_HEIGHT_PX in EditStagesPanelNew.svelte).
	test('F004-Regression: BottomNav bleibt bei Standard-Viewport (390×844, scrollY=0) klickbar', async ({
		page
	}) => {
		const id = 'e2e-963-bottomnav';
		await seed(page, id, 'E2E #963 BottomNav', 'Tag 1');
		await openMobileStagesEditor(page, id);

		// Ausdrücklich KEIN Scrollen — genau die vom Adversary reproduzierte Situation
		// (Tab gerade erst geöffnet).
		const scrollY = await page.evaluate(() => document.querySelector('main')?.scrollTop ?? 0);
		expect(scrollY, 'Test setzt scrollY=0 voraus').toBe(0);

		const editorBox = await page.getByTestId('mobile-editor').boundingBox();
		const bottomNavBox = await page.getByTestId('bottom-nav').boundingBox();
		expect(editorBox, 'mobile-editor: keine boundingBox').not.toBeNull();
		expect(bottomNavBox, 'bottom-nav: keine boundingBox').not.toBeNull();
		expect(
			editorBox!.y + editorBox!.height,
			`mobile-editor (bottom=${editorBox!.y + editorBox!.height}) ragt in die BottomNav-Zone (top=${bottomNavBox!.y}) hinein`
		).toBeLessThanOrEqual(bottomNavBox!.y);

		// Echter Klick (kein force:true) — muss ohne "subtree intercepts pointer events" gelingen.
		await page.getByTestId('bottom-nav-item-home').click({ timeout: 5000 });
		await expect(page).toHaveURL('/');
	});
});

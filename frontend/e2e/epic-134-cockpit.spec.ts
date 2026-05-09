import { test, expect } from '@playwright/test';

/**
 * TDD RED Tests — Epic #134 Startseite: Trip-Cockpit
 * Issues #147–#152
 *
 * Diese Tests MÜSSEN vor der Implementierung ROT sein:
 * - [data-testid="cockpit-topbar"] existiert noch nicht in +page.svelte
 * - [data-testid="active-trip-card"] existiert noch nicht (_cockpit/ActiveTripCard.svelte fehlt)
 * - [data-testid="stage-strip"] existiert noch nicht (_cockpit/StageStrip.svelte fehlt)
 * - [data-testid="briefings-timeline"] existiert noch nicht
 * - [data-testid="alert-feed"] existiert noch nicht
 * - [data-testid="bottom-row"] existiert noch nicht
 * - Alte Selektoren (trip-card, subscription-card, "Meine Trips") müssen verschwinden
 *
 * Auth: storageState aus global.setup (playwright/.auth/admin.json)
 * Base URL: http://localhost:4173
 */

test.describe('Epic #134 — Startseite: Trip-Cockpit', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/');
	});

	// =========================================================================
	// Issue #147 — Topbar
	// =========================================================================
	test.describe('Issue #147 — Topbar', () => {
		test('Topbar: [data-testid="cockpit-topbar"] ist sichtbar', async ({ page }) => {
			/**
			 * GIVEN: User ist eingeloggt, Startseite geladen
			 * WHEN: DOM inspiziert
			 * THEN: Topbar-Container mit data-testid="cockpit-topbar" ist sichtbar
			 * RED: +page.svelte hat kein cockpit-topbar-Element
			 */
			await expect(page.getByTestId('cockpit-topbar')).toBeVisible();
		});

		test('Topbar: Heutiges Datum im deutschen Format (DD. Month YYYY)', async ({ page }) => {
			/**
			 * GIVEN: Heute ist 2026-05-09
			 * WHEN: Topbar gerendert
			 * THEN: Text enthält z.B. "9. Mai 2026"
			 * RED: Cockpit existiert noch nicht
			 */
			const topbar = page.getByTestId('cockpit-topbar');
			await expect(topbar).toBeVisible();
			// Deutsches Datumsformat: Tag. Monatsname Jahr
			await expect(topbar).toContainText(/\d{1,2}\.\s+\w+\s+\d{4}/);
		});

		test('Topbar: [data-testid="cta-test-briefing"] Button ist sichtbar', async ({ page }) => {
			/**
			 * GIVEN: Startseite geladen
			 * WHEN: Topbar gerendert
			 * THEN: Test-Briefing-Button vorhanden und sichtbar
			 * RED: Cockpit-Topbar existiert noch nicht
			 */
			await expect(page.getByTestId('cta-test-briefing')).toBeVisible();
		});

		test('Topbar: [data-testid="cta-new-trip"] verlinkt auf /trips/new', async ({ page }) => {
			/**
			 * GIVEN: Startseite geladen
			 * WHEN: Topbar gerendert
			 * THEN: "Neuer Trip"-Link zeigt auf /trips/new
			 * RED: Cockpit-Topbar existiert noch nicht
			 */
			const link = page.getByTestId('cta-new-trip');
			await expect(link).toBeVisible();
			await expect(link).toHaveAttribute('href', '/trips/new');
		});
	});

	// =========================================================================
	// Issue #148 — Hero: Aktiver Trip
	// =========================================================================
	test.describe('Issue #148 — Hero: Aktiver Trip', () => {
		test('Hero: [data-testid="active-trip-card"] ist sichtbar wenn Trip heute aktiv ist', async ({ page }) => {
			/**
			 * GIVEN: Test-User hat einen Trip dessen Etappe heute (2026-05-09) aktiv ist
			 * WHEN: Startseite geladen
			 * THEN: ActiveTripCard ist sichtbar
			 * RED: _cockpit/ActiveTripCard.svelte existiert noch nicht,
			 *       +page.svelte hat kein active-trip-card-Element
			 * NOTE: Dieser Test bleibt auch RED wenn kein Trip mit heutigem Datum vorhanden —
			 *       das ist gewollt (Phase GREEN braucht aktiven Trip in Testdaten)
			 */
			await expect(page.getByTestId('active-trip-card')).toBeVisible();
		});

		test('Hero: Status-Pill enthält "Live" oder "Tag X von Y"', async ({ page }) => {
			/**
			 * GIVEN: Aktiver Trip vorhanden
			 * WHEN: ActiveTripCard gerendert
			 * THEN: [data-testid="status-pill"] zeigt "Live · Tag X von Y" oder "Live"
			 * RED: Cockpit-Komponenten existieren noch nicht
			 */
			const activeCard = page.getByTestId('active-trip-card');
			await expect(activeCard).toBeVisible();
			const pill = activeCard.getByTestId('status-pill');
			await expect(pill).toBeVisible();
			await expect(pill).toContainText(/Live|Tag \d+ von \d+/);
		});

		test('Hero: ElevSparkline [data-slot="elev-sparkline"] ist in ActiveTripCard vorhanden', async ({ page }) => {
			/**
			 * GIVEN: Aktiver Trip mit Wegpunkt-Höhendaten vorhanden
			 * WHEN: ActiveTripCard gerendert
			 * THEN: ElevSparkline-SVG-Element ist im Card vorhanden
			 * RED: ActiveTripCard und ElevSparkline-Integration existieren nicht
			 */
			const activeCard = page.getByTestId('active-trip-card');
			await expect(activeCard).toBeVisible();
			const sparkline = activeCard.locator('[data-slot="elev-sparkline"]');
			await expect(sparkline).toBeVisible();
		});

		test('Hero: ActiveTripCard enthält NICHT "Kein aktiver Trip"', async ({ page }) => {
			/**
			 * GIVEN: Aktiver Trip vorhanden
			 * WHEN: ActiveTripCard gerendert
			 * THEN: Der Leerstand-Text erscheint nicht im aktiven Trip-Card
			 * RED: Cockpit existiert noch nicht
			 */
			const activeCard = page.getByTestId('active-trip-card');
			await expect(activeCard).toBeVisible();
			await expect(activeCard).not.toContainText('Kein aktiver Trip');
		});

		test('Hero (Leerstand): [data-testid="no-active-trip"] sichtbar wenn kein Trip heute aktiv ist', async ({ page }) => {
			/**
			 * GIVEN: Kein Trip hat eine Etappe mit heutigem Datum
			 * WHEN: Startseite geladen
			 * THEN: Leerstand-Element mit no-active-trip ist sichtbar
			 * RED: Cockpit existiert noch nicht — beide Zustände fehlen
			 * NOTE: Falls active-trip-card vorhanden ist, ist dieser Test eine logische Prüfung
			 *       (einer der beiden Zustände muss existieren)
			 */
			const hasActiveTrip = await page.getByTestId('active-trip-card').count() > 0;
			if (!hasActiveTrip) {
				await expect(page.getByTestId('no-active-trip')).toBeVisible();
			}
			// Wenn aktiver Trip vorhanden: Test ist trivial grün (korrekter Zustand),
			// aber das active-trip-card-Fehlen macht den anderen Test rot.
		});

		test('Hero (Leerstand): no-active-trip enthält Link zu /trips/new', async ({ page }) => {
			/**
			 * GIVEN: Kein aktiver Trip
			 * WHEN: Leerstand-GCard gerendert
			 * THEN: Link zu /trips/new vorhanden
			 * RED: Cockpit existiert noch nicht
			 */
			const hasActiveTrip = await page.getByTestId('active-trip-card').count() > 0;
			if (!hasActiveTrip) {
				const emptyState = page.getByTestId('no-active-trip');
				await expect(emptyState).toBeVisible();
				const newTripLink = emptyState.locator('a[href="/trips/new"]');
				await expect(newTripLink).toBeVisible();
			}
		});
	});

	// =========================================================================
	// Issue #149 — Stage-Strip
	// =========================================================================
	test.describe('Issue #149 — Stage-Strip', () => {
		test('Stage-Strip: [data-testid="stage-strip"] ist sichtbar', async ({ page }) => {
			/**
			 * GIVEN: Aktiver Trip vorhanden
			 * WHEN: Startseite geladen
			 * THEN: Stage-Strip-Container ist sichtbar
			 * RED: _cockpit/StageStrip.svelte existiert noch nicht
			 */
			await expect(page.getByTestId('stage-strip')).toBeVisible();
		});

		test('Stage-Strip: mindestens ein [data-testid="stage-pill"] ist vorhanden', async ({ page }) => {
			/**
			 * GIVEN: Aktiver Trip mit Etappen
			 * WHEN: StageStrip gerendert
			 * THEN: Mindestens eine StagePill ist vorhanden
			 * RED: _cockpit/StagePill.svelte + StageStrip.svelte existieren nicht
			 */
			const strip = page.getByTestId('stage-strip');
			await expect(strip).toBeVisible();
			const pills = strip.getByTestId('stage-pill');
			await expect(pills.first()).toBeVisible();
		});
	});

	// =========================================================================
	// Issue #150 — Briefings-Timeline
	// =========================================================================
	test.describe('Issue #150 — Briefings-Timeline', () => {
		test('Briefings-Timeline: [data-testid="briefings-timeline"] ist sichtbar', async ({ page }) => {
			/**
			 * GIVEN: Startseite geladen
			 * WHEN: BriefingsTimeline gerendert
			 * THEN: Container ist sichtbar
			 * RED: _cockpit/BriefingsTimeline.svelte existiert noch nicht
			 */
			await expect(page.getByTestId('briefings-timeline')).toBeVisible();
		});

		test('Briefings-Timeline: enthält mindestens eine Job-Zeile ODER "nicht verfügbar"', async ({ page }) => {
			/**
			 * GIVEN: Scheduler-Status von /api/scheduler/status geladen
			 * WHEN: BriefingsTimeline gerendert
			 * THEN: Entweder Job-Zeilen mit [data-slot="dot"] oder Leerstand-Text
			 * RED: _cockpit/BriefingsTimeline.svelte existiert noch nicht
			 */
			const timeline = page.getByTestId('briefings-timeline');
			await expect(timeline).toBeVisible();
			const hasDots = await timeline.locator('[data-slot="dot"]').count() > 0;
			if (!hasDots) {
				// Leerstand: Scheduler nicht verfügbar
				await expect(timeline).toContainText(/nicht verfügbar|nicht verfuegbar/);
			} else {
				await expect(timeline.locator('[data-slot="dot"]').first()).toBeVisible();
			}
		});
	});

	// =========================================================================
	// Issue #151 — Alert-Feed
	// =========================================================================
	test.describe('Issue #151 — Alert-Feed', () => {
		test('Alert-Feed: [data-testid="alert-feed"] ist sichtbar', async ({ page }) => {
			/**
			 * GIVEN: Startseite geladen
			 * WHEN: AlertFeed gerendert
			 * THEN: Container ist sichtbar
			 * RED: _cockpit/AlertFeed.svelte existiert noch nicht
			 */
			await expect(page.getByTestId('alert-feed')).toBeVisible();
		});

		test('Alert-Feed: zeigt Placeholder "Keine Alerts"', async ({ page }) => {
			/**
			 * GIVEN: Kein Alert-Backend-Endpoint vorhanden
			 * WHEN: AlertFeed gerendert
			 * THEN: Placeholder-Text "Keine Alerts in den letzten 24h" ist sichtbar
			 * RED: _cockpit/AlertFeed.svelte existiert noch nicht
			 */
			const feed = page.getByTestId('alert-feed');
			await expect(feed).toBeVisible();
			await expect(feed).toContainText('Keine Alerts');
		});

		test('Alert-Feed: enthält KEINE echten Alert-Daten (Backend nicht implementiert)', async ({ page }) => {
			/**
			 * GIVEN: Kein Alert-Backend-Endpoint
			 * WHEN: AlertFeed gerendert
			 * THEN: Kein [data-testid="alert-item"] vorhanden (Placeholder-only)
			 * RED: _cockpit/AlertFeed.svelte existiert noch nicht
			 */
			const feed = page.getByTestId('alert-feed');
			await expect(feed).toBeVisible();
			await expect(feed.getByTestId('alert-item')).toHaveCount(0);
		});
	});

	// =========================================================================
	// Issue #152 — Bottom Row: Morgen-Vorschau + Archiv-Grid
	// =========================================================================
	test.describe('Issue #152 — Morgen-Vorschau + Archiv-Grid', () => {
		test('Bottom-Row: [data-testid="bottom-row"] ist sichtbar', async ({ page }) => {
			/**
			 * GIVEN: Startseite geladen
			 * WHEN: BottomRow gerendert
			 * THEN: Container ist sichtbar
			 * RED: _cockpit/BottomRow.svelte existiert noch nicht
			 */
			await expect(page.getByTestId('bottom-row')).toBeVisible();
		});

		test('Bottom-Row: Archiv-Sektion vorhanden (Tiles oder Leerstand)', async ({ page }) => {
			/**
			 * GIVEN: Trips mit vergangenen Etappen vorhanden ODER keine
			 * WHEN: BottomRow gerendert
			 * THEN: Archiv-Tiles ([data-testid="archive-trip-tile"]) ODER Leerstand-Text
			 * RED: _cockpit/BottomRow.svelte existiert noch nicht
			 */
			const bottomRow = page.getByTestId('bottom-row');
			await expect(bottomRow).toBeVisible();
			const hasTiles = await bottomRow.getByTestId('archive-trip-tile').count() > 0;
			if (!hasTiles) {
				await expect(bottomRow).toContainText(/Keine abgeschlossenen Trips|keine abgeschlossenen/i);
			} else {
				await expect(bottomRow.getByTestId('archive-trip-tile').first()).toBeVisible();
			}
		});
	});

	// =========================================================================
	// Regression: Alte Elemente MÜSSEN verschwunden sein
	// =========================================================================
	test.describe('Regression — Alte Kachelansicht entfernt', () => {
		test('Regression: section "Meine Trips" existiert NICHT mehr', async ({ page }) => {
			/**
			 * GIVEN: Cockpit implementiert (Epic #134)
			 * WHEN: Startseite geladen
			 * THEN: Alte Trip-Kachel-Sektion ist weg
			 * RED: Cockpit noch nicht implementiert — alte Sektion ist noch vorhanden
			 * NOTE: Dieser Test wird erst GRÜN wenn +page.svelte vollständig neu geschrieben ist
			 */
			const oldSection = page.locator('section', { hasText: 'Meine Trips' });
			await expect(oldSection).toHaveCount(0);
		});

		test('Regression: [data-testid="trip-card"] existiert NICHT mehr', async ({ page }) => {
			/**
			 * GIVEN: Cockpit implementiert (Epic #134)
			 * WHEN: Startseite geladen
			 * THEN: Alter Trip-Card-Grid ist weg (ersetzt durch Cockpit-Ansicht)
			 * RED: Alte +page.svelte ist noch aktiv
			 */
			await expect(page.getByTestId('trip-card')).toHaveCount(0);
		});

		test('Regression: [data-testid="subscription-card"] existiert NICHT mehr', async ({ page }) => {
			/**
			 * GIVEN: Cockpit implementiert (Epic #134)
			 * WHEN: Startseite geladen
			 * THEN: Subscription-Cards sind von der Startseite entfernt
			 * RED: Alte +page.svelte enthält noch Subscription-Cards
			 */
			await expect(page.getByTestId('subscription-card')).toHaveCount(0);
		});
	});

	// =========================================================================
	// Topbar CTA — Test-Briefing Feedback
	// =========================================================================
	test.describe('Topbar CTA — Test-Briefing Feedback', () => {
		test('Test-Briefing: Klick zeigt Inline-Feedback ohne Seitenreload', async ({ page }) => {
			/**
			 * GIVEN: Startseite geladen, Topbar mit CTA-Button sichtbar
			 * WHEN: [data-testid="cta-test-briefing"] geklickt
			 * THEN: Seite lädt NICHT neu (kein Full-Page-Reload)
			 *       AND: Innerhalb von 5 Sekunden erscheint Feedback-Zustand
			 *            (Button-Text ändert sich zu "Gesendet" oder Fehlermeldung)
			 * RED: Cockpit-Topbar existiert noch nicht
			 */
			const ctaButton = page.getByTestId('cta-test-briefing');
			await expect(ctaButton).toBeVisible();

			// URL vor dem Klick merken — nach dem Klick darf sich URL nicht ändern
			const urlBefore = page.url();

			await ctaButton.click();

			// Kein Full-Page-Reload — URL bleibt gleich
			await page.waitForTimeout(500);
			expect(page.url()).toBe(urlBefore);

			// Innerhalb von 5 Sekunden muss ein Feedback-Zustand sichtbar sein
			// (Button zeigt "Gesendet" / "Fehler" / loading-State)
			await expect(async () => {
				const btnText = await ctaButton.textContent();
				const hasError = await page.getByTestId('briefing-error').count() > 0;
				// Entweder Button-Text hat sich geändert ODER eine Fehlermeldung erscheint
				expect(
					btnText?.includes('Gesendet') ||
					btnText?.includes('…') ||
					btnText?.includes('Laden') ||
					hasError
				).toBe(true);
			}).toPass({ timeout: 5000 });
		});
	});
});

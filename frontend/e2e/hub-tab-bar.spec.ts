// E2E — Issue #2347 S2 (Epic #2345, Etappe P6): Reiterleiste des Hubs — EINE
// Zusicherung für BEIDE Hubs (Trip und Ortsvergleich) per Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s2_paritaets_e2e.md § AC-1 (HT-1..HT-10)
//
// Ersetzt die Reiterleisten-Fälle einer entfernten Compare-Altdatei, der entfernten
// Trip-Reiterleisten-Spec (veraltet mit 7 Reitern — korrekt sind 5, Befund 2) und
// AC-22 der entfernten mobilen Compare-Sammelspec; Zuordnung alt → neu:
// Spec-Tabelle Zeilen 1-5, 36-38, 44-49.
//
// Kind-eigene Zweige NUR dort, wo die Spec sie ausweist: HT-8 (Optik-Werte je Art).
// HT-10 (Kennzahlen-Raster der Übersicht) läuft seit Issue #2682 für BEIDE Arten —
// die Übersicht ist ein geteilter Baustein (shared/hub-uebersicht/, Spec
// feat_2682_hub_uebersicht_geteilt.md AC-2/AC-17); nur die testids unterscheiden
// sich (Tabelle RASTER). HT-13 (#2682 AC-11): kein „Alle Alerts →" in der Übersicht.
// Selektor-Unterschiede kommen aus HUB_SEL[kind] (helpers.ts); Seed-Besonderheiten
// stehen hier im Spec.
//
// Kein fester Schlaf, kein networkidle: gewartet wird auf sichtbare Elemente und
// Attribute. Anmeldung über den storageState aus global.setup.ts (Admin-Sitzung).

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, seedHub, type HubKind, type SeededHub } from './helpers';

const MOBIL = { width: 390, height: 844 };
const DESKTOP = { width: 1280, height: 900 };

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

/** Seed mit drei Punkten (Badge-Fall HT-6): Trip drei Etappen, Vergleich drei Orte. */
function seedDrei(request: APIRequestContext, kind: HubKind): Promise<SeededHub> {
	const extra: Record<string, unknown> =
		kind === 'route'
			? {
					stages: [
						{ id: 's1', name: 'Tag 1', date: '2027-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] },
						{ id: 's2', name: 'Tag 2', date: '2027-08-02', waypoints: [wp('c', 42.1), wp('d', 42.14)] },
						{ id: 's3', name: 'Tag 3', date: '2027-08-03', waypoints: [wp('e', 42.2), wp('f', 42.24)] }
					]
				}
			: { location_ids: ['e2e-loc-innsbruck', 'e2e-loc-stubai', 'e2e-loc-zillertal'] };
	return seedHub(request, kind, { extra });
}

/** Direkter Aufruf (Deep-Link ohne nachträglichen Reiter-Klick), wartet auf die Leiste. */
async function oeffneDirekt(page: Page, kind: HubKind, id: string, tab: string): Promise<void> {
	await page.goto(`${HUB_SEL[kind].liste.url}/${id}?tab=${tab}`);
	await expect(page.getByTestId(HUB_SEL[kind].reiterListe)).toBeVisible({ timeout: 15_000 });
}

/** Reiter-Knopf (`:visible` — beide Hubs können Desktop-/Mobil-Knoten parallel tragen). */
const reiter = (page: Page, kind: HubKind, tabId: string) =>
	page.locator(`[data-testid="${HUB_SEL[kind].reiter}-${tabId}"]:visible`);

/** Alle Reiter der Hub-Leiste (Scope: Reiterliste des Hubs, nicht Panel-Segmente). */
const alleReiter = (page: Page, kind: HubKind) =>
	page.getByTestId(HUB_SEL[kind].reiterListe).locator('.mtabbar').getByRole('tab');

/** Aktiver Reiter vollständig im 390-px-Fenster (Scope `.mtabbar`, Panel-Segmente tragen auch role=tab). */
async function erwarteAktivenReiterSichtbar(page: Page): Promise<void> {
	const aktiv = page.locator('.mtabbar').getByRole('tab', { selected: true });
	await expect(aktiv).toBeVisible();
	const box = await aktiv.boundingBox();
	expect(box, 'aktiver Reiter hat eine Box').not.toBeNull();
	expect(box!.x).toBeGreaterThanOrEqual(0);
	expect(box!.x + box!.width).toBeLessThanOrEqual(390 + 1);
}

for (const kind of HUB_KINDS) {
	// Zur Sammelzeit gelesen: ohne HUB_SEL in helpers.ts bricht schon die Liste ab.
	const sel = HUB_SEL[kind];

	test(`HT-1 (${kind}): Mobil — Deep-Link ?tab=alarme positioniert den aktiven Reiter sichtbar`, async ({ page }) => {
		await page.setViewportSize(MOBIL);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffneDirekt(page, kind, hub.id, 'alarme');
			await expect(reiter(page, kind, 'alarme')).toHaveAttribute('aria-selected', 'true');
			await erwarteAktivenReiterSichtbar(page);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`HT-2 (${kind}): Mobil — Alt-Link ?tab=versand landet aktiv und sichtbar auf Wetter-Metriken`, async ({
		page
	}) => {
		await page.setViewportSize(MOBIL);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffneDirekt(page, kind, hub.id, 'versand');
			await expect(reiter(page, kind, 'wetter-metriken')).toHaveAttribute('aria-selected', 'true');
			await expect(page).toHaveURL(sel.hubUrl(hub.id));
			await expect(page).toHaveURL(/[?&]tab=wetter-metriken#versand$/);
			await erwarteAktivenReiterSichtbar(page);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`HT-3 (${kind}): Mobil — letzter Reiter „Alarme" per Wisch + echtem Klick erreichbar, Panel wechselt`, async ({
		page
	}) => {
		await page.setViewportSize(MOBIL);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffneDirekt(page, kind, hub.id, 'uebersicht');
			await expect(page.locator(`[data-testid="${sel.panel}-uebersicht"]`)).toBeVisible({ timeout: 10_000 });

			const letzter = reiter(page, kind, 'alarme');
			// scrollIntoViewIfNeeded = Playwright-Äquivalent zum horizontalen Nutzer-Wisch.
			await letzter.scrollIntoViewIfNeeded();
			await expect(letzter).toBeInViewport({ timeout: 5_000 });
			await letzter.click();

			await expect(letzter).toHaveAttribute('aria-selected', 'true');
			await erwarteAktivenReiterSichtbar(page);
			await expect(page.locator(`[data-testid="${sel.panel}-alarme"]:visible`)).toBeVisible({ timeout: 10_000 });
			await expect(page.locator(`[data-testid="${sel.reiter}-vorschau"]`)).toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`HT-4 (${kind}): Mobil — A11y: tablist/tab, genau 5 Reiter, aria-selected, roving tabindex, Pfeiltaste`, async ({
		page
	}) => {
		await page.setViewportSize(MOBIL);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffneDirekt(page, kind, hub.id, 'uebersicht');

			// Scope auf die Hub-Leiste (.mtabbar): Panel-Segmente rendern ebenfalls role=tablist/tab.
			const tablist = page.getByTestId(sel.reiterListe).locator('.mtabbar');
			await expect(tablist).toBeVisible();
			await expect(tablist).toHaveAttribute('role', 'tablist');
			await expect(tablist.getByRole('tab')).toHaveCount(5);

			const uebersicht = reiter(page, kind, 'uebersicht');
			const punkte = reiter(page, kind, sel.punkteReiter);
			await expect(uebersicht).toHaveAttribute('aria-selected', 'true');
			await expect(punkte).toHaveAttribute('aria-selected', 'false');
			await expect(uebersicht).toHaveAttribute('tabindex', '0');
			await expect(punkte).toHaveAttribute('tabindex', '-1');

			await uebersicht.focus();
			await page.keyboard.press('ArrowRight');
			await expect(punkte).toHaveAttribute('aria-selected', 'true');
			await expect(punkte).toBeFocused();
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`HT-5 (${kind}): Mobil — alle 5 Reiter-Trigger sind mindestens 44 px hoch`, async ({ page }) => {
		await page.setViewportSize(MOBIL);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffneDirekt(page, kind, hub.id, 'uebersicht');
			const tabs = alleReiter(page, kind);
			await expect(tabs).toHaveCount(5);
			for (let i = 0; i < 5; i++) {
				const box = await tabs.nth(i).boundingBox();
				expect(box, `Reiter ${i} hat eine Box`).not.toBeNull();
				expect(box!.height, `Reiter ${i} Tippfläche`).toBeGreaterThanOrEqual(44);
			}
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`HT-6 (${kind}): Mobil — Badge am Punkte-Reiter zeigt die Anzahl 3`, async ({ page }) => {
		await page.setViewportSize(MOBIL);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffneDirekt(page, kind, hub.id, 'uebersicht');
			const badge = reiter(page, kind, sel.punkteReiter).locator('[data-slot="segmented-badge"]');
			await expect(badge).toBeVisible();
			await expect(badge).toHaveText('3');
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`HT-7 (${kind}): Desktop — alle 5 Reiter liegen ohne Band-Scroll im Fenster`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffneDirekt(page, kind, hub.id, 'uebersicht');
			const tabs = alleReiter(page, kind);
			await expect(tabs).toHaveCount(5);
			for (let i = 0; i < 5; i++) {
				const box = await tabs.nth(i).boundingBox();
				expect(box, `Reiter ${i} hat eine Box`).not.toBeNull();
				expect(box!.x + box!.width, `Reiter ${i} rechte Kante`).toBeLessThanOrEqual(1280);
			}
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`HT-8 (${kind}): Desktop — Optik der Reiterleiste unverändert`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffneDirekt(page, kind, hub.id, 'uebersicht');
			// kind-Zweig (Spec HT-8): Optik-Werte sind nicht Gegenstand der Teilung —
			// sie bleiben je Art exakt wie in den Alt-Specs.
			if (kind === 'vergleich') {
				// Altfall Zuordnung Zeile 5 — neutraler Badge (--g-paper-deep), 13-px-Trigger.
				const badge = reiter(page, kind, sel.punkteReiter).locator('[data-slot="segmented-badge"]');
				await expect(badge).toBeVisible();
				expect(await badge.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe('rgb(236, 234, 217)');
				expect(await reiter(page, kind, 'uebersicht').evaluate((el) => getComputedStyle(el).fontSize)).toBe('13px');
			} else {
				// Altfall Zuordnung Zeile 49 — Unterline-Optik: aktiver Reiter transparent.
				expect(
					await reiter(page, kind, 'uebersicht').evaluate((el) => getComputedStyle(el).backgroundColor)
				).toBe('rgba(0, 0, 0, 0)');
			}
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`HT-9 (${kind}): Mobil — echter Klick auf den Punkte-Reiter wechselt das Panel, Übersicht verlässt das DOM`, async ({
		page
	}) => {
		await page.setViewportSize(MOBIL);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffneDirekt(page, kind, hub.id, 'uebersicht');
			await expect(page.locator(`[data-testid="${sel.panel}-uebersicht"]`)).toBeVisible({ timeout: 10_000 });

			const punkte = reiter(page, kind, sel.punkteReiter);
			await expect(punkte).toBeVisible({ timeout: 10_000 });
			await punkte.click();

			await expect(page.locator(`[data-testid="${sel.panel}-${sel.punkteReiter}"]`)).toBeVisible({ timeout: 10_000 });
			// Ein Reiter-Inhalt ist jeweils gemountet (kein CSS-Hide).
			await expect(page.locator(`[data-testid="${sel.panel}-uebersicht"]`)).toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── HT-11, HT-12 (#2347 S4) ─────────────────────────────────────────────────
// HT-11: Ersatz für trip-edit „tabs: zurück zu Etappen stellt Inhalt her".
// HT-12: Ersatz für compare-flow-navigation AC-30 („Bearbeiten →" der Orte-Karte).
// Seed-Text des Punkte-Panels (aus seedDrei bzw. global.setup.ts) und Sprungknopf
// der Übersicht je kind (Kind-Kontraste „HT-12 Sprungknopf": Trip HubOverview.svelte:88
// „Im Editor öffnen →", Vergleich CompareTabs.svelte:841 „Bearbeiten →" auf der
// Orte-Karte). Die Sprungziele gehören zur context-eigenen Hauptfläche (Etappen bzw.
// Orte, #2682 Entscheidung 1) — nur die Beschriftung unterscheidet sich, die Aussage
// ist gleich. Ein Sprungknopf „Alle Alerts →" existiert in KEINER Art mehr (HT-13).
const PUNKTE_TEXT: Record<HubKind, string> = { route: 'Tag 1', vergleich: 'Innsbruck (E2E)' };
const SPRUNGKNOPF: Record<HubKind, (page: Page) => ReturnType<Page['locator']>> = {
	route: (page) =>
		page.locator(`[data-testid="${HUB_SEL.route.panel}-uebersicht"]`).getByRole('button', { name: 'Im Editor öffnen →' }),
	vergleich: (page) =>
		page
			.locator(`[data-testid="${HUB_SEL.vergleich.panel}-uebersicht"] [data-slot="card"]`, { hasText: 'Kandidaten' })
			.getByRole('button', { name: 'Bearbeiten →' })
};

for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];

	test(`HT-11 (${kind}): Desktop — Reiter A → B → A stellt den Inhalt von A wieder her`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffneDirekt(page, kind, hub.id, sel.punkteReiter);
			const panelA = page.locator(`[data-testid="${sel.panel}-${sel.punkteReiter}"]:visible`).first();
			await expect(panelA).toBeVisible({ timeout: 10_000 });
			await expect(panelA).toContainText(PUNKTE_TEXT[kind]);

			await reiter(page, kind, 'wetter-metriken').first().click();
			await expect(page.locator(`[data-testid="${sel.panel}-wetter-metriken"]:visible`).first()).toBeVisible({
				timeout: 10_000
			});
			await expect(page.locator(`[data-testid="${sel.panel}-${sel.punkteReiter}"]:visible`)).toHaveCount(0);

			await reiter(page, kind, sel.punkteReiter).first().click();
			await expect(panelA, 'HT-11: Inhalt von Reiter A nach der Rückkehr nicht wiederhergestellt').toBeVisible({
				timeout: 10_000
			});
			await expect(panelA).toContainText(PUNKTE_TEXT[kind]);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`HT-12 (${kind}): Desktop — Sprungknopf der Übersicht wechselt den Reiter inline (tab ändert sich, keine volle Navigation)`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffneDirekt(page, kind, hub.id, 'uebersicht');
			const knopf = SPRUNGKNOPF[kind](page).first();
			await expect(knopf, 'HT-12: Sprungknopf der Übersicht fehlt').toBeVisible({ timeout: 10_000 });
			// Marker im window: eine volle Navigation lädt das Dokument neu und verliert ihn.
			await page.evaluate(() => {
				(window as unknown as { __gzHt12?: boolean }).__gzHt12 = true;
			});
			await knopf.click();
			await expect.poll(() => new URL(page.url()).searchParams.get('tab'), { message: 'HT-12: tab ändert sich nicht' }).toBe(
				sel.punkteReiter
			);
			await expect(page.locator(`[data-testid="${sel.panel}-${sel.punkteReiter}"]:visible`).first()).toBeVisible({
				timeout: 10_000
			});
			expect(
				await page.evaluate(() => (window as unknown as { __gzHt12?: boolean }).__gzHt12 === true),
				'HT-12: der Sprung hat das Dokument neu geladen (volle Navigation)'
			).toBe(true);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// HT-10 (#2682, AC-2/AC-17): das Kennzahlen-Raster der Übersicht ist EIN geteilter
// Baustein (shared/hub-uebersicht/) — beide Arten zeigen mobil dieselben vier
// Kennzahlen im 2×2-Raster. Nur die testids folgen dem Präfix je Art (Spec „Stabile
// testids": Vergleich compare-*, Trip hub-uebersicht-*). Altfall Zuordnung Zeile 36.
const RASTER: Record<HubKind, { raster: string; statBriefings: string }> = {
	route: { raster: 'hub-uebersicht-monitoring-mobile', statBriefings: 'hub-uebersicht-stat-briefings' },
	vergleich: { raster: 'compare-detail-monitoring-mobile', statBriefings: 'compare-detail-stat-briefings' }
};

for (const kind of HUB_KINDS) {
	test(`HT-10 (${kind}): Mobil — Übersicht zeigt genau 4 Stat-Karten im 2×2-Raster, kein „Briefings"-Stat`, async ({
		page
	}) => {
		await page.setViewportSize(MOBIL);
		const hub = await seedHub(page.request, kind);
		try {
			await oeffneDirekt(page, kind, hub.id, 'uebersicht');

			const monitoring = page.locator(`[data-testid="${RASTER[kind].raster}"]:visible`);
			await expect(monitoring).toBeVisible({ timeout: 10_000 });
			await expect(monitoring.locator('[data-slot="card"]')).toHaveCount(4);
			await expect(monitoring).toContainText('Status');
			await expect(monitoring).toContainText('Nächster Versand');
			await expect(monitoring).toContainText('Zuletzt raus');
			await expect(monitoring).toContainText('Kanäle');
			await expect(monitoring).not.toContainText('Briefings');
			// Die Desktop-exklusive Briefings-Stat existiert im mobilen DOM-Baum gar nicht.
			await expect(page.locator(`[data-testid="${RASTER[kind].statBriefings}"]`)).toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});

	// HT-13 (#2682 AC-11): die Alerts-Attrappe („Alerts (letzte 7 Tage)", Festtext,
	// Knopf „Alle Alerts →") ist entfernt; die Alarme bleiben über den Reiter erreichbar.
	test(`HT-13 (${kind}): Desktop — Übersicht ohne „Alle Alerts →", Reiter Alarme öffnet sich per Klick`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedHub(page.request, kind);
		try {
			await oeffneDirekt(page, kind, hub.id, 'uebersicht');
			const uebersicht = page.locator(`[data-testid="${HUB_SEL[kind].panel}-uebersicht"]:visible`).first();
			await expect(uebersicht).toBeVisible({ timeout: 10_000 });
			await expect(uebersicht.getByRole('button', { name: 'Alle Alerts →' })).toHaveCount(0);
			await expect(uebersicht.getByText('Keine aktuellen Alerts.')).toHaveCount(0);
			await expect(uebersicht.getByText('Alerts (letzte 7 Tage)')).toHaveCount(0);

			await reiter(page, kind, 'alarme').first().click();
			await expect(page.locator(`[data-testid="${HUB_SEL[kind].panel}-alarme"]:visible`).first()).toBeVisible({
				timeout: 10_000
			});
		} finally {
			await hub.aufraeumen();
		}
	});
}

// E2E (Staging) — Hub-Übersicht für BEIDE Arten (Trip und Ortsvergleich) per
// Schleife über HUB_KINDS. Herkunft: Issue #1256 Scheibe S8c (Hub-Fidelity der
// Vergleichs-Übersicht); seit Issue #2682 (Epic #2345) ist die Übersicht EIN
// geteilter Baustein (shared/hub-uebersicht/HubUebersicht.svelte, context=
// "route"|"vergleich") — der frühere `gz-eigenstaendig`-Kopf („kein Gegenpart im
// Trip-Hub") ist damit entfallen (AC-17, tests/unit/test_e2e_compare_paritaet_waechter.py).
//
// Specs: docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md (AC-1, AC-2, AC-3,
//        AC-5, AC-8, AC-11, AC-13), docs/specs/modules/feat_1256_s8c_hub_fidelity.md
//
// Kind-Kontraste (nur dort, wo die Spec sie ausweist):
//   - testids: Vergleich behält `compare-*`, Trip bekommt `hub-uebersicht-*`
//     (Spec „Stabile testids"; Tabelle UE unten, keine Assertions darin).
//   - mobile Pfeil-Zeilen: Vergleich Orte · Wertebereiche · Versand (3), Trip nur
//     Versand (1) — Orte/Wertebereiche-Karten sind Vergleichs-Hauptfläche
//     (Spec Entscheidung 1, AC-2).
//   - Status: Vergleich „Läuft autom." (mobil) / „Läuft automatisch" (Desktop);
//     Trip wortgleich zum Status-Badge im Trip-Kopf (Entscheidung 2, AC-5).
//   - Orte-Karte („+N weitere") und Orte-Reiter-Texte sind compare-eigen
//     (CLAUDE.md-Katalog: Orte-Reiter), eigener Block am Ende.
//
// Korrektur gegenüber dem Altstand (gemessen am Code, nicht abgeschwächt): der
// mobile Stapel hat seit #1360 KEINE Zeile „Layout" mehr (3 statt 4 Zeilen), der
// Draft-Text lautet „Briefing-Uhrzeiten unter Wetter-Metriken im Abschnitt Versand
// festlegen." (#1743), „Reihenfolge nach Priorität." steht nicht in der Übersicht.
//
// Ausführen (gegen Staging, aus frontend/, NACH Push+Staging-Deploy):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1256-s8c.staging.config.ts
//
// storageState-Login (Setup-Projekt), kein per-Test-Login (429-Rate-Limit).
// Eigene Orte je Lauf (der Staging-Setup legt keine Seed-Orte an).

import { test, expect, type Page } from '@playwright/test';
import { createTestLocation, HUB_KINDS, HUB_SEL, openHub, seedHub, type HubKind, type SeededHub } from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 390, height: 844 };

/** Selektor-Tabelle der Übersicht je kind (reine Konstanten, keine Assertions). */
const UE: Record<
	HubKind,
	{
		statKanaele: string;
		statKanaeleMobil: string;
		statBriefings: string;
		versandEdit: string;
		raster: string;
		stapel: string;
		pfeilZeilen: readonly string[];
	}
> = {
	route: {
		statKanaele: 'hub-uebersicht-stat-kanaele',
		statKanaeleMobil: 'hub-uebersicht-stat-kanaele-mobile',
		statBriefings: 'hub-uebersicht-stat-briefings',
		versandEdit: 'hub-uebersicht-versand-edit',
		raster: 'hub-uebersicht-monitoring-mobile',
		stapel: 'hub-uebersicht-summary-mobile',
		pfeilZeilen: ['Versand']
	},
	vergleich: {
		statKanaele: 'compare-detail-stat-kanaele',
		statKanaeleMobil: 'compare-detail-stat-kanaele-mobile',
		statBriefings: 'compare-detail-stat-briefings',
		versandEdit: 'compare-hub-versand-edit',
		raster: 'compare-detail-monitoring-mobile',
		stapel: 'compare-detail-summary-mobile',
		pfeilZeilen: ['Orte', 'Wertebereiche', 'Versand']
	}
};

let hubs: SeededHub[] = [];
let orte: string[] = [];

test.afterEach(async ({ page }) => {
	for (const hub of hubs) await hub.aufraeumen().catch(() => {});
	hubs = [];
	for (const id of orte) await page.request.delete(`/api/locations/${id}`).catch(() => {});
	orte = [];
});

async function ort(page: Page, name: string, lat: number): Promise<string> {
	const loc = await createTestLocation(page.request, { name, lat, lon: 11.4 });
	orte.push(loc.id);
	return loc.id;
}

/** Aktiver Hub je kind: Trip mit datierter Etappe, Vergleich mit Name + einem eigenen Ort. */
async function aktiverHub(page: Page, kind: HubKind, extra: Record<string, unknown> = {}): Promise<SeededHub> {
	const basis =
		kind === 'vergleich'
			? { location_ids: [await ort(page, `E2E-GZ-2682 Ort ${Date.now()}`, 47.2)], profil: 'wandern' }
			: {};
	const hub = await seedHub(page.request, kind, { extra: { ...basis, ...extra } });
	hubs.push(hub);
	return hub;
}

/** Entwurf je kind: Trip ohne datierte Etappe (deriveTripStatus ⇒ draft), Vergleich ohne Ort. */
async function entwurfHub(page: Page, kind: HubKind): Promise<SeededHub> {
	const extra =
		kind === 'route'
			? { stages: [{ id: 's1', name: 'Tag 1', waypoints: [{ id: 'a', name: 'a', lat: 42.0, lon: 9.0, elevation_m: 800 }] }] }
			: { location_ids: [] };
	const hub = await seedHub(page.request, kind, { extra });
	hubs.push(hub);
	return hub;
}

const uebersicht = (page: Page, kind: HubKind) =>
	page.locator(`[data-testid="${HUB_SEL[kind].panel}-uebersicht"]:visible`).first();

for (const kind of HUB_KINDS) {
	const ue = UE[kind];

	test.describe(`Hub-Übersicht (${kind}) — Desktop`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize(DESKTOP);
		});

		test(`UE-1 (${kind}): Kennzahlen-Leiste mit fünf Kennzahlen, Kanäle- und Briefings-Wert vorhanden (AC-1, AC-13)`, async ({ page }) => {
			const hub = await aktiverHub(page, kind);
			await openHub(page, kind, hub.id);
			const p = uebersicht(page, kind);
			await expect(p).toBeVisible({ timeout: 10_000 });
			for (const label of ['Status', 'Nächster Versand', 'Briefings', 'Zuletzt raus', 'Kanäle']) {
				await expect(p.getByText(label, { exact: true }).first(), `Kennzahl „${label}" fehlt`).toBeVisible();
			}
			await expect(page.locator(`[data-testid="${ue.statKanaele}"]:visible`)).toHaveCount(1);
			await expect(page.locator(`[data-testid="${ue.statBriefings}"]:visible`)).toHaveCount(1);
			await expect(page.locator(`[data-testid="${ue.statKanaele}"]:visible`)).toContainText(/E-?Mail/i);
		});

		test(`UE-2 (${kind}): Status-Kennzahl (AC-3/AC-5)`, async ({ page }) => {
			const hub = await aktiverHub(page, kind);
			await openHub(page, kind, hub.id);
			const p = uebersicht(page, kind);
			await expect(p).toBeVisible({ timeout: 10_000 });
			if (kind === 'vergleich') {
				await expect(p.getByText('Läuft automatisch')).toBeVisible();
			} else {
				// Trip: wortgleich zum Badge im Trip-Kopf (kein zweites Vokabular).
				const badge = page.getByTestId('trip-detail-status-badge').first();
				await expect(badge).toBeVisible({ timeout: 10_000 });
				// textContent statt innerText: das Pill-Badge schreibt per CSS gross
				// (app.css [data-slot="pill"] text-transform: uppercase) — innerText
				// liefert „GEPLANT", der DOM-Wortlaut ist „Geplant".
				const text = ((await badge.textContent()) ?? '').trim();
				expect(text.length, 'Badge-Text leer').toBeGreaterThan(0);
				await expect(p.getByText(text, { exact: true }).first()).toBeVisible();
			}
		});

		test(`UE-3 (${kind}): Versand-Karte „Bearbeiten →" springt in Wetter-Metriken › Versand (AC-8)`, async ({ page }) => {
			const hub = await aktiverHub(page, kind);
			await openHub(page, kind, hub.id);
			await expect(uebersicht(page, kind)).toBeVisible({ timeout: 10_000 });
			const knopf = page.locator(`[data-testid="${ue.versandEdit}"]:visible`);
			await expect(knopf).toHaveCount(1);
			await expect(knopf).toHaveText('Bearbeiten →');
			await knopf.click();
			await expect(page.locator(`[data-testid="${HUB_SEL[kind].panel}-wetter-metriken"]:visible`).first()).toBeVisible({
				timeout: 10_000
			});
			await expect(page.locator('[data-testid="versand-abschnitt"]:visible').first()).toBeInViewport({ timeout: 10_000 });
			await expect.poll(() => new URL(page.url()).hash).toBe('#versand');
		});

		test(`UE-4 (${kind}): Entwurf ⇒ Versand-Karte „Noch nicht geplant" (AC-8, S8c AC-5)`, async ({ page }) => {
			const hub = await entwurfHub(page, kind);
			await openHub(page, kind, hub.id);
			const p = uebersicht(page, kind);
			await expect(p).toBeVisible({ timeout: 10_000 });
			await expect(p.getByText('Noch nicht geplant')).toBeVisible();
			if (kind === 'vergleich') {
				await expect(p.getByText('Briefing-Uhrzeiten unter Wetter-Metriken im Abschnitt Versand festlegen.')).toBeVisible();
			}
		});

		test(`UE-5 (${kind}): aktiver Hub ⇒ Versand-Karte nennt Zeiten statt „Noch nicht geplant"`, async ({ page }) => {
			const hub = await aktiverHub(page, kind);
			await openHub(page, kind, hub.id);
			const p = uebersicht(page, kind);
			await expect(p).toBeVisible({ timeout: 10_000 });
			await expect(p.getByText('Noch nicht geplant')).toHaveCount(0);
			// Seed (helpers.seedRumpf): Morgen 06:00 aktiv.
			await expect(page.locator(`[data-testid="${ue.statBriefings}"]:visible`)).toContainText('06:00');
		});

		test(`UE-6 (${kind}): Versand-Historie unter der Hauptfläche, keine Alerts-Attrappe (AC-11, AC-13)`, async ({ page }) => {
			const hub = await aktiverHub(page, kind);
			await openHub(page, kind, hub.id);
			const p = uebersicht(page, kind);
			await expect(p).toBeVisible({ timeout: 10_000 });
			await expect(p.locator(`[data-testid="briefing-history"][data-kind="${kind}"]`)).toHaveCount(1);
			await expect(p.getByText('Keine aktuellen Alerts.')).toHaveCount(0);
			await expect(p.getByRole('button', { name: 'Alle Alerts →' })).toHaveCount(0);
		});
	});

	test.describe(`Hub-Übersicht (${kind}) — mobil 390×844`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize(MOBIL);
		});

		test(`UE-7 (${kind}): 2×2-Raster mit vier Kennzahlen, ohne Briefings (AC-2, S8c AC-22)`, async ({ page }) => {
			const hub = await aktiverHub(page, kind);
			await openHub(page, kind, hub.id);
			const raster = page.locator(`[data-testid="${ue.raster}"]:visible`);
			await expect(raster).toBeVisible({ timeout: 10_000 });
			await expect(raster.locator('[data-slot="card"]')).toHaveCount(4);
			for (const label of ['Status', 'Nächster Versand', 'Zuletzt raus', 'Kanäle']) await expect(raster).toContainText(label);
			await expect(raster).not.toContainText('Briefings');
			await expect(page.locator(`[data-testid="${ue.statBriefings}"]`)).toHaveCount(0);
			await expect(page.locator(`[data-testid="${ue.statKanaeleMobil}"]:visible`)).toHaveCount(1);
		});

		test(`UE-8 (${kind}): Pfeil-Zeilen-Stapel; Versand-Zeile springt in Wetter-Metriken (AC-2, S8c AC-7)`, async ({ page }) => {
			const hub = await aktiverHub(page, kind);
			await openHub(page, kind, hub.id);
			const stapel = page.locator(`[data-testid="${ue.stapel}"]:visible`);
			await expect(stapel).toBeVisible({ timeout: 10_000 });
			const zeilen = stapel.locator('[data-testid="hub-summary-row-mobile"]');
			await expect(zeilen).toHaveCount(ue.pfeilZeilen.length);
			for (const [i, eyebrow] of ue.pfeilZeilen.entries()) await expect(zeilen.nth(i)).toContainText(eyebrow);
			await zeilen.nth(ue.pfeilZeilen.indexOf('Versand')).click();
			await expect(page.locator(`[data-testid="${HUB_SEL[kind].panel}-wetter-metriken"]:visible`).first()).toBeVisible({
				timeout: 10_000
			});
			await expect(page.locator(`[data-testid="${HUB_SEL[kind].panel}-uebersicht"]`)).toHaveCount(0);
		});

		test(`UE-9 (${kind}): Status-Kurzform im Raster (S8c AC-8, AC-5)`, async ({ page }) => {
			const hub = await aktiverHub(page, kind);
			await openHub(page, kind, hub.id);
			const raster = page.locator(`[data-testid="${ue.raster}"]:visible`);
			await expect(raster).toBeVisible({ timeout: 10_000 });
			if (kind === 'vergleich') {
				await expect(raster.getByText('Läuft autom.', { exact: true })).toBeVisible();
			} else {
				// textContent statt innerText (CSS-uppercase des Pill-Badges, s. UE-2).
				const text = ((await page.getByTestId('trip-detail-status-badge').first().textContent()) ?? '').trim();
				expect(text.length, 'Badge-Text leer').toBeGreaterThan(0);
				await expect(raster.getByText(text, { exact: true })).toBeVisible();
			}
		});

		test(`UE-10 (${kind}): Entwurf ⇒ Status-Kurzform „Entwurf" im Raster`, async ({ page }) => {
			const hub = await entwurfHub(page, kind);
			await openHub(page, kind, hub.id);
			const raster = page.locator(`[data-testid="${ue.raster}"]:visible`);
			await expect(raster).toBeVisible({ timeout: 10_000 });
			await expect(raster.getByText('Entwurf', { exact: true })).toBeVisible();
		});
	});
}

// ─── compare-eigen: Orte-Karte und Orte-Reiter (CLAUDE.md-Katalog: Orte-Reiter) ──

test.describe('Ortsvergleich: Orte-Karte und Orte-Reiter (compare-eigen)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(DESKTOP);
	});

	test('S8c AC-3/AC-4/AC-6: vier Orte ⇒ „4 Kandidaten" und „+1 weitere"; Profil „Wandern", Kanal „Email"', async ({ page }) => {
		const s = Date.now();
		const ids = [
			await ort(page, `E2E-GZ-2682 4a ${s}`, 47.61),
			await ort(page, `E2E-GZ-2682 4b ${s}`, 47.62),
			await ort(page, `E2E-GZ-2682 4c ${s}`, 47.63),
			await ort(page, `E2E-GZ-2682 4d ${s}`, 47.64)
		];
		const hub = await seedHub(page.request, 'vergleich', { extra: { location_ids: ids, profil: 'wandern' } });
		hubs.push(hub);
		await openHub(page, 'vergleich', hub.id);
		const p = uebersicht(page, 'vergleich');
		await expect(p).toBeVisible({ timeout: 10_000 });
		await expect(p.getByText('4 Kandidaten')).toBeVisible();
		await expect(p.getByText('+1 weitere')).toBeVisible();
		await expect(p.getByText('Wandern').first()).toBeVisible();
		await expect(page.locator('[data-testid="compare-detail-stat-kanaele"]:visible')).toContainText('Email');
	});

	test('S8c AC-9: Orte-Reiter zeigt „Verglichene Orte" und den Desktop-Sortier-Hinweis', async ({ page }) => {
		const hub = await aktiverHub(page, 'vergleich');
		await openHub(page, 'vergleich', hub.id, { tab: 'orte' });
		const panel = page.locator('[data-testid="compare-detail-panel-orte"]:visible').first();
		await expect(panel).toBeVisible({ timeout: 10_000 });
		await expect(panel.getByText('Verglichene Orte')).toBeVisible();
		await expect(panel.getByText('Reihenfolge = Spalten im Briefing · ziehen zum Sortieren')).toBeVisible();
	});
});

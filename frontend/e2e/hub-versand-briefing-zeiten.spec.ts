// E2E — Issue #2347 S3b (Epic #2345, Etappe P6): Briefing-Zeiten in Übersicht
// und Versand-Abschnitt, Neutralisierung, „Bearbeiten →", `?tab=`, Reiterleiste —
// EINE Zusicherung für BEIDE Hubs (Trip und Ortsvergleich) per Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s3b_paritaets_e2e.md § AC-7, AC-8 (VB-1..VB-9),
// Entscheidung „Frage 1"
//
// Ersetzt compare-hub-briefing-times.spec.ts (#1229, nur Vergleich, nicht geratscht):
//   AC-1 Stat Desktop          → VB-1 (je kind, eigenes Ist-Format)
//   AC-2 mobil                 → VB-2 (je kind, an der TATSÄCHLICHEN mobilen Stelle)
//   AC-4 Versand-Überschriften → VB-3 (je kind; „Zeitplan"-Negativprüfung entfällt mit
//                                Beleg VTSchedulePlan.svelte:75 „Briefing-Zeitplan")
//   Fix-Loop 1                 → VB-4 (je kind)
//   AC-5 „Bearbeiten →"        → VB-5 (je kind)
//   AC-6 unbekannter ?tab=     → VB-6 (je kind)
//   AC-7 „Kein Score"          → VB-7 (vergleich)
//   AC-8 Vorschau-Reiter       → entfällt mit dem Produkt (#1743); Abwesenheit: VB-8
//   AC-10 fünf Reiter          → VB-8 (je kind; Anzahl bleibt in hub-tab-bar)
//   Draft ohne Slots „—"       → VB-9 (je kind, eigenes Ist-Format)
//
// Übersicht-Format je kind (Spec „Kind-Kontraste", Zeile Übersicht Briefing-Angabe):
// der Vergleich rendert einen zusammengesetzten Stat „Morgen 07:00 · Abend 18:00"
// (bzw. „—", subscriptionHelpers.ts presetBriefingTimesLabel), mobil in der
// Summary-Zeile „Versand"; der Trip rendert in beiden Breiten die Karte
// „Briefings laufen" mit zwei ReportLine-Zeilen (Label, Zeit, Punkt in Aktiv- bzw.
// Inaktiv-Farbe, ReportLine.svelte). Jeder kind prüft sein eigenes Ist-Format.
//
// Seed: beide Slots aktiv, Morgen 07:00, Abend 18:00 — Erwartungen aus dem Seed.
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh). Aufräumen im finally.

import { test, expect, type Locator, type Page } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind } from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 390, height: 844 };

// Seed je kind (Feldpfad): seedHub ersetzt report_config flach ⇒ vollständig.
const SEED: Record<HubKind, Record<string, unknown>> = {
	route: {
		report_config: {
			enabled: true,
			morning_enabled: true,
			evening_enabled: true,
			morning_time: '07:00:00',
			evening_time: '18:00:00'
		}
	},
	vergleich: {
		morning_enabled: true,
		morning_time: '07:00:00',
		evening_enabled: true,
		evening_time: '18:00:00',
		hour_from: 7,
		hour_to: 16
	}
};
const STAT = 'Morgen 07:00 · Abend 18:00';
// slotZeit (HubOverview.svelte) hängt bei bekanntem Briefing das Zonenkürzel an.
const MORGEN = /^07:00( \(.+\))?$/;
const ABEND = /^18:00( \(.+\))?$/;

// Hub-Adresse je kind (reine Selektor-/Pfad-Tabelle, wie openHub in helpers.ts).
const basis = (kind: HubKind, id: string) => (kind === 'route' ? `/trips/${id}` : `/compare/${id}`);
const panel = (page: Page, kind: HubKind, tab: string) =>
	page.locator(`[data-testid="${HUB_SEL[kind].panel}-${tab}"]:visible`).first();

/** Trip-Karte „Briefings laufen" (innerstes Element, das Eyebrow und „Zeitplan bearbeiten →" enthält). */
function tripKarte(page: Page): Locator {
	return page
		.locator('[data-testid="hub-overview"]:visible div')
		.filter({ has: page.getByText('Briefings laufen', { exact: true }) })
		.filter({ has: page.getByRole('button', { name: 'Zeitplan bearbeiten →' }) })
		.last();
}

/** ReportLine-Zeile (Elternelement des Labels): `> span` 0 = Punkt, 2 = Zeit. */
function zeile(karte: Locator, label: 'Morgen-Briefing' | 'Abend-Briefing') {
	const reihe = karte.getByText(label, { exact: true }).locator('xpath=..');
	return { reihe, punkt: reihe.locator(':scope > span').nth(0), zeit: reihe.locator(':scope > span').nth(2) };
}

const hintergrund = (el: Locator) => el.evaluate((e) => getComputedStyle(e).backgroundColor);

/** Löst ein CSS-Token zur berechneten Hintergrundfarbe auf (Vergleichsmaß für die Punkte). */
function tokenFarbe(page: Page, token: string): Promise<string> {
	return page.evaluate((t) => {
		const probe = document.createElement('span');
		probe.style.background = `var(${t})`;
		document.body.appendChild(probe);
		const farbe = getComputedStyle(probe).backgroundColor;
		probe.remove();
		return farbe;
	}, token);
}

async function pruefeTripKarte(page: Page): Promise<void> {
	const karte = tripKarte(page);
	await expect(karte).toBeVisible({ timeout: 10_000 });
	const morgen = zeile(karte, 'Morgen-Briefing');
	const abend = zeile(karte, 'Abend-Briefing');
	await expect(morgen.reihe).toBeVisible();
	await expect(abend.reihe).toBeVisible();
	await expect(morgen.zeit).toHaveText(MORGEN);
	await expect(abend.zeit).toHaveText(ABEND);
	const gut = await tokenFarbe(page, '--g-good');
	expect(await hintergrund(morgen.punkt), 'Morgen-Punkt in Aktiv-Farbe').toBe(gut);
	expect(await hintergrund(abend.punkt), 'Abend-Punkt in Aktiv-Farbe').toBe(gut);
}

for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];

	test.describe(`Hub · Briefing-Zeiten (${kind})`, () => {
		// VB-1 (Alt AC-1) — fängt: Slot-Label-Format bzw. feste statt echter Zeiten.
		test(`VB-1 (${kind}): Übersicht (Desktop) zeigt die Briefing-Angabe Morgen 07:00 / Abend 18:00`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedHub(page.request, kind, { extra: SEED[kind] });
			try {
				await openHub(page, kind, hub.id);
				await expect(panel(page, kind, 'uebersicht')).toBeVisible({ timeout: 10_000 });
				// Übersicht-Format je kind (Kopfkommentar, Spec „Kind-Kontraste").
				if (kind === 'vergleich') {
					await expect(page.locator('[data-testid="compare-detail-stat-briefings"]:visible').first()).toHaveText(STAT, {
						timeout: 10_000
					});
				} else {
					await pruefeTripKarte(page);
				}
			} finally {
				await hub.aufraeumen();
			}
		});

		// VB-2 (Alt AC-2, umformuliert nach „Frage 1") — fängt: mobil fehlt die Angabe.
		test(`VB-2 (${kind}): Übersicht (mobil 390×844) zeigt dieselbe Briefing-Angabe an der mobilen Stelle`, async ({ page }) => {
			await page.setViewportSize(MOBIL);
			const hub = await seedHub(page.request, kind, { extra: SEED[kind] });
			try {
				await openHub(page, kind, hub.id);
				await expect(panel(page, kind, 'uebersicht')).toBeVisible({ timeout: 10_000 });
				// Mobile Stelle je kind (Spec „Kind-Kontraste" / „Frage 1"): Vergleich
				// Summary-Zeile „Versand" (der Desktop-Stat steht mobil nicht,
				// CompareTabs.svelte isMobileViewport); Trip dieselbe HubOverview-Karte.
				if (kind === 'vergleich') {
					const versandZeile = page
						.locator('[data-testid="hub-summary-row-mobile"]:visible')
						.filter({ has: page.locator('.hub-summary-row-eyebrow', { hasText: /^Versand$/ }) });
					await expect(versandZeile).toHaveCount(1, { timeout: 10_000 });
					await expect(versandZeile.locator('.hub-summary-row-title')).toHaveText(STAT);
					await expect(page.locator('[data-testid="compare-detail-stat-briefings"]')).toHaveCount(0);
				} else {
					await pruefeTripKarte(page);
				}
			} finally {
				await hub.aufraeumen();
			}
		});

		// VB-3 (Alt AC-4, umformuliert) — fängt: Überschrift zurück auf Rhythmus-Sprache.
		test(`VB-3 (${kind}): Versand-Abschnitt zeigt „Briefing-Zeitplan" mit Morgen-/Abend-Briefing, keine Rhythmus-Sprache`, async ({
			page
		}) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedHub(page.request, kind, { extra: SEED[kind] });
			try {
				await openHub(page, kind, hub.id);
				await page.locator(`[data-testid="${sel.reiter}-wetter-metriken"]:visible`).first().click();
				const abschnitt = page.locator('[data-testid="versand-abschnitt"]:visible').first();
				await expect(abschnitt).toBeVisible({ timeout: 10_000 });
				// Ist-Texte der geteilten Bausteine (VTBriefingChannels / VTSchedulePlan).
				await expect(abschnitt).toContainText('Geplantes Briefing · Kanäle');
				await expect(abschnitt).toContainText('Briefing-Zeitplan');
				await expect(abschnitt).toContainText('Morgen-Briefing');
				await expect(abschnitt).toContainText('Abend-Briefing');
				await expect(abschnitt).not.toContainText('Rhythmus & Vorausschau');
				await expect(abschnitt).not.toContainText('Zeitfenster');
				// Stundenbereich nur im vergleich-Zweig: nur der Vergleichs-Seed trägt
				// hour_from/hour_to; ohne Gegenstand wäre die Negativprüfung unfangbar
				// (Spec „Kind-Kontraste", Zeile Stundenbereich).
				if (kind === 'vergleich') await expect(abschnitt).not.toContainText('7–16 Uhr');
			} finally {
				await hub.aufraeumen();
			}
		});

		// VB-4 (Alt Fix-Loop 1) — fängt: roher Stundenbereich/Rhythmus-Sprache in der Übersicht.
		test(`VB-4 (${kind}): Übersicht-Panel ohne Rhythmus-Sprache`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedHub(page.request, kind, { extra: SEED[kind] });
			try {
				await openHub(page, kind, hub.id);
				const p = panel(page, kind, 'uebersicht');
				await expect(p).toBeVisible({ timeout: 10_000 });
				await expect(p).not.toContainText('Rhythmus');
				await expect(p).not.toContainText('Zeitfenster');
				// Nur vergleich: Stundenbereich (nur dort geseedet, s. VB-3) und „Zeitplan" —
				// der Trip trägt legitim „Zeitplan bearbeiten →" (HubOverview.svelte).
				if (kind === 'vergleich') {
					await expect(p).not.toContainText('7–16 Uhr');
					await expect(p).not.toContainText('Zeitplan');
				}
			} finally {
				await hub.aufraeumen();
			}
		});

		// VB-5 (Alt AC-5) — fängt: Sprungziel falsch bzw. Seitenwechsel nach /edit.
		test(`VB-5 (${kind}): „Bearbeiten →" der Versand-Karte wechselt inline auf den Versand-Abschnitt`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedHub(page.request, kind, { extra: SEED[kind] });
			try {
				await openHub(page, kind, hub.id);
				await expect(panel(page, kind, 'uebersicht')).toBeVisible({ timeout: 10_000 });
				// Selektor-Tabelle (Spec „Kind-Kontraste", Zeile „Bearbeiten →"): gleicher Zielvertrag.
				const knopf =
					kind === 'vergleich'
						? page.locator('[data-testid="compare-hub-versand-edit"]:visible').first()
						: page.locator('[data-testid="hub-overview"]:visible').getByRole('button', { name: 'Zeitplan bearbeiten →' });
				await knopf.click();

				await expect(panel(page, kind, 'wetter-metriken')).toBeVisible({ timeout: 10_000 });
				await expect(page.locator('[data-testid="versand-abschnitt"]:visible').first()).toBeInViewport({ timeout: 10_000 });
				await expect(page).toHaveURL(sel.hubUrl(hub.id));
				expect(page.url()).not.toMatch(/\/edit/);
			} finally {
				await hub.aufraeumen();
			}
		});

		// VB-6 (Alt AC-6) — fängt: Absturz bzw. leere Seite bei unbekanntem Reiter.
		test(`VB-6 (${kind}): unbekannter ?tab=-Wert → Übersicht aktiv, kein Absturz; ohne ?tab= ebenfalls`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedHub(page.request, kind, { extra: SEED[kind] });
			try {
				// bewusst page.goto (openHub wartet auf den Reiter des ?tab=-Werts)
				await page.goto(`${basis(kind, hub.id)}?tab=doesnotexist`);
				await expect(panel(page, kind, 'uebersicht')).toBeVisible({ timeout: 10_000 });

				await page.goto(basis(kind, hub.id));
				await expect(panel(page, kind, 'uebersicht')).toBeVisible({ timeout: 10_000 });
			} finally {
				await hub.aufraeumen();
			}
		});

		// VB-7 — nur vergleich: Ranking-Neutralität betrifft nur den Ortsvergleich;
		// der Text steht nur in dessen Übersicht (CompareTabs.svelte Idealwerte-Karte).
		// Spec „Kind-Kontraste", Zeile „Kein Score, kein Ranking".
		if (kind === 'vergleich') {
			test(`VB-7 (${kind}): Idealwerte-Karte zeigt „Kein Score, kein Ranking", nicht „bestimmen das Ranking"`, async ({ page }) => {
				await page.setViewportSize(DESKTOP);
				const hub = await seedHub(page.request, kind, { extra: SEED[kind] });
				try {
					await openHub(page, kind, hub.id);
					const p = panel(page, kind, 'uebersicht');
					await expect(p).toContainText('Kein Score, kein Ranking', { timeout: 10_000 });
					await expect(p).not.toContainText('bestimmen das Ranking');
				} finally {
					await hub.aufraeumen();
				}
			});
		}

		// VB-8 (Alt AC-10) — fängt: Reiter ohne Panel bzw. Versand-/Vorschau-Reiter zurück.
		test(`VB-8 (${kind}): alle fünf Reiter klickbar, Panel je sichtbar; kein Versand-/Vorschau-Reiter`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedHub(page.request, kind, { extra: SEED[kind] });
			try {
				await openHub(page, kind, hub.id);
				// Reihenfolge = shared/subscriptionTabs.ts; Punkte-Reiter je kind aus HUB_SEL.
				for (const tab of ['uebersicht', sel.punkteReiter, 'wetter-metriken', 'wertebereiche', 'alarme']) {
					await page.locator(`[data-testid="${sel.reiter}-${tab}"]:visible`).first().click();
					await expect(panel(page, kind, tab), `Panel ${tab} sichtbar`).toBeVisible({ timeout: 10_000 });
				}
				await expect(page.locator(`[data-testid="${sel.reiter}-versand"]`)).toHaveCount(0);
				await expect(page.locator(`[data-testid="${sel.reiter}-vorschau"]`)).toHaveCount(0);
			} finally {
				await hub.aufraeumen();
			}
		});

		// VB-9 (Alt Edge Case „Draft ohne Slots → —") — fängt: „—"-Zweig fehlt bzw.
		// Inaktiv-Farbe des Punkts gleich der Aktiv-Farbe.
		test(`VB-9 (${kind}): beide Slots abschalten → Übersicht zeigt den Slot-aus-Zustand`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedHub(page.request, kind, { extra: SEED[kind] });
			try {
				await openHub(page, kind, hub.id);
				await expect(panel(page, kind, 'uebersicht')).toBeVisible({ timeout: 10_000 });
				// Ausgangszustand je kind (Übersicht-Format, Kopfkommentar).
				let vorherFarbe = '';
				if (kind === 'vergleich') {
					await expect(page.locator('[data-testid="compare-detail-stat-briefings"]:visible').first()).toHaveText(STAT, {
						timeout: 10_000
					});
				} else {
					await pruefeTripKarte(page);
					vorherFarbe = await hintergrund(zeile(tripKarte(page), 'Morgen-Briefing').punkt);
				}

				// Beide Slots im Versand-Abschnitt abschalten (echte Geste, Autosave).
				await openHub(page, kind, hub.id, { tab: 'wetter-metriken', hash: 'versand' });
				const abschnitt = page.locator('[data-testid="versand-abschnitt"]:visible');
				for (const slot of ['morning', 'evening']) {
					const schalter = abschnitt.locator(`[data-testid="${slot}-master-switch"] input[type="checkbox"]`);
					await expect(schalter, `Vorbedingung: ${slot}-Slot an`).toBeChecked({ timeout: 10_000 });
					await schalter.click();
					await expect(schalter).not.toBeChecked();
				}
				await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await expect
					.poll(
						async () => {
							const s = (await (await page.request.get(hubApiPath(kind, hub.id))).json()) as Record<string, unknown>;
							// Feldpfad je kind (Spec „Kind-Kontraste"): Trip report_config, Vergleich oben.
							const quelle = kind === 'route' ? ((s.report_config as Record<string, unknown> | undefined) ?? {}) : s;
							return [quelle.morning_enabled, quelle.evening_enabled];
						},
						{ timeout: 10_000, message: 'beide Slots sind im Server-Stand aus' }
					)
					.toEqual([false, false]);

				await openHub(page, kind, hub.id);
				await expect(panel(page, kind, 'uebersicht')).toBeVisible({ timeout: 10_000 });
				if (kind === 'vergleich') {
					// exakt „—": nicht leer, kein verwaister Trennpunkt
					await expect(page.locator('[data-testid="compare-detail-stat-briefings"]:visible').first()).toHaveText('—', {
						timeout: 10_000
					});
				} else {
					// Trip-Ist-Format: kein „—", beide Zeilen bleiben mit ihrer Zeit stehen,
					// die Punkte wechseln von der Aktiv- auf die Inaktiv-Farbe.
					const karte = tripKarte(page);
					await expect(karte).toBeVisible({ timeout: 10_000 });
					await expect(karte).not.toContainText('—');
					const morgen = zeile(karte, 'Morgen-Briefing');
					const abend = zeile(karte, 'Abend-Briefing');
					await expect(morgen.zeit).toHaveText(MORGEN);
					await expect(abend.zeit).toHaveText(ABEND);
					const aus = await tokenFarbe(page, '--g-rule');
					expect(await hintergrund(morgen.punkt), 'Morgen-Punkt in Inaktiv-Farbe').toBe(aus);
					expect(await hintergrund(abend.punkt), 'Abend-Punkt in Inaktiv-Farbe').toBe(aus);
					expect(await hintergrund(morgen.punkt), 'Inaktiv- und Aktiv-Farbe unterscheiden sich').not.toBe(vorherFarbe);
				}
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}

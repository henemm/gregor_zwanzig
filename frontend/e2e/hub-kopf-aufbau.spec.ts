// E2E — Issue #2347 S2 (Epic #2345, Etappe P6): Hub-Kopf — Markup und
// Bedienung des geteilten Bausteins SubscriptionHeader — EINE Zusicherung für
// BEIDE Hubs (Trip und Ortsvergleich) per Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s2_paritaets_e2e.md § „Neue Specs“ (KA-1..KA-9), AC-3, AC-11
//
// Ersetzt Fälle zweier entfernter Compare-Altdateien (Kopf-Markup/-Bedienung und
// #2283 AC-13 „Senden nur im Hub-Kopf"); Zuordnung alt → neu: Spec-Tabelle Zeilen
// 13-14, 18-23, 41.
//
// KA-6..KA-9 laufen NUR für `vergleich` (Orte-Anzahl = fachlich verschieden). Seit #2837 S1
// (ADR-0110) UMGEDREHT: die Mobil-Eyebrow „Orts-Vergleich · Hub“ und der Krümel „Hub“
// entfallen; der Breadcrumb „Orts-Vergleiche / <Name>“ kommt aus dem geteilten HubKopf
// (Parität beider Arten: hub-kopf-paritaet-compare-trip.spec.ts).
// Das Trip-Gegenstück („Eyebrow nur Datum“) bleibt in
// trip-hub-kopf-region-aktivitaet.spec.ts AC-2.
//
// KA-5 fängt JEDEN Sende-Abruf (`/api/briefings/<id>/send…`) per page.route ab
// und beantwortet ihn selbst — es findet nie ein echter Versand statt.
// KA-5b (#2347 S3b) ergänzt Desktop + „Körper ohne Empfänger" (Alt
// compare-hub-versand-inline #2283; Spec feat_2347_s3b_paritaets_e2e.md „Frage 2").
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh) bzw. gegen Staging,
// Anmeldung über den storageState aus global.setup.ts (Admin-Sitzung).
// Wegwerf-Daten räumt jeder Fall im `finally` ab (max. 2 aktive Vergleiche je Nutzer).

import { test, expect, type Page } from '@playwright/test';
import {
	createTestLocation,
	HUB_KINDS,
	HUB_KOPF_SEL,
	HUB_SEL,
	hubApiPath,
	openHub,
	seedHub,
	testMitZustellbaremZiel,
	type HubKind,
	type SeededHub
} from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 375, height: 812 };
// Viewport des Altfalls #2283 AC-13 (Spec-Zuordnung Zeile 41).
const MOBIL_SENDEN = { width: 390, height: 844 };

// Wertevorrat des Profils je kind (Selektor-Unterschied): Trip `activity`
// mit 8 Werten (ACTIVITY_TYPE_OPTIONS), Vergleich `profil` mit 4 Werten.
const PROFIL_WERTE: Record<HubKind, readonly string[]> = {
	route: ['trekking', 'skitour', 'hochtour', 'klettersteig', 'mtb', 'fahrrad_15', 'fahrrad_20', 'fahrrad_25'],
	vergleich: ['allgemein', 'wintersport', 'wandern', 'summer_trekking']
};

// Seed-Startwerte je kind. Vergleich behält das Standard-Profil `wandern` aus
// helpers.seedHub (die Unterzeile „Wandern · 2 Orte“ der Altfälle hängt daran);
// der Trip bekommt Aktivität und Region explizit (Feldpfad Trip `region`,
// Vergleich `display_config.region`).
const REGION = 'Ötztal';
const START: Record<HubKind, { profil: string; extra: Record<string, unknown> }> = {
	route: { profil: 'trekking', extra: { activity: 'trekking', region: REGION } },
	vergleich: { profil: 'wandern', extra: { display_config: { region: REGION } } }
};

function seedKopf(page: Page, kind: HubKind, extra: Record<string, unknown> = {}): Promise<SeededHub> {
	return seedHub(page.request, kind, { extra: { ...START[kind].extra, ...extra } });
}

async function holeStand(page: Page, kind: HubKind, id: string): Promise<Record<string, unknown>> {
	const pfad = hubApiPath(kind, id);
	const res = await page.request.get(pfad);
	expect(res.ok(), `GET ${pfad} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Record<string, unknown>;
}

function regionAus(kind: HubKind, s: Record<string, unknown>): unknown {
	return kind === 'route' ? s.region : (s.display_config as Record<string, unknown> | undefined)?.region;
}

function sicht(page: Page, kind: HubKind, rest: string) {
	return page.locator(`[data-testid="${HUB_SEL[kind].kopf}-${rest}"]:visible`);
}

function abbrechen(page: Page) {
	return page.getByRole('button', { name: /^(Abbrechen|×)$/ }).filter({ visible: true }).first().click();
}

/** Kopf-Bedienelemente je kind: beide Stifte + jede Profil-Kachel. */
function kopfIds(kind: HubKind): string[] {
	const { kopf } = HUB_SEL[kind];
	return [`${kopf}-name-edit-toggle`, `${kopf}-region-edit-toggle`, ...PROFIL_WERTE[kind].map((v) => `${kopf}-profil-option-${v}`)];
}

/** Vergleich-Meta-Zeile seit #2913 c2 (AC-4): „2 Orte · Vergleichstabelle[ · Briefing HH:MM]“ (vorher „Wandern · 2 Orte“). */
function vergleichUnterzeile(page: Page) {
	return page.getByText(/2 Orte\s*·\s*Vergleichstabelle|Wandern\s*·\s*2 Orte/).filter({ visible: true }).first();
}

/** Region-Text in der Region-Zeile (Elternelement des Stifts), für beide kinds. */
function regionText(page: Page) {
	return page.locator('span:visible', { hasText: new RegExp(`^\\s*${REGION}\\s*$`) });
}

/**
 * Orte-Anzahl des Vergleichs-Rahmens. #2913 c2 (Mockup): EINE Meta-Zeile `hub-kopf-meta`
 * „N Orte · Vergleichstabelle · …" für beide Breiten (Zähler = gespeicherte IDs); die früheren
 * Viewport-Spans existieren nicht mehr.
 * Compare-eigen (siehe Kopfkommentar) — wird nur im Zweig `vergleich` aufgerufen.
 */
async function pruefeOrteAnzahlSpans(page: Page, _viewport: 'desktop' | 'mobil'): Promise<void> {
	for (const alt of ['compare-hub-orte-anzahl', 'compare-hub-orte-anzahl-desktop', 'compare-hub-orte-anzahl-mobil'])
		expect(await page.locator(`[data-testid="${alt}"]`).count(), `alte testid ${alt}`).toBe(0);
	const meta = page.getByTestId('hub-kopf-meta');
	expect(await meta.count(), 'hub-kopf-meta: Anzahl im DOM').toBe(1);
	await expect(meta).toBeVisible();
	await expect(meta).toHaveText(/^\d+ Orte? · Vergleichstabelle\b/);
}

/** Bearbeiten-Modus: Eingabe und Speichern-Knopf ebenfalls genau einmal im DOM. */
async function pruefeEditEinmal(page: Page, kind: HubKind): Promise<void> {
	const { kopf } = HUB_SEL[kind];
	await page.locator(`[data-testid="${kopf}-name-edit-toggle"]:visible`).click();
	for (const id of [`${kopf}-name-edit`, `${kopf}-name-save`]) {
		const loc = page.locator(`[data-testid="${id}"]`);
		await expect(loc.filter({ visible: true }).first()).toBeVisible();
		expect(await loc.count(), `${id}: Anzahl im DOM (ohne :visible)`).toBe(1);
	}
}

// ─── KA-1 ──────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`KA-1 (${kind}): Desktop — jede Kopf-testid genau einmal im DOM und sichtbar`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind);
		try {
			await openHub(page, kind, hub.id);
			for (const id of kopfIds(kind)) {
				const loc = page.locator(`[data-testid="${id}"]`);
				await expect(loc.filter({ visible: true }).first()).toBeVisible({ timeout: 10_000 });
				// Zählung bewusst OHNE :visible — sonst bliebe eine ausgeblendete Zweitinstanz unsichtbar.
				expect(await loc.count(), `${id}: Anzahl im DOM (ohne :visible)`).toBe(1);
				await expect(loc).toBeVisible();
			}
			// Compare-eigener Rahmen (Orte-Anzahl gibt es nur im Vergleich).
			if (kind === 'vergleich') await pruefeOrteAnzahlSpans(page, 'desktop');
			await pruefeEditEinmal(page, kind);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KA-2 ──────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`KA-2 (${kind}): Mobil 375 — jede Kopf-testid genau einmal im DOM, Knopf + Auswahl statt Kacheln`, async ({
		page
	}) => {
		await page.setViewportSize(MOBIL);
		const hub = await seedKopf(page, kind);
		const { kopf } = HUB_SEL[kind];
		try {
			await openHub(page, kind, hub.id);
			for (const id of kopfIds(kind)) {
				const loc = page.locator(`[data-testid="${id}"]`);
				expect(await loc.count(), `${id}: Anzahl im DOM (ohne :visible)`).toBe(1);
				if (id.startsWith(`${kopf}-profil-option-`)) {
					await expect(loc, `${id}: Kachel ist auf dem Handy sichtbar (Knopf statt Kacheln)`).toBeHidden();
				} else {
					await expect(loc).toBeVisible({ timeout: 10_000 });
				}
			}
			const knopf = page.locator(`[data-testid="${kopf}-profil-knopf"]`);
			const auswahl = page.locator(`[data-testid="${kopf}-profil-auswahl"]`);
			await expect(knopf, `${kopf}-profil-knopf: auf dem Handy nicht sichtbar`).toBeVisible({ timeout: 10_000 });
			expect(await knopf.count(), `${kopf}-profil-knopf: Anzahl im DOM (ohne :visible)`).toBe(1);
			expect(await auswahl.count(), `${kopf}-profil-auswahl: Anzahl im DOM (ohne :visible)`).toBe(1);
			await expect(knopf).toHaveAttribute('data-selected-value', START[kind].profil);
			for (const v of PROFIL_WERTE[kind]) {
				const opt = page.locator(`[data-testid="${kopf}-profil-auswahl-option-${v}"]`);
				expect(await opt.count(), `${kopf}-profil-auswahl-option-${v}: Anzahl im DOM (ohne :visible)`).toBe(1);
			}
			// Compare-eigener Rahmen (Orte-Anzahl gibt es nur im Vergleich).
			if (kind === 'vergleich') await pruefeOrteAnzahlSpans(page, 'mobil');
			await pruefeEditEinmal(page, kind);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KA-3 ──────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	for (const [label, viewport] of [
		['Desktop 1280', DESKTOP],
		['Mobil 375', MOBIL]
	] as const) {
		test(`KA-3 (${kind}, ${label}): Region höchstens 60 Zeichen, Unterzeile während der Bearbeitung weg`, async ({
			page
		}) => {
			await page.setViewportSize(viewport);
			const hub = await seedKopf(page, kind);
			try {
				await openHub(page, kind, hub.id);
				await expect(regionText(page).first(), 'Vorbedingung: Region steht in der Unterzeile').toBeVisible({
					timeout: 10_000
				});
				// Compare-eigene Unterzeile (Profil-Label + Orte-Anzahl); der Trip zeigt dort nur die Region.
				if (kind === 'vergleich') await expect(vergleichUnterzeile(page)).toBeVisible();

				await sicht(page, kind, 'region-edit-toggle').click();
				const eingabe = sicht(page, kind, 'region-edit');
				await expect(eingabe).toHaveAttribute('maxlength', '60');
				await eingabe.fill('');
				await eingabe.pressSequentially('x'.repeat(61));
				expect((await eingabe.inputValue()).length).toBe(60);
				await expect(regionText(page), 'Unterzeile (Region) während der Bearbeitung weg').toHaveCount(0);
				if (kind === 'vergleich') await expect(page.locator('span:visible', { hasText: /2 Orte/ })).toHaveCount(0);

				await abbrechen(page);
				await expect(regionText(page).first()).toBeVisible();
				if (kind === 'vergleich') await expect(vergleichUnterzeile(page)).toBeVisible();
			} finally {
				await hub.aufraeumen();
			}
		});
	}
}

// ─── KA-4 ──────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`KA-4 (${kind}): Desktop-Bedienung — Vorbelegung, Kacheln gesperrt während Speichern, Fallback-Texte, Abbrechen verwirft Fehler`, async ({
		page
	}) => {
		test.setTimeout(60_000);
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind);
		const pfad = hubApiPath(kind, hub.id);
		const { kopf, profilFeld } = HUB_SEL[kind];
		const ziel = PROFIL_WERTE[kind].find((v) => v !== START[kind].profil) as string;
		try {
			const name = (await holeStand(page, kind, hub.id)).name as string;
			await openHub(page, kind, hub.id);

			// Stift öffnen ⇒ Feld trägt den aktuellen Wert.
			await sicht(page, kind, 'name-edit-toggle').click();
			await expect(sicht(page, kind, 'name-edit')).toHaveValue(name);
			await abbrechen(page);
			await sicht(page, kind, 'region-edit-toggle').click();
			await expect(sicht(page, kind, 'region-edit')).toHaveValue(REGION);
			await abbrechen(page);

			// Profil-PUT hängt ⇒ alle Kacheln gesperrt, bis die Antwort kommt.
			let freigeben: () => void = () => {};
			const gehalten = new Promise<void>((r) => (freigeben = r));
			await page.route(`**${pfad}`, async (route) => {
				if (route.request().method() !== 'PUT') return route.continue();
				await gehalten;
				return route.continue();
			});
			await sicht(page, kind, `profil-option-${ziel}`).click();
			for (const v of PROFIL_WERTE[kind]) {
				await expect(sicht(page, kind, `profil-option-${v}`)).toBeDisabled();
			}
			freigeben();
			await expect(sicht(page, kind, `profil-option-${ziel}`)).toHaveAttribute('data-selected', 'true', {
				timeout: 5_000
			});
			await expect(sicht(page, kind, `profil-option-${START[kind].profil}`)).toBeEnabled();
			await page.unroute(`**${pfad}`);
			await expect
				.poll(async () => (await holeStand(page, kind, hub.id))[profilFeld], { timeout: 8_000 })
				.toBe(ziel);

			// 500 ohne `error` im Rumpf ⇒ Fallback-Meldung „Speichern fehlgeschlagen“.
			await page.route(`**${pfad}`, (route) =>
				route.request().method() === 'PUT'
					? route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
					: route.continue()
			);
			await sicht(page, kind, 'region-edit-toggle').click();
			await sicht(page, kind, 'region-edit').fill('Wallis');
			await sicht(page, kind, 'region-save').click();
			await expect(sicht(page, kind, 'region-save-error')).toHaveText('Speichern fehlgeschlagen', { timeout: 5_000 });

			// Abbrechen verwirft den Fehler; erneut öffnen ⇒ kein Fehler, alter Wert.
			await abbrechen(page);
			await expect(page.locator(`[data-testid="${kopf}-region-save-error"]`)).toHaveCount(0);
			await sicht(page, kind, 'region-edit-toggle').click();
			await expect(page.locator(`[data-testid="${kopf}-region-save-error"]`)).toHaveCount(0);
			await expect(sicht(page, kind, 'region-edit')).toHaveValue(REGION);
			await page.unroute(`**${pfad}`);

			// Leere Region ⇒ Fallback-Text „—“ in der Region-Zeile, auch nach dem Neuladen.
			await sicht(page, kind, 'region-edit').fill('');
			const antwort = page.waitForResponse(
				(r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === pfad
			);
			await sicht(page, kind, 'region-save').click();
			expect((await antwort).ok()).toBeTruthy();
			const regionZeile = () => sicht(page, kind, 'region-edit-toggle').locator('xpath=..');
			await expect(regionZeile().locator('span').first()).toHaveText('—', { timeout: 5_000 });
			expect(regionAus(kind, await holeStand(page, kind, hub.id)) ?? '').toBe('');
			await page.reload();
			await expect(regionZeile().locator('span').first()).toHaveText('—', { timeout: 10_000 });
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KA-5 ──────────────────────────────────────────────────────────────────
// Vorbedingung „zustellbares Ziel": der Sende-Dialog sperrt „Senden" ohne
// bestätigte Konto-Adresse (sendTargetLabel.ts), der Env-Admin des CI-Stacks
// hat keine. Deshalb läuft KA-5 als bestätigter Zweitnutzer
// (testMitZustellbaremZiel, helpers.ts) — der Admin bleibt unberührt.
for (const kind of HUB_KINDS) {
	testMitZustellbaremZiel(`KA-5 (${kind}): Mobil — Versand-Abschnitt ohne Test-Senden, Hub-Kopf-„Senden“ öffnet den Dialog und löst genau EINEN Sende-Abruf aus`, async ({
		page
	}) => {
		await page.setViewportSize(MOBIL_SENDEN);
		// Seed-Besonderheit (kind-Zweig nur für den Seed): die e2e-loc-* aus
		// global.setup.ts gehören dem Admin — der Zweitnutzer bekommt eigene Orte.
		const orte =
			kind === 'vergleich'
				? [await createTestLocation(page.request, { name: 'KA5-A' }), await createTestLocation(page.request, { name: 'KA5-B' })]
				: [];
		const hub = await seedKopf(page, kind, orte.length ? { location_ids: orte.map((o) => o.id) } : {});
		try {
			// Jeder Sende-Abruf (gleich welche ID/Query) wird abgefangen und selbst
			// beantwortet — kein echter Versand. Gezählt wird gesamt UND der erwartete.
			const sende: string[] = [];
			await page.route(/\/api\/briefings\/[^/]+\/send(\?|$)/, async (route) => {
				sende.push(route.request().url());
				await route.fulfill({ status: 200, json: { status: 'queued' } });
			});
			// Trip hängt `&report_type=…` an (sendOutcome.briefingSendUrl), der Vergleich nicht.
			const erwartet = new RegExp(`/api/briefings/${hub.id}/send\\?kind=${kind}(&report_type=(morning|evening))?$`);

			await openHub(page, kind, hub.id, { tab: 'zustellung' }); // #2795 S3b 1b: Reiter Zustellung (ersetzt den Versand-Abschnitt)
			const panel = page.locator('[data-testid="zustellung-tab"]:visible');
			await expect(panel).toBeVisible({ timeout: 10_000 });
			await expect(panel.locator('[data-testid$="-activation-testsend"]')).toHaveCount(0);
			await expect(panel.getByRole('button', { name: /Test-Briefing/ })).toHaveCount(0);

			const kopfSenden = page.locator('[data-testid="subscription-hub-send"]:visible');
			await expect(kopfSenden).toBeInViewport();
			// #2837 S1: „Senden“ sitzt in der Leiste ganz oben (HubKopf), bei beiden Arten.
			await expect(page.getByTestId(HUB_KOPF_SEL.leiste).locator('[data-testid="subscription-hub-send"]:visible')).toHaveCount(1);
			await kopfSenden.click();
			await expect(page.getByTestId('send-confirm-dialog')).toBeVisible();
			expect(sende.length, 'das Öffnen des Dialogs sendet nichts').toBe(0);
			await page.getByTestId('send-confirm-yes').click();

			// Genau EIN Abruf: die Zahl bleibt 1,5 s lang stabil bei 1 (kein Schlaf).
			let seit = 0;
			await expect
				.poll(
					() => {
						if (sende.length !== 1) {
							seit = 0;
							return sende.length;
						}
						seit ||= Date.now();
						return Date.now() - seit >= 1_500 ? 'stabil' : 1;
					},
					{ message: 'KA-5: „Senden“ im Hub-Kopf muss genau EINEN Sende-Abruf auslösen', timeout: 10_000, intervals: [200] }
				)
				.toBe('stabil');
			expect(sende[0], `KA-5: Sende-Abruf geht an diesen ${kind}`).toMatch(erwartet);
		} finally {
			await hub.aufraeumen();
			for (const o of orte) await page.request.delete(`/api/locations/${o.id}`).catch(() => {});
		}
	});
}

// ─── KA-5b ─────────────────────────────────────────────────────────────────
// #2347 S3b (Spec feat_2347_s3b_paritaets_e2e.md, „Frage 2", AC-5): schließt die
// zwei Lücken von KA-5 gegenüber dem Alt-Fall #2283 aus compare-hub-versand-inline
// (:384-419) — Desktop-Viewport und „der Sende-Abruf trägt KEINE Empfänger im
// Körper" (kein systemseitiges „an mich": der Server sendet an die konfigurierten
// Empfänger dieses Nutzers). Gleiche Vorbedingung wie KA-5 (Zweitnutzer).
for (const kind of HUB_KINDS) {
	testMitZustellbaremZiel(`KA-5b (${kind}): Desktop — Hub-Kopf-„Senden“ löst genau EINEN Sende-Abruf an diesen ${kind} aus, ohne Empfänger im Körper`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		// Seed-Besonderheit wie KA-5: der Zweitnutzer bekommt für den Vergleich eigene Orte.
		const orte =
			kind === 'vergleich'
				? [await createTestLocation(page.request, { name: 'KA5b-A' }), await createTestLocation(page.request, { name: 'KA5b-B' })]
				: [];
		const hub = await seedKopf(page, kind, orte.length ? { location_ids: orte.map((o) => o.id) } : {});
		try {
			// Jeder Sende-Abruf wird abgefangen und selbst beantwortet — kein echter Versand.
			const sende: { url: string; koerper: string }[] = [];
			await page.route(/\/api\/briefings\/[^/]+\/send(\?|$)/, async (route) => {
				sende.push({ url: route.request().url(), koerper: route.request().postData() ?? '' });
				await route.fulfill({ status: 200, json: { status: 'queued' } });
			});
			const erwartet = new RegExp(`/api/briefings/${hub.id}/send\\?kind=${kind}(&report_type=(morning|evening))?$`);

			await openHub(page, kind, hub.id, { tab: 'zustellung' }); // #2795 S3b 1b: Reiter Zustellung (ersetzt den Versand-Abschnitt)
			const panel = page.locator('[data-testid="zustellung-tab"]:visible');
			await expect(panel).toBeVisible({ timeout: 10_000 });
			await expect(panel.getByRole('button', { name: /Test-Briefing/ })).toHaveCount(0);

			const kopfSenden = page.locator('[data-testid="subscription-hub-send"]:visible');
			await expect(kopfSenden).toBeVisible();
			// #2837 S1: „Senden“ sitzt in der Leiste ganz oben (HubKopf), bei beiden Arten.
			await expect(page.getByTestId(HUB_KOPF_SEL.leiste).locator('[data-testid="subscription-hub-send"]:visible')).toHaveCount(1);
			await kopfSenden.click();
			await expect(page.getByTestId('send-confirm-dialog')).toBeVisible();
			expect(sende.length, 'das Öffnen des Dialogs sendet nichts').toBe(0);
			await page.getByTestId('send-confirm-yes').click();

			let seit = 0;
			await expect
				.poll(
					() => {
						if (sende.length !== 1) {
							seit = 0;
							return sende.length;
						}
						seit ||= Date.now();
						return Date.now() - seit >= 1_500 ? 'stabil' : 1;
					},
					{ message: 'KA-5b: „Senden“ im Hub-Kopf muss genau EINEN Sende-Abruf auslösen', timeout: 10_000, intervals: [200] }
				)
				.toBe('stabil');
			expect(sende[0].url, `KA-5b: Sende-Abruf geht an diesen ${kind} (kind-Parameter)`).toMatch(erwartet);
			expect(sende[0].koerper, 'der Sende-Abruf darf keine Empfänger vom Client mitschicken').not.toMatch(/@/);
		} finally {
			await hub.aufraeumen();
			for (const o of orte) await page.request.delete(`/api/locations/${o.id}`).catch(() => {});
		}
	});
}

// ─── KA-10, KA-11 (#2347 S4): Rückweg vom Hub zur Liste ─────────────────────
// Ersatz für compare-flow-navigation AC-28 (Desktop-Breadcrumb, mobiler
// Zurück-Pfeil). Krümel-Beschriftung je kind (Trip „Trips", Vergleich
// „Orts-Vergleiche"); Zusicherung gleich: Klick führt zur Liste dieser Art.
// #2837 S1 (ADR-0110): UMGEDREHT von „ORTS-VERGLEICHE" (Versalien im Markup) auf den
// Katalog-Wortlaut im geteilten Breadcrumb des HubKopf — für beide Arten derselbe Ort.
const KRUEMEL: Record<HubKind, (page: Page) => ReturnType<Page['locator']>> = {
	route: (page) => page.getByTestId(HUB_KOPF_SEL.breadcrumb).getByRole('link', { name: 'Trips', exact: true }),
	// #2913 c2 (Mockup): Elternteil „Orte" statt „Orts-Vergleiche".
	vergleich: (page) => page.getByTestId(HUB_KOPF_SEL.breadcrumb).getByRole('link', { name: /^Orte$/i })
};

for (const kind of HUB_KINDS) {
	test(`KA-10 (${kind}): Desktop — Breadcrumb-Klick führt zur Liste`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind);
		try {
			await openHub(page, kind, hub.id);
			const kruemel = KRUEMEL[kind](page).filter({ visible: true }).first();
			await expect(kruemel, 'KA-10: Breadcrumb zur Liste fehlt').toBeVisible({ timeout: 10_000 });
			await kruemel.click();
			await expect.poll(() => new URL(page.url()).pathname, { message: 'KA-10: Breadcrumb führt nicht zur Liste' }).toBe(
				HUB_SEL[kind].liste.url
			);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`KA-11 (${kind}): Mobil — Zurück-Pfeil führt zur Liste`, async ({ page }) => {
		await page.setViewportSize(MOBIL);
		const hub = await seedKopf(page, kind);
		try {
			await openHub(page, kind, hub.id);
			const zurueck = page.locator('[aria-label^="Zurück"]:visible').first();
			await expect(zurueck, 'KA-11: mobiler Zurück-Pfeil fehlt').toBeVisible({ timeout: 10_000 });
			await zurueck.click();
			await expect.poll(() => new URL(page.url()).pathname, { message: 'KA-11: Zurück-Pfeil führt nicht zur Liste' }).toBe(
				HUB_SEL[kind].liste.url
			);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KA-6..KA-9: nur vergleich ─────────────────────────────────────────────
// Begründung: Eyebrow, Breadcrumb und Orte-Anzahl gehören zum Rahmen des
// Orts-Vergleichs (compare/[id]/+page.svelte), nicht zum geteilten Kopf; das
// Trip-Gegenstück bleibt in trip-hub-kopf-region-aktivitaet.spec.ts AC-2.
test.describe('KA-6..KA-9 (vergleich, compare-eigen)', () => {
	const kind: HubKind = 'vergleich';

	// #2837 S1 (ADR-0110, Entscheidung 4) — UMGEDREHT: die Mobil-Eyebrow „Orts-Vergleich · Hub“
	// entfällt (Trip hat keine); Unterzeile und „kein · ·“ bleiben.
	test('KA-6 (vergleich): Mobil — keine Eyebrow „Orts-Vergleich · Hub“, Unterzeile „Wandern · 2 Orte“, kein „· ·“', async ({
		page
	}) => {
		await page.setViewportSize(MOBIL);
		const hub = await seedKopf(page, kind);
		try {
			await openHub(page, kind, hub.id);
			await expect(page.getByText(/Orts-Vergleich\s*·\s*Hub/i), 'KA-6: Mobil-Eyebrow „Orts-Vergleich · Hub“ steht noch').toHaveCount(0);
			await expect(vergleichUnterzeile(page)).toBeVisible();
			await expect(page.getByText(/·\s*·/)).toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});

	// #2837 S1 (ADR-0110, Entscheidung 4) — UMGEDREHT: Breadcrumb „Orts-Vergleiche / <Name>“
	// statt „ORTS-VERGLEICHE / Hub“; genau zwei Krümel bleiben, das Kind ist der
	// Vergleichsname und kein Link, „Hub“ kommt im Kopf nicht mehr vor.
	// #2913 c2: Elternteil „Orte" (Mockup); die alte Eyebrow „Orts-Vergleich · Hub" bleibt weg,
	// die neue Eyebrow „Orte · Region" prüft hub-kopf-c2-mockup.staging.spec.ts.
	test('KA-7 (vergleich): Desktop — keine alte Eyebrow „Orts-Vergleich · Hub“, Breadcrumb „Orte / <Name>“, Unterzeile mit Profil', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind);
		try {
			await openHub(page, kind, hub.id);
			const name = ((await (await page.request.get(hubApiPath(kind, hub.id))).json()) as { name: string }).name;
			await expect(page.getByText(/Orts-Vergleich\s*·\s*Hub/i)).toHaveCount(0);
			const krumen = page.getByTestId(HUB_KOPF_SEL.breadcrumb);
			await expect(krumen).toBeVisible();
			await expect(krumen.getByText('Hub', { exact: true }), 'KA-7: Krümel „Hub“ steht noch').toHaveCount(0);
			await expect(page.getByTestId(HUB_KOPF_SEL.leiste).getByText('Hub', { exact: true })).toHaveCount(0);
			// #2347 S4, Rumpf-Abgleich compare-hub-fidelity-s8c AC-10: genau ZWEI Krümel —
			// ein Link „Orte", kein app-weiter Extra-Krümel „WORKSPACE".
			const kruemel = krumen.locator('a:visible');
			await expect(kruemel, 'KA-7: Breadcrumb hat nicht genau einen Link-Krümel').toHaveCount(1);
			await expect(kruemel).toHaveText('Orte');
			await expect(krumen).toContainText(name);
			await expect(kruemel, 'KA-7: der Vergleichsname ist Teil des Links').not.toContainText(name);
			await expect(page.getByText('WORKSPACE', { exact: true }), 'KA-7: Extra-Krümel „WORKSPACE"').toHaveCount(0);
			await expect(vergleichUnterzeile(page)).toBeVisible();
		} finally {
			await hub.aufraeumen();
		}
	});

	// #2913 c2 (Mockup, Vertrag hub_kopf_c2_mockup.test.ts): EINE Meta-Zeile für beide Breiten,
	// Zähler = gespeicherte IDs (location_ids.length) — vormals Mobil = aufgelöste Orte.
	test('KA-8 (vergleich): Orte-Anzahl — Desktop und Mobil zählen die gespeicherten IDs', async ({
		page
	}) => {
		// Zustand „gespeicherte ID ohne aufgelösten Ort": Ein vom Vergleich
		// referenzierter Ort lässt sich seit #2216 nicht mehr löschen (409
		// location_in_use). Der Vergleich speichert location_ids ungeprüft —
		// deshalb eine eigene, nie existierende ID (kein Ort eines anderen Nutzers).
		const geisterOrt = `e2e-gz-geist-${Date.now()}`;
		let hub: SeededHub | null = null;
		try {
			hub = await seedKopf(page, kind, { location_ids: ['e2e-loc-innsbruck', geisterOrt] });
			const ort = await page.request.get(`/api/locations/${geisterOrt}`);
			expect(ort.status(), 'Messaufbau: die zweite ID ist nicht auflösbar').toBe(404);
			expect(
				((await holeStand(page, kind, hub.id)).location_ids as string[]).length,
				'Messaufbau: der Vergleich behält beide IDs'
			).toBe(2);

			const meta = page.getByTestId('hub-kopf-meta');
			for (const viewport of [DESKTOP, MOBIL]) {
				await page.setViewportSize(viewport);
				await openHub(page, kind, hub.id);
				expect(await meta.count(), 'Meta-Zeile genau 1 im DOM').toBe(1);
				await expect(meta).toBeVisible();
				await expect(meta).toHaveText(/^2 Orte · Vergleichstabelle\b/);
			}
		} finally {
			await hub?.aufraeumen();
		}
	});

	test('KA-9 (vergleich): Orte-Anzahl Desktop-Singular — Vergleich mit 1 Ort zeigt „1 Ort · …“', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind, { location_ids: ['e2e-loc-innsbruck'] });
		try {
			await openHub(page, kind, hub.id);
			const sichtbar = page.getByTestId('hub-kopf-meta');
			await expect(sichtbar).toBeVisible();
			await expect(sichtbar).toHaveText(/^1 Ort · Vergleichstabelle\b/);
		} finally {
			await hub.aufraeumen();
		}
	});
});

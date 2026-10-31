// E2E — Issue #2347 S2 (Epic #2345, Etappe P6): Listen-Menü und mobile Aktionen —
// EINE Zusicherung für Trip-Liste UND Ortsvergleich-Liste per Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s2_paritaets_e2e.md § „hub-list-menu.spec.ts (LM)",
// AC-4 (LM-1..LM-8) und AC-5 (LM-9, LM-10).
// #2347 S4 (feat_2347_s4_paritaets_e2e.md AC-1..AC-3): LM-1b (nacktes /edit),
// LM-10b (Archivieren im Hub-Blatt), LM-11 (aktives Blatt), LM-12 (Entwurf),
// LM-13 (Desktop-Zeilenklick) — Ersatz für compare-edit-redirect, trip-edit,
// compare-detail-edit-entry und Teile von compare-flow-navigation.
//
// Ersetzt (Zuordnung Zeilen 24-30, 35, 39, 53-55):
//   die entfernte Compare-Listenmenü-Altdatei (AC-1..AC-7; Titel „5 Aktionen" war
//   veraltet, es gelten 6; alle zwölf festen Schlaf-Pausen durch Ereignis-Warten
//   ersetzt; `.first()`-Kachel durch Eigen-Seed je kind ersetzt; UI-Login entfällt),
//   die entfernte Trip-Listen-Aktionen-Spec (Pausieren/Fortsetzen, Reihenfolge,
//   Archiv) und die mobilen Fälle der entfernten Compare-Sammelspec (Karte/
//   Aktionsblatt, ⋯-Blatt).
//
// Kein fester Schlaf: gewartet wird auf den Schreibaufruf (waitForRequest/
// waitForResponse), auf sichtbare Zustände und auf Zähler (toHaveCount/toHaveText).
// Kein echter Versand: „Senden" wird nur als Menüeintrag geprüft, nie ausgelöst.
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den
// storageState aus global.setup.ts (Admin-Sitzung), kein UI-Login.
// Seeds strikt im `finally` aufräumen: Vergleiche sind auf 2 aktive je Nutzer begrenzt.

import { test, expect, type APIRequestContext, type Page, type Response } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind, type SeededHub } from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 390, height: 844 };

/** Tagesdatum in UTC — `deriveTripStatus` vergleicht auf UTC-Tageskorn. */
const HEUTE = new Date().toISOString().slice(0, 10);

const etappe = (date: string) => ({
	id: 's1',
	name: 'Tag 1',
	date,
	waypoints: [
		{ id: 'a', name: 'a', lat: 42.0, lon: 9.0, elevation_m: 800 },
		{ id: 'b', name: 'b', lat: 42.04, lon: 9.0, elevation_m: 1200 }
	]
});

type Zustand = 'aktiv' | 'pausiert' | 'entwurf';

/**
 * Seed je Zustand. Kind-Zweig nur für die Seed-Felder (Begründung: der Lebenszyklus
 * entsteht je Art aus anderen Feldern — Trip aus Etappen-Datum/`paused_at`,
 * Vergleich aus `location_ids`/`schedule`). Die Zusicherungen sind identisch.
 */
async function seed(request: APIRequestContext, kind: HubKind, zustand: Zustand): Promise<SeededHub> {
	if (kind === 'route') {
		// Trip: „aktiv" braucht eine Etappe am heutigen Tag (sonst „geplant");
		// „Entwurf" = Etappe ohne Datum; „pausiert" = aktiver Trip + PATCH /state.
		const hub = await seedHub(request, kind, {
			extra: { stages: [etappe(zustand === 'entwurf' ? '' : HEUTE)] }
		});
		if (zustand === 'pausiert') {
			const res = await request.patch(`${hubApiPath(kind, hub.id)}/state`, { data: { paused: true } });
			if (!res.ok()) {
				await hub.aufraeumen();
				throw new Error(`Trip pausieren (Seed) fehlgeschlagen: HTTP ${res.status()}`);
			}
		}
		return hub;
	}
	// Vergleich: „pausiert" = schedule manual; „Entwurf" = keine Orte.
	if (zustand === 'pausiert') return seedHub(request, kind, { extra: { schedule: 'manual' } });
	if (zustand === 'entwurf') return seedHub(request, kind, { extra: { location_ids: [] } });
	return seedHub(request, kind);
}

async function serverStand(request: APIRequestContext, kind: HubKind, id: string): Promise<Record<string, unknown>> {
	const res = await request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Record<string, unknown>;
}

/** Feldpfad der Punkte je kind (Trip: Etappen, Vergleich: Orte) — nur Feldpfad-Unterschied. */
const punkte = (kind: HubKind, stand: Record<string, unknown>) =>
	kind === 'route' ? stand.stages : stand.location_ids;

/** Gilt der gespeicherte Stand als pausiert? Trip: `paused_at`; Vergleich: `schedule` ≠ daily. */
const istPausiertGespeichert = (kind: HubKind, stand: Record<string, unknown>): boolean =>
	kind === 'route' ? Boolean(stand.paused_at) : stand.schedule !== 'daily';

/**
 * Wartet auf den Schreibaufruf des Statuswechsels. Kind-Zweig nur für den Endpunkt
 * (Trip: PATCH …/state; Vergleich: PUT auf das Objekt, `setPaused` in subscriptionExec.ts).
 */
function statusSchreibaufruf(page: Page, kind: HubKind, id: string): Promise<Response> {
	const pfad = hubApiPath(kind, id);
	return page.waitForResponse((r) => {
		const req = r.request();
		const p = new URL(r.url()).pathname;
		return kind === 'route' ? req.method() === 'PATCH' && p === `${pfad}/state` : req.method() === 'PUT' && p === pfad;
	});
}

const zeile = (page: Page, kind: HubKind, id: string) => page.getByTestId(HUB_SEL[kind].liste.zeile(id));
const statusLabel = (page: Page, kind: HubKind, id: string, label: string) =>
	zeile(page, kind, id).getByText(`· ${label}`, { exact: true });

/** Liste öffnen; `goto` wartet auf `load` — die Zeilen sind dann server-seitig gerendert (SSR-Loader). */
async function oeffneListe(page: Page, kind: HubKind): Promise<void> {
	await page.goto(HUB_SEL[kind].liste.url);
}

/** Öffnet das Zeilenmenü dieses Eintrags und liefert das sichtbare Menü. */
async function oeffneMenue(page: Page, kind: HubKind, id: string) {
	const z = zeile(page, kind, id);
	await expect(z).toBeVisible({ timeout: 15_000 });
	await z.getByTestId(HUB_SEL[kind].liste.menue).click();
	const menue = page.getByRole('menu');
	await expect(menue).toBeVisible();
	return menue;
}

test.describe('Listen-Menü (Desktop 1280)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(DESKTOP);
	});

	for (const kind of HUB_KINDS) {
		test(`LM-1 (${kind}): „Bearbeiten" im Listen-Menü öffnet den Hub dieses Eintrags (kein /edit)`, async ({
			page
		}) => {
			const hub = await seed(page.request, kind, 'aktiv');
			try {
				await oeffneListe(page, kind);
				const menue = await oeffneMenue(page, kind, hub.id);
				await menue.getByRole('menuitem', { name: 'Bearbeiten', exact: true }).click();
				await expect(page).toHaveURL(HUB_SEL[kind].hubUrl(hub.id), { timeout: 10_000 });
				expect(new URL(page.url()).pathname, 'kein /edit-Ziel').not.toMatch(/\/edit$/);
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	for (const kind of HUB_KINDS) {
		test(`LM-2 (${kind}): das Listen-Menü bietet keine Aktion „Vorschau"`, async ({ page }) => {
			const hub = await seed(page.request, kind, 'aktiv');
			try {
				await oeffneListe(page, kind);
				const menue = await oeffneMenue(page, kind, hub.id);
				await expect(menue.getByRole('menuitem', { name: 'Bearbeiten', exact: true })).toBeVisible();
				await expect(menue.getByRole('menuitem', { name: 'Vorschau', exact: true })).toHaveCount(0);
				await page.keyboard.press('Escape');
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	for (const kind of HUB_KINDS) {
		test(`LM-3 (${kind}): „Pausieren" pausiert wirklich (Anzeige UND Serverstand), Punkte unverändert, danach „Fortsetzen"`, async ({
			page
		}) => {
			const hub = await seed(page.request, kind, 'aktiv');
			try {
				const vorher = await serverStand(page.request, kind, hub.id);
				expect(istPausiertGespeichert(kind, vorher), 'Vorbedingung: Seed ist nicht pausiert').toBe(false);

				await oeffneListe(page, kind);
				await expect(statusLabel(page, kind, hub.id, 'aktiv'), 'Vorbedingung: Status „aktiv"').toBeVisible({
					timeout: 15_000
				});
				const menue = await oeffneMenue(page, kind, hub.id);
				const eintraege = menue.getByRole('menuitem');
				await expect(eintraege.first()).toHaveText('Pausieren');

				const schreibt = statusSchreibaufruf(page, kind, hub.id);
				await eintraege.first().click();
				const antwort = await schreibt;
				expect(antwort.ok(), `Statuswechsel HTTP ${antwort.status()}`).toBeTruthy();
				// Der Rumpf trägt den Zielzustand (kein Umschalten). Kind-Zweig nur für die
				// Rumpf-Form: Trip PATCH {paused:true} (Altfall Zuordnung Zeile 53), Vergleich
				// Teil-PUT mit schedule 'manual' (statusZielNutzlast, #2375).
				const rumpf = antwort.request().postDataJSON() as Record<string, unknown>;
				if (kind === 'route') expect(rumpf).toEqual({ paused: true });
				else expect(rumpf.schedule).toBe('manual');
				await expect(page.getByRole('menu')).toHaveCount(0);

				await expect(statusLabel(page, kind, hub.id, 'pausiert')).toBeVisible({ timeout: 10_000 });
				const nachher = await serverStand(page.request, kind, hub.id);
				expect(istPausiertGespeichert(kind, nachher), 'Serverstand: pausiert gespeichert').toBe(true);
				expect(punkte(kind, nachher), 'Pausieren darf Etappen/Orte nicht verändern').toEqual(punkte(kind, vorher));

				const menue2 = await oeffneMenue(page, kind, hub.id);
				await expect(menue2.getByRole('menuitem').first()).toHaveText('Fortsetzen');
				await page.keyboard.press('Escape');
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	for (const kind of HUB_KINDS) {
		test(`LM-4 (${kind}): „Fortsetzen" setzt fort — Status „aktiv", danach „Pausieren"`, async ({ page }) => {
			const hub = await seed(page.request, kind, 'pausiert');
			try {
				await oeffneListe(page, kind);
				await expect(statusLabel(page, kind, hub.id, 'pausiert'), 'Vorbedingung: Status „pausiert"').toBeVisible({
					timeout: 15_000
				});
				const menue = await oeffneMenue(page, kind, hub.id);
				const fortsetzen = menue.getByRole('menuitem', { name: 'Fortsetzen', exact: true });
				await expect(fortsetzen).toBeVisible();

				const schreibt = statusSchreibaufruf(page, kind, hub.id);
				await fortsetzen.click();
				const antwort = await schreibt;
				expect(antwort.ok(), `Statuswechsel HTTP ${antwort.status()}`).toBeTruthy();
				await expect(page.getByRole('menu')).toHaveCount(0);

				await expect(statusLabel(page, kind, hub.id, 'aktiv')).toBeVisible({ timeout: 10_000 });
				const nachher = await serverStand(page.request, kind, hub.id);
				expect(istPausiertGespeichert(kind, nachher), 'Serverstand: nicht mehr pausiert').toBe(false);

				const menue2 = await oeffneMenue(page, kind, hub.id);
				await expect(menue2.getByRole('menuitem').first()).toHaveText('Pausieren');
				await page.keyboard.press('Escape');
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	for (const kind of HUB_KINDS) {
		test(`LM-5 (${kind}): Entwurf — „Setup fortsetzen" öffnet den Hub`, async ({ page }) => {
			const hub = await seed(page.request, kind, 'entwurf');
			try {
				await oeffneListe(page, kind);
				await expect(statusLabel(page, kind, hub.id, 'draft'), 'Vorbedingung: Status „draft"').toBeVisible({
					timeout: 15_000
				});
				const menue = await oeffneMenue(page, kind, hub.id);
				await menue.getByRole('menuitem', { name: 'Setup fortsetzen', exact: true }).click();
				await expect(page).toHaveURL(HUB_SEL[kind].hubUrl(hub.id), { timeout: 10_000 });
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	for (const kind of HUB_KINDS) {
		test(`LM-6 (${kind}): das Listen-Menü enthält „Senden"`, async ({ page }) => {
			const hub = await seed(page.request, kind, 'aktiv');
			try {
				await oeffneListe(page, kind);
				const menue = await oeffneMenue(page, kind, hub.id);
				await expect(menue.getByRole('menuitem', { name: 'Senden', exact: true })).toBeVisible();
				await page.keyboard.press('Escape');
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	for (const kind of HUB_KINDS) {
		test(`LM-7 (${kind}): aktives Eintrags-Menü hat genau 6 Einträge in fester Reihenfolge, ohne „Archivieren"`, async ({
			page
		}) => {
			const hub = await seed(page.request, kind, 'aktiv');
			try {
				await oeffneListe(page, kind);
				const menue = await oeffneMenue(page, kind, hub.id);
				// Feste Sollliste — dieselbe für beide Arten (Reihenfolge + Anzahl in einem Schritt).
				await expect(menue.getByRole('menuitem')).toHaveText([
					'Pausieren',
					'Senden',
					'Alarme',
					'Wetter-Metriken',
					'Bearbeiten',
					'Löschen'
				]);
				await expect(menue.getByRole('menuitem', { name: 'Archivieren' })).toHaveCount(0);
				await page.keyboard.press('Escape');
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	for (const kind of HUB_KINDS) {
		test(`LM-8 (${kind}): ein archivierter Eintrag erscheint nicht in der Liste und ist unter /archiv auffindbar`, async ({
			page
		}) => {
			const hub = await seed(page.request, kind, 'aktiv');
			try {
				const name = String((await serverStand(page.request, kind, hub.id)).name);
				await oeffneListe(page, kind);
				await expect(zeile(page, kind, hub.id), 'Vorbedingung: Eintrag steht in der Liste').toBeVisible({
					timeout: 15_000
				});

				// Archiv-Auslöser beider Arten: PATCH <objekt>/state {archived:true}
				// (setArchived in subscriptionExec.ts — Hub-Aktion „Archivieren").
				const res = await page.request.patch(`${hubApiPath(kind, hub.id)}/state`, { data: { archived: true } });
				expect(res.ok(), `Archivieren HTTP ${res.status()}`).toBeTruthy();

				await oeffneListe(page, kind);
				await expect(zeile(page, kind, hub.id)).toHaveCount(0);

				await page.goto('/archiv');
				await expect(page.getByText(name, { exact: true })).toBeVisible({ timeout: 15_000 });
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	// #2347 S4: Alt compare-edit-redirect AC-1 + trip-edit AC-1 (Zuordnung „Gelöscht:
	// compare-edit-redirect"). Nur das nackte /edit: `?tab=` reicht nur der Trip durch
	// (Befund 3), deshalb wird es bewusst nicht geprüft.
	for (const kind of HUB_KINDS) {
		test(`LM-1b (${kind}): nacktes /edit führt in den Hub — /edit weg, Reiterleiste da, kein Anlege-Editor`, async ({
			page
		}) => {
			const hub = await seed(page.request, kind, 'aktiv');
			try {
				await page.goto(`${HUB_SEL[kind].liste.url}/${hub.id}/edit`);
				await expect(page).toHaveURL(HUB_SEL[kind].hubUrl(hub.id), { timeout: 15_000 });
				expect(new URL(page.url()).pathname, 'LM-1b: /edit steht noch in der Adresse').not.toMatch(/\/edit$/);
				await expect(page.getByTestId(HUB_SEL[kind].reiterListe), 'LM-1b: Reiterleiste fehlt').toBeVisible({
					timeout: 15_000
				});
				await expect(page.getByTestId('trip-new-editor'), 'LM-1b: Anlege-Editor gerendert').toHaveCount(0);
				await expect(page.getByTestId('compare-editor'), 'LM-1b: Anlege-Editor gerendert').toHaveCount(0);
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	// #2347 S4: Alt compare-detail-edit-entry AC-4 (Entwurf ohne „Bearbeiten").
	for (const kind of HUB_KINDS) {
		test(`LM-12 (${kind}): Entwurf — Hub-Kebab ohne „Bearbeiten"`, async ({ page }) => {
			const hub = await seed(page.request, kind, 'entwurf');
			try {
				await openHub(page, kind, hub.id);
				// Kind-Kontrast „LM-12 Entwurf" (Spec): der Knopf „Setup abschließen" existiert
				// nur im Vergleichs-Hub (routes/compare/[id]/+page.svelte:388); der Trip-Hub hat
				// keinen Draft-CTA. Die Kebab-Aussage unten gilt für beide Arten.
				if (kind === 'vergleich') {
					await expect(page.getByRole('button', { name: 'Setup abschließen' })).toBeVisible({ timeout: 10_000 });
					await expect(page.locator('[data-testid="compare-detail-edit-button"]')).toHaveCount(0);
				}
				const mehr = page.locator('[data-testid="subscription-kebab"]:visible').first();
				await expect(mehr).toBeVisible({ timeout: 10_000 });
				await mehr.click();
				const flaeche = page.getByRole('menu').or(page.locator('[data-snap]:visible'));
				await expect(flaeche.first(), 'LM-12: Hub-Kebab öffnet nichts').toBeVisible({ timeout: 5_000 });
				await expect(flaeche.first().getByText('Bearbeiten', { exact: true }), 'LM-12: „Bearbeiten" im Entwurfs-Kebab').toHaveCount(0);
				await page.keyboard.press('Escape');
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	// #2347 S4: Alt compare-flow-navigation AC-25 (Desktop-Klick auf Zeile/Kachel öffnet Detail).
	for (const kind of HUB_KINDS) {
		test(`LM-13 (${kind}): Desktop-Klick auf die Zeile öffnet den Hub dieses Eintrags`, async ({ page }) => {
			const hub = await seed(page.request, kind, 'aktiv');
			try {
				const name = String((await serverStand(page.request, kind, hub.id)).name);
				await oeffneListe(page, kind);
				const z = zeile(page, kind, hub.id);
				await expect(z).toBeVisible({ timeout: 15_000 });
				await z.getByText(name, { exact: true }).first().click();
				await expect(page, 'LM-13: Zeilen-Klick öffnet den Hub nicht').toHaveURL(HUB_SEL[kind].hubUrl(hub.id), {
					timeout: 10_000
				});
				await expect(page.getByTestId(HUB_SEL[kind].reiterListe)).toBeVisible({ timeout: 15_000 });
			} finally {
				await hub.aufraeumen();
			}
		});
	}
});

test.describe('Mobile Aktionen (390)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(MOBIL);
	});

	for (const kind of HUB_KINDS) {
		test(`LM-9 (${kind}): mobile Karte mit Menü-Knopf öffnet das Aktionsblatt, Tipp auf die Karte öffnet den Hub, fünf Status-Pillen`, async ({
			page
		}) => {
			const hub = await seed(page.request, kind, 'aktiv');
			try {
				await page.goto(HUB_SEL[kind].liste.url);
				const karte = page.getByTestId(`subscription-card-${hub.id}`);
				await expect(karte).toBeVisible({ timeout: 15_000 });
				const menueKnopf = page.getByTestId(`subscription-card-menu-${hub.id}`);
				await expect(menueKnopf).toBeVisible();
				await expect(page.locator('[data-testid^="status-filter-pill-"]:visible')).toHaveCount(5);

				await menueKnopf.click();
				const blatt = page.locator('[data-snap]:visible');
				await expect(blatt).toBeVisible({ timeout: 5_000 });
				await expect(blatt.getByTestId('subscription-action-pause')).toBeVisible();
				await page.locator('button[aria-label="Schliessen"]:visible').click();
				await expect(blatt).toHaveCount(0);

				await karte.click({ position: { x: 24, y: 24 } });
				await expect(page).toHaveURL(HUB_SEL[kind].hubUrl(hub.id), { timeout: 10_000 });
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	for (const kind of HUB_KINDS) {
		test(`LM-10 (${kind}): ⋯ im Hub öffnet das Blatt mit genau Fortsetzen/Archivieren/Löschen (pausiert), Schließen funktioniert`, async ({
			page
		}) => {
			const hub = await seed(page.request, kind, 'pausiert');
			try {
				await openHub(page, kind, hub.id);
				const mehr = page.locator('[data-testid="subscription-kebab"]:visible');
				await expect(mehr).toBeVisible({ timeout: 10_000 });
				await mehr.click();

				const blatt = page.locator('[data-snap="half"]:visible');
				await expect(blatt).toBeVisible({ timeout: 5_000 });
				await expect(blatt.locator('[data-testid^="subscription-action-"]')).toHaveText([
					'Fortsetzen',
					'Archivieren',
					'Löschen'
				]);
				for (const fehlt of ['Senden', 'Vorschau', 'Bearbeiten']) {
					await expect(blatt.getByText(fehlt, { exact: true }), `kein „${fehlt}" im Hub-Blatt`).toHaveCount(0);
				}

				// Nur öffnen/lesen/schließen — keine Aktion auslösen.
				await page.locator('button[aria-label="Schliessen"]:visible').click();
				await expect(blatt).toHaveCount(0);
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	// #2347 S4: Alt compare-flow-navigation KL-7 — LM-10 öffnet nur, hier wird archiviert.
	for (const kind of HUB_KINDS) {
		test(`LM-10b (${kind}): „Archivieren" im Hub-Blatt ⇒ PATCH …/state, Eintrag fehlt in der aktiven Liste, steht unter /archiv`, async ({
			page
		}) => {
			const hub = await seed(page.request, kind, 'pausiert');
			try {
				const name = String((await serverStand(page.request, kind, hub.id)).name);
				await openHub(page, kind, hub.id);
				const mehr = page.locator('[data-testid="subscription-kebab"]:visible');
				await expect(mehr).toBeVisible({ timeout: 10_000 });
				await mehr.click();
				const blatt = page.locator('[data-snap="half"]:visible');
				await expect(blatt).toBeVisible({ timeout: 5_000 });

				const pfad = `${hubApiPath(kind, hub.id)}/state`;
				const schreibt = page.waitForResponse(
					(r) => r.request().method() === 'PATCH' && new URL(r.url()).pathname === pfad,
					{ timeout: 15_000 }
				);
				await blatt.locator('[data-testid^="subscription-action-"]', { hasText: 'Archivieren' }).click();
				// Kind-Unterschied der Bedienung: der Trip-Hub fragt vor dem Archivieren nach
				// (ConfirmDialog trip-detail-archive-confirm-dialog, routes/trips/[id]/+page.svelte),
				// der Vergleichs-Hub archiviert sofort. Die Zusicherung (PATCH, Liste, Archiv) ist gleich.
				if (kind === 'route') {
					await page.getByTestId('trip-detail-archive-confirm-dialog').getByRole('button', { name: 'Archivieren' }).click();
				}
				const antwort = await schreibt;
				expect(antwort.ok(), `LM-10b: PATCH ${pfad} HTTP ${antwort.status()}`).toBeTruthy();
				expect(antwort.request().postDataJSON()).toEqual({ archived: true });

				await page.setViewportSize(DESKTOP);
				await oeffneListe(page, kind);
				await expect(zeile(page, kind, hub.id), 'LM-10b: archivierter Eintrag steht noch in der Liste').toHaveCount(0);
				await page.goto('/archiv');
				await expect(page.getByText(name, { exact: true }).first(), 'LM-10b: Eintrag fehlt unter /archiv').toBeVisible({
					timeout: 15_000
				});
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	// #2347 S4: Alt compare-detail-edit-entry AC-3 — LM-10 prüft nur den pausierten Zustand.
	for (const kind of HUB_KINDS) {
		test(`LM-11 (${kind}): mobiles Hub-Blatt eines aktiven Eintrags zeigt „Pausieren", kein „Bearbeiten"`, async ({
			page
		}) => {
			const hub = await seed(page.request, kind, 'aktiv');
			try {
				await openHub(page, kind, hub.id);
				const mehr = page.locator('[data-testid="subscription-kebab"]:visible');
				await expect(mehr).toBeVisible({ timeout: 10_000 });
				await mehr.click();
				const blatt = page.locator('[data-snap="half"]:visible');
				await expect(blatt).toBeVisible({ timeout: 5_000 });
				await expect(blatt.locator('[data-testid^="subscription-action-"]', { hasText: 'Pausieren' })).toBeVisible();
				await expect(blatt.getByText('Bearbeiten', { exact: true }), 'LM-11: „Bearbeiten" im Blatt').toHaveCount(0);
				await page.locator('button[aria-label="Schliessen"]:visible').click();
				await expect(blatt).toHaveCount(0);
			} finally {
				await hub.aufraeumen();
			}
		});
	}
});

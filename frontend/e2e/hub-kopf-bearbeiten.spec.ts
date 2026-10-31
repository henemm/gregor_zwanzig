// E2E — Issue #2347 S2 (Epic #2345, Etappe P6): Hub-Kopf inline bearbeiten —
// EINE Zusicherung für BEIDE Hubs (Trip und Ortsvergleich) per Schleife über
// HUB_KINDS. Geprüft wird der geteilte Baustein SubscriptionHeader samt dem
// Speicherweg der jeweiligen Seite (TripHeader bzw. compare/[id]/+page.svelte).
//
// Spec: docs/specs/modules/feat_2347_s2_paritaets_e2e.md § „Neue Specs“ (KB-1..KB-10), AC-2, AC-11
//
// Ersetzt (Zuordnungstabelle Zeilen 6-12, 15-17, 50-52):
//   Fälle zweier entfernter Compare-Kopf-Altdateien und der entfernten
//   Trip-Spec zum Namens-Speicherfehler (Ratschen-Zeile entfällt).
// Der feste 2-s-Schlaf des Altfalls (Zuordnung Zeile 10) ist durch ein
// `expect.poll`-Stabilitätsfenster auf den Server-Stand ersetzt.
//
// Kind-Unterschiede stehen ausschließlich als Selektor-/Feldpfad-Daten in
// HUB_SEL (helpers.ts) bzw. als kommentierte Konstanten hier; die Zusicherung
// selbst ist je kind identisch. Wegwerf-Daten (Präfix E2E-GZ-) räumt jeder Fall
// im `finally` ab (max. 2 aktive Vergleiche je Nutzer, Befund 11).
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh) bzw. gegen Staging,
// Anmeldung über den storageState aus global.setup.ts (Admin-Sitzung).

import { test, expect, type Page, type Request } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind, type SeededHub } from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 375, height: 812 };

// Startwerte des Seeds je kind. Kind-Zweig, weil Trip und Vergleich
// verschiedene Wertevorräte haben (Trip `activity`, 8 Werte; Vergleich
// `profil`, 4 Werte) und die Region an verschiedenen Pfaden liegt (Trip
// `region`, Vergleich `display_config.region`). Der Startwert ist bewusst vom
// Zielwert HUB_SEL[kind].profilWert verschieden — sonst prüfte KB-3/KB-8 einen
// Klick auf die schon gewählte Kachel (Vergleich-Standardseed ist `wandern`).
const START: Record<HubKind, { profil: string; region: string; extra: Record<string, unknown> }> = {
	route: { profil: 'trekking', region: 'Alpen Sued', extra: { activity: 'trekking', region: 'Alpen Sued' } },
	vergleich: { profil: 'allgemein', region: 'Ötztal', extra: { profil: 'allgemein', display_config: { region: 'Ötztal' } } }
};

type Stand = Record<string, unknown>;

function seedKopf(page: Page, kind: HubKind): Promise<SeededHub> {
	return seedHub(page.request, kind, { extra: START[kind].extra });
}

async function holeStand(page: Page, kind: HubKind, id: string): Promise<Stand> {
	const pfad = hubApiPath(kind, id);
	const res = await page.request.get(pfad);
	expect(res.ok(), `GET ${pfad} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

/** Feldpfad der Region je kind (Trip `region`, Vergleich `display_config.region`). */
function regionAus(kind: HubKind, s: Stand): unknown {
	return kind === 'route' ? s.region : (s.display_config as Stand | undefined)?.region;
}

/** Überschrift je kind: Trip trägt die testid `trip-detail-h1`, der Vergleich keine (Befund 5). */
function ueberschrift(page: Page, kind: HubKind) {
	return kind === 'route' ? page.getByTestId('trip-detail-h1') : page.getByRole('heading', { level: 1 });
}

/** Sichtbarer Treffer einer Kopf-testid `${kopf}-<rest>`. */
function sicht(page: Page, kind: HubKind, rest: string) {
	return page.locator(`[data-testid="${HUB_SEL[kind].kopf}-${rest}"]:visible`);
}

function abbrechen(page: Page) {
	return page.getByRole('button', { name: /^(Abbrechen|×)$/ }).filter({ visible: true }).first().click();
}

/** Mitschnitt aller PUT-Rümpfe auf genau dieses Objekt. */
function putMitschnitt(page: Page, pfad: string): Stand[] {
	const bodies: Stand[] = [];
	page.on('request', (req: Request) => {
		if (req.method() === 'PUT' && new URL(req.url()).pathname === pfad) {
			bodies.push((req.postDataJSON() ?? {}) as Stand);
		}
	});
	return bodies;
}

/** Lässt jeden PUT auf das Objekt mit 500 scheitern (Rumpf `{error:'Serverfehler'}`). */
async function putScheitert(page: Page, pfad: string): Promise<void> {
	await page.route(`**${pfad}`, (route) =>
		route.request().method() === 'PUT'
			? route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'Serverfehler' }) })
			: route.continue()
	);
}

/** Server-Felder, die sich bei jedem Schreiben ändern dürfen. */
function ohneZeitstempel(p: Stand): Stand {
	const { updated_at: _u, created_at: _c, etag: _e, version: _v, ...rest } = p;
	return rest;
}

// ─── KB-1 ──────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`KB-1 (${kind}): Name ändern ⇒ Überschrift sofort neu, nach Reload persistent`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind);
		const neu = `Umbenannt ${Date.now()}`;
		try {
			await openHub(page, kind, hub.id);
			await expect(sicht(page, kind, 'name-edit-toggle'), 'KB-1: Stift zum Umbenennen fehlt').toBeVisible({
				timeout: 10_000
			});
			await sicht(page, kind, 'name-edit-toggle').click();
			await sicht(page, kind, 'name-edit').fill(neu);
			await sicht(page, kind, 'name-save').click();

			// Sofort sichtbar (kein Reload).
			await expect(ueberschrift(page, kind)).toContainText(neu, { timeout: 5_000 });

			await page.reload();
			await expect(ueberschrift(page, kind)).toContainText(neu, { timeout: 10_000 });
			expect((await holeStand(page, kind, hub.id)).name).toBe(neu);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KB-2 ──────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`KB-2 (${kind}): Region ändern ⇒ sichtbar, persistent am Feldpfad des kind`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind);
		const neu = `Zillertal ${Date.now()}`;
		try {
			await openHub(page, kind, hub.id);
			await expect(sicht(page, kind, 'region-edit-toggle'), 'KB-2: Stift für die Region fehlt').toBeVisible({
				timeout: 10_000
			});
			await sicht(page, kind, 'region-edit-toggle').click();
			await sicht(page, kind, 'region-edit').fill(neu);
			await sicht(page, kind, 'region-save').click();

			await expect(page.getByText(neu, { exact: false }).filter({ visible: true }).first()).toBeVisible({
				timeout: 5_000
			});

			await page.reload();
			await expect(page.getByText(neu, { exact: false }).filter({ visible: true }).first()).toBeVisible({
				timeout: 10_000
			});
			expect(regionAus(kind, await holeStand(page, kind, hub.id))).toBe(neu);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KB-3 ──────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`KB-3 (${kind}): Profil/Aktivität wählen ⇒ Kachel markiert, persistent`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind);
		const { profilFeld, profilWert } = HUB_SEL[kind];
		try {
			expect(profilWert, 'Vorbedingung: Zielwert ist vom Seed verschieden').not.toBe(START[kind].profil);
			expect((await holeStand(page, kind, hub.id))[profilFeld], 'Vorbedingung: Startwert geseedet').toBe(
				START[kind].profil
			);
			await openHub(page, kind, hub.id);

			const kachel = sicht(page, kind, `profil-option-${profilWert}`);
			await expect(kachel, 'KB-3: die Profil-Kacheln fehlen im Kopf').toBeVisible({ timeout: 10_000 });
			await expect(kachel).toHaveAttribute('data-selected', 'false');
			await kachel.click();
			await expect(kachel).toHaveAttribute('data-selected', 'true', { timeout: 5_000 });

			await expect
				.poll(async () => (await holeStand(page, kind, hub.id))[profilFeld], { timeout: 8_000 })
				.toBe(profilWert);
			await page.reload();
			await expect(sicht(page, kind, `profil-option-${profilWert}`)).toHaveAttribute('data-selected', 'true', {
				timeout: 10_000
			});
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KB-4 ──────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`KB-4 (${kind}): jeder Kopf-PUT trägt genau das eine geänderte Feld, alles andere bleibt`, async ({ page }) => {
		test.setTimeout(90_000);
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind);
		const pfad = hubApiPath(kind, hub.id);
		const { profilFeld, profilWert } = HUB_SEL[kind];
		try {
			const vorher = ohneZeitstempel(await holeStand(page, kind, hub.id));
			await openHub(page, kind, hub.id);
			const bodies = putMitschnitt(page, pfad);
			const putOk = () =>
				page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === pfad);

			// Region
			await sicht(page, kind, 'region-edit-toggle').click();
			await sicht(page, kind, 'region-edit').fill('Pitztal');
			let antwort = putOk();
			await sicht(page, kind, 'region-save').click();
			expect((await antwort).ok()).toBeTruthy();
			await expect(sicht(page, kind, 'region-edit-toggle')).toBeVisible({ timeout: 5_000 });
			expect(bodies.length, 'genau ein PUT nach Region-Speichern').toBe(1);
			// Feldpfad-Zweig: Trip schreibt `region` auf oberster Ebene, der Vergleich
			// `display_config.region` — in beiden Fällen GENAU der eine Schlüssel.
			if (kind === 'route') {
				expect(Object.keys(bodies[0]).sort()).toEqual(['region']);
			} else {
				expect(Object.keys(bodies[0]).sort()).toEqual(['display_config']);
				expect(Object.keys(bodies[0].display_config as object).sort()).toEqual(['region']);
			}

			// Name
			await sicht(page, kind, 'name-edit-toggle').click();
			await sicht(page, kind, 'name-edit').fill('Nur Name');
			antwort = putOk();
			await sicht(page, kind, 'name-save').click();
			expect((await antwort).ok()).toBeTruthy();
			await expect(ueberschrift(page, kind)).toContainText('Nur Name', { timeout: 5_000 });
			expect(bodies.length).toBe(2);
			expect(Object.keys(bodies[1]).sort()).toEqual(['name']);

			// Profil/Aktivität
			antwort = putOk();
			await sicht(page, kind, `profil-option-${profilWert}`).click();
			expect((await antwort).ok()).toBeTruthy();
			await expect(sicht(page, kind, `profil-option-${profilWert}`)).toHaveAttribute('data-selected', 'true', {
				timeout: 5_000
			});
			expect(bodies.length).toBe(3);
			expect(Object.keys(bodies[2]).sort()).toEqual([profilFeld]);

			// Server-Wahrheit: nur die drei Felder geändert, alles andere wie vorher
			// (Orte/Etappen, Empfänger, Zeitplan, Wertebereiche … — Fehlerklasse #2375/#2381).
			const nachher = ohneZeitstempel(await holeStand(page, kind, hub.id));
			expect(nachher.name).toBe('Nur Name');
			expect(nachher[profilFeld]).toBe(profilWert);
			expect(regionAus(kind, nachher)).toBe('Pitztal');
			const ohneGeaendert = (s: Stand): Stand => {
				const { name: _n, [profilFeld]: _p, region: _r, display_config: dc, ...rest } = s;
				const { region: _dr, ...dcRest } = (dc ?? {}) as Stand;
				return { ...rest, display_config: dcRest };
			};
			expect(ohneGeaendert(nachher)).toEqual(ohneGeaendert(vorher));
			if (kind === 'vergleich') {
				// Seed-Bestand aus helpers.seedHub: 2 Orte, 1 Empfänger, täglich.
				expect((nachher.location_ids as string[]).length).toBe(2);
				expect((nachher.empfaenger as string[]).length).toBe(1);
				expect(nachher.schedule).toBe('daily');
			} else {
				expect((nachher.stages as unknown[]).length).toBe(1);
				expect(nachher.report_config).toEqual(vorher.report_config);
			}
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KB-5 ──────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`KB-5 (${kind}): Name ändern, dann Wertebereiche-Commit im selben Seitenaufenthalt ⇒ Name bleibt`, async ({
		page
	}) => {
		test.setTimeout(60_000);
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind);
		const pfad = hubApiPath(kind, hub.id);
		const neu = `CrossTab ${Date.now()}`;
		try {
			await openHub(page, kind, hub.id);
			const bodies = putMitschnitt(page, pfad);

			// 1) Namen im Kopf ändern + speichern.
			await sicht(page, kind, 'name-edit-toggle').click();
			await sicht(page, kind, 'name-edit').fill(neu);
			await sicht(page, kind, 'name-save').click();
			await expect(ueberschrift(page, kind)).toContainText(neu, { timeout: 5_000 });
			await expect.poll(() => bodies.length, { timeout: 10_000 }).toBe(1);

			// 2) Im SELBEN Seitenaufenthalt (kein Reload/goto — ein Reload lüde den
			//    Namen ohnehin frisch vom Server, Adversary-Fund F001 aus #1273 S2) per
			//    In-Page-Klick in den Reiter Wertebereiche, eine Metrik hinzufügen und
			//    einen Wert per blur() committen.
			await page.locator(`[data-testid="${HUB_SEL[kind].reiter}-wertebereiche"]:visible`).first().click();
			const panel = page.locator(`[data-testid="${HUB_SEL[kind].panel}-wertebereiche"]:visible`).first();
			await expect(panel).toBeVisible({ timeout: 10_000 });
			await panel.locator('[data-testid^="corridor-editor-pool-item-"]:visible').first().click();
			const field = panel.getByTestId('corridor-editor-table').locator('input[type="number"]').first();
			await expect(field).toBeVisible({ timeout: 10_000 });
			await field.focus();
			await field.fill('42');
			await field.blur();

			// Der Reiter-Commit hat wirklich geschrieben (sonst hielte „Name bleibt“ trivial).
			await expect
				.poll(() => bodies.length, { message: 'KB-5: der Wertebereiche-Commit löst keinen PUT aus', timeout: 10_000 })
				.toBeGreaterThanOrEqual(2);
			expect(
				bodies.slice(1).every((b) => !('name' in b) || b.name === neu),
				'KB-5: ein Reiter-PUT schreibt einen alten Namen zurück'
			).toBe(true);

			// 3) Stabilitätsfenster statt Schlaf: der Server-Name bleibt 2 s lang neu.
			let seit = 0;
			let verloren: unknown = null;
			await expect
				.poll(
					async () => {
						const name = (await holeStand(page, kind, hub.id)).name;
						if (name !== neu) verloren = name;
						if (verloren !== null) return `verloren: ${String(verloren)}`;
						seit ||= Date.now();
						return Date.now() - seit >= 2_000 ? 'stabil' : 'wartet';
					},
					{ message: 'KB-5: der Cross-Tab-Commit setzt den Namen zurück', timeout: 8_000, intervals: [250] }
				)
				.toBe('stabil');
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KB-6 ──────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`KB-6 (${kind}): Mobil 375 — Name, Region, Profil (Knopf + Auswahl) ändern ⇒ nach Reload persistent`, async ({
		page
	}) => {
		await page.setViewportSize(MOBIL);
		const hub = await seedKopf(page, kind);
		const neuName = `Mobil ${Date.now()}`;
		const neuRegion = `Zillertal ${Date.now()}`.slice(0, 40);
		const { kopf, profilFeld, profilWert } = HUB_SEL[kind];
		try {
			await openHub(page, kind, hub.id);

			// Sichtbarkeitsfilter Pflicht: das Mobil-Markup wird geprüft.
			await expect(sicht(page, kind, 'name-edit-toggle'), 'KB-6: Stift auch mobil sichtbar').toBeVisible({
				timeout: 10_000
			});
			await sicht(page, kind, 'name-edit-toggle').click();
			await sicht(page, kind, 'name-edit').fill(neuName);
			await sicht(page, kind, 'name-save').click();
			await expect(page.getByText(neuName).filter({ visible: true }).first()).toBeVisible({ timeout: 5_000 });

			await sicht(page, kind, 'region-edit-toggle').click();
			await sicht(page, kind, 'region-edit').fill(neuRegion);
			await sicht(page, kind, 'region-save').click();
			await expect(page.getByText(neuRegion).filter({ visible: true }).first()).toBeVisible({ timeout: 5_000 });

			// Mobil: Wahl über Knopf + Auswahl statt Kachel; je genau einmal im DOM.
			const knopf = page.locator(`[data-testid="${kopf}-profil-knopf"]`);
			const auswahl = page.locator(`[data-testid="${kopf}-profil-auswahl"]`);
			expect(await knopf.count(), `${kopf}-profil-knopf: Anzahl im DOM (ohne :visible)`).toBe(1);
			expect(await auswahl.count(), `${kopf}-profil-auswahl: Anzahl im DOM (ohne :visible)`).toBe(1);
			await expect(knopf).toHaveAttribute('data-selected-value', START[kind].profil);
			await knopf.click();
			await expect(auswahl).toBeVisible({ timeout: 5_000 });
			await page.locator(`[data-testid="${kopf}-profil-auswahl-option-${profilWert}"]`).click();
			await expect(auswahl).toBeHidden({ timeout: 5_000 });
			await expect(knopf).toHaveAttribute('data-selected-value', profilWert, { timeout: 5_000 });
			await expect
				.poll(async () => (await holeStand(page, kind, hub.id))[profilFeld], { timeout: 8_000 })
				.toBe(profilWert);

			await page.reload();
			await expect(page.getByText(neuName).filter({ visible: true }).first()).toBeVisible({ timeout: 10_000 });
			await expect(page.getByText(neuRegion).filter({ visible: true }).first()).toBeVisible();
			await expect(knopf).toHaveAttribute('data-selected-value', profilWert);
			expect(await knopf.count(), `${kopf}-profil-knopf nach Reload: Anzahl im DOM`).toBe(1);
			expect(await auswahl.count(), `${kopf}-profil-auswahl nach Reload: Anzahl im DOM`).toBe(1);

			const s = await holeStand(page, kind, hub.id);
			expect(s.name).toBe(neuName);
			expect(regionAus(kind, s)).toBe(neuRegion);
			expect(s[profilFeld]).toBe(profilWert);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KB-7 ──────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`KB-7 (${kind}): Name-PUT 500 ⇒ Fehlermeldung role=alert, Eingabe offen mit Versuchswert, Server + Überschrift unverändert`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind);
		const pfad = hubApiPath(kind, hub.id);
		const versuch = `Fehlversuch ${Date.now()}`;
		try {
			const alterName = (await holeStand(page, kind, hub.id)).name as string;
			await openHub(page, kind, hub.id);
			await expect(ueberschrift(page, kind)).toContainText(alterName, { timeout: 10_000 });
			await putScheitert(page, pfad);

			await sicht(page, kind, 'name-edit-toggle').click();
			const eingabe = sicht(page, kind, 'name-edit');
			await eingabe.fill(versuch);
			await sicht(page, kind, 'name-save').click();

			const err = sicht(page, kind, 'name-save-error');
			await expect(err, 'KB-7: ein fehlgeschlagener PUT muss eine Fehlermeldung am Feld zeigen').toBeVisible({
				timeout: 8_000
			});
			await expect(err).toHaveAttribute('role', 'alert');
			await expect(err).toHaveText('Serverfehler');
			await expect(err).not.toHaveText('');
			// Eingabe bleibt offen mit dem Versuchswert (kein stiller Datenverlust).
			await expect(eingabe).toBeVisible();
			await expect(eingabe).toHaveValue(versuch);
			// Der fehlgeschlagene PUT hat nichts geschrieben.
			expect((await holeStand(page, kind, hub.id)).name).toBe(alterName);

			// Überschrift unverändert: nach dem Schließen steht der alte Name, nicht der Versuch.
			await abbrechen(page);
			await expect(ueberschrift(page, kind)).toContainText(alterName);
			await expect(ueberschrift(page, kind)).not.toContainText(versuch);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KB-8 ──────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`KB-8 (${kind}): Profil-PUT 500 ⇒ Fehler unter den Kacheln, bisherige Kachel bleibt einzige Auswahl`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind);
		const pfad = hubApiPath(kind, hub.id);
		const { kopf, profilFeld, profilWert } = HUB_SEL[kind];
		try {
			await openHub(page, kind, hub.id);
			await expect(sicht(page, kind, `profil-option-${START[kind].profil}`)).toHaveAttribute('data-selected', 'true', {
				timeout: 10_000
			});
			await putScheitert(page, pfad);

			await sicht(page, kind, `profil-option-${profilWert}`).click();

			const fehler = sicht(page, kind, 'profil-save-error');
			await expect(fehler).toBeVisible({ timeout: 8_000 });
			await expect(fehler).toHaveAttribute('role', 'alert');
			await expect(fehler).toContainText('Serverfehler');
			const gewaehlt = page.locator(`[data-testid^="${kopf}-profil-option-"][data-selected="true"]:visible`);
			await expect(gewaehlt).toHaveCount(1);
			await expect(gewaehlt).toHaveAttribute('data-testid', `${kopf}-profil-option-${START[kind].profil}`);
			await page.unroute(`**${pfad}`);
			expect((await holeStand(page, kind, hub.id))[profilFeld]).toBe(START[kind].profil);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KB-9 ──────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`KB-9 (${kind}): Name-PUT 2xx ⇒ Feld schließt, Name aktuell, keine Fehlermeldung`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind);
		const pfad = hubApiPath(kind, hub.id);
		const neu = `Erfolgreich ${Date.now()}`;
		const { kopf } = HUB_SEL[kind];
		try {
			await openHub(page, kind, hub.id);
			await sicht(page, kind, 'name-edit-toggle').click();
			await sicht(page, kind, 'name-edit').fill(neu);
			const antwort = page.waitForResponse(
				(r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === pfad
			);
			await sicht(page, kind, 'name-save').click();
			expect((await antwort).ok(), 'KB-9: echter Speicherweg antwortet 2xx').toBeTruthy();

			await expect(page.locator(`[data-testid="${kopf}-name-edit"]`)).toHaveCount(0, { timeout: 8_000 });
			await expect(ueberschrift(page, kind)).toContainText(neu);
			await expect(page.locator(`[data-testid="${kopf}-name-save-error"]`)).toHaveCount(0);
			expect((await holeStand(page, kind, hub.id)).name).toBe(neu);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KB-10 ─────────────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`KB-10 (${kind}): Fehlermeldung verschwindet bei „Abbrechen“ und erneutem Öffnen`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedKopf(page, kind);
		const pfad = hubApiPath(kind, hub.id);
		const { kopf } = HUB_SEL[kind];
		try {
			await openHub(page, kind, hub.id);
			await putScheitert(page, pfad);

			// Fehler provozieren.
			await sicht(page, kind, 'name-edit-toggle').click();
			await sicht(page, kind, 'name-edit').fill('E2E reset-test');
			await sicht(page, kind, 'name-save').click();
			await expect(sicht(page, kind, 'name-save-error')).toBeVisible({ timeout: 8_000 });

			// Abbrechen ⇒ Bearbeitung schließt, Meldung weg.
			await abbrechen(page);
			await expect(page.locator(`[data-testid="${kopf}-name-edit"]`)).toHaveCount(0);
			await expect(page.locator(`[data-testid="${kopf}-name-save-error"]`)).toHaveCount(0);

			// Neu öffnen über den Stift ⇒ Meldung bleibt weg.
			await sicht(page, kind, 'name-edit-toggle').click();
			await expect(sicht(page, kind, 'name-edit')).toBeVisible();
			await expect(page.locator(`[data-testid="${kopf}-name-save-error"]`)).toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── KB-11 (#2347 S4) ──────────────────────────────────────────────────────
// Ersatz für compare-legacy-fields-survive-save AC-3 (#1268 F003, Go ohne
// RMW-Schutz) und trip-edit „data integrity". Feldmenge je kind (Kind-Kontraste
// „KB-11 Bestandsfelder"): Trip weather_config/report_config/display_config/
// avalanche_regions/aggregation + Etappenzahl, Vergleich hour_from/hour_to/
// forecast_hours/empfaenger — alle mit NICHT-Default-Werten, sonst wäre ein
// Nullen unsichtbar. Zusicherung gleich: zwei Kopf-Umbenennungen lassen alles
// Übrige bitgleich.
const KB11_BESTAND: Record<HubKind, Stand> = {
	route: {
		weather_config: { provider: 'e2e-kb11', extra_flag: true },
		report_config: {
			enabled: true,
			morning_enabled: true,
			evening_enabled: true,
			// Volle Stunden: der Go-Schreibpfad kürzt Versandzeiten auf die Stunde
			// (store.NormalizeReportConfigSlotTimes, #1280) — Minuten wären kein
			// persistierbarer Wert. 05:00/19:00 ≠ Standard 07:00/18:00.
			morning_time: '05:00:00',
			evening_time: '19:00:00'
		},
		display_config: { metrics: [{ metric_id: 'snow_depth', enabled: true, bucket: 'primary', order: 0 }] },
		avalanche_regions: ['AT-07-14'],
		aggregation: { profile: 'e2e-kb11' },
		stages: [
			{ id: 's1', name: 'Tag 1', date: '2027-08-01', waypoints: [{ id: 'a', name: 'a', lat: 42.0, lon: 9.0, elevation_m: 800 }] },
			{ id: 's2', name: 'Tag 2', date: '2027-08-02', waypoints: [{ id: 'b', name: 'b', lat: 42.1, lon: 9.0, elevation_m: 900 }] }
		]
	},
	vergleich: { hour_from: 10, hour_to: 14, forecast_hours: 72, empfaenger: ['kb11-bestand@example.com'] }
};

/** Bestandsfelder des kind aus dem Server-Stand (Trip zusätzlich die Etappenzahl). */
function kb11Felder(kind: HubKind, s: Stand): Stand {
	const felder = Object.fromEntries(
		Object.keys(KB11_BESTAND[kind])
			.filter((k) => k !== 'stages')
			.map((k) => [k, s[k]])
	);
	return kind === 'route' ? { ...felder, etappen: (s.stages as unknown[] | undefined)?.length } : felder;
}

for (const kind of HUB_KINDS) {
	test(`KB-11 (${kind}): zwei Umbenennungen im Kopf lassen alle Bestandsfelder bitgleich`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedHub(page.request, kind, { extra: { ...START[kind].extra, ...KB11_BESTAND[kind] } });
		const pfad = hubApiPath(kind, hub.id);
		try {
			const vorher = await holeStand(page, kind, hub.id);
			// Vorbedingung (AC-4): der Seed steht wirklich auf den Nicht-Default-Werten.
			for (const [k, v] of Object.entries(KB11_BESTAND[kind])) {
				if (k === 'stages') continue;
				const meldung = `Vorbedingung: Seed-Feld „${k}" steht nicht auf dem Nicht-Default-Wert`;
				// Objekte darf der Server um Standardschlüssel ergänzen; Skalare/Listen exakt.
				if (v && typeof v === 'object' && !Array.isArray(v)) expect(vorher[k], meldung).toMatchObject(v as Stand);
				else expect(vorher[k], meldung).toEqual(v);
			}
			if (kind === 'route') expect((vorher.stages as unknown[]).length, 'Vorbedingung: zwei Etappen').toBe(2);
			const bestand = kb11Felder(kind, vorher);

			await openHub(page, kind, hub.id);
			for (const runde of [1, 2]) {
				const neu = `E2E-GZ-KB11-${runde}-${Date.now()}`;
				await sicht(page, kind, 'name-edit-toggle').click();
				await sicht(page, kind, 'name-edit').fill(neu);
				const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === pfad, {
					timeout: 15_000
				});
				await sicht(page, kind, 'name-save').click();
				expect((await put).ok(), `KB-11: Umbenennung ${runde} scheitert`).toBeTruthy();
				await expect(ueberschrift(page, kind)).toContainText(neu, { timeout: 5_000 });

				const nachher = await holeStand(page, kind, hub.id);
				expect(nachher.name, `KB-11: Name nach Umbenennung ${runde}`).toBe(neu);
				expect(kb11Felder(kind, nachher), `KB-11: Bestandsfelder nach Umbenennung ${runde} nicht bitgleich`).toEqual(bestand);
			}
		} finally {
			await hub.aufraeumen();
		}
	});
}

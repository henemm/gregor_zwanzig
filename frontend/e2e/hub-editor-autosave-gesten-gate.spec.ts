// E2E — Issue #2347 S3d (Epic #2345, Etappe P6): Autosave-Gesten-Gate im Hub — EINE
// Zusicherung für BEIDE Hubs (Trip und Ortsvergleich) per Schleife über HUB_KINDS. Nur die
// „Punkte-Geste" ist kind-eigen: Trip = Etappen-Datum ändern + blur (Etappen-Reiter),
// Vergleich = Ort entfernen (Orte-Reiter) — Muster hub-save-chip SC-2.
//
// Spec: docs/specs/modules/feat_2347_s3d_paritaets_e2e.md § AC-4..AC-7 (GG-1..GG-5)
//
// Ersetzt compare-editor-autosave.spec.ts (Zuordnung): AC-7 → GG-1 · AC-8 → GG-2 ·
// F001 → GG-3 · AC-5 → GG-4 · AC-6 → GG-5 (AC-9/AC-10 → hub-save-chip SC-2/SC-4,
// AC-14/AC-1 → WS-8, F003 → WS-2/WW-2/WW-3c bereits gedeckt).
//
// Kein fester Schlaf und kein waitForTimeout: „kein PUT" ist ein Stabilitätsfenster
// (`bleibtBei`), die Verzögerung des Speicherns ist ein `page.route`-Handler, die zweite
// Geste startet erst nach `waitForRequest` des ersten PUT (kausal, nicht geraten).
// Anmeldung über den storageState aus global.setup.ts (Admin-Sitzung), keine Registrierung.

import { test, expect, type Page, type Request } from '@playwright/test';
import { createTestLocation, HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind, type SeededHub } from './helpers';

type Stand = Record<string, unknown>;

const VERZOEGERUNG_MS = 900;
const wp = (id: string, lat: number, elevation_m: number) => ({ id, name: id, lat, lon: 9.0, elevation_m });

/** Trip mit ZWEI Etappen (Datum der zweiten ist die zweite unabhängige Geste). */
const TRIP_ZWEI_ETAPPEN = {
	stages: [
		{ id: 's1', name: 'Tag 1', date: '2027-08-01', waypoints: [wp('a', 42.0, 800), wp('b', 42.04, 1200)] },
		{ id: 's2', name: 'Tag 2', date: '2027-08-02', waypoints: [wp('c', 42.1, 900), wp('d', 42.14, 1300)] }
	]
};

async function stand(page: Page, kind: HubKind, id: string): Promise<Stand> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

/** Alle Schreibzugriffe (PUT/PATCH) auf das Objekt bzw. seine Unterpfade (z. B. …/weather-config). */
function sammleSchreiber(page: Page, pfad: string): Request[] {
	const schreiber: Request[] = [];
	page.on('request', (r) => {
		const p = new URL(r.url()).pathname;
		if ((r.method() === 'PUT' || r.method() === 'PATCH') && (p === pfad || p.startsWith(`${pfad}/`))) schreiber.push(r);
	});
	return schreiber;
}

/** Nur die PUTs auf genau das Objekt. */
const nurObjekt = (rs: Request[], pfad: string) => rs.filter((r) => r.method() === 'PUT' && new URL(r.url()).pathname === pfad);

/** Stabilitätsfenster statt festem Schlaf: `lies()` muss `ms` lang `soll` liefern. */
async function bleibtBei(lies: () => number, soll: number, ms: number, message: string): Promise<void> {
	let seit = 0;
	await expect
		.poll(
			() => {
				const n = lies();
				if (n !== soll) {
					seit = 0;
					return n;
				}
				seit ||= Date.now();
				return Date.now() - seit >= ms ? 'stabil' : n;
			},
			{ message, timeout: ms + 8_000, intervals: [200] }
		)
		.toBe('stabil');
}

/** Verzögert PUTs auf das Objekt, damit eine zweite Geste „während des laufenden Speicherns" möglich ist. */
async function verzoegerePuts(page: Page, pfad: string): Promise<void> {
	await page.route(`**${pfad}`, async (route) => {
		if (route.request().method() === 'PUT') await new Promise((r) => setTimeout(r, VERZOEGERUNG_MS));
		await route.continue();
	});
}

/** Öffnet den Punkte-Reiter und wartet auf die kind-eigene Ausgangslage. */
async function oeffnePunkte(page: Page, kind: HubKind, id: string, anzahl: number): Promise<void> {
	const sel = HUB_SEL[kind];
	await openHub(page, kind, id, { tab: sel.punkteReiter });
	await expect(page.locator(`[data-testid="${sel.panel}-${sel.punkteReiter}"]:visible`)).toBeVisible({ timeout: 10_000 });
	if (kind === 'vergleich') {
		await expect(page.getByTestId('hub-orte-row')).toHaveCount(anzahl, { timeout: 10_000 });
	} else {
		await expect(page.getByTestId('edit-stages-panel')).toBeVisible({ timeout: 10_000 });
		await expect(page.getByTestId('stage-date-field')).toHaveCount(anzahl, { timeout: 10_000 });
	}
}

/** Erste Punkte-Geste: Trip = Datum der ersten Etappe + blur · Vergleich = ersten Ort entfernen. */
async function ersteGeste(page: Page, kind: HubKind): Promise<void> {
	if (kind === 'vergleich') {
		await page.getByTestId('hub-orte-remove').first().click();
	} else {
		const feld = page.getByTestId('stage-date-field').nth(0).locator('input[type="date"]');
		await feld.fill('2027-08-20');
		await feld.blur();
	}
}

/** Zweite, unabhängige Geste im selben Reiter: Trip = Datum der zweiten Etappe · Vergleich = nächsten Ort entfernen. */
async function zweiteGeste(page: Page, kind: HubKind): Promise<void> {
	if (kind === 'vergleich') {
		await page.getByTestId('hub-orte-remove').first().click();
	} else {
		const feld = page.getByTestId('stage-date-field').nth(1).locator('input[type="date"]');
		await feld.fill('2027-08-25');
		await feld.blur();
	}
}

const etappenDaten = (s: Stand) => ((s.stages as Array<{ date?: string }> | undefined) ?? []).map((e) => e.date);
const ortIds = (s: Stand) => (s.location_ids as string[] | undefined) ?? [];

interface Aufbau {
	hub: SeededHub;
	orte: string[];
}

/** Seed je kind: Trip mit zwei Etappen · Vergleich mit drei eigenen Test-Orten. */
async function baueAuf(page: Page, kind: HubKind): Promise<Aufbau> {
	if (kind === 'route') {
		return { hub: await seedHub(page.request, kind, { extra: TRIP_ZWEI_ETAPPEN }), orte: [] };
	}
	const a = await createTestLocation(page.request, { lat: 47.0, lon: 11.0 });
	const b = await createTestLocation(page.request, { lat: 47.1, lon: 11.1 });
	const c = await createTestLocation(page.request, { lat: 47.2, lon: 11.2 });
	const orte = [a.id, b.id, c.id];
	return { hub: await seedHub(page.request, kind, { extra: { location_ids: orte } }), orte };
}

const anzahlPunkte = (kind: HubKind) => (kind === 'vergleich' ? 3 : 2);

for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];

	test.describe(`Hub · Autosave-Gesten-Gate (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
		});

		// GG-1 (Alt AC-7) — fängt: ein geteilter Reiter speichert beim Hydrieren ohne Nutzergeste.
		test(`GG-1 (${kind}): alle Reiter ohne Geste öffnen und verlassen → kein Schreibzugriff, Stand unverändert`, async ({
			page
		}) => {
			const { hub } = await baueAuf(page, kind);
			try {
				const pfad = hubApiPath(kind, hub.id);
				const vorher = await stand(page, kind, hub.id);
				const schreiber = sammleSchreiber(page, pfad);

				for (const tab of [sel.punkteReiter, 'alarme', 'wertebereiche', 'wetter-metriken']) {
					await openHub(page, kind, hub.id, { tab });
					await expect(page.locator(`[data-testid="${sel.panel}-${tab}"]:visible`)).toBeVisible({ timeout: 10_000 });
					await bleibtBei(() => schreiber.length, 0, 1_500, `GG-1 FAIL: der Reiter „${tab}" schreibt ohne Nutzergeste`);
				}

				await page.goto(sel.liste.url);
				await bleibtBei(() => schreiber.length, 0, 1_500, 'GG-1 FAIL: das Verlassen des Hubs löst einen Schreibzugriff aus');
				expect(await stand(page, kind, hub.id), 'GG-1 FAIL: der gespeicherte Stand hat sich ohne Geste verändert').toEqual(vorher);
			} finally {
				await hub.aufraeumen();
			}
		});

		// GG-2 (Alt AC-8) — fängt: Navigation bricht den laufenden Speichervorgang ab / Flush entfällt.
		test(`GG-2 (${kind}): Punkte-Geste und SOFORT zur Liste → Änderung steht auf dem Server (kein Datenverlust)`, async ({
			page
		}) => {
			const { hub } = await baueAuf(page, kind);
			try {
				await oeffnePunkte(page, kind, hub.id, anzahlPunkte(kind));
				// Echte Race: Geste und sofort wegnavigieren, OHNE auf den PUT zu warten.
				await ersteGeste(page, kind);
				await page.goto(sel.liste.url);

				await expect
					.poll(
						async () => {
							const s = await stand(page, kind, hub.id);
							return kind === 'vergleich' ? ortIds(s).length : etappenDaten(s)[0];
						},
						{ timeout: 10_000, message: 'GG-2 FAIL: die Änderung ging trotz sofortiger Navigation verloren' }
					)
					.toBe(kind === 'vergleich' ? 2 : '2027-08-20');
			} finally {
				await hub.aufraeumen();
			}
		});

		// GG-3 (Alt F001) — fängt: die Schreib-Warteschlange verwirft eine zweite Änderung,
		// solange der erste PUT läuft („zweite Änderung während laufendem Speichern ging verloren").
		test(`GG-3 (${kind}): zweite Geste während der erste PUT läuft → BEIDE Änderungen landen auf dem Server`, async ({
			page
		}) => {
			const { hub, orte } = await baueAuf(page, kind);
			try {
				const pfad = hubApiPath(kind, hub.id);
				await oeffnePunkte(page, kind, hub.id, anzahlPunkte(kind));
				await verzoegerePuts(page, pfad);

				const ersterPut = page.waitForRequest((r) => r.method() === 'PUT' && new URL(r.url()).pathname === pfad, { timeout: 10_000 });
				await ersteGeste(page, kind);
				await ersterPut; // kausal: der erste Speichervorgang ist unterwegs (und wird 900 ms gehalten)
				await zweiteGeste(page, kind);

				await expect
					.poll(
						async () => {
							const s = await stand(page, kind, hub.id);
							return kind === 'vergleich'
								? ortIds(s)
								: etappenDaten(s);
						},
						{ timeout: 15_000, message: 'GG-3 FAIL: zweite Änderung während laufendem Speichern ging verloren' }
					)
					.toEqual(kind === 'vergleich' ? [orte[2]] : ['2027-08-20', '2027-08-25']);
				await page.unroute(`**${pfad}`);
			} finally {
				await hub.aufraeumen();
			}
		});

		// GG-4 (Alt AC-5) — fängt: Punkte-Geste sendet das Vollobjekt (Körper trägt `name`).
		test(`GG-4 (${kind}): Punkte-Geste ohne Speichern-Klick → genau EIN PUT (200), Körper ohne name, mit Punkte-Teilfeld`, async ({
			page
		}) => {
			const { hub, orte } = await baueAuf(page, kind);
			try {
				const pfad = hubApiPath(kind, hub.id);
				const schreiber = sammleSchreiber(page, pfad);
				await oeffnePunkte(page, kind, hub.id, anzahlPunkte(kind));

				const antwort = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === pfad, { timeout: 15_000 });
				await ersteGeste(page, kind);
				const res = await antwort;
				expect(res.status(), 'GG-4 FAIL: die Punkte-Geste wurde nicht mit 200 beantwortet').toBe(200);

				await bleibtBei(() => nurObjekt(schreiber, pfad).length, 1, 1_200, 'GG-4 FAIL: genau EIN PUT je Punkte-Geste');
				const koerper = res.request().postDataJSON() as Stand;
				expect(Object.keys(koerper), 'GG-4 FAIL: der PUT darf kein Vollobjekt sein (`name` im Körper)').not.toContain('name');
				if (kind === 'vergleich') {
					expect(koerper.location_ids, 'GG-4 FAIL: der Körper trägt die verbleibenden Orte nicht').toEqual([orte[1], orte[2]]);
				} else {
					expect(Object.keys(koerper), 'GG-4 FAIL: der Körper trägt das Teilfeld `stages` nicht').toContain('stages');
					expect((koerper.stages as Array<{ date?: string }>)[0].date).toBe('2027-08-20');
				}

				const s = await stand(page, kind, hub.id);
				if (kind === 'vergleich') expect(ortIds(s)).toEqual([orte[1], orte[2]]);
				else expect(etappenDaten(s)[0]).toBe('2027-08-20');
			} finally {
				await hub.aufraeumen();
			}
		});

		// GG-5 (Alt AC-6) — fängt: Doppel-Feuer (Zähler 3 statt 2) bzw. eine verlorene Aktion.
		test(`GG-5 (${kind}): Punkte-Geste + Versand-Uhrzeit → genau ZWEI PUTs, beide Änderungen im Stand`, async ({ page }) => {
			const { hub, orte } = await baueAuf(page, kind);
			try {
				const pfad = hubApiPath(kind, hub.id);
				const schreiber = sammleSchreiber(page, pfad);
				await oeffnePunkte(page, kind, hub.id, anzahlPunkte(kind));

				await ersteGeste(page, kind);
				await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await bleibtBei(() => nurObjekt(schreiber, pfad).length, 1, 1_000, 'GG-5 FAIL: die Punkte-Geste muss genau EINEN PUT auslösen');

				await page.locator(`[data-testid="${sel.reiter}-wetter-metriken"]:visible`).first().click();
				const zeit = page.locator('[data-testid="versand-abschnitt"]:visible [data-testid="report-morning-time"]:visible');
				await expect(zeit).toBeVisible({ timeout: 10_000 });
				await zeit.selectOption('05:00');
				await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				await bleibtBei(() => nurObjekt(schreiber, pfad).length, 2, 1_500, 'GG-5 FAIL: insgesamt genau ZWEI PUTs (kein Doppel-Feuer, keine verlorene Aktion)');

				const s = await stand(page, kind, hub.id);
				if (kind === 'vergleich') {
					expect(ortIds(s), 'GG-5 FAIL: die Punkte-Änderung fehlt im Stand').toEqual([orte[1], orte[2]]);
					expect(String(s.morning_time), 'GG-5 FAIL: die Versand-Uhrzeit fehlt im Stand').toMatch(/^05:00/);
				} else {
					expect(etappenDaten(s)[0], 'GG-5 FAIL: die Punkte-Änderung fehlt im Stand').toBe('2027-08-20');
					const rc = (s.report_config as Stand | undefined) ?? {};
					expect(String(rc.morning_time), 'GG-5 FAIL: die Versand-Uhrzeit fehlt im Stand').toMatch(/^05:00/);
				}
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}

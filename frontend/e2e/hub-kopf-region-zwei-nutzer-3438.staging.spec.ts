// Abnahme — Issue #3438 (Epic #2913), Punkt 2a: Region über den Stift an der Oberzeile bearbeiten.
// Spec: docs/specs/modules/fix_3438_wetter_ganzseite.md — AC-4 (Region ändern, neu laden, Name/Profil
// bleiben; zweiter Nutzer sieht und ändert die Region nicht), AC-3 (Stift an der Oberzeile).
//
// Nur in /e2e-verify gegen Staging, nie gegen Produktion, nicht in der CI-Positivliste.
// Config (legt der Developer an, Phase 6 — Vorlage playwright.2913-c2-seitenkopf.staging.config.ts,
// Setup-Projekt fix-1895-modus-rueckbau.staging.setup.ts, testMatch /hub-kopf-region-zwei-nutzer-3438\.staging\.spec\.ts/):
//   cd frontend && npx playwright test --config playwright.3438-region-zwei-nutzer.staging.config.ts
//
// Nutzer A = das Staging-Konto des Setup-Projekts (fix-1895-modus-rueckbau.staging.setup.ts), Wegwerf-Hubs.
// Nutzer B = frisch registriertes, bestätigtes Wegwerf-Konto (wie hub-kopf-c2-mockup.staging.spec.ts AC-14),
// am Ende samt Daten gelöscht. Speicherweg: Read-Modify-Write (Merge) — außer der Region bleibt jedes Feld.

import { test, expect, type Page, type Locator, type APIRequestContext } from '@playwright/test';
import {
	hubApiPath,
	registriereBestaetigtenZweitnutzer,
	HUB_KINDS,
	HUB_SEL,
	HUB_KOPF_SEL,
	type HubKind,
	type SeededHub,
	seedHub,
	openHub,
	createTestLocation,
	cleanupTracked
} from './helpers';
import { wegwerfPasswort } from './stagingZugang';

type Stand = Record<string, unknown>;
const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 390, height: 844 };
const EYEBROW_VOR: Record<HubKind, string> = { route: 'Trip · ', vergleich: 'Orte · ' };

const wp = (id: string, lat: number, elevation_m: number) => ({ id, name: id, lat, lon: 2.7, elevation_m });
const ETAPPEN = [
	{ id: 'r1', name: 'Tag 1', date: '2027-02-23', waypoints: [wp('a', 39.58, 20), wp('b', 39.65, 420)] },
	{ id: 'r2', name: 'Tag 2', date: '2027-02-24', waypoints: [wp('c', 39.66, 380), wp('d', 39.67, 1100)] }
];

const sichtbar = (p: Page | Locator, id: string): Locator => p.locator(`[data-testid="${id}"]:visible`).first();
const kopf = (p: Page, kind: HubKind, rest: string): Locator => sichtbar(p, `${HUB_SEL[kind].kopf}-${rest}`);

function regionAus(kind: HubKind, s: Stand): unknown {
	return kind === 'route' ? s.region : (s.display_config as Stand | undefined)?.region;
}
/** Stand ohne Region und ohne Felder, die sich bei jedem Schreiben ändern dürfen. */
function ohneRegion(kind: HubKind, s: Stand): Stand {
	const { updated_at: _u, created_at: _c, etag: _e, version: _v, ...rest } = s;
	if (kind === 'route') {
		const { region: _r, ...ohne } = rest;
		return ohne;
	}
	const { region: _r, ...dc } = (rest.display_config ?? {}) as Stand;
	return { ...rest, display_config: dc };
}
async function stand(req: APIRequestContext, kind: HubKind, id: string): Promise<Stand> {
	const res = await req.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)}: HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

test.describe.configure({ mode: 'serial' });

let seeded: SeededHub[] = [];
let orte: string[] = [];

async function seedA(page: Page, kind: HubKind, region: string): Promise<SeededHub> {
	if (kind === 'route') {
		const hub = await seedHub(page.request, 'route', { extra: { region, activity: 'trekking', stages: ETAPPEN } });
		seeded.push(hub);
		return hub;
	}
	for (let i = 0; i < 2; i++) orte.push((await createTestLocation(page.request, { lat: 51.9 + i * 0.05, lon: 7.6 + i * 0.05 })).id);
	const hub = await seedHub(page.request, 'vergleich', {
		extra: { location_ids: orte.slice(-2), profil: 'allgemein', morning_enabled: true, morning_time: '07:00:00', display_config: { region } }
	});
	seeded.push(hub);
	return hub;
}

test.afterEach(async ({ page }) => {
	for (const hub of seeded) await hub.aufraeumen();
	for (const o of orte) await page.request.delete(`/api/locations/${o}`).catch(() => {});
	seeded = [];
	orte = [];
	await cleanupTracked(page.request);
});

for (const kind of HUB_KINDS) {
	for (const [vp, groesse] of [['desktop', DESKTOP], ['mobil', MOBIL]] as const) {
		test(`#3438 AC-4 (${kind}, ${vp}): Region über den Stift an der Oberzeile ändern, neu laden — Name und Profil bleiben`, async ({ page }) => {
			await page.setViewportSize(groesse);
			const alt = `Altregion ${Date.now()}`;
			const neu = `Neuregion ${Date.now()}`;
			const hub = await seedA(page, kind, alt);
			const vorher = await stand(page.request, kind, hub.id);

			await openHub(page, kind, hub.id);
			const eyebrow = sichtbar(page, 'hub-kopf-eyebrow');
			await expect(eyebrow).toHaveText(`${EYEBROW_VOR[kind]}${alt}`);
			// AC-3: der Stift steht in der Zeile des Eyebrows, über dem Titel.
			const stift = kopf(page, kind, 'region-edit-toggle');
			await expect(stift, 'Region-Stift fehlt').toBeVisible({ timeout: 10_000 });
			const sb = (await stift.boundingBox())!;
			const eb = (await eyebrow.boundingBox())!;
			const tb = (await page.locator('h1:visible').first().boundingBox())!;
			expect(Math.abs(sb.y + sb.height / 2 - (eb.y + eb.height / 2)), 'Region-Stift nicht in der Oberzeile').toBeLessThanOrEqual(12);
			expect(sb.y + sb.height / 2, 'Region-Stift steht nicht über dem Titel').toBeLessThan(tb.y);

			await stift.click();
			await kopf(page, kind, 'region-edit').fill(neu);
			await kopf(page, kind, 'region-save').click();
			await expect(eyebrow, 'Oberzeile zeigt die neue Region sofort').toHaveText(`${EYEBROW_VOR[kind]}${neu}`, { timeout: 5_000 });

			await page.reload();
			await expect(sichtbar(page, 'hub-kopf-eyebrow'), 'nach Neuladen: neue Region in der Oberzeile').toHaveText(`${EYEBROW_VOR[kind]}${neu}`, { timeout: 10_000 });
			await expect(sichtbar(page, HUB_KOPF_SEL.breadcrumb), 'Brotkrumen: Name unverändert').toContainText(String(vorher.name));
			await expect(page.locator('h1:visible').first(), 'Titel: Name unverändert').toContainText(String(vorher.name));
			await expect(page.locator(`.hub-kopf-titel :text-is("${neu}"):visible`), 'keine eigene Regionszeile unter dem Titel').toHaveCount(0);

			const nachher = await stand(page.request, kind, hub.id);
			expect(regionAus(kind, nachher), 'Region gespeichert').toBe(neu);
			expect(nachher[HUB_SEL[kind].profilFeld], 'Profil unverändert').toEqual(vorher[HUB_SEL[kind].profilFeld]);
			expect(ohneRegion(kind, nachher), 'Merge: außer der Region kein Feld verändert oder verloren').toEqual(ohneRegion(kind, vorher));
		});
	}
}

for (const kind of HUB_KINDS) {
	test(`#3438 AC-4 (${kind}): zweiter Nutzer sieht und ändert die Region von Nutzer A nicht`, async ({ page, browser }) => {
		test.setTimeout(180_000);
		await page.setViewportSize(DESKTOP);
		const regionA = `Geheimregion A ${Date.now()}`;
		const hubA = await seedA(page, kind, regionA);
		const standA = await stand(page.request, kind, hubA.id);
		const gast = await browser.newContext({
			baseURL: test.info().project.use.baseURL,
			storageState: undefined,
			serviceWorkers: 'block',
			httpCredentials: test.info().project.use.httpCredentials
		});
		const kennwort = wegwerfPasswort();
		try {
			await registriereBestaetigtenZweitnutzer(page.request, gast.request, `e2e3438${kind}${Date.now()}`, kennwort);

			// B hat einen eigenen Hub mit eigener Region und ändert sie über den Stift an der Oberzeile.
			const regionB = `Region B ${Date.now()}`;
			let hubB: SeededHub;
			if (kind === 'route') {
				hubB = await seedHub(gast.request, 'route', { extra: { region: 'Startregion B', stages: ETAPPEN.slice(0, 1) } });
			} else {
				const ort = await createTestLocation(gast.request, { lat: 48.1, lon: 11.5 });
				hubB = await seedHub(gast.request, 'vergleich', { extra: { location_ids: [ort.id], display_config: { region: 'Startregion B' } } });
			}
			const seiteB = await gast.newPage();
			await seiteB.setViewportSize(DESKTOP);
			await openHub(seiteB, kind, hubB.id);
			await kopf(seiteB, kind, 'region-edit-toggle').click();
			await kopf(seiteB, kind, 'region-edit').fill(regionB);
			await kopf(seiteB, kind, 'region-save').click();
			await expect(sichtbar(seiteB, 'hub-kopf-eyebrow')).toHaveText(`${EYEBROW_VOR[kind]}${regionB}`, { timeout: 5_000 });
			expect(regionAus(kind, await stand(page.request, kind, hubA.id)), 'B-Änderung schreibt nicht in A').toBe(regionA);

			// B öffnet A's Hub: kein fremder Kopf, A's Region nirgends sichtbar.
			await seiteB.goto(kind === 'route' ? `/trips/${hubA.id}` : `/compare/${hubA.id}`);
			await seiteB.waitForLoadState('networkidle').catch(() => {});
			expect(await seiteB.locator('body').innerText(), 'B sieht A’s Region nicht').not.toContain(regionA);
			await expect(seiteB.locator(`[data-testid="${HUB_SEL[kind].kopf}-region-edit-toggle"]:visible`), 'B: kein Region-Stift an A’s Hub').toHaveCount(0);

			// B versucht, A's Region direkt über die API zu ändern: abgelehnt, A unverändert.
			const rumpf = kind === 'route' ? { region: 'Übernommen von B' } : { display_config: { region: 'Übernommen von B' } };
			const schreiben = await gast.request.put(hubApiPath(kind, hubA.id), { data: rumpf });
			expect([403, 404], `B schreibt A's Region: HTTP ${schreiben.status()}`).toContain(schreiben.status());
			const lesen = await gast.request.get(hubApiPath(kind, hubA.id));
			expect([403, 404], `B liest A's Objekt: HTTP ${lesen.status()}`).toContain(lesen.status());
			expect(await stand(page.request, kind, hubA.id), 'A-Daten unverändert').toEqual(standA);

			// A sieht B's Region nicht in seinem Hub.
			await openHub(page, kind, hubA.id);
			await expect(sichtbar(page, 'hub-kopf-eyebrow')).toHaveText(`${EYEBROW_VOR[kind]}${regionA}`);
			expect(await page.locator('body').innerText(), 'A sieht B’s Region nicht').not.toContain(regionB);
		} finally {
			await gast.request.post('/api/auth/account/delete', { data: { password: kennwort } }).catch(() => {});
			await gast.close();
		}
	});
}

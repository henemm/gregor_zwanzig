// E2E — Issue #2347 S3a (Epic #2345, Etappe P6): Autospeichern im Hub —
// Mandantentrennung für BEIDE kinds (Trip und Ortsvergleich) per Schleife über
// HUB_KINDS. Der Autosave-Auslöser darf NIEMALS auf ein fremdes Objekt schreiben —
// der PUT trifft ausschließlich das eigene Objekt des angemeldeten Nutzers.
//
// Spec: docs/specs/modules/feat_2347_s3a_paritaets_e2e.md § AC-6 (UI-1)
//
// Ersetzt compare-editor-autosave-user-isolation.spec.ts (#1261 (b) AC-12, nur Vergleich).
//
// Zwei echte Sitzungen, kein Mock: Nutzer A = Admin-storageState der
// Projekt-Konfiguration, Nutzer B = registrierter, bestätigter Zweitnutzer im
// leeren Kontext. Genau EINE Registrierung für beide kinds (Registrierungsbremse
// 5/h je IP), deshalb serieller Modus mit beforeAll (Vorbild
// hub-cross-user-write-block.spec.ts).
//
// Autosave-Geste je kind (Spec UI-1): die Geste ist kind-eigen, die
// Trennungs-Zusicherung gemeinsam — Ortsvergleich: Ort entfernen (Orte-Reiter,
// compare-eigen, der Trip hat keine Orte), Trip: Etappen-Datum ändern + blur
// (Etappen-Reiter, Vorbild hub-save-chip SC-2).

import { test, expect, type BrowserContext, type Page } from '@playwright/test';
import {
	HUB_KINDS,
	HUB_SEL,
	createTestLocation,
	hubApiPath,
	openHub,
	registriereBestaetigtenZweitnutzer,
	seedHub,
	type HubKind,
	type SeededHub
} from './helpers';

test.describe.configure({ mode: 'serial' });

const ORT_ZUM_ENTFERNEN = 'e2e-loc-stubai'; // Seed-Ort aus global.setup.ts (im Seed von A)
const SEED_DATUM = '2027-08-01'; // Datum der einzigen Etappe aus seedHub('route')

let ctxA: BrowserContext;
let ctxB: BrowserContext;
const hubsA = new Map<HubKind, SeededHub>();
const hubsB = new Map<HubKind, SeededHub>();
let ortB: string | undefined;

test.beforeAll(async ({ browser }) => {
	// Nutzer A: erbt den Admin-storageState der Projekt-Konfiguration.
	ctxA = await browser.newContext();
	for (const kind of HUB_KINDS) hubsA.set(kind, await seedHub(ctxA.request, kind));

	// Nutzer B: ausdrücklich OHNE storageState — sonst erbte er den Admin-Cookie
	// und seine Objekte lägen unter der Identität von A.
	ctxB = await browser.newContext({ storageState: undefined });
	const userB = `e2e2347s3a${Date.now()}`;
	// Issue #2271: das Token holt die Sitzung von A, nicht der Gast.
	await registriereBestaetigtenZweitnutzer(ctxA.request, ctxB.request, userB, 'test1234');

	// B hat die Seed-Orte des Admins nicht — eigener Ort mit Bs Sitzung.
	ortB = (await createTestLocation(ctxB.request, { name: `E2E-GZ-2347-S3a-B-${Date.now()}`, lat: 48.6, lon: 12.6 })).id;
	hubsB.set('route', await seedHub(ctxB.request, 'route'));
	hubsB.set('vergleich', await seedHub(ctxB.request, 'vergleich', { extra: { location_ids: [ortB] } }));
});

test.afterAll(async () => {
	for (const hub of hubsA.values()) await hub.aufraeumen();
	for (const hub of hubsB.values()) await hub.aufraeumen();
	if (ortB) await ctxB?.request.delete(`/api/locations/${ortB}`).catch(() => {});
	hubsA.clear();
	hubsB.clear();
	await ctxB?.close();
	await ctxA?.close();
});

/** Löst die kind-eigene Autosave-Geste im Hub von A aus. */
async function autosaveGeste(page: Page, kind: HubKind, id: string): Promise<void> {
	const sel = HUB_SEL[kind];
	await openHub(page, kind, id, { tab: sel.punkteReiter });
	await expect(page.locator(`[data-testid="${sel.panel}-${sel.punkteReiter}"]:visible`)).toBeVisible({ timeout: 10_000 });
	if (kind === 'vergleich') {
		// compare-eigen: Orte-Geste (der Trip hat keinen Orte-Reiter).
		const entfernen = page.locator(
			`[data-testid="hub-orte-row"][data-loc-id="${ORT_ZUM_ENTFERNEN}"] [data-testid="hub-orte-remove"]`
		);
		await expect(entfernen, 'Vorbedingung: A hat den Seed-Ort im Vergleich').toBeVisible({ timeout: 10_000 });
		await entfernen.click();
	} else {
		// Trip-Gegenstück: Etappen-Datum ändern + blur (Eigen-Seed: genau eine Etappe).
		await expect(page.getByTestId('stage-date-field')).toHaveCount(1, { timeout: 10_000 });
		const datum = page.getByTestId('stage-date-field').locator('input[type="date"]');
		await expect(datum, 'Vorbedingung: Seed-Datum').toHaveValue(SEED_DATUM);
		await datum.fill('2027-08-20');
		await datum.blur();
	}
}

for (const kind of HUB_KINDS) {
	test(`UI-1 (${kind}): Autosave-Änderung bei Nutzer A ändert das eigene Objekt von Nutzer B NICHT, Cross-GET ⇒ 404`, async () => {
		const hubA = hubsA.get(kind);
		const hubB = hubsB.get(kind);
		expect(hubA, `Seed von A für ${kind} fehlt`).toBeTruthy();
		expect(hubB, `Seed von B für ${kind} fehlt`).toBeTruthy();
		const pfadA = hubApiPath(kind, hubA!.id);
		const pfadB = hubApiPath(kind, hubB!.id);

		const beforeRes = await ctxB.request.get(pfadB);
		expect(beforeRes.ok(), `GET ${pfadB} (B) HTTP ${beforeRes.status()}`).toBeTruthy();
		const beforeB = await beforeRes.json();

		const pageA = await ctxA.newPage();
		try {
			await pageA.setViewportSize({ width: 1280, height: 900 });
			const putA = pageA.waitForResponse(
				(r) => new URL(r.url()).pathname === pfadA && r.request().method() === 'PUT',
				{ timeout: 10_000 }
			);
			await autosaveGeste(pageA, kind, hubA!.id);
			const putARes = await putA;
			expect(putARes.ok(), 'Autosave-PUT (A) fehlgeschlagen: ' + putARes.status()).toBeTruthy();
			// KERN: der Autosave-PUT trifft ausschließlich das eigene Objekt von A.
			expect(putARes.url()).toContain(pfadA);
			expect(putARes.url()).not.toContain(hubB!.id);

			// Das eigene Objekt von B bleibt vollständig unverändert.
			const afterB = await (await ctxB.request.get(pfadB)).json();
			expect(afterB).toEqual(beforeB);

			// A hat weiterhin KEINEN Zugriff auf Bs Objekt (Mandantentrennung).
			const crossGet = await ctxA.request.get(pfadB);
			expect(crossGet.status()).toBe(404);
		} finally {
			await pageA.close();
		}
	});
}

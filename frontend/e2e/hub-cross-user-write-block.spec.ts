// E2E — Issue #2347 S1 (Epic #2345, Etappe P6): Mandantentrennung —
// PUT-Cross-User-Block für BEIDE kinds (Trip und Ortsvergleich).
//
// Spec: docs/specs/modules/feat_2347_s1_paritaets_e2e.md § AC-2
//
// Ersetzt compare-cross-user-write-block.spec.ts (Epic #1273 S4a, nur Vergleich)
// und schließt die Lücke: für den Trip gab es keine Cross-User-Schreibprüfung.
//
// Rein API-basiert, zwei echte Sitzungen (Eigentümer = Admin-storageState,
// Gast = registrierter Zweitnutzer im leeren Kontext) — kein Mock. Genau EINE
// Registrierung für beide kinds (Registrierungsbremse 5/h je IP), deshalb
// serieller Modus mit beforeAll.
//
// Erwartung exakt 404: beide Update-Handler laden über den nutzergebundenen
// Store, finden das fremde Objekt nicht und antworten `404 not_found` vor
// If-Match-Prüfung und Rumpf-Dekodierung (nicht 403, nicht 200).

import { test, expect, type APIRequestContext, type BrowserContext } from '@playwright/test';
import { HUB_KINDS, hubApiPath, registriereBestaetigtenZweitnutzer, seedHub, type HubKind, type SeededHub } from './helpers';

test.describe.configure({ mode: 'serial' });

let ctxA: BrowserContext;
let ctxB: BrowserContext;
const hubs = new Map<HubKind, SeededHub>();

test.beforeAll(async ({ browser }) => {
	// Eigentümer: erbt den Admin-storageState der Projekt-Konfiguration.
	ctxA = await browser.newContext();
	for (const kind of HUB_KINDS) hubs.set(kind, await seedHub(ctxA.request, kind));

	// Gast: ausdrücklich OHNE storageState — sonst erbte er den Admin-Cookie und
	// der PUT liefe unter der Identität des Eigentümers.
	ctxB = await browser.newContext({ storageState: undefined });
	const userB = `e2e2347s1${Date.now()}`;
	// Issue #2271: das Token holt die Sitzung des Eigentümers, nicht der Gast.
	await registriereBestaetigtenZweitnutzer(ctxA.request, ctxB.request, userB, 'test1234');
});

test.afterAll(async () => {
	for (const hub of hubs.values()) await hub.aufraeumen();
	hubs.clear();
	await ctxB?.close();
	await ctxA?.close();
});

async function eigentuemerStand(
	request: APIRequestContext,
	pfad: string
): Promise<{ body: Record<string, unknown>; etag: string | undefined }> {
	const res = await request.get(pfad);
	expect(res.ok(), `GET ${pfad} (Eigentümer) HTTP ${res.status()}`).toBeTruthy();
	return { body: (await res.json()) as Record<string, unknown>, etag: res.headers()['etag'] };
}

for (const kind of HUB_KINDS) {
	test(`AC-2 (${kind}): Nutzer B schreibt per PUT auf das Objekt von A ⇒ 404, Stand von A unverändert`, async () => {
		const hub = hubs.get(kind);
		expect(hub, `Seed für ${kind} fehlt`).toBeTruthy();
		const pfad = hubApiPath(kind, hub!.id);

		const vorher = await eigentuemerStand(ctxA.request, pfad);
		expect(vorher.etag, 'Vorbedingung: GET des Eigentümers liefert einen ETag').toBeTruthy();

		// Vollständiger, gültiger Rumpf — nur der Name geändert, damit ein Erfolg
		// am Stand erkennbar wäre.
		const putB = await ctxB.request.put(pfad, { data: { ...vorher.body, name: 'Hijack' } });
		expect(putB.status(), `PUT von B auf ${pfad}`).toBe(404);

		const nachher = await eigentuemerStand(ctxA.request, pfad);
		expect(nachher.body.name, 'Name des Eigentümers unverändert').toBe(vorher.body.name);
		expect(nachher.etag, 'ETag des Eigentümers unverändert').toBe(vorher.etag);
		expect(nachher.body.updated_at, 'updated_at des Eigentümers unverändert').toEqual(vorher.body.updated_at);
	});
}

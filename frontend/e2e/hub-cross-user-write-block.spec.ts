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
// If-Match-Prüfung und Rumpf-Dekodierung (nicht 403, nicht 200). „Unverändert"
// wird über Name und ETag des Eigentümer-GET belegt.

import { test, expect, type APIRequestContext, type BrowserContext } from '@playwright/test';
import {
	ANLEGE_SEL,
	HUB_KINDS,
	hubApiPath,
	registriereBestaetigtenZweitnutzer,
	seedHub,
	type HubKind,
	type SeededHub
} from './helpers';

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
		// Unverändert-Nachweis über Name + ETag (ein `updated_at` führt das Modell
		// nicht — ein Vergleich darauf wäre undefined === undefined).
		expect(nachher.etag, 'Nachher-GET des Eigentümers liefert einen ETag').toBeTruthy();
		expect(nachher.etag, 'ETag des Eigentümers unverändert').toBe(vorher.etag);
	});
}

// XU-3 — #2347 S4 (feat_2347_s4_paritaets_e2e.md AC-13): Mandantentrennung beim
// ANLEGEN. Nutzer A legt per POST (echte user_id aus der Sitzung) ein frisches
// Objekt an; Nutzer B bekommt es weder per GET (404) noch in seiner Liste. Nutzt
// den Zweitnutzer aus beforeAll — KEINE zusätzliche Registrierung (Bremse 5/h/IP) —
// und das in beforeAll von A per POST angelegte Objekt (kein zweiter aktiver
// Vergleich, Grenze 2 je Nutzer); aufgeräumt in afterAll.
for (const kind of HUB_KINDS) {
	test(`XU-3 (${kind}): von Nutzer A angelegtes Objekt ⇒ Nutzer B GET 404 und nicht in B's Liste`, async () => {
		const neu = hubs.get(kind);
		expect(neu, `Seed für ${kind} fehlt`).toBeTruthy();
		const pfad = hubApiPath(kind, neu!.id);
		const eigen = await ctxA.request.get(pfad);
		expect(eigen.ok(), `Vorbedingung: Eigentümer liest ${pfad} (HTTP ${eigen.status()})`).toBeTruthy();

		const fremd = await ctxB.request.get(pfad);
		expect(fremd.status(), `GET von B auf ${pfad}`).toBe(404);

		const sammel = ANLEGE_SEL[kind].postPfad;
		const listeB = await ctxB.request.get(sammel);
		expect(listeB.ok(), `GET ${sammel} (B) HTTP ${listeB.status()}`).toBeTruthy();
		const ids = ((await listeB.json()) as Array<{ id: string }>).map((e) => e.id);
		expect(ids, `Objekt von A steht in B's Liste ${sammel}`).not.toContain(neu!.id);
	});
}

// Issue #3399 S2 (AC-5), Fix-Loop 1 (Adversary F001): die Load-Funktion von /compare/new loest die
// Vorlage der Quelle serverseitig auf und die Seite reicht sie an den Editor.
// Spec: docs/specs/modules/rework_3399_vorlage_aufloesung.md (S2, AC-5)
//
// Die exportierte `load()` aus `compare/new/+page.server.ts` wird ECHT aufgerufen (Muster
// compare_page_server_profile_isolation.test.ts). Ersetzt ist nur die Netzgrenze zur Go-API
// (`fetch`); sie antwortet je Session-Cookie mit der Quelle DIESES Nutzers. Die Aufloesung selbst
// rechnet das ECHTE Python `resolve_entwurf` (`aufloesungPost`, Subprozess) auf den Rumpf, den
// `load()` wirklich sendet. Die Weitergabe in `+page.svelte` wird am echten Attribut-Ausdruck
// der Einbettung gemessen, ausgewertet gegen die Rueckgabe von `load()` (Instanz-Pruefstand).
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
//   cd frontend && npm test -- src/routes/compare/__tests__/compare_new_load_vorlage_3399.test.ts

import { test, describe, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import { attributAusdruck, findeKomponenten, werte, type Knoten } from '../../../lib/components/shared/__tests__/svelteInstanzPruefstand.ts';
import { aufgeloestVon, aufloesungPost } from '../../../lib/components/shared/wetter-tab/__tests__/wetterTabDaten.ts';

register(new URL('./server-load-resolve.hooks.mjs', import.meta.url));

const { load } = (await import('../new/+page.server.ts')) as { load: (e: unknown) => Promise<Knoten> };

const SEITE = join(dirname(fileURLToPath(import.meta.url)), '..', 'new', '+page.svelte');
const AUFLOESUNG = '/api/ampel/aufloesung';

const quelleVon = (id: string, over: Knoten) => ({
	id,
	name: `Quelle ${id}`,
	location_ids: ['loc-a', 'loc-b'],
	schedule: 'daily',
	empfaenger: [],
	display_config: { region: 'Tirol' },
	...over
});
// Je Nutzer eine eigene Quelle mit EIGENER Vorlage: verwechselte Sessions fallen am Ergebnis auf.
const QUELLE: Record<string, Knoten> = {
	'sess-anna': quelleVon('cmp-anna', { profil: 'wintersport' }),
	'sess-bodo': quelleVon('cmp-bodo', { profil: 'wandern', display_config: { region: 'Tirol', ampel: { template: 'wassersport' } } })
};

type Modus = 'python' | '502' | '400' | 'kaputt' | 'netz';
let modus: Modus = 'python';
let aufloesungen: Array<{ session: string | null; rumpf: Knoten }> = [];
const python = aufloesungPost();

function sessionAus(init: Knoten | undefined): string | null {
	const kopf = init?.headers ?? {};
	return String(kopf.Cookie ?? kopf.cookie ?? '').match(/gz_session=([^;]+)/)?.[1] ?? null;
}
const json = (body: unknown, status = 200) =>
	new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

async function goApi(input: unknown, init?: Knoten): Promise<Response> {
	const pfad = new URL(String(input)).pathname;
	const session = sessionAus(init);
	if (pfad === AUFLOESUNG && init?.method === 'POST') {
		const rumpf = JSON.parse(String(init.body)) as Knoten;
		aufloesungen.push({ session, rumpf });
		if (!session || !QUELLE[session]) return json({ error: 'unauthorized' }, 401);
		if (modus === 'netz') throw new TypeError('fetch failed');
		if (modus === 'kaputt') return new Response('{"ergebnisse": [', { status: 200 });
		// Fehlerstatus MIT brauchbar aussehendem Rumpf: allein der Status entscheidet.
		const ergebnis = await python(AUFLOESUNG, rumpf);
		if (modus === '502') return json(ergebnis, 502);
		if (modus === '400') return json(ergebnis, 400);
		return json(ergebnis);
	}
	if (!session || !QUELLE[session]) return json({ error: 'unauthorized' }, 401);
	if (pfad === '/api/locations') return json([]);
	if (pfad === '/api/auth/profile') return json({});
	const q = QUELLE[session];
	if (pfad === `/api/compare/presets/${q.id}`) return json(q);
	return json({ error: 'not_found' }, 404);
}

const eventFuer = (session: string, from: string | null) => ({
	cookies: { get: (name: string) => (name === 'gz_session' ? session : undefined) },
	url: new URL(`http://localhost/compare/new${from ? `?from=${from}` : ''}`),
	params: {},
	route: { id: '/compare/new' },
	setHeaders: () => {},
	depends: () => {}
});

let vorherFetch: typeof globalThis.fetch;
before(() => {
	vorherFetch = globalThis.fetch;
	globalThis.fetch = goApi as unknown as typeof globalThis.fetch;
});
after(() => {
	globalThis.fetch = vorherFetch;
});
beforeEach(() => {
	modus = 'python';
	aufloesungen = [];
});

describe('AC-5: load() von /compare/new löst die Vorlage der Quelle auf', () => {
	test('ohne ?from= ⇒ kein POST /api/ampel/aufloesung, vorlage und vorlageId null', async () => {
		const d = await load(eventFuer('sess-anna', null));
		assert.equal(aufloesungen.length, 0, 'ohne Quelle darf nichts aufgeloest werden');
		assert.equal(d.vorlage, null);
		assert.equal(d.vorlageId, null);
	});

	for (const session of ['sess-anna', 'sess-bodo']) {
		test(`Erfolg (${session}): vorlageId == echtes resolve_entwurf der eigenen Quelle`, async () => {
			const q = QUELLE[session];
			const d = await load(eventFuer(session, q.id));
			assert.equal(d.vorlage?.id, q.id, 'Messaufbau: Quelle nicht geladen');
			const soll = aufgeloestVon(q as never).vorlage_id;
			assert.notEqual(soll, 'allgemein', 'Messaufbau: Quelle muss eine Vorlage ungleich allgemein tragen');
			assert.equal(d.vorlageId, soll, 'vorlageId weicht von der Server-Aufloesung ab');
			assert.equal(aufloesungen.length, 1, 'genau ein Aufloesungs-POST erwartet');
		});
	}

	test('zwei Nutzer: der Aufloesungs-POST traegt genau den eigenen Cookie, nie „default", nie den fremden', async () => {
		const a = await load(eventFuer('sess-anna', QUELLE['sess-anna'].id));
		const b = await load(eventFuer('sess-bodo', QUELLE['sess-bodo'].id));
		assert.deepEqual(aufloesungen.map((x) => x.session), ['sess-anna', 'sess-bodo'], 'Cookie nicht je Nutzer durchgereicht');
		assert.equal(a.vorlageId, aufgeloestVon(QUELLE['sess-anna'] as never).vorlage_id);
		assert.equal(b.vorlageId, aufgeloestVon(QUELLE['sess-bodo'] as never).vorlage_id);
		assert.notEqual(a.vorlageId, b.vorlageId, 'Messaufbau: beide Quellen muessen verschiedene Vorlagen tragen');
	});

	for (const fall of ['502', '400', 'kaputt', 'netz'] as const) {
		test(`Aufloesung scheitert (${fall}) ⇒ vorlageId null, vorlage bleibt, load wirft nicht`, async () => {
			modus = fall;
			const q = QUELLE['sess-anna'];
			const d = await load(eventFuer('sess-anna', q.id));
			assert.equal(aufloesungen.length, 1, 'Messaufbau: Aufloesung nicht befragt');
			assert.equal(d.vorlageId, null, `bei ${fall} geratene Vorlage: ${JSON.stringify(d.vorlageId)}`);
			assert.equal(d.vorlage?.id, q.id, 'Quelle geht beim Aufloesungsfehler verloren');
		});
	}
});

describe('AC-5: +page.svelte reicht vorlageId aus load() an CompareNewEditor', () => {
	const quelle = readFileSync(SEITE, 'utf-8');
	const ast = parse(quelle, { modern: true }) as Knoten;
	const editoren = findeKomponenten(ast, 'CompareNewEditor');

	test('Einbettung wertet vorlageId und vorlage gegen die echte load()-Rueckgabe aus', async () => {
		assert.equal(editoren.length, 1, 'Messaufbau: genau ein CompareNewEditor erwartet');
		const q = QUELLE['sess-bodo'];
		const data = await load(eventFuer('sess-bodo', q.id));
		const ausdruck = attributAusdruck(editoren[0], quelle, 'vorlageId');
		assert.ok(ausdruck, 'CompareNewEditor bekommt kein vorlageId');
		assert.equal(werte(ausdruck, { data }), aufgeloestVon(q as never).vorlage_id, 'Seite reicht eine andere Vorlage durch');
		assert.equal((werte(attributAusdruck(editoren[0], quelle, 'vorlage') ?? 'undefined', { data }) as Knoten)?.id, q.id);
	});
});

// Issue #3442 Fix-Loop 1 — Adversary F003 (AC-5): nach bestätigtem Archivieren im Orts-Vergleich-Hub
// übernimmt die Seite den frischen Stand samt neuem Stempel (ETag), der Status zeigt „archiviert“, und das
// folgende Speichern läuft ohne Konflikt — ohne Navigation und ohne Neuladen.
//
// Prüfstand wie compare_hub_aktionen_verhalten.test.ts: der ECHTE Instanz-Code von routes/compare/[id]/+page.svelte
// (svelteInstanzPruefstand.umgebungFuer) läuft gegen einen Ersatz-Server (globales fetch). Der Ersatz-Server
// verhält sich wie der Go-Handler: PATCH /state ändert den Stand und damit den Stempel, liefert aber keinen
// ETag; erst der GET liefert ihn. Ein PUT mit veraltetem If-Match bekommt 412 (Konflikt).
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/routes/compare/__tests__/compare_hub_archiv_uebernahme_3442.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer, ohneTypen, werte, type Knoten } from '../../../lib/components/shared/__tests__/svelteInstanzPruefstand.ts';
import { clearEtagRegistry, getKnownEtag, setKnownEtag } from '../../../lib/etagRegistry.ts';
// `createSaveStatus` (Runen) ist im Prüfstand nicht herleitbar — echte SaveStatus-Instanz, gesät wie die Seite sie hält.
import { createController } from '../../../lib/components/shared/__tests__/versandVergleichPruefstand.ts';

const SEITE = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '[id]', '+page.svelte');
const ADRESSE = 'https://gregor.test/compare/c1?tab=orte';

interface Aufruf {
	method: string;
	url: string;
	ifMatch: string | null;
	body?: any;
}

/** Ersatz-Server: ein Vergleich mit Fassung (Stempel `"vN"`), PATCH /state archiviert und erhöht die Fassung. */
function server(opt: { getScheitert?: boolean } = {}) {
	const stand: Knoten = { id: 'c1', name: 'Vergleich', location_ids: ['a', 'b'], schedule: 'daily', previous_schedule: 'daily', archived_at: null };
	let fassung = 1;
	const aufrufe: Aufruf[] = [];
	const fetchFn = (async (url: any, init?: any) => {
		const method = String(init?.method ?? 'GET');
		const ifMatch = new Headers(init?.headers).get('If-Match');
		const body = init?.body ? JSON.parse(init.body) : undefined;
		aufrufe.push({ method, url: String(url), ifMatch, body });
		const u = String(url);
		if (method === 'PATCH' && u.endsWith('/api/compare/presets/c1/state')) {
			stand.archived_at = body?.archived ? '2026-11-27T10:00:00Z' : null;
			fassung++;
			return new Response(JSON.stringify(stand), { status: 200 });
		}
		if (method === 'GET' && u.endsWith('/api/compare/presets/c1')) {
			if (opt.getScheitert) return new Response('{"detail":"boom"}', { status: 500 });
			return new Response(JSON.stringify(stand), { status: 200, headers: { ETag: `"v${fassung}"` } });
		}
		if (method === 'PUT' && u.endsWith('/api/compare/presets/c1')) {
			if (ifMatch && ifMatch !== `"v${fassung}"`) return new Response('{"detail":"conflict"}', { status: 412 });
			Object.assign(stand, body);
			fassung++;
			return new Response(JSON.stringify(stand), { status: 200, headers: { ETag: `"v${fassung}"` } });
		}
		return new Response('{}', { status: 200 });
	}) as typeof fetch;
	return { aufrufe, fetchFn, stand };
}

let originalFetch: typeof fetch;
let originalWindow: unknown;
let fenster: Knoten;

beforeEach(() => {
	clearEtagRegistry();
	originalFetch = globalThis.fetch;
	originalWindow = (globalThis as any).window;
	// Fenster-Umgebung: Adresse (der Hub liest ?tab=) und die Ereignis-Schnittstelle, die api.ts beim Laden und je
	// Abruf benutzt; Navigation/Neuladen werden aufgezeichnet.
	fenster = {
		location: { href: ADRESSE, reloads: 0, reload() { this.reloads++; } },
		addEventListener() {},
		removeEventListener() {},
		dispatchEvent: () => true
	};
	(globalThis as any).window = fenster;
});
afterEach(() => {
	globalThis.fetch = originalFetch;
	(globalThis as any).window = originalWindow;
});

async function bis(bedingung: () => boolean, was: string): Promise<void> {
	const ende = Date.now() + 5000;
	while (!bedingung()) {
		if (Date.now() > ende) assert.fail(`Zeitüberschreitung beim Warten auf: ${was}`);
		await new Promise((r) => setTimeout(r, 5));
	}
}
async function ruhe(): Promise<void> {
	for (let i = 0; i < 10; i++) await Promise.resolve();
	await new Promise((r) => setTimeout(r, 120));
}

/** Die `$derived`-Werte der Seite neu herleiten (der Prüfstand wertet sie nur beim Aufbau aus). */
function neuHerleiten(k: { ast: Knoten; quelle: string; u: Knoten }): void {
	for (const stmt of (k.ast.instance?.content?.body ?? []) as Knoten[]) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.type !== 'Identifier' || !d.init) continue;
			if (!/^\$derived/.test(k.quelle.slice(d.init.start, d.init.end))) continue;
			try {
				k.u[d.id.name] = werte(ohneTypen(k.quelle, d.init), k.u);
			} catch {
				/* Herleitungen, die Browser-Zustand brauchen (page.url …), sind hier nicht Gegenstand */
			}
		}
	}
}

async function hub(srv: ReturnType<typeof server>) {
	globalThis.fetch = srv.fetchFn;
	const k = await umgebungFuer(SEITE, { data: { preset: { ...srv.stand }, locations: [], profile: { mail_to: 'a@example.org' } }, hubSaveCtl: createController('c1') }, { jsAlsTs: true });
	// Stempel aus dem Seitenaufbau (wie adoptEtagFromPageLoad): Fassung 1.
	setKnownEtag('c1', '"v1"');
	return k;
}

const ARCHIVIERT_MELDUNG = 'Archiviert. Im Archiv kannst du es reaktivieren.';

describe('F003/AC-5: Archivieren im Orts-Vergleich-Hub übernimmt den frischen Stand ohne Konflikt', () => {
	test('nach bestätigtem Archivieren: frischer Stand und neuer Stempel übernommen, Status „archiviert“, keine Navigation', async () => {
		const srv = server();
		const k = await hub(srv);
		const vorher = k.u.currentPreset;
		k.u.handleAction('archive');
		await bis(() => k.u.uebernommeneFassung === 1, 'Übernahme des frischen Stands nach dem Archivieren');
		await ruhe();
		neuHerleiten(k);
		assert.equal(getKnownEtag('c1'), '"v2"', 'der neue Stempel nach dem Archivieren steht nicht in der Registry');
		assert.notEqual(k.u.currentPreset, vorher, 'der frische Stand wurde nicht übernommen');
		assert.equal(k.u.currentPreset.archived_at, '2026-11-27T10:00:00Z', 'übernommener Stand ist nicht der archivierte');
		assert.equal(k.u.kopfStatus, 'archived', 'Status zeigt nicht „archiviert“');
		assert.equal(k.u.aktionMsg, ARCHIVIERT_MELDUNG);
		assert.equal(fenster.location.href, ADRESSE, 'Archivieren navigiert');
		assert.equal(fenster.location.reloads, 0, 'Archivieren lädt die Seite neu');
	});

	test('folgendes Speichern (Name ändern) trägt den neuen Stempel und läuft ohne Konflikt (kein 412)', async () => {
		const srv = server();
		const k = await hub(srv);
		k.u.handleAction('archive');
		// Bewusst NICHT auf die Übernahme warten: gemessen wird, was das nächste Speichern nach dem Archivieren trägt.
		await bis(() => k.u.aktionMsg === ARCHIVIERT_MELDUNG, 'Archivieren bestätigt');
		await ruhe();
		let zu = 0;
		await k.u.onSaveField('name', 'Neuer Name', () => void zu++);
		const puts = srv.aufrufe.filter((a) => a.method === 'PUT');
		assert.equal(puts.length, 1, `genau ein PUT erwartet: ${JSON.stringify(srv.aufrufe)}`);
		assert.equal(puts[0].ifMatch, '"v2"', 'Speichern nach dem Archivieren trägt den veralteten Stempel (Konflikt)');
		assert.equal(zu, 1, 'Speichern nach dem Archivieren endete nicht erfolgreich (Konflikt-Banner)');
		assert.notEqual(k.u.hubSaveCtl.state, 'conflict', 'Konflikt nach dem Archivieren');
	});

	test('scheitert das Nachholen des Stands, zeigt der Status trotzdem „archiviert“ (Override), keine Navigation', async () => {
		const srv = server({ getScheitert: true });
		const k = await hub(srv);
		k.u.handleAction('archive');
		await bis(() => srv.aufrufe.some((a) => a.method === 'GET'), 'Nachholen des Stands');
		await ruhe();
		neuHerleiten(k);
		assert.equal(k.u.uebernommeneFassung, 0, 'Vorbedingung: der gescheiterte GET baut nichts neu auf');
		assert.equal(k.u.currentPreset.archived_at, null, 'Vorbedingung: der alte Stand bleibt');
		assert.equal(k.u.kopfStatus, 'archived', 'Status zeigt nach dem Archivieren nicht „archiviert“');
		assert.equal(k.u.aktionMsg, ARCHIVIERT_MELDUNG);
		assert.equal(fenster.location.href, ADRESSE);
	});
});

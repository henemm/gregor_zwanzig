// Fix-Loop 3 — Issue #2278, F021/F024 (AC-3, AC-5, AC-7, AC-12, AC-16): die WIRKUNG der Lebenszyklus-Aktionen
// im Compare-Hub als Verhalten — nach dem Muster von trip_hub_aktionen_verhalten. Der ECHTE Instanz-Code
// von routes/compare/[id]/+page.svelte (Pruefstand `umgebungFuer`) laeuft gegen einen Ersatz-Server;
// gemessen werden die Requests.
//
// Grenze: Pausieren/Fortsetzen schreibt der Hub NICHT selbst, sondern ueber das Kind `CompareDetail`
// (`compareDetailRef.toggleActiveFromParent()` -> CompareTabs.handleToggleActive -> PUT). Der Hub-Test
// misst hier nur die Schnittstelle zum Kind (genau ein Aufruf, Fehlschlag landet in `pauseError`) mit einem
// Stellvertreter. Der ECHTE Weg samt PUT steht in compare_hub_pausieren_kette.test.ts (Seite -> CompareDetail
// -> CompareTabs -> Ersatz-Server); subscription_pausieren_zielzustand.test.ts bewacht nur den Listen-Adapter.
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/routes/compare/__tests__/compare_hub_aktionen_verhalten.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer } from '../../../lib/components/shared/__tests__/svelteInstanzPruefstand.ts';
import { clearEtagRegistry } from '../../../lib/etagRegistry.ts';

const SEITE = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '[id]', '+page.svelte');

interface Aufruf {
	method: string;
	url: string;
	body?: any;
}
let aufrufe: Aufruf[] = [];
let offen = 0;
let originalFetch: typeof fetch;
let originalWindow: unknown;
let fenster: { location: { href: string; reloads: number; reload(): void } };

const PRESET = { id: 'c1', name: 'Vergleich', location_ids: ['a', 'b'], schedule: 'daily', previous_schedule: 'daily' };

beforeEach(() => {
	clearEtagRegistry();
	aufrufe = [];
	offen = 0;
	originalFetch = globalThis.fetch;
	originalWindow = (globalThis as any).window;
	fenster = { location: { href: '', reloads: 0, reload() { this.reloads++; } } };
	(globalThis as any).window = fenster;
	globalThis.fetch = (async (url: any, init?: any) => {
		aufrufe.push({ method: String(init?.method ?? 'GET'), url: String(url), body: init?.body ? JSON.parse(init.body) : undefined });
		offen++;
		try {
			return new Response(JSON.stringify(PRESET), { status: 200 });
		} finally {
			offen--;
		}
	}) as typeof fetch;
});
afterEach(() => {
	globalThis.fetch = originalFetch;
	(globalThis as any).window = originalWindow;
});

const nach = (m: string, teil: string) => aufrufe.filter((a) => a.method === m && a.url.includes(teil));
async function bis(bedingung: () => boolean, was: string): Promise<void> {
	const ende = Date.now() + 5000;
	while (!bedingung()) {
		if (Date.now() > ende) assert.fail(`Zeitueberschreitung beim Warten auf: ${was}`);
		await new Promise((r) => setTimeout(r, 5));
	}
}
/** Abwesenheitspruefung (F024): Ruhe + Zeitpuffer, in dem auch verzoegert angestossene Handler senden wuerden. */
async function ruhe(): Promise<void> {
	for (let i = 0; i < 10; i++) await Promise.resolve();
	await new Promise((r) => setTimeout(r, 120));
	await bis(() => offen === 0, 'Ruhe nach der Aktion');
}

async function hub() {
	const { u } = await umgebungFuer(SEITE, { data: { preset: { ...PRESET }, locations: [], profile: { mail_to: 'a@example.org' } } }, { jsAlsTs: true });
	const toggles: number[] = [];
	let ergebnis = true;
	u.compareDetailRef = { toggleActiveFromParent: async () => (toggles.push(1), ergebnis) };
	return { u, toggles, kindScheitert: () => (ergebnis = false), aktion: (id: string) => u.handleAction(id) };
}

describe('F021: Pausieren/Fortsetzen erreichen den Schreibweg des Hubs', () => {
	test('„pause" und „resume" rufen toggleActiveFromParent je genau einmal; kein Fehler', async () => {
		const { aktion, toggles, u } = await hub();
		aktion('pause');
		await bis(() => toggles.length === 1 && u.isPausing === false, 'Ende von „pause"');
		aktion('resume');
		await bis(() => toggles.length === 2 && u.isPausing === false, 'Ende von „resume"');
		assert.equal(u.pauseError, null);
	});

	test('scheitert das Kind, meldet der Hub die Fehlermeldung', async () => {
		const { aktion, kindScheitert, u } = await hub();
		kindScheitert();
		aktion('pause');
		await bis(() => typeof u.pauseError === 'string', 'pauseError');
		assert.match(u.pauseError, /Status-Änderung fehlgeschlagen/);
	});
});

describe('F021: Archivieren, Reaktivieren, Loeschen', () => {
	test('„archive" -> PATCH /state {archived:true}, danach zurueck in die Liste', async () => {
		const { aktion } = await hub();
		aktion('archive');
		await bis(() => nach('PATCH', '/state').length === 1 && fenster.location.href === '/compare', 'Archivieren');
		assert.deepEqual(nach('PATCH', '/state').map((a) => [a.url, a.body]), [['/api/compare/presets/c1/state', { archived: true }]]);
	});

	test('„unarchive" -> PATCH /state {archived:false}, danach Neuladen', async () => {
		const { aktion } = await hub();
		aktion('unarchive');
		await bis(() => nach('PATCH', '/state').length === 1 && fenster.location.reloads === 1, 'Reaktivieren');
		assert.deepEqual(nach('PATCH', '/state').map((a) => a.body), [{ archived: false }]);
		assert.equal(fenster.location.href, '', 'Reaktivieren darf nicht in die Liste springen');
	});

	test('„delete" oeffnet nur den Dialog; erst die Bestaetigung loescht (DELETE) und fuehrt in die Liste', async () => {
		const { aktion, u } = await hub();
		aktion('delete');
		await ruhe();
		assert.equal(u.deleteDialogOpen, true);
		assert.equal(nach('DELETE', '/c1').length, 0, 'Loeschen ohne Rueckfrage');
		await u.handleDeleteConfirm();
		assert.equal(u.deleteDialogOpen, false);
		assert.deepEqual(nach('DELETE', '/c1').map((a) => a.url), ['/api/compare/presets/c1']);
		assert.equal(fenster.location.href, '/compare');
	});
});

describe('F021/F024: Senden erst nach Bestaetigung', () => {
	test('Aktion „send" im Hub-Dispatch sendet nichts — auch nicht verzoegert', async () => {
		const { aktion } = await hub();
		aktion('send');
		await ruhe();
		assert.equal(nach('POST', '/send').length, 0);
	});

	test('handleTestSend (Bestaetigung des Dialogs) -> genau ein POST /api/briefings/c1/send?kind=vergleich, Meldung gesetzt', async () => {
		const { u } = await hub();
		await u.handleTestSend();
		assert.deepEqual(nach('POST', '/send').map((a) => a.url), ['/api/briefings/c1/send?kind=vergleich']);
		assert.equal(typeof u.sendMsg, 'string');
		assert.equal(u.isSending, false);
	});
});

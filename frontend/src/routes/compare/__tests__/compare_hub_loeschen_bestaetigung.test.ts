// Issue #2214: Compare-Hub loescht den Ortsvergleich ohne Rueckfrage — fortgeschrieben durch #3442.
//
// Spec: docs/specs/modules/bug_2214_compare_hub_delete_confirm.md (AC-1..AC-4), fortgeschrieben durch
// docs/specs/modules/feat_3442_kebab_rueckfragen.md (AC-1, AC-2, AC-12, AC-13): die Rueckfrage
// („Löschen?“ / „Endgültig löschen“ / „Abbrechen“) sitzt seit #3442 IM Kebab-Menue bzw. Aktionsblatt
// (KebabBestaetigungPanel); dass vor der Bestaetigung nichts an die Seite geht, belegt
// shared/__tests__/kebab_seiten_bindung.test.ts. Die Seite selbst hat keinen ConfirmDialog mehr:
// `handleAction('delete')` ist die BESTAETIGTE Aktion und loescht direkt.
//
// Pruefstand: der ECHTE Instanz-Code von routes/compare/[id]/+page.svelte (svelteInstanzPruefstand.umgebungFuer)
// laeuft gegen einen Ersatz-Netzwerkrand (fetch, window.location); gemessen werden Requests, Navigation und
// die angezeigte Meldung (Text aus kebabBestaetigung.fehlerText, gleich welche Variable ihn traegt).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/compare/__tests__/compare_hub_loeschen_bestaetigung.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer } from '../../../lib/components/shared/__tests__/svelteInstanzPruefstand.ts';
import { clearEtagRegistry } from '../../../lib/etagRegistry.ts';

const SEITE = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '[id]', '+page.svelte');
const PRESET = { id: 'cp-2214', name: 'Dolomiten Süd', location_ids: ['a', 'b'], schedule: 'daily', previous_schedule: 'daily' };

interface Aufruf {
	url: string;
	method: string;
}
/** Antwort je Methode: Status + Body, oder 'netz' (fetch wirft wie im Browser). */
type Antwort = { status: number; body?: unknown } | 'netz';

let aufrufe: Aufruf[] = [];
let antwortFuer: Record<string, Antwort> = {};
let originalFetch: typeof fetch;
let originalWindow: unknown;
let fenster: { location: { href: string; reloads: number; reload(): void } };

beforeEach(() => {
	clearEtagRegistry();
	aufrufe = [];
	antwortFuer = {};
	originalFetch = globalThis.fetch;
	originalWindow = (globalThis as any).window;
	fenster = { location: { href: '/compare/cp-2214', reloads: 0, reload() { this.reloads++; } } };
	(globalThis as any).window = fenster;
	globalThis.fetch = (async (url: any, init?: any) => {
		const method = String(init?.method ?? 'GET');
		aufrufe.push({ url: String(url), method });
		const a = antwortFuer[method] ?? { status: 200, body: PRESET };
		if (a === 'netz') throw new TypeError('Failed to fetch');
		return new Response(a.body === undefined ? '' : JSON.stringify(a.body), { status: a.status, headers: { 'Content-Type': 'application/json' } });
	}) as typeof fetch;
});
afterEach(() => {
	globalThis.fetch = originalFetch;
	(globalThis as any).window = originalWindow;
});

async function hub() {
	const { u } = await umgebungFuer(SEITE, { data: { preset: { ...PRESET }, locations: [], profile: { mail_to: 'a@example.org' } } }, { jsAlsTs: true });
	u.compareDetailRef = { toggleActiveFromParent: async () => true };
	return u as Record<string, any>;
}

const loeschen = (a: Aufruf) => a.method === 'DELETE';
const meldet = (u: Record<string, any>, text: string) => Object.values(u).some((v) => v === text);
async function bis(bedingung: () => boolean, was: string): Promise<void> {
	const ende = Date.now() + 5000;
	while (!bedingung()) {
		if (Date.now() > ende) assert.fail(`Zeitueberschreitung beim Warten auf: ${was}`);
		await new Promise((r) => setTimeout(r, 5));
	}
}
const ruhe = async () => {
	for (let i = 0; i < 10; i++) await Promise.resolve();
	await new Promise((r) => setTimeout(r, 60));
};

describe('#2214 AC-1/AC-2 → #3442: die Rueckfrage sitzt im Kebab-Menue, nicht mehr als Seitendialog', () => {
	test('die Seite haelt keinen eigenen Loesch-Dialog mehr (kein deleteDialogOpen, keine Dialog-Handler)', async () => {
		const u = await hub();
		for (const n of ['deleteDialogOpen', 'handleDeleteConfirm', 'handleDeleteCancel', 'handleDeleteDialogOpenChange'])
			assert.ok(!(n in u), `Compare-Hub haelt noch ${n} (Seitendialog statt Rueckfrage im Menue)`);
	});
});

describe('#2214 AC-3 → #3442 AC-2: bestaetigtes Loeschen', () => {
	test('handleAction("delete") (im Menue bestaetigt) sendet genau einen DELETE und navigiert nach /compare', async () => {
		const u = await hub();
		u.handleAction('delete');
		await bis(() => aufrufe.filter(loeschen).length === 1 && fenster.location.href === '/compare', 'DELETE und Navigation');
		await ruhe();
		const del = aufrufe.filter(loeschen);
		assert.equal(del.length, 1);
		assert.equal(del[0].url, '/api/compare/presets/cp-2214');
		assert.equal(u.isDeleting, false, 'isDeleting wird nach dem Request zurueckgesetzt');
	});
});

describe('#2214 AC-4 → #3442 AC-12: Fehler beim Loeschen/Archivieren — Hub bleibt, Meldung nach Fehlerklasse', () => {
	const faelle: Array<[string, string, Antwort, string]> = [
		['delete', 'DELETE', { status: 500 }, 'Löschen hat nicht geklappt: Fehler auf dem Server. Versuch es später noch einmal.'],
		['delete', 'DELETE', 'netz', 'Löschen hat nicht geklappt: keine Verbindung zum Server. Versuch es gleich noch einmal.'],
		['delete', 'DELETE', { status: 409, body: { detail: 'Der Vergleich wird gerade bearbeitet.' } }, 'Der Vergleich wird gerade bearbeitet.'],
		['archive', 'PATCH', 'netz', 'Archivieren hat nicht geklappt: keine Verbindung zum Server. Versuch es gleich noch einmal.'],
		['archive', 'PATCH', { status: 503 }, 'Archivieren hat nicht geklappt: Fehler auf dem Server. Versuch es später noch einmal.']
	];
	for (const [id, method, antwort, text] of faelle) {
		const art = antwort === 'netz' ? 'Netzfehler' : `HTTP ${antwort.status}`;
		test(`„${id}“ mit ${art} ⇒ „${text}“, keine Navigation, kein Neuladen`, async () => {
			antwortFuer[method] = antwort;
			const u = await hub();
			u.handleAction(id);
			await bis(() => aufrufe.some((a) => a.method === method), `${method}-Anfrage`);
			await bis(() => meldet(u, text), `Meldung „${text}“`);
			assert.equal(fenster.location.href, '/compare/cp-2214', 'Navigation trotz Fehler');
			assert.equal(fenster.location.reloads, 0, 'Neuladen trotz Fehler');
			if (id === 'delete') assert.equal(u.isDeleting, false);
		});
	}
});

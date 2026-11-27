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

async function hub(preset: Record<string, unknown> = PRESET) {
	const { u } = await umgebungFuer(SEITE, { data: { preset: { ...preset }, locations: [], profile: { mail_to: 'a@example.org' } } }, { jsAlsTs: true });
	const toggles: number[] = [];
	let ergebnis = true;
	u.compareDetailRef = { toggleActiveFromParent: async () => (toggles.push(1), ergebnis) };
	// #3443: $app/navigation ist unter node nicht ladbar — goto wird mitgeschrieben (Muster Trip-Hub-Test).
	const gotos: unknown[][] = [];
	u.goto = (...args: unknown[]) => void gotos.push(args);
	return { u, toggles, gotos, kindScheitert: () => (ergebnis = false), aktion: (id: string) => u.handleAction(id) };
}

describe('F021: Pausieren/Fortsetzen erreichen den Schreibweg des Hubs', () => {
	test('„pause" und „resume" rufen toggleActiveFromParent je genau einmal; kein Fehler', async () => {
		const { aktion, toggles, u } = await hub();
		aktion('pause');
		await bis(() => toggles.length === 1 && u.isPausing === false, 'Ende von „pause"');
		aktion('resume');
		await bis(() => toggles.length === 2 && u.isPausing === false, 'Ende von „resume"');
		assert.equal(u.pauseError, false);
	});

	test('scheitert das Kind, meldet der Hub die Fehlermeldung', async () => {
		const { aktion, kindScheitert, u } = await hub();
		kindScheitert();
		aktion('pause');
		// Issue #2659 (i18n F10): Flag statt eingefrorenem Text (Text beim Rendern, listen.meldung.status_fehlgeschlagen).
		await bis(() => u.pauseError === true, 'pauseError');
		assert.equal(u.pauseError, true);
	});
});

// #3442 (feat_3442 AC-2/AC-5/AC-10/AC-11): die Rückfrage für Archivieren/Löschen sitzt im Kebab-Menü
// (kebab_seiten_bindung.test.ts); handleAction kommt erst nach der Bestätigung an und wirkt direkt.
// Archivieren und Reaktivieren bleiben auf der Seite (kein Sprung zur Liste, kein Neuladen) mit Meldung.
/** Steht der Meldungstext im Zustand der Seite (gleich welche Variable ihn trägt)? */
const meldet = (u: Record<string, any>, text: string) => Object.values(u).some((v) => v === text);

describe('F021 → #3442: Archivieren, Reaktivieren, Loeschen', () => {
	test('„archive" (im Menü bestätigt) -> PATCH /state {archived:true}, bleibt auf der Seite, Meldung „Archiviert. …“ (AC-5)', async () => {
		const { aktion, u } = await hub();
		aktion('archive');
		await bis(() => nach('PATCH', '/state').length === 1, 'Archivieren');
		await ruhe();
		assert.deepEqual(nach('PATCH', '/state').map((a) => [a.url, a.body]), [['/api/compare/presets/c1/state', { archived: true }]]);
		assert.equal(fenster.location.href, '', 'Archivieren springt in die Liste');
		assert.equal(fenster.location.reloads, 0, 'Archivieren lädt die Seite neu');
		assert.ok(meldet(u, 'Archiviert. Im Archiv kannst du es reaktivieren.'), 'Erfolgsmeldung „Archiviert. …“ fehlt');
	});

	test('„unarchive" -> PATCH /state {archived:false} ohne Rückfrage und ohne Neuladen, Meldung „Reaktiviert.“ (AC-10)', async () => {
		const { aktion, u } = await hub();
		aktion('unarchive');
		await bis(() => nach('PATCH', '/state').length === 1, 'Reaktivieren');
		await ruhe();
		assert.deepEqual(nach('PATCH', '/state').map((a) => a.body), [{ archived: false }]);
		assert.equal(fenster.location.href, '', 'Reaktivieren darf nicht in die Liste springen');
		assert.equal(fenster.location.reloads, 0, 'Reaktivieren lädt die Seite neu');
		assert.ok(meldet(u, 'Reaktiviert.'), 'Erfolgsmeldung „Reaktiviert.“ fehlt');
	});

	test('„delete" (im Menü bestätigt) -> genau ein DELETE, danach in die Liste; kein Seitendialog (AC-2)', async () => {
		const { aktion, u } = await hub();
		aktion('delete');
		await bis(() => nach('DELETE', '/c1').length === 1 && fenster.location.href === '/compare', 'Loeschen');
		await ruhe();
		assert.deepEqual(nach('DELETE', '/c1').map((a) => a.url), ['/api/compare/presets/c1']);
		assert.notEqual(u.deleteDialogOpen, true, 'Seitendialog geöffnet statt gelöscht');
	});

	test('„pause"/„resume" melden bei Erfolg „Pausiert. …“ bzw. „Fortgesetzt. …“ (AC-11)', async () => {
		const { aktion, toggles, u } = await hub();
		aktion('pause');
		await bis(() => toggles.length === 1 && u.isPausing === false, 'Ende von „pause"');
		assert.ok(meldet(u, 'Pausiert. Bis ‚Fortsetzen‘ kommen keine Briefings und Alarme.'), 'Meldung „Pausiert. …“ fehlt');
		aktion('resume');
		await bis(() => toggles.length === 2 && u.isPausing === false, 'Ende von „resume"');
		assert.ok(meldet(u, 'Fortgesetzt. Das nächste Briefing kommt wie geplant.'), 'Meldung „Fortgesetzt. …“ fehlt');
	});
});

describe('F021/F024: Senden erst nach Bestaetigung', () => {
	test('Aktion „send" im Hub-Dispatch sendet nichts — auch nicht verzoegert', async () => {
		const { aktion } = await hub();
		aktion('send');
		await ruhe();
		assert.equal(nach('POST', '/send').length, 0);
	});

	// #3440: Menü „Test schicken ▾“ — der Klick auf eine Zeile ist die Auslösung (handleTest).
	test('handleTest (Alle eingerichteten Kanäle) -> genau ein POST /api/briefings/c1/send?kind=vergleich, Meldung gesetzt', async () => {
		const { u } = await hub();
		await u.handleTest({ kanal: 'alle', berichtsart: 'morning' });
		assert.deepEqual(nach('POST', '/send').map((a) => a.url), ['/api/briefings/c1/send?kind=vergleich']);
		assert.equal(u.sendStatus, 'ok');
		assert.match(String(u.sendMsg), /^Briefing geschickt: /);
		assert.equal(u.isSending, false);
	});
	test('handleTest (Einzelkanal E-Mail) -> genau ein POST mit channel=email', async () => {
		const { u } = await hub();
		await u.handleTest({ kanal: 'email', berichtsart: 'morning' });
		assert.deepEqual(nach('POST', '/send').map((a) => a.url), ['/api/briefings/c1/send?kind=vergleich&channel=email']);
	});
});

// #3443 (feat_3443 AC-4/AC-5/AC-6/AC-10): „Aktivieren“ im Orts-Vergleich-Entwurf. Der Klick schreibt nichts (kein PUT,
// kein Umschalten über das Kind), zeigt den Hinweis über den Meldungsweg der Seite (hub-aktion-meldung) und öffnet
// den Reiter Orte; fehlt nur der Name, bleibt die Seite stehen (der Name wird im Kopf bearbeitet).
const SCHREIBEND = new Set(['PUT', 'PATCH', 'POST', 'DELETE']);
const schreibAufrufe = () => aufrufe.filter((a) => SCHREIBEND.has(a.method)).map((a) => `${a.method} ${a.url}`);
const hinweise = (u: Record<string, any>) => Object.values(u).filter((v) => typeof v === 'string' && v.startsWith('Zum Aktivieren'));

describe('#3443: „Aktivieren“ im Orts-Vergleich-Entwurf nennt, was fehlt, und öffnet die Stelle — ohne Schreibzugriff', () => {
	test('ohne Orte: „activate“ -> „Zum Aktivieren fehlen noch: Orte.“ als Erfolgs-Meldung, goto ?tab=orte, nichts geschrieben', async () => {
		const { aktion, u, gotos, toggles } = await hub({ ...PRESET, location_ids: [] });
		assert.equal(u.lifecycle, 'draft', 'Messaufbau: Vergleich ohne Orte ist ein Entwurf');
		aktion('activate');
		await ruhe();
		assert.ok(meldet(u, 'Zum Aktivieren fehlen noch: Orte.'), 'Hinweis „Zum Aktivieren fehlen noch: Orte.“ fehlt');
		assert.equal(u.aktionOk, true, 'Hinweis läuft nicht über den Meldungsweg hub-aktion-meldung (aktionOk)');
		assert.equal(gotos.length, 1, `Navigation: ${JSON.stringify(gotos)}`);
		assert.match(String(gotos[0][0]), /[?&]tab=orte(&|$)/, `Ziel ${String(gotos[0][0])}`);
		assert.deepEqual(gotos[0][1], { noScroll: true, keepFocus: true }, 'goto ohne noScroll/keepFocus');
		assert.deepEqual(schreibAufrufe(), [], 'Schreibaufruf beim Aktivieren-Klick');
		assert.deepEqual(toggles, [], 'Aktivieren schaltet über den Pausier-Weg um');
		assert.equal(fenster.location.href, '', 'Aktivieren lädt eine andere Adresse');
		assert.equal(fenster.location.reloads, 0, 'Aktivieren lädt die Seite neu');
	});

	test('nur der Name fehlt: „Zum Aktivieren fehlt noch: ein Name.“, keine Navigation (AC-5)', async () => {
		const { aktion, u, gotos } = await hub({ ...PRESET, name: '' });
		aktion('activate');
		await ruhe();
		assert.ok(meldet(u, 'Zum Aktivieren fehlt noch: ein Name.'), 'Hinweis „… ein Name.“ fehlt');
		assert.deepEqual(gotos, [], 'bei nur fehlendem Namen darf nicht navigiert werden');
		assert.deepEqual(schreibAufrufe(), []);
	});

	test('Name und Orte fehlen: „Zum Aktivieren fehlen noch: Name und Orte.“, goto ?tab=orte (AC-5)', async () => {
		const { aktion, u, gotos } = await hub({ ...PRESET, name: '', location_ids: [] });
		aktion('activate');
		await ruhe();
		assert.ok(meldet(u, 'Zum Aktivieren fehlen noch: Name und Orte.'), 'Hinweis „… Name und Orte.“ fehlt');
		assert.equal(gotos.length, 1);
		assert.match(String(gotos[0][0]), /[?&]tab=orte(&|$)/);
		assert.deepEqual(schreibAufrufe(), []);
	});

	test('Kopf-Knopf (handleAktivieren) und Kebab („activate“) wirken gleich (AC-6)', async () => {
		const kopf = await hub({ ...PRESET, location_ids: [] });
		assert.equal(typeof kopf.u.handleAktivieren, 'function', 'Orte-Hub hat keine Seitenfunktion handleAktivieren (Kopf-Knopf)');
		kopf.u.handleAktivieren();
		await ruhe();
		const kebab = await hub({ ...PRESET, location_ids: [] });
		kebab.aktion('activate');
		await ruhe();
		assert.ok(kopf.gotos.length === 1 && hinweise(kopf.u).length >= 1, 'Kopf-Knopf wirkt nicht');
		assert.deepEqual({ gotos: kebab.gotos, hinweise: hinweise(kebab.u) }, { gotos: kopf.gotos, hinweise: hinweise(kopf.u) });
	});

	test('vollständiger Vergleich (Stand-Wettlauf): „activate“ zeigt nichts, navigiert nicht, schreibt nicht', async () => {
		const { aktion, u, gotos } = await hub();
		aktion('activate');
		await ruhe();
		assert.deepEqual(hinweise(u), []);
		assert.deepEqual(gotos, []);
		assert.deepEqual(schreibAufrufe(), []);
	});
});

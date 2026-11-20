// Fix-Loop 4 — Issue #3197 (Workflow feat-3197-tempo-je-etappe), Adversary Runde 3 F001/F002/F004.
// Spec: docs/specs/modules/feat_3197_tempo_je_etappe.md — AC-2, AC-5, AC-6
//
// Gemessen dort, wo es WIRKT: am PUT, der das Netz verlässt. Gesät ist NUR die Netzgrenze
// (`api.put` zeichnet den Rumpf auf) und der Speicher-Regler als Prop (`saveController.schedule`
// sammelt die Speicherfunktion; der Test löst sie aus wie der Regler nach der Entprellung).
// Alles dazwischen ist ECHT: Instanz-Skript des Panels (svelteInstanzPruefstand), sein
// scheduleSave → buildStagesSave → baueTripSpeicherung → etappenStand.autoSaveClient → etappenRumpf,
// bzw. save() → etappenStand.direktClient → etappenRumpf.
//
//   F001 (AC-5) Rückruf der Etappen-Karte („Tempo ändern" → Grundtempo) löst einen PUT aus,
//               dessen Rumpf stages[i].grundtempo_kmh trägt.
//   F002 (AC-6/AC-5) Fortbewegungswechsel: der PUT (Autosave UND direktes Speichern) trägt das
//               neue Trip-Tempo und die Etappen ohne grundtempo_kmh.
//   F004 (AC-2) Die geöffnete Etappen-Karte ist mit dem Etappen-Tempo vorbelegt (SSR-DOM).
//
//   cd frontend && npm test -- src/lib/components/trip-detail/__tests__/tempo_je_etappe_3197_fixloop4.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const T = await import('./f9Pruefstand.ts');
const P = await import('../../shared/__tests__/svelteInstanzPruefstand.ts');
const { umgebungFuer, findeKomponenten, attributAusdruck, werte } = P;
const { render } = await import('svelte/server');
const { createRawSnippet } = await import('svelte');
const { baum, alle } = await import('../../shared/hub-kopf/__tests__/htmlBaum.ts');
type Knoten = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const PANEL = path.join(T.KOMP, 'edit', 'EditStagesPanelNew.svelte');
const { locale } = T;
afterEach(() => locale.set('de'));

const TABELLE = JSON.parse(readFileSync(path.resolve(T.FRONTEND, '..', 'tests', 'fixtures', 'naismith_dav_paritaet.json'), 'utf-8'));
const UE = TABELLE.etappen_ueberschreibung;
const TRIP_TEMPO = UE.tempo; // zu Fuß, 4 km/h
/** S1 folgt dem Trip, S2 überschreibt auf 3 km/h (Falltabelle). */
const etappen = () => structuredClone(UE.stages) as Knoten[];
const ohne = () => etappen().map(({ grundtempo_kmh: _x, ...s }: Knoten) => s);

/** Panel mit gesäter Netzgrenze. `regler: false` ⇒ ohne Speicher-Regler (direktes Speichern). */
async function panel(stages: Knoten[], regler = true) {
	const puts: { pfad: string; rumpf: Knoten }[] = [];
	const api = {
		put: async (pfad: string, rumpf: Knoten) => {
			puts.push({ pfad, rumpf: JSON.parse(JSON.stringify(rumpf)) });
			return { id: 't', stages: rumpf.stages, ...(rumpf.tempo ? { tempo: rumpf.tempo } : {}) };
		}
	};
	const geplant: Array<(init?: RequestInit) => Promise<void>> = [];
	const saveController = regler
		? { schedule: (fn: (init?: RequestInit) => Promise<void>) => geplant.push(fn), defer: () => {}, imWiederholen: false }
		: undefined;
	const r = await umgebungFuer(PANEL, { stages, tripId: 't', showSave: false, tempo: { ...TRIP_TEMPO }, saveController, api, onTripUpdate: undefined });
	assert.equal(typeof r.u.scheduleSave, 'function', 'Messaufbau: scheduleSave nicht herleitbar');
	assert.equal(typeof r.u.etappenStand?.autoSaveClient?.put, 'function', 'Messaufbau: etappenStand nicht herleitbar');
	/** Was der Regler nach der Entprellung tut: die zuletzt geplante Speicherfunktion ausführen. */
	const reglerFeuert = async () => {
		assert.ok(geplant.length >= 1, 'kein Speichern geplant');
		await geplant[geplant.length - 1]();
	};
	return { ...r, puts, geplant, reglerFeuert };
}

/** Rückruf-Attribut der einzigen Einbettung `komp`, ausgewertet mit Snippet-Parametern. */
function rueckruf(p: Knoten, komp: string, attr: string, lokal: Knoten): (...a: unknown[]) => unknown {
	const treffer = findeKomponenten(p.ast, komp);
	assert.equal(treffer.length, 1, `Messaufbau: genau eine ${komp}-Einbettung erwartet (${treffer.length})`);
	const ausdruck = attributAusdruck(treffer[0], p.quelle, attr);
	assert.ok(ausdruck, `${komp}: Attribut ${attr} fehlt`);
	const f = werte(ausdruck!, Object.assign(Object.create(p.u), lokal));
	assert.equal(typeof f, 'function', `${komp}.${attr} ist keine Funktion`);
	return f as (...a: unknown[]) => unknown;
}

// ═══ F001 (AC-5): Etappen-Tempo setzen löst den PUT aus ════════════════════════════════════
describe('F001 (AC-5): „Tempo ändern" einer Etappe wird gespeichert', () => {
	test('Desktop: onchange der Etappen-Karte ⇒ PUT mit stages[0].grundtempo_kmh = 5, S2 behält 3', async () => {
		const p = await panel(etappen());
		rueckruf(p, 'TempoKarteInhalt', 'onchange', { stage: p.u.stages[0] })({ fortbewegung: 'fuss', grundtempo_kmh: 5 });
		assert.equal(p.geplant.length, 1, 'Etappen-Tempo setzen plant kein Speichern');
		await p.reglerFeuert();
		assert.equal(p.puts.length, 1, 'kein PUT');
		assert.equal(p.puts[0].pfad, '/api/trips/t');
		assert.equal(p.puts[0].rumpf.stages[0].grundtempo_kmh, 5, 'PUT trägt das neue Etappen-Tempo nicht');
		assert.equal(p.puts[0].rumpf.stages[1].grundtempo_kmh, 3, 'übrige Überschreibung geht verloren');
		assert.ok(!('tempo' in p.puts[0].rumpf), 'Trip-Tempo unverändert ⇒ kein tempo im Rumpf');
	});

	test('Mobil: onetappentempo der StageCardM ⇒ PUT mit stages[1].grundtempo_kmh = 2.5', async () => {
		const p = await panel(etappen());
		rueckruf(p, 'StageCardM', 'onetappentempo', { stage: p.u.stages[1], i: 1 })({ fortbewegung: 'fuss', grundtempo_kmh: 2.5 });
		await p.reglerFeuert();
		assert.equal(p.puts.length, 1, 'kein PUT (mobil)');
		assert.equal(p.puts[0].rumpf.stages[1].grundtempo_kmh, 2.5, 'PUT trägt das neue Etappen-Tempo nicht (mobil)');
	});
});

// ═══ F002 (AC-6/AC-5): neues Trip-Tempo im Speicher-Rumpf ═══════════════════════════════════
describe('F002 (AC-6): Fortbewegungswechsel speichert neues Trip-Tempo und verworfene Etappen', () => {
	const RAD = { fortbewegung: 'rad', grundtempo_kmh: 20 };

	test('Autosave: Tempo-Karte des Reiters (Rad) ⇒ PUT { tempo: Rad 20, stages ohne grundtempo_kmh }', async () => {
		const p = await panel(etappen());
		rueckruf(p, 'TempoKarte', 'onchange', {})({ ...RAD });
		await p.reglerFeuert();
		assert.equal(p.puts.length, 1, 'kein PUT');
		assert.deepEqual(p.puts[0].rumpf.tempo, RAD, 'neues Trip-Tempo fehlt im Autosave-Rumpf');
		assert.equal(p.puts[0].rumpf.stages.length, 2);
		assert.ok(p.puts[0].rumpf.stages.every((s: Knoten) => !('grundtempo_kmh' in s)), 'verworfene Etappen-Tempi im Rumpf');
	});

	test('Direktes Speichern (ohne Regler): save() nach Wechsel ⇒ PUT trägt tempo Rad 20', async () => {
		const p = await panel(etappen(), false);
		p.u.tempoAendern({ ...RAD });
		assert.equal(p.puts.length, 0, 'Messaufbau: ohne Regler kein Autosave');
		const antwort = await p.u.save();
		assert.ok(antwort, `save() scheiterte: ${p.u.saveError}`);
		assert.equal(p.puts.length, 1, 'kein PUT');
		assert.deepEqual(p.puts[0].rumpf.tempo, RAD, 'neues Trip-Tempo fehlt im direkten PUT');
		assert.ok(p.puts[0].rumpf.stages.every((s: Knoten) => !('grundtempo_kmh' in s)), 'verworfene Etappen-Tempi im Rumpf');
	});

	test('Ohne Tempo-Änderung: direktes Speichern schickt kein tempo (Bestandstrip unverändert)', async () => {
		const p = await panel(ohne(), false);
		await p.u.save();
		assert.equal(p.puts.length, 1);
		assert.ok(!('tempo' in p.puts[0].rumpf));
	});
});

// ═══ F004 (AC-2): Etappen-Karte mit dem Etappen-Tempo vorbelegt (DOM) ════════════════════════
describe('F004 (AC-2): Etappen-Karte zeigt beim Öffnen das Etappen-Tempo', () => {
	const kopf = () => createRawSnippet(() => ({ render: () => '<div data-testid="probe-kopf">Etappen</div>' }));
	async function karteBei(etappeId: string): Promise<string[]> {
		const ers: [string, string][] = [['let tempoEtappeId = $state<string | null>(null);', `let tempoEtappeId = $state<string | null>('${etappeId}');`]];
		const K = (await import(`${pathToFileURL(PANEL).href}?f8variante=${Buffer.from(JSON.stringify(ers)).toString('base64url')}`)).default;
		const b = baum(render(K, { props: { stages: etappen(), tripId: 't', showSave: false, tempo: TRIP_TEMPO, kopf: kopf(), listeZuerst: true } }).body);
		const karten = alle(b as never, (n: Knoten) => n.attrs['data-testid'] === 'etappen-tempo-karte');
		assert.equal(karten.length, 1, `Messaufbau: genau eine geöffnete Etappen-Karte erwartet (${karten.length})`);
		return alle(karten[0] as never, (n: Knoten) => n.attrs['data-testid'] === 'tempo-grundtempo').map((n: Knoten) => String(n.attrs.value));
	}

	test('S2 (eigenes Tempo 3 km/h) ⇒ Feld zeigt 3, nicht das Trip-Tempo 4', async () => {
		assert.deepEqual(await karteBei('S2'), ['3']);
	});

	test('S1 (folgt dem Trip) ⇒ Feld zeigt das Trip-Tempo 4', async () => {
		assert.deepEqual(await karteBei('S1'), ['4']);
	});
});

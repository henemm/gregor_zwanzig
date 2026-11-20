// TDD RED: Issue #3197 (Workflow feat-3197-tempo-je-etappe) — Grundtempo je Etappe (ADR-0108).
// Spec: docs/specs/modules/feat_3197_tempo_je_etappe.md — AC-1, AC-2, AC-4, AC-6, AC-7, AC-10
//
// Reine Funktionen, ECHTE Module, ECHTER Katalog, kein Mock. Sollwerte aus der gemeinsamen
// Falltabelle tests/fixtures/naismith_dav_paritaet.json, Abschnitt "etappen_ueberschreibung"
// (dieselbe lesen Go internal/model/naismith_stage_tempo_3197_test.go und Python
// tests/test_3197_tempo_je_etappe.py).
//
// ── VERTRAG für den Developer (von RED festgelegt) ──────────────────────────────────────
// naismith.ts:
//   stageTempo(stage, tripTempo: Tempo): Tempo
//     Fortbewegung immer vom Trip; Grundtempo = stage.grundtempo_kmh, wenn Zahl in 0,5..60,
//     sonst Trip-Grundtempo. (AC-2, ungültige Werte ⇒ Trip-Tempo)
//   verwirfEtappenTempo(stages: Stage[]): { stages: Stage[]; anzahl: number }
//     entfernt grundtempo_kmh aus JEDER Etappe (Feld gelöscht, nicht undefined gesetzt), übrige
//     Etappenfelder unverändert, Eingabe nicht mutiert; anzahl = Zahl der Etappen, die das Feld
//     trugen. (AC-6, Fortbewegungswechsel)
//   ohneEtappenTempo(stage: Stage): Stage
//     „Trip-Tempo verwenden": dieselbe Etappe ohne grundtempo_kmh, sonst unverändert. (AC-4)
// edit/etappenListe.ts — EtappenZeile bekommt zwei Felder:
//   eigenesTempo?: boolean   true, wenn die Etappe ein gültiges eigenes Grundtempo trägt
//   tempoAendern?: boolean   true bei Etappe mit Wegpunkten (Knopf „Tempo ändern"), Pausentag: fehlt/false
//   etappenZeile(stage, index, lang, t, tripTempo) rechnet die Gehzeit mit stageTempo(stage, tripTempo).
// Katalog trip.json DE/EN (AC-10):
//   trip.tempo.hinweis                          (Wert enthält jetzt „je Etappe überschreibbar")
//   trip.tempo.trip_tempo_verwenden             „Trip-Tempo verwenden"
//   trip.tempo.eigenes_tempo                    Kennzeichen einer Etappe mit eigenem Tempo
//   trip.tempo.etappen_zurueckgesetzt.one/.other  Plural nach Katalogkonvention (x.one/x.other, {count})
//   trip.hub.tempo_aendern                      existiert schon
// ─────────────────────────────────────────────────────────────────────────────────────
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/utils/naismith_stage_tempo_3197.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Namensraum-Importe: eine fehlende Funktion lässt den einzelnen Test scheitern, nicht die ganze Datei.
import * as N from './naismith.ts';
import * as L from '../components/edit/etappenListe.ts';
import { trFor, trnFor } from '../i18n/index.ts';
import type { Stage, Tempo } from '../types.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TABELLE = JSON.parse(
	readFileSync(path.resolve(HERE, '../../../../tests/fixtures/naismith_dav_paritaet.json'), 'utf-8')
);
const UE = TABELLE.etappen_ueberschreibung;
const TRIP_TEMPO: Tempo = UE.tempo;
const etappen = (): Stage[] => structuredClone(UE.stages);
const etappe = (id: string): Stage => etappen().find((s) => s.id === id)!;

type Lang = 'de' | 'en';
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const katalog = (lang: Lang) => (key: any, params?: Record<string, string | number>) => trFor(lang, key, params);

function fn<K extends string>(mod: Record<string, unknown>, name: K): (...a: any[]) => any { // eslint-disable-line @typescript-eslint/no-explicit-any
	const f = mod[name];
	assert.equal(typeof f, 'function', `TDD RED: ${name} fehlt`);
	return f as (...a: any[]) => any; // eslint-disable-line @typescript-eslint/no-explicit-any
}

// ═══ stageTempo gegen die Falltabelle (AC-2) ════════════════════════════════════════════
describe('#3197 stageTempo (AC-2): Falltabelle etappen_ueberschreibung', () => {
	for (const id of ['S1', 'S2'] as const) {
		test(`${id}: Ankünfte ${UE.erwartet[id].ankuenfte.join('/')}`, () => {
			const stageTempo = fn(N, 'stageTempo');
			const s = etappe(id);
			const tempo = stageTempo(s, TRIP_TEMPO) as Tempo;
			assert.deepEqual(N.computeArrivalTimes(s, undefined, tempo), UE.erwartet[id].ankuenfte);
			const sp = N.tempoSpeeds(tempo);
			assert.equal(sp.flatKmh, UE.erwartet[id].flat_kmh);
			assert.ok(Math.abs(sp.ascentMh - UE.erwartet[id].r_auf) < 1e-9, `${id}: R_auf ${sp.ascentMh}`);
			assert.ok(Math.abs(sp.descentMh - UE.erwartet[id].r_ab) < 1e-9, `${id}: R_ab ${sp.descentMh}`);
			assert.equal(L.gehzeitMinuten(s, tempo), UE.erwartet[id].gehzeit_min);
		});
	}

	test('Fortbewegung kommt immer vom Trip, nur das Grundtempo von der Etappe', () => {
		const stageTempo = fn(N, 'stageTempo');
		assert.deepEqual(stageTempo(etappe('S2'), TRIP_TEMPO), { fortbewegung: 'fuss', grundtempo_kmh: 3 });
		assert.deepEqual(stageTempo(etappe('S1'), TRIP_TEMPO), { fortbewegung: 'fuss', grundtempo_kmh: 4 });
		const rad: Tempo = { fortbewegung: 'rad', grundtempo_kmh: 20 };
		assert.deepEqual(stageTempo({ ...etappe('S2'), grundtempo_kmh: 15 }, rad), { fortbewegung: 'rad', grundtempo_kmh: 15 });
	});

	test('Positivkontrolle: ohne Auflösung rechnet S2 mit dem Trip-Tempo (Überschreibung wirkt nur über stageTempo)', () => {
		assert.deepEqual(N.computeArrivalTimes(etappe('S2'), undefined, TRIP_TEMPO), UE.erwartet.S1.ankuenfte);
	});

	for (const v of [...UE.ungueltige_werte, '3', null, Number.NaN, Number.POSITIVE_INFINITY]) {
		test(`ungültiger Etappenwert ${typeof v === "string" ? JSON.stringify(v) : String(v)} ⇒ Trip-Tempo`, () => {
			const stageTempo = fn(N, 'stageTempo');
			const s = { ...etappe('S2'), grundtempo_kmh: v } as unknown as Stage;
			const tempo = stageTempo(s, TRIP_TEMPO) as Tempo;
			assert.deepEqual(tempo, TRIP_TEMPO);
			assert.deepEqual(N.computeArrivalTimes(s, undefined, tempo), UE.erwartet.S1.ankuenfte);
		});
	}

	test('Grenzen 0,5 und 60 sind gültig', () => {
		const stageTempo = fn(N, 'stageTempo');
		for (const v of [0.5, 60]) {
			assert.equal((stageTempo({ ...etappe('S2'), grundtempo_kmh: v }, TRIP_TEMPO) as Tempo).grundtempo_kmh, v);
		}
	});
});

// ═══ etappenZeile: Gehzeit mit Etappen-Tempo, Kennzeichen, Knopf (AC-1, AC-2, AC-7) ═══
describe('#3197 etappenZeile (AC-1, AC-2, AC-7)', () => {
	for (const lang of ['de', 'en'] as const) {
		test(`${lang}: S1 folgt dem Trip (4:12), S2 eigenes Tempo (5:36), beide mit Knopf`, () => {
			const t = katalog(lang);
			const z1 = L.etappenZeile(etappe('S1'), 0, lang, t, TRIP_TEMPO) as Record<string, unknown>;
			const z2 = L.etappenZeile(etappe('S2'), 1, lang, t, TRIP_TEMPO) as Record<string, unknown>;
			assert.equal(z1.meta, trFor(lang, 'trip.hub.etappe_gehzeit', { dauer: '4:12' }));
			assert.equal(z2.meta, trFor(lang, 'trip.hub.etappe_gehzeit', { dauer: '5:36' }), 'S2 rechnet nicht mit eigenem Tempo');
			assert.equal(z2.eigenesTempo, true, 'S2 nicht als „eigenes Tempo" gekennzeichnet');
			assert.ok(!z1.eigenesTempo, 'S1 fälschlich als „eigenes Tempo" gekennzeichnet');
			assert.equal(z1.tempoAendern, true, 'S1 ohne Knopf „Tempo ändern"');
			assert.equal(z2.tempoAendern, true, 'S2 ohne Knopf „Tempo ändern"');
		});
	}

	test('AC-1: ohne Überschreibung entsprechen alle Gehzeiten dem Trip-Tempo', () => {
		const t = katalog('de');
		const ohne = etappen().map((s) => ({ ...s, grundtempo_kmh: undefined }));
		for (const [i, s] of ohne.entries()) {
			const z = L.etappenZeile(s as Stage, i, 'de', t, TRIP_TEMPO) as Record<string, unknown>;
			assert.equal(z.meta, 'Gehzeit 4:12');
			assert.ok(!z.eigenesTempo);
			assert.equal(z.tempoAendern, true);
		}
	});

	test('ungültiger Etappenwert: Gehzeit wie Trip, kein Kennzeichen', () => {
		const z = L.etappenZeile({ ...etappe('S2'), grundtempo_kmh: 61 }, 1, 'de', katalog('de'), TRIP_TEMPO) as Record<string, unknown>;
		assert.equal(z.meta, 'Gehzeit 4:12');
		assert.ok(!z.eigenesTempo);
	});

	test('AC-7: Pausentag (keine Wegpunkte) — keine Gehzeit, kein Knopf, auch mit gespeichertem Etappen-Tempo', () => {
		const pause = { id: 'P', name: 'Ruhetag', date: '2026-07-03', waypoints: [], grundtempo_kmh: 3 } as Stage;
		const z = L.etappenZeile(pause, 2, 'de', katalog('de'), TRIP_TEMPO) as Record<string, unknown>;
		assert.equal(z.meta, undefined, 'Pausentag zeigt Gehzeit');
		assert.ok(!z.tempoAendern, 'Pausentag zeigt Knopf „Tempo ändern"');
		assert.ok(!z.eigenesTempo, 'Pausentag als „eigenes Tempo" gekennzeichnet');
	});
});

// ═══ Fortbewegungswechsel verwirft Überschreibungen (AC-6) ═══════════════════════════════
describe('#3197 verwirfEtappenTempo (AC-6)', () => {
	test('zwei überschriebene Etappen ⇒ anzahl 2, Feld entfernt, übrige Felder unverändert, Eingabe unberührt', () => {
		const verwirf = fn(N, 'verwirfEtappenTempo');
		const ein = etappen();
		ein[0] = { ...ein[0], grundtempo_kmh: 5, start_time: '07:15', notes: 'Bergetappe' } as Stage;
		ein.push({ id: 'S3', name: 'Ruhetag', date: '2026-07-03', waypoints: [] } as Stage);
		const vorher = structuredClone(ein);
		const { stages, anzahl } = verwirf(ein) as { stages: Stage[]; anzahl: number };
		assert.equal(anzahl, 2);
		assert.equal(stages.length, 3);
		for (const s of stages) assert.ok(!('grundtempo_kmh' in s), `${s.id}: grundtempo_kmh nicht entfernt`);
		vorher.forEach((alt, i) => {
			const { grundtempo_kmh: _weg, ...rest } = alt as Stage & { grundtempo_kmh?: number };
			assert.deepEqual(stages[i], rest, `${alt.id}: übrige Felder verändert`);
		});
		assert.deepEqual(ein, vorher, 'Eingabe mutiert');
	});

	test('keine Etappe betroffen ⇒ anzahl 0, Etappen gleich', () => {
		const verwirf = fn(N, 'verwirfEtappenTempo');
		const ein = etappen().map(({ grundtempo_kmh: _x, ...s }) => s as Stage);
		const { stages, anzahl } = verwirf(ein) as { stages: Stage[]; anzahl: number };
		assert.equal(anzahl, 0);
		assert.deepEqual(stages, ein);
	});

	test('nach dem Verwerfen rechnet jede Etappe mit dem neuen Trip-Tempo (Rad 20)', () => {
		const verwirf = fn(N, 'verwirfEtappenTempo');
		const stageTempo = fn(N, 'stageTempo');
		const rad = N.wechsleFortbewegung(TRIP_TEMPO, 'rad');
		const { stages } = verwirf(etappen()) as { stages: Stage[] };
		for (const s of stages) {
			assert.deepEqual(stageTempo(s, rad), rad);
			assert.deepEqual(N.computeArrivalTimes(s, undefined, stageTempo(s, rad)), ['08:00', '09:06', '09:48']);
		}
	});
});

// ═══ „Trip-Tempo verwenden" (AC-4) ══════════════════════════════════════════════════════
describe('#3197 ohneEtappenTempo (AC-4)', () => {
	test('entfernt das Feld, übrige Etappenfelder bleiben, Gehzeit wieder wie Trip', () => {
		const ohne = fn(N, 'ohneEtappenTempo');
		const s2 = etappe('S2');
		const neu = ohne(s2) as Stage;
		assert.ok(!('grundtempo_kmh' in neu), 'grundtempo_kmh nicht entfernt');
		const { grundtempo_kmh: _weg, ...rest } = s2 as Stage & { grundtempo_kmh?: number };
		assert.deepEqual(neu, rest);
		assert.equal(s2.grundtempo_kmh, 3, 'Eingabe mutiert');
		const z = L.etappenZeile(neu, 1, 'de', katalog('de'), TRIP_TEMPO) as Record<string, unknown>;
		assert.equal(z.meta, 'Gehzeit 4:12');
		assert.ok(!z.eigenesTempo);
	});
});

// ═══ Katalog DE/EN (AC-10) ══════════════════════════════════════════════════════════════
describe('#3197 Katalog DE/EN (AC-10)', () => {
	const lies = (lang: Lang): Record<string, string> =>
		JSON.parse(readFileSync(path.resolve(HERE, '../i18n/messages', lang, 'trip.json'), 'utf-8'));
	const DE = lies('de');
	const EN = lies('en');
	const NEU = [
		'trip.tempo.trip_tempo_verwenden',
		'trip.tempo.eigenes_tempo',
		'trip.tempo.etappen_zurueckgesetzt.one',
		'trip.tempo.etappen_zurueckgesetzt.other',
		'trip.hub.tempo_aendern'
	];
	for (const k of NEU) {
		test(`${k} in DE und EN vorhanden, nicht leer, verschieden übersetzt`, () => {
			assert.ok(typeof DE[k] === 'string' && DE[k].trim() !== '', `DE fehlt: ${k}`);
			assert.ok(typeof EN[k] === 'string' && EN[k].trim() !== '', `EN fehlt: ${k}`);
		});
	}
	test('DE-Texte: „Trip-Tempo verwenden", Hinweis „je Etappe überschreibbar"', () => {
		assert.equal(DE['trip.tempo.trip_tempo_verwenden'], 'Trip-Tempo verwenden');
		assert.match(DE['trip.tempo.hinweis'], /Gilt für alle Etappen/);
		assert.match(DE['trip.tempo.hinweis'], /je Etappe überschreibbar/);
		assert.match(EN['trip.tempo.hinweis'], /per stage/i);
		assert.notEqual(EN['trip.tempo.trip_tempo_verwenden'], DE['trip.tempo.trip_tempo_verwenden']);
	});
	for (const lang of ['de', 'en'] as const) {
		test(`${lang}: Plural „zurückgesetzte Etappen" mit Zahl (1 und 2)`, () => {
			const eins = trnFor(lang, 'trip.tempo.etappen_zurueckgesetzt', 1);
			const zwei = trnFor(lang, 'trip.tempo.etappen_zurueckgesetzt', 2);
			assert.ok(!eins.includes('trip.tempo') && !zwei.includes('trip.tempo'), `${lang}: Schlüssel statt Text (${eins} / ${zwei})`);
			assert.match(eins, /\b1\b/, `${lang}: Zahl 1 fehlt: ${eins}`);
			assert.match(zwei, /\b2\b/, `${lang}: Zahl 2 fehlt: ${zwei}`);
			assert.notEqual(eins.replace('1', '#'), zwei.replace('2', '#'), `${lang}: keine Pluralform`);
			if (lang === 'de') assert.match(zwei, /2 Etappen/);
			else assert.match(zwei, /2 stages/i);
		});
	}
});

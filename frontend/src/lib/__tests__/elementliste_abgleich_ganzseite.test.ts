// TDD RED — Issue #2913 (Epic #2791), Workflow feature-2913-abgleich-ganzseite.
// Spec: docs/specs/modules/feat_2913_abgleich_ganzseite.md — AC-1 bis AC-11 (Logik) und AC-5, AC-10,
// AC-13 (Verdrahtung). Ohne Browser, ohne Mocks: echte Fixture-Befunde, echte Freigaben-Datei,
// echte Besitzer-Datei, echter Starter. Der Live-Lauf (AC-5, AC-12 bis AC-14) läuft nur gegen Staging.
//
// Vertrag (vom Developer in e2e/elementliste_abgleich_logik.ts umzusetzen):
//   type Status = 'gefunden' | 'abweichend' | 'nicht_pruefbar' | 'freigegeben' | 'zusaetzlich'
//   type ZusaetzlichEintrag = { id; ctx; reiter; text; status: 'zusaetzlich'; besitzer?: { grund; verweis } }
//   type Bericht = { eintraege; zusaetzlich: ZusaetzlichEintrag[]; zaehler: Record<Status, number> }
//   zusaetzlichId(ctx, reiter, text): string            — `zus:<ctx>/<reiter>/<hash>`, Zahlen → {zahl}
//   findeZusaetzliche(befund: { ctx; reiter; texte: string[] }, liste, ausnahmen, kontoTexte, sprache)
//        → ZusaetzlichEintrag[] (je Text höchstens einmal)
//   sammleKontoTexte(daten: unknown): string[]          — alle `name`-Werte (Trip/Preset/Etappe/Ort) aus API-JSON
//   leseAusnahmen(jsonText): Ausnahme[]                  — {"ausnahmen":[{ctx?,reiter?,text?|muster?,grund,spec}]}
//   leseBesitzer(jsonText): Besitzer[]                   — {"besitzer":[{art,id?|ctx/reiter/abschnitt|text?/muster?,grund,verweis}]}
//        verweis: `#2913-c2` | `#2913-d` | `#2913-e` | `#NNNN`
//   wendeBesitzerAn(bericht, besitzer): Bericht          — setzt `besitzer` je gedecktem Eintrag, Status/Zähler unverändert
//   baueBericht(elemente, ergebnisse, zusaetzlich = [])
//   exitCode(bericht, { strict, abnahme? })              — abnahme: ≠0 bei herrenlosem abweichend/nicht_pruefbar/zusaetzlich
//   leseOptionen → { strict, scope, abnahme }; flagsAlsUmgebung(['--abnahme']) → ELEMENTLISTE_ABNAHME='1'
//   GEGENRICHTUNG_WURZEL = '[data-seite="hub"]'; istGegenrichtung(k: Kombi): boolean (nur normal, ohne Segment)
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/elementliste_abgleich_ganzseite.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as logik from '../../../e2e/elementliste_abgleich_logik.ts';
import { starterUmgebung } from '../../../../scripts/elementliste_abgleich.ts';
import type { ListenElement } from '../../../e2e/elementliste_abgleich_logik.ts';

// Namespace-Import: fehlende Exporte machen jeden Test einzeln rot statt das ganze Modul zu sprengen.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const L = logik as any;

const FRONTEND = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..');
const REPO = join(FRONTEND, '..');
const KONTEXT = join(REPO, 'docs/context/einstellungen_neu');

const el = (id: string, extra: Partial<ListenElement> = {}): ListenElement => ({
	id,
	ctx: 'trip',
	reiter: 'zustellung',
	zustand: 'normal',
	segment: null,
	abschnitt: 'kanaele',
	ordnung: 1,
	rolle: 'text',
	text_de: id,
	muster: null,
	i18n_key: null,
	text_en: null,
	luecke: true,
	...extra
});

// Fixture-Liste: ein Reiter-Eintrag (DE+EN), ein Kopf- und ein Reiterleisten-Eintrag (unter Reiter wetter,
// wie in der echten elementliste.json), alles ctx trip. ctx orte hat nur den Reiter-Eintrag.
const LISTE: ListenElement[] = [
	el('trip.zustellung.kanal', { text_de: 'Kanäle', text_en: 'Channels', luecke: false, ordnung: 1 }),
	el('trip.zustellung.zeit', { text_de: 'Versand um {zeit}', muster: 'Versand um {zeit}', text_en: 'Sent at {zeit}', luecke: false, ordnung: 2 }),
	el('trip.wetter.kopf', { reiter: 'wetter', abschnitt: 'kopf', text_de: 'Trips /' }),
	el('trip.wetter.reiter', { reiter: 'wetter', abschnitt: 'reiterleiste', text_de: 'Zustellung', text_en: 'Delivery', luecke: false }),
	el('orte.zustellung.kanal', { ctx: 'orte', text_de: 'Kanäle', text_en: 'Channels', luecke: false })
];

const ids = (z: Array<{ id: string }>) => z.map((x) => x.id);
const texte = (z: Array<{ text: string }>) => z.map((x) => x.text);

// ---------------------------------------------------------------- AC-1
describe('AC-1: Fremdtext wird zusaetzlich, eigene Liste, eigener Zähler, plan.elemente unverändert', () => {
	test('Fremdtext erscheint in bericht.zusaetzlich, Zähler +1, Listeneinträge unberührt', () => {
		const befund = { ctx: 'trip', reiter: 'zustellung', texte: ['Kanäle', 'Fremder Hinweis ohne Eintrag'] };
		const zus = L.findeZusaetzliche(befund, LISTE, [], [], 'de');
		assert.deepEqual(texte(zus), ['Fremder Hinweis ohne Eintrag']);
		assert.equal(zus[0].status, 'zusaetzlich');

		const elemente = LISTE.filter((e) => e.ctx === 'trip' && e.reiter === 'zustellung');
		const erg = new Map([
			['trip.zustellung.kanal', { status: 'gefunden' as const }],
			['trip.zustellung.zeit', { status: 'gefunden' as const }]
		]);
		const ohne = L.baueBericht(elemente, erg);
		const mit = L.baueBericht(elemente, erg, zus);
		assert.equal(ohne.zaehler.zusaetzlich, 0);
		assert.equal(mit.zaehler.zusaetzlich, 1);
		assert.deepEqual(mit.eintraege, ohne.eintraege, 'zusaetzliche Texte gehören nicht in eintraege');
		assert.equal(mit.zusaetzlich.length, 1);
		assert.equal(mit.zusaetzlich[0].text, 'Fremder Hinweis ohne Eintrag');
		// abschluss vergleicht weiter nur die Listenelemente
		assert.doesNotThrow(() => L.abschluss(mit, elemente, { strict: false, abnahme: false }));
	});

	test('ohne Fremdtext bleibt die Zusätzlich-Liste leer', () => {
		const zus = L.findeZusaetzliche({ ctx: 'trip', reiter: 'zustellung', texte: ['Kanäle'] }, LISTE, [], [], 'de');
		assert.deepEqual(zus, []);
	});

	test('Markdown nennt Zähler zusaetzlich und eine Zusätzlich-Tabelle mit Text und ID', () => {
		const zus = L.findeZusaetzliche({ ctx: 'trip', reiter: 'zustellung', texte: ['Fremder Hinweis ohne Eintrag'] }, LISTE, [], [], 'de');
		const md: string = L.berichtAlsMarkdown(L.baueBericht([], new Map(), zus));
		assert.match(md, /\| gefunden \| abweichend \| nicht_pruefbar \| freigegeben \| zusaetzlich \|/);
		assert.match(md, /\| 0 \| 0 \| 0 \| 0 \| 1 \|/);
		assert.ok(md.includes('Fremder Hinweis ohne Eintrag'), 'Fremdtext fehlt im Markdown');
		assert.ok(md.includes(zus[0].id), 'ID des Fremdtexts fehlt im Markdown');
	});
});

// ---------------------------------------------------------------- AC-2
describe('AC-2: stabile ID zus:<ctx>/<reiter>/<hash>, Zahlen normalisiert', () => {
	test('„3 Etappen“ und „7 Etappen“ ergeben dieselbe ID', () => {
		const a = L.zusaetzlichId('trip', 'zustellung', '3 Etappen');
		const b = L.zusaetzlichId('trip', 'zustellung', '7 Etappen');
		assert.match(a, /^zus:trip\/zustellung\/[0-9a-z]+$/);
		assert.equal(a, b);
	});
	test('anderer Text ⇒ anderer Hash; anderer ctx/Reiter ⇒ andere ID', () => {
		const a = L.zusaetzlichId('trip', 'zustellung', '3 Etappen');
		assert.notEqual(a, L.zusaetzlichId('trip', 'zustellung', '3 Orte'));
		assert.notEqual(a, L.zusaetzlichId('orte', 'zustellung', '3 Etappen'));
		assert.notEqual(a, L.zusaetzlichId('trip', 'wetter', '3 Etappen'));
	});
	test('findeZusaetzliche vergibt dieselbe ID über zwei Läufe', () => {
		const lauf1 = L.findeZusaetzliche({ ctx: 'trip', reiter: 'zustellung', texte: ['3 Etappen'] }, LISTE, [], [], 'de');
		const lauf2 = L.findeZusaetzliche({ ctx: 'trip', reiter: 'zustellung', texte: ['7 Etappen'] }, LISTE, [], [], 'de');
		assert.equal(lauf1.length, 1);
		assert.deepEqual(ids(lauf1), ids(lauf2));
		assert.equal(lauf1[0].id, L.zusaetzlichId('trip', 'zustellung', '3 Etappen'));
	});
});

// ---------------------------------------------------------------- AC-3
describe('AC-3: Text eines Eintrags (Reiter, kopf, reiterleiste) ist erklärt — DE/EN, Reihenfolge, Duplikat, ctx', () => {
	test('DE: Reiter-, Muster-, Kopf- und Reiterleisten-Text, vertauscht und doppelt ⇒ nichts zusaetzlich', () => {
		const befund = { ctx: 'trip', reiter: 'zustellung', texte: ['Zustellung', 'Versand um 07:00', 'Kanäle', 'Trips /', 'Kanäle'] };
		assert.deepEqual(L.findeZusaetzliche(befund, LISTE, [], [], 'de'), []);
	});
	test('EN: Katalogtexte sind erklärt', () => {
		const befund = { ctx: 'trip', reiter: 'zustellung', texte: ['Sent at 07:00', 'Channels', 'Delivery'] };
		assert.deepEqual(L.findeZusaetzliche(befund, LISTE, [], [], 'en'), []);
	});
	test('Mehrfach vorkommender Fremdtext ergibt genau einen Eintrag', () => {
		const zus = L.findeZusaetzliche({ ctx: 'trip', reiter: 'zustellung', texte: ['Fremd', 'Kanäle', 'Fremd'] }, LISTE, [], [], 'de');
		assert.deepEqual(texte(zus), ['Fremd']);
	});
	test('ctx-Wechsel: Kopf-Text von trip ist unter orte (ohne Kopf-Eintrag) zusaetzlich', () => {
		const zus = L.findeZusaetzliche({ ctx: 'orte', reiter: 'zustellung', texte: ['Kanäle', 'Trips /'] }, LISTE, [], [], 'de');
		assert.deepEqual(texte(zus), ['Trips /']);
		assert.match(zus[0].id, /^zus:orte\/zustellung\//);
	});
	test('Text eines anderen Reiters (nicht kopf/reiterleiste) erklärt nicht', () => {
		const liste = [...LISTE, el('trip.wetter.nur', { reiter: 'wetter', abschnitt: 'metriken', text_de: 'Nur im Wetter' })];
		const zus = L.findeZusaetzliche({ ctx: 'trip', reiter: 'zustellung', texte: ['Nur im Wetter'] }, liste, [], [], 'de');
		assert.deepEqual(texte(zus), ['Nur im Wetter']);
	});
});

// ---------------------------------------------------------------- AC-4
describe('AC-4: Konto-Texte und Ausnahmen erklären; Ausnahme ohne Grund/Spec bricht ab', () => {
	const TRIP_API = {
		id: 't1',
		name: 'GR20 Nord',
		stages: [
			{ id: 's1', name: 'Calenzana – Ortu', waypoints: [{ id: 'w1', name: 'Bocca a u Saltu' }] },
			{ id: 's2', name: 'Ortu – Carrozzu', waypoints: [] }
		]
	};
	test('sammleKontoTexte liest Trip-, Etappen- und Ortsnamen', () => {
		const k: string[] = L.sammleKontoTexte(TRIP_API);
		for (const n of ['GR20 Nord', 'Calenzana – Ortu', 'Ortu – Carrozzu', 'Bocca a u Saltu']) assert.ok(k.includes(n), `${n} fehlt`);
		assert.ok(!k.includes('t1') && !k.includes('s1'), 'IDs sind keine Konto-Texte');
	});
	test('Konto-Text ist erklärt, auch als Preset-/Ortsname', () => {
		const konto = [...L.sammleKontoTexte(TRIP_API), ...L.sammleKontoTexte({ name: 'Alpen-Vergleich', locations: [{ name: 'Innsbruck' }] })];
		const befund = { ctx: 'trip', reiter: 'zustellung', texte: ['GR20 Nord', 'Calenzana – Ortu', 'Innsbruck', 'Alpen-Vergleich', 'Kanäle'] };
		assert.deepEqual(L.findeZusaetzliche(befund, LISTE, [], konto, 'de'), []);
	});
	test('gültige Ausnahme (Text bzw. Muster, mit Grund und Spec) erklärt', () => {
		const ausnahmen = L.leseAusnahmen(
			JSON.stringify({
				ausnahmen: [
					{ ctx: 'trip', reiter: 'zustellung', text: 'Gespeichert', grund: 'Speicher-Rückmeldung', spec: 'docs/specs/modules/x.md' },
					{ muster: 'Stand {zeit}', grund: 'Zeitstempel', spec: 'docs/specs/modules/y.md' }
				]
			})
		);
		const befund = { ctx: 'trip', reiter: 'zustellung', texte: ['Gespeichert', 'Stand 08:15', 'Fremd'] };
		assert.deepEqual(texte(L.findeZusaetzliche(befund, LISTE, ausnahmen, [], 'de')), ['Fremd']);
	});
	test('Ausnahme mit ctx/Reiter gilt nicht in einem anderen Reiter', () => {
		const ausnahmen = L.leseAusnahmen(JSON.stringify({ ausnahmen: [{ ctx: 'trip', reiter: 'wetter', text: 'Gespeichert', grund: 'g', spec: 's.md' }] }));
		assert.deepEqual(texte(L.findeZusaetzliche({ ctx: 'trip', reiter: 'zustellung', texte: ['Gespeichert'] }, LISTE, ausnahmen, [], 'de')), ['Gespeichert']);
	});
	test('Ausnahme ohne Grund oder ohne Spec ⇒ Parser-Fehler', () => {
		assert.throws(() => L.leseAusnahmen(JSON.stringify({ ausnahmen: [{ text: 'x', spec: 's.md' }] })), /grund/);
		assert.throws(() => L.leseAusnahmen(JSON.stringify({ ausnahmen: [{ text: 'x', grund: 'g' }] })), /spec/);
		assert.throws(() => L.leseAusnahmen(JSON.stringify({ ausnahmen: [{ text: 'x', grund: '  ', spec: 's.md' }] })), /grund/);
	});
});

// ---------------------------------------------------------------- AC-6 / AC-7
const BESITZER_JSON = {
	besitzer: [
		{ art: 'element', id: 'trip.zustellung.kanal', grund: 'Kanalzeile kommt mit Scheibe d', verweis: '#2913-d' },
		{ art: 'abschnitt', ctx: 'trip', reiter: 'wetter', abschnitt: 'kopf', grund: 'Kopf wird in c2 neu gebaut', verweis: '#2913-c2' },
		{ art: 'zusaetzlich', ctx: 'trip', reiter: 'zustellung', text: 'Profil: Wandern', grund: 'Profil-Zeile fehlt im Mockup', verweis: '#2960' },
		{ art: 'zusaetzlich', muster: 'Stand {zeit}', grund: 'Zeitstempel', verweis: '#2913-e' }
	]
};

function beispielBericht() {
	const elemente = [
		el('trip.zustellung.kanal'),
		el('trip.wetter.kopf1', { reiter: 'wetter', abschnitt: 'kopf', ordnung: 1 }),
		el('trip.wetter.kopf2', { reiter: 'wetter', abschnitt: 'kopf', ordnung: 2 }),
		el('trip.wetter.metrik', { reiter: 'wetter', abschnitt: 'metriken' })
	];
	const erg = new Map<string, { status: 'abweichend' | 'nicht_pruefbar'; grund?: string; ist?: string }>([
		['trip.zustellung.kanal', { status: 'abweichend', ist: 'x' }],
		['trip.wetter.kopf1', { status: 'abweichend', ist: 'y' }],
		['trip.wetter.kopf2', { status: 'nicht_pruefbar', grund: 'g' }],
		['trip.wetter.metrik', { status: 'abweichend', ist: 'z' }]
	]);
	const zus = L.findeZusaetzliche({ ctx: 'trip', reiter: 'zustellung', texte: ['Profil: Wandern', 'Stand 08:15', 'Ganz fremd'] }, LISTE, [], [], 'de');
	return { elemente, bericht: L.baueBericht(elemente, erg, zus) };
}

describe('AC-6: Besitzer für element, abschnitt und zusaetzlich (Text/Muster)', () => {
	test('gedeckte Einträge tragen Besitzer und Verweis; Status und Zähler bleiben', () => {
		const { bericht } = beispielBericht();
		const vorher = JSON.parse(JSON.stringify(bericht.zaehler));
		const status = bericht.eintraege.map((e: { status: string }) => e.status);
		const b = L.wendeBesitzerAn(bericht, L.leseBesitzer(JSON.stringify(BESITZER_JSON)));
		const e = (id: string) => b.eintraege.find((x: { id: string }) => x.id === id);
		assert.equal(e('trip.zustellung.kanal').besitzer?.verweis, '#2913-d');
		assert.equal(e('trip.zustellung.kanal').besitzer?.grund, 'Kanalzeile kommt mit Scheibe d');
		assert.equal(e('trip.wetter.kopf1').besitzer?.verweis, '#2913-c2', 'Abschnitts-Besitzer deckt abweichend');
		assert.equal(e('trip.wetter.kopf2').besitzer?.verweis, '#2913-c2', 'Abschnitts-Besitzer deckt nicht_pruefbar');
		assert.equal(e('trip.wetter.metrik').besitzer, undefined, 'anderer Abschnitt bleibt herrenlos');
		const z = (t: string) => b.zusaetzlich.find((x: { text: string }) => x.text === t);
		assert.equal(z('Profil: Wandern').besitzer?.verweis, '#2960');
		assert.equal(z('Stand 08:15').besitzer?.verweis, '#2913-e', 'Muster-Besitzer deckt den Zeitstempel');
		assert.equal(z('Ganz fremd').besitzer, undefined);
		assert.deepEqual(b.zaehler, vorher, 'Zähler unverändert');
		assert.deepEqual(b.eintraege.map((x: { status: string }) => x.status), status, 'Status unverändert');
	});
	test('Markdown hat eine Besitzer-Spalte mit dem Verweis', () => {
		const { bericht } = beispielBericht();
		const md: string = L.berichtAlsMarkdown(L.wendeBesitzerAn(bericht, L.leseBesitzer(JSON.stringify(BESITZER_JSON))));
		const kopf = md.split('\n').find((z) => z.startsWith('| id |'));
		assert.ok(kopf && /\| Besitzer \|/.test(kopf), 'Besitzer-Spalte fehlt in der Elementtabelle');
		const zeile = md.split('\n').find((z) => z.startsWith('| trip.zustellung.kanal |'));
		assert.ok(zeile && zeile.includes('#2913-d'), 'Verweis fehlt in der Zeile');
		const zusZeile = md.split('\n').find((z) => z.includes('Profil: Wandern'));
		assert.ok(zusZeile && zusZeile.includes('#2960'), 'Verweis fehlt in der Zusätzlich-Tabelle');
	});
});

describe('AC-7: leseBesitzer lehnt Einträge ohne Grund, ohne oder mit ungültigem Verweis ab', () => {
	const eins = (b: Record<string, unknown>) => JSON.stringify({ besitzer: [b] });
	test('Grund fehlt ⇒ Fehler, der den Eintrag nennt', () => {
		assert.throws(() => L.leseBesitzer(eins({ art: 'element', id: 'a.b', verweis: '#2913-d' })), /Besitzer 0.*grund/);
	});
	test('Verweis fehlt ⇒ Fehler', () => {
		assert.throws(() => L.leseBesitzer(eins({ art: 'element', id: 'a.b', grund: 'g' })), /Besitzer 0.*verweis/);
	});
	test('Verweis ungültig ⇒ Fehler', () => {
		for (const v of ['Scheibe d', '#2913-x', '2913', '#29a', '#2913-c3']) {
			assert.throws(() => L.leseBesitzer(eins({ art: 'element', id: 'a.b', grund: 'g', verweis: v })), /verweis/, `„${v}“ darf nicht gelten`);
		}
	});
	test('gültige Verweise werden angenommen', () => {
		for (const v of ['#2913-c2', '#2913-d', '#2913-e', '#2795', '#12345']) {
			assert.equal(L.leseBesitzer(eins({ art: 'element', id: 'a.b', grund: 'g', verweis: v })).length, 1, `„${v}“ muss gelten`);
		}
	});
	test('unbekannte Ziel-Art ⇒ Fehler', () => {
		assert.throws(() => L.leseBesitzer(eins({ art: 'seite', grund: 'g', verweis: '#2795' })), /art/);
	});
});

// ---------------------------------------------------------------- AC-8
describe('AC-8: Freigabe (echte elementliste_freigaben.json) zählt bei --abnahme als Besitzer', () => {
	test('freigegebener Eintrag ⇒ Exit 0, ohne Freigabe ⇒ Exit 1', () => {
		const freigaben = logik.leseFreigaben(readFileSync(join(KONTEXT, 'elementliste_freigaben.json'), 'utf8'));
		const f = freigaben[0];
		const e = el('fg.1', { ctx: f.ctx, reiter: f.reiter, abschnitt: f.abschnitt, i18n_key: f.i18n_keys[0] });
		const roh = new Map([['fg.1', { status: 'abweichend' as const, ist: 'fehlt' }]]);
		const mit = L.baueBericht([e], logik.wendeFreigabenAn([e], roh, freigaben));
		assert.equal(mit.eintraege[0].status, 'freigegeben');
		assert.equal(L.exitCode(mit, { strict: false, abnahme: true }), 0);
		const ohne = L.baueBericht([e], roh);
		assert.equal(L.exitCode(ohne, { strict: false, abnahme: true }), 1);
	});
});

// ---------------------------------------------------------------- AC-9
describe('AC-9: --abnahme — Kreuzprobe über abweichend, nicht_pruefbar, zusaetzlich', () => {
	const elemente = [el('a.ab', { abschnitt: 's1' }), el('a.np', { abschnitt: 's2' })];
	const erg = new Map<string, { status: 'abweichend' | 'nicht_pruefbar'; grund?: string; ist?: string }>([
		['a.ab', { status: 'abweichend', ist: 'x' }],
		['a.np', { status: 'nicht_pruefbar', grund: 'g' }]
	]);
	const zus = () => L.findeZusaetzliche({ ctx: 'trip', reiter: 'zustellung', texte: ['Fremd'] }, LISTE, [], [], 'de');
	const B = {
		ab: { art: 'element', id: 'a.ab', grund: 'g', verweis: '#2913-d' },
		np: { art: 'element', id: 'a.np', grund: 'g', verweis: '#2913-d' },
		zus: { art: 'zusaetzlich', text: 'Fremd', grund: 'g', verweis: '#2913-e' }
	};
	const lauf = (welche: Array<keyof typeof B>) =>
		L.exitCode(L.wendeBesitzerAn(L.baueBericht(elemente, erg, zus()), L.leseBesitzer(JSON.stringify({ besitzer: welche.map((k) => B[k]) }))), {
			strict: false,
			abnahme: true
		});
	test('alle drei mit Besitzer ⇒ Exit 0', () => assert.equal(lauf(['ab', 'np', 'zus']), 0));
	test('herrenlos abweichend allein ⇒ Exit ≠ 0', () => assert.notEqual(lauf(['np', 'zus']), 0));
	test('herrenlos nicht_pruefbar allein ⇒ Exit ≠ 0', () => assert.notEqual(lauf(['ab', 'zus']), 0));
	test('herrenlos zusaetzlich allein ⇒ Exit ≠ 0', () => assert.notEqual(lauf(['ab', 'np']), 0));
	test('ohne jeden Besitzer ⇒ Exit ≠ 0', () => assert.notEqual(lauf([]), 0));
	test('gefunden braucht keinen Besitzer', () => {
		const b = L.baueBericht([el('a.ok')], new Map([['a.ok', { status: 'gefunden' as const }]]));
		assert.equal(L.exitCode(b, { strict: false, abnahme: true }), 0);
	});
});

// ---------------------------------------------------------------- AC-10
describe('AC-10: --strict unverändert, zusaetzlich allein ohne --abnahme kein Exit ≠ 0, Optionen', () => {
	const zus = () => L.findeZusaetzliche({ ctx: 'trip', reiter: 'zustellung', texte: ['Fremd'] }, LISTE, [], [], 'de');
	test('strict: nur zusaetzlich ⇒ Exit 0; abweichend ⇒ ≠ 0; freigegeben zählt nicht', () => {
		const nurZus = L.baueBericht([el('a.ok')], new Map([['a.ok', { status: 'gefunden' as const }]]), zus());
		assert.equal(nurZus.zaehler.zusaetzlich, 1);
		assert.equal(L.exitCode(nurZus, { strict: true, abnahme: false }), 0);
		assert.equal(L.exitCode(nurZus, { strict: true }), 0);
		const ab = L.baueBericht([el('a.ab')], new Map([['a.ab', { status: 'abweichend' as const, ist: 'x' }]]));
		assert.notEqual(L.exitCode(ab, { strict: true, abnahme: false }), 0);
		const fg = L.baueBericht([el('a.fg')], new Map([['a.fg', { status: 'freigegeben' as const, grund: 'g (s.md)' }]]));
		assert.equal(L.exitCode(fg, { strict: true, abnahme: false }), 0);
	});
	test('ohne beide Flags immer Exit 0', () => {
		const b = L.baueBericht([el('a.ab')], new Map([['a.ab', { status: 'abweichend' as const, ist: 'x' }]]), zus());
		assert.equal(L.exitCode(b, { strict: false, abnahme: false }), 0);
	});
	test('leseOptionen: --abnahme aus Argumenten und ELEMENTLISTE_ABNAHME', () => {
		assert.deepEqual(L.leseOptionen(['--abnahme'], {}), { strict: false, scope: null, abnahme: true });
		assert.deepEqual(L.leseOptionen([], { ELEMENTLISTE_ABNAHME: '1' }), { strict: false, scope: null, abnahme: true });
		assert.deepEqual(L.leseOptionen([], {}), { strict: false, scope: null, abnahme: false });
	});
	test('flagsAlsUmgebung und Starter reichen --abnahme durch; planeAbgleich liest es', () => {
		assert.deepEqual(L.flagsAlsUmgebung(['--abnahme']), { ELEMENTLISTE_ABNAHME: '1' });
		assert.deepEqual(L.flagsAlsUmgebung(['--strict', '--abnahme', '--sprache', 'en']), {
			ELEMENTLISTE_STRICT: '1',
			ELEMENTLISTE_ABNAHME: '1',
			ELEMENTLISTE_SPRACHE: 'en'
		});
		assert.equal(starterUmgebung(['--abnahme'], { PATH: '/x' }, null).ELEMENTLISTE_ABNAHME, '1');
		const liste: ListenElement[] = JSON.parse(readFileSync(join(KONTEXT, 'elementliste.json'), 'utf8')).elemente;
		const p = L.planeAbgleich({ liste, env: { ELEMENTLISTE_ABNAHME: '1' }, baseURL: 'https://staging.gregor20.henemm.com' });
		assert.equal(p.optionen.abnahme, true);
	});
	test('abschluss meldet abnahme und nutzt ihren Exit', () => {
		const elemente = [el('a.ok')];
		const b = L.baueBericht(elemente, new Map([['a.ok', { status: 'gefunden' as const }]]), zus());
		const r = L.abschluss(b, elemente, { strict: false, abnahme: true });
		assert.equal(r.exit, 1);
		assert.match(r.meldung, /zusaetzlich 1/);
		assert.match(r.meldung, /abnahme/);
	});
});

// ---------------------------------------------------------------- AC-11
describe('AC-11: Rot-Probe Profil-Zeile — herrenlos Exit 1, mit Besitzer Exit 0', () => {
	test('Profil-Zeile des Seitenkopfs ist zusaetzlich; Besitzer macht den Lauf grün', () => {
		const elemente = LISTE.filter((e) => e.ctx === 'trip' && e.reiter === 'zustellung');
		const erg = new Map(elemente.map((e) => [e.id, { status: 'gefunden' as const }]));
		const befund = { ctx: 'trip', reiter: 'zustellung', texte: ['Trips /', 'Profil: Wandern', 'Kanäle', 'Versand um 07:00'] };
		const zus = L.findeZusaetzliche(befund, LISTE, [], [], 'de');
		assert.deepEqual(texte(zus), ['Profil: Wandern']);
		const bericht = L.baueBericht(elemente, erg, zus);
		assert.equal(L.abschluss(bericht, elemente, { strict: false, abnahme: true }).exit, 1);
		const besitzer = L.leseBesitzer(
			JSON.stringify({ besitzer: [{ art: 'zusaetzlich', ctx: 'trip', reiter: 'zustellung', text: 'Profil: Wandern', grund: 'Profil-Zeile fehlt im Mockup', verweis: '#2913-c2' }] })
		);
		assert.equal(L.abschluss(L.wendeBesitzerAn(bericht, besitzer), elemente, { strict: false, abnahme: true }).exit, 0);
	});
});

// ---------------------------------------------------------------- Fix-Loop 1 (Adversary F002–F004)
describe('Fix-Loop 1: Besitzer-Bindung, Hash-Normalisierung, Parser-Härte', () => {
	const eins = (b: unknown) => JSON.stringify({ besitzer: [b] });
	test('F002: Abschnitts-Besitzer gilt nur für denselben ctx und Reiter', () => {
		const elemente = [
			el('t.w.k', { reiter: 'wetter', abschnitt: 'kopf' }),
			el('o.w.k', { ctx: 'orte', reiter: 'wetter', abschnitt: 'kopf' }),
			el('t.z.k', { reiter: 'zustellung', abschnitt: 'kopf' })
		];
		const erg = new Map(elemente.map((e) => [e.id, { status: 'abweichend' as const, ist: 'x' }]));
		const b = L.wendeBesitzerAn(L.baueBericht(elemente, erg), L.leseBesitzer(eins({ art: 'abschnitt', ctx: 'trip', reiter: 'wetter', abschnitt: 'kopf', grund: 'g', verweis: '#2913-c2' })));
		const v = (id: string) => b.eintraege.find((x: { id: string }) => x.id === id).besitzer?.verweis;
		assert.equal(v('t.w.k'), '#2913-c2');
		assert.equal(v('o.w.k'), undefined, 'anderer ctx darf nicht gedeckt sein');
		assert.equal(v('t.z.k'), undefined, 'anderer Reiter darf nicht gedeckt sein');
	});
	test('F002: gefunden und freigegeben bekommen nie einen Besitzer', () => {
		const elemente = [el('a.g', { abschnitt: 's' }), el('a.f', { abschnitt: 's' })];
		const erg = new Map<string, { status: 'gefunden' | 'freigegeben'; grund?: string }>([
			['a.g', { status: 'gefunden' }],
			['a.f', { status: 'freigegeben', grund: 'g (s.md)' }]
		]);
		const besitzer = L.leseBesitzer(
			JSON.stringify({
				besitzer: [
					{ art: 'element', id: 'a.g', grund: 'g', verweis: '#2913-d' },
					{ art: 'abschnitt', ctx: 'trip', reiter: 'zustellung', abschnitt: 's', grund: 'g', verweis: '#2913-d' }
				]
			})
		);
		const b = L.wendeBesitzerAn(L.baueBericht(elemente, erg), besitzer);
		for (const e of b.eintraege) assert.equal(e.besitzer, undefined, `${e.id} (${e.status}) darf keinen Besitzer tragen`);
		assert.ok(!L.berichtAlsMarkdown(b).includes('#2913-d'), 'kein Besitzer-Verweis im Markdown');
	});
	test('F003: „Etappe 3“ und „Etappe“ ergeben verschiedene IDs (Zahl wird {zahl}, nicht entfernt)', () => {
		assert.notEqual(L.zusaetzlichId('trip', 'zustellung', 'Etappe 3'), L.zusaetzlichId('trip', 'zustellung', 'Etappe'));
		assert.notEqual(L.zusaetzlichId('trip', 'zustellung', '3 Etappen'), L.zusaetzlichId('trip', 'zustellung', 'Etappen'));
		assert.equal(L.zusaetzlichId('trip', 'zustellung', 'Etappe 3'), L.zusaetzlichId('trip', 'zustellung', 'Etappe 12'));
	});
	test('F004: null- bzw. Nicht-Objekt-Eintrag ⇒ Fehler mit Index', () => {
		for (const roh of [null, 'text', 3, ['x']]) {
			assert.throws(() => L.leseBesitzer(JSON.stringify({ besitzer: [{ art: 'element', id: 'a', grund: 'g', verweis: '#2795' }, roh] })), /Besitzer 1: Eintrag ist kein Objekt/);
		}
	});
	test('F004: element-Besitzer mit unbekannter ID ⇒ Fehler mit Index und ID, bekannte ID gilt', () => {
		const liste = [el('a.bekannt')];
		assert.throws(() => L.leseBesitzer(eins({ art: 'element', id: 'a.fremd', grund: 'g', verweis: '#2795' }), liste), /Besitzer 0: Element „a\.fremd“/);
		assert.equal(L.leseBesitzer(eins({ art: 'element', id: 'a.bekannt', grund: 'g', verweis: '#2795' }), liste).length, 1);
	});
});

// ---------------------------------------------------------------- AC-5 (Verdrahtung)
describe('AC-5: Gegenrichtung liest nur [data-seite="hub"], nur normal/ohne Segment', () => {
	test('Wurzel-Selektor ist [data-seite="hub"], nie body', () => {
		assert.equal(L.GEGENRICHTUNG_WURZEL, '[data-seite="hub"]');
	});
	test('Kombi-Filter: nur Zustand normal ohne Segment', () => {
		assert.equal(L.istGegenrichtung({ ctx: 'trip', reiter: 'wetter', zustand: 'normal', segment: null }), true);
		assert.equal(L.istGegenrichtung({ ctx: 'orte', reiter: 'zustellung', zustand: 'normal', segment: null }), true);
		assert.equal(L.istGegenrichtung({ ctx: 'trip', reiter: 'wetter', zustand: 'laedt', segment: null }), false);
		assert.equal(L.istGegenrichtung({ ctx: 'trip', reiter: 'wetter', zustand: 'fehler', segment: null }), false);
		assert.equal(L.istGegenrichtung({ ctx: 'trip', reiter: 'wetter', zustand: 'luecken', segment: null }), false);
		assert.equal(L.istGegenrichtung({ ctx: 'trip', reiter: 'zustellung', zustand: 'normal', segment: 'email' }), false);
	});
	test('Staging-Spec nutzt Wurzel, Kombi-Filter, Gegenrichtung und Besitzer-Datei (doc-compliance-test)', () => {
		// doc-compliance-test: Verdrahtung der Live-Spec; die Wirkung belegt der Staging-Lauf (AC-5, AC-12).
		const spec = readFileSync(join(FRONTEND, 'e2e/elementliste-abgleich.staging.spec.ts'), 'utf8');
		assert.match(spec, /GEGENRICHTUNG_WURZEL/);
		assert.match(spec, /istGegenrichtung\(/);
		assert.match(spec, /findeZusaetzliche\(/);
		// Fix-Loop 1 (F001): Besitzer wendet werteLaufAus an (Wirkung: elementliste_abgleich_verdrahtung.test.ts).
		assert.match(spec, /werteLaufAus\(/);
		assert.match(spec, /elementliste_besitzer\.json/);
		assert.ok(!/querySelectorAll\(\s*['"]body['"]/.test(spec), 'Gegenrichtung darf nicht body lesen');
	});
});

// ---------------------------------------------------------------- Besitzer-Datei (AC-6, AC-14 Vorbedingung)
describe('Echte Besitzer-Datei elementliste_besitzer.json ist gültig', () => {
	test('Datei existiert, Besitzer und Ausnahmen parsen ohne Fehler', () => {
		const text = readFileSync(join(KONTEXT, 'elementliste_besitzer.json'), 'utf8');
		assert.ok(Array.isArray(L.leseBesitzer(text)));
		assert.ok(Array.isArray(L.leseAusnahmen(text)));
	});
});

// ---------------------------------------------------------------- AC-13 (Marker)
describe('AC-13: unsichtbare Marker an den geteilten Komponenten (doc-compliance-test)', () => {
	// doc-compliance-test: Attribut-Präsenz; Wirkung (Abschnitte gefunden) belegt der Staging-Lauf.
	const quelle = (p: string) => readFileSync(join(FRONTEND, 'src/lib/components', p), 'utf8');
	test('HubKopf: data-seite="hub" und data-abschnitt="kopf" an der Wurzel', () => {
		assert.match(quelle('shared/hub-kopf/HubKopf.svelte'), /<div class="hub-kopf"[^>]*data-seite="hub"[^>]*data-abschnitt="kopf"|<div class="hub-kopf"[^>]*data-abschnitt="kopf"[^>]*data-seite="hub"/);
	});
	for (const [datei, klasse] of [
		['trip-detail/TripTabs.svelte', 'trip-tabs'],
		['compare/CompareTabs.svelte', 'compare-tabs']
	] as const) {
		test(`${datei}: data-seite="hub" an der Wurzel, styleloser Wrapper reiterleiste um MTabBar`, () => {
			const q = quelle(datei);
			assert.match(q, new RegExp(`<div class="${klasse}"[^>]*data-seite="hub"`));
			const m = q.match(/<div\s+data-abschnitt="reiterleiste"\s*>\s*(?:<!--[\s\S]*?-->\s*)*<MTabBar/);
			assert.ok(m, 'Wrapper <div data-abschnitt="reiterleiste"> ohne class/style direkt um MTabBar fehlt');
		});
	}
	test('VorlageKarte: data-abschnitt="vorlage"', () => {
		assert.match(quelle('organisms/wetter-tab/VorlageKarte.svelte'), /<div class="wt-karte"[^>]*data-abschnitt="vorlage"/);
	});
	test('WetterTabInhalt: data-abschnitt="laden" und "warnung"', () => {
		const q = quelle('organisms/wetter-tab/WetterTabInhalt.svelte');
		assert.match(q, /<div class="wt-karte wt-laden"[^>]*data-abschnitt="laden"/);
		assert.match(q, /<div class="wt-karte wt-fehler"[^>]*data-abschnitt="warnung"/);
	});
});

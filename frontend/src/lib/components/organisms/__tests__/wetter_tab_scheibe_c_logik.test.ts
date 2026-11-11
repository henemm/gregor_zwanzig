// Issue #2913 Scheibe (c) — Fix-Loops 1 und 2 (Adversary F002–F005).
// Spec: docs/specs/modules/feat_2913_scheibe_c_wetter_rest.md — AC-2, AC-3, AC-5.
//
//   F002/F004  Tagesfenster (organisms/wetter-tab/tagesfensterEingabe.ts, echte Klemme aus
//              versand-tab/dayWindowClamp.ts): ganze Stunde aus `HH:MM`, 0–23, über Mitternacht erlaubt,
//              Ende = Start geklemmt, Start auf aktuelles Ende zieht Ende nach, Neuaufbau-Fall 6/7/6;
//              dazu die Verdrahtung tagesfensterSteuerung mit aufzeichnenden Handlern (keine Mocks).
//   F003/F005  Zuordnung Schalter → Handler der Karte Warnungen/Radar (warnungenRadarZeilen.ts) mit
//              aufzeichnenden Handlern, SSR-Zustand je Testid.
//   Wirkstelle in den .svelte (kein Client-Mount im Repo, kein jsdom): Quellregeln per Svelte-AST.
//   # doc-compliance-test (nur die Abschnitte „Verdrahtung in der Komponente“)
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/wetter_tab_scheibe_c_logik.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

import { endeEingabe, startEingabe, stundeAlsUhrzeit, stundeAusEingabe, tagesfensterSteuerung, type Fenster } from '../wetter-tab/tagesfensterEingabe.ts';
import { schalterZeilen } from '../wetter-tab/warnungenRadarZeilen.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const WT = path.resolve(HERE, '..', 'wetter-tab');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

// ─── F002 / AC-5: reine Eingabe-Logik ────────────────────────────────────────

describe('AC-5: Tagesfenster-Eingabe in ganzen Stunden', () => {
	test('Stunde aus HH:MM: Minute ignoriert, 0–23, sonst abgewiesen', () => {
		assert.equal(stundeAusEingabe('06:00'), 6);
		assert.equal(stundeAusEingabe('06:30'), 6, 'HH:30 ergibt die ganze Stunde (Minute ignoriert)');
		assert.equal(stundeAusEingabe('00:00'), 0);
		assert.equal(stundeAusEingabe('23:00'), 23);
		assert.equal(stundeAusEingabe('24:00'), null);
		assert.equal(stundeAusEingabe(''), null);
		assert.equal(stundeAusEingabe('6'), null);
	});
	test('Anzeige HH:00', () => {
		assert.equal(stundeAlsUhrzeit(6), '06:00');
		assert.equal(stundeAlsUhrzeit(0), '00:00');
		assert.equal(stundeAlsUhrzeit(22), '22:00');
	});
	test('Ende: über Mitternacht (22 → 6) erlaubt, kein Neuaufbau', () => {
		assert.deepEqual(endeEingabe({ start: 22, end: 23 }, '06:00'), { ende: 6, endeNeuAufbauen: false });
	});
	test('Ende: normale Stunde wird übernommen', () => {
		assert.deepEqual(endeEingabe({ start: 6, end: 20 }, '16:00'), { ende: 16, endeNeuAufbauen: false });
		assert.deepEqual(endeEingabe({ start: 6, end: 20 }, '05:00'), { ende: 5, endeNeuAufbauen: false });
	});
	test('Ende = Start wird auf die nächste Stunde geklemmt und das Feld neu aufgebaut', () => {
		assert.deepEqual(endeEingabe({ start: 6, end: 20 }, '06:00'), { ende: 7, endeNeuAufbauen: true });
		assert.deepEqual(endeEingabe({ start: 23, end: 2 }, '23:00'), { ende: 0, endeNeuAufbauen: true });
	});
	test('Start 6, Ende 7, getippt 6 → Ende bleibt 7, Feld muss neu aufgebaut werden (Prop unverändert)', () => {
		assert.deepEqual(endeEingabe({ start: 6, end: 7 }, '06:00'), { ende: 7, endeNeuAufbauen: true });
	});
	test('Ende ungültig → keine Änderung', () => {
		assert.equal(endeEingabe({ start: 6, end: 20 }, ''), null);
	});
	test('Start: neue Stunde, Ende bleibt (keine Ende-Meldung)', () => {
		assert.deepEqual(startEingabe({ start: 6, end: 20 }, '08:00'), { start: 8, endeNeuAufbauen: false });
	});
	test('Start auf das aktuelle Ende zieht das Ende nach', () => {
		assert.deepEqual(startEingabe({ start: 6, end: 20 }, '20:00'), { start: 20, ende: 21, endeNeuAufbauen: false });
		assert.deepEqual(startEingabe({ start: 6, end: 23 }, '23:00'), { start: 23, ende: 0, endeNeuAufbauen: false });
	});
	test('Start über Mitternacht (Start 22 bei Ende 6) erlaubt', () => {
		assert.deepEqual(startEingabe({ start: 20, end: 6 }, '22:00'), { start: 22, endeNeuAufbauen: false });
	});
	test('Start ungültig → keine Änderung', () => {
		assert.equal(startEingabe({ start: 6, end: 20 }, 'x'), null);
	});
});

// ─── F004 / AC-5: Verdrahtung tagesfensterSteuerung ──────────────────────────

describe('AC-5: tagesfensterSteuerung ruft die richtigen Handler', () => {
	function aufbau(fenster: Fenster) {
		const rufe: string[] = [];
		let stand = { ...fenster };
		const s = tagesfensterSteuerung({
			fenster: () => stand,
			onStart: (h) => {
				rufe.push(`start:${h}`);
				stand = { ...stand, start: h };
			},
			onEnde: (h) => {
				rufe.push(`ende:${h}`);
				stand = { ...stand, end: h };
			},
			onNeuAufbau: () => rufe.push('neuaufbau')
		});
		return { s, rufe, stand: () => stand };
	}
	test('Start ohne Klemmung: nur onStart', () => {
		const a = aufbau({ start: 6, end: 20 });
		a.s.beiStart('08:00');
		assert.deepEqual(a.rufe, ['start:8']);
	});
	test('Start auf das Ende: onStart, dann onEnde geklemmt', () => {
		const a = aufbau({ start: 6, end: 20 });
		a.s.beiStart('20:00');
		assert.deepEqual(a.rufe, ['start:20', 'ende:21']);
		assert.deepEqual(a.stand(), { start: 20, end: 21 });
	});
	test('Ende normal: nur onEnde', () => {
		const a = aufbau({ start: 6, end: 20 });
		a.s.beiEnde('16:00');
		assert.deepEqual(a.rufe, ['ende:16']);
	});
	test('Ende über Mitternacht: onEnde ungeklemmt', () => {
		const a = aufbau({ start: 22, end: 23 });
		a.s.beiEnde('02:00');
		assert.deepEqual(a.rufe, ['ende:2']);
	});
	test('Ende = Start: onEnde geklemmt und Neuaufbau', () => {
		const a = aufbau({ start: 6, end: 20 });
		a.s.beiEnde('06:00');
		assert.deepEqual(a.rufe, ['ende:7', 'neuaufbau']);
	});
	test('Neuaufbau-Fall Start 6, Ende 7, getippt 6: onEnde(7) und Neuaufbau', () => {
		const a = aufbau({ start: 6, end: 7 });
		a.s.beiEnde('06:00');
		assert.deepEqual(a.rufe, ['ende:7', 'neuaufbau']);
	});
	test('liest das Fenster lebendig (nach Start-Änderung klemmt Ende gegen den neuen Start)', () => {
		const a = aufbau({ start: 6, end: 20 });
		a.s.beiStart('10:00');
		a.s.beiEnde('10:00');
		assert.deepEqual(a.rufe, ['start:10', 'ende:11', 'neuaufbau']);
	});
	test('ungültige Eingabe: kein Handler', () => {
		const a = aufbau({ start: 6, end: 20 });
		a.s.beiStart('');
		a.s.beiEnde('25:00');
		assert.deepEqual(a.rufe, []);
	});
});

// ─── F003 / AC-2, AC-3: Zuordnung Schalter → Handler ─────────────────────────

describe('AC-2/AC-3: Schalter → Handler der Karte Warnungen/Radar', () => {
	function aufzeichnung() {
		const rufe: string[] = [];
		return {
			rufe,
			onWarnungen: (an: boolean) => rufe.push(`warnungen:${an}`),
			onRadar: (an: boolean) => rufe.push(`radar:${an}`)
		};
	}
	test('Orts-Briefing: Warnungen-Schalter ruft onWarnungen, Radar-Schalter ruft onRadar', () => {
		const a = aufzeichnung();
		const z = schalterZeilen({ warnungenAn: true, radarAn: false, mitRadar: true, onWarnungen: a.onWarnungen, onRadar: a.onRadar });
		assert.deepEqual(z.map((x) => x.testid), ['wetter-warnungen-schalter', 'wetter-radar-schalter']);
		const nach = Object.fromEntries(z.map((x) => [x.testid, x]));
		nach['wetter-warnungen-schalter'].umlegen(false);
		nach['wetter-radar-schalter'].umlegen(true);
		assert.deepEqual(a.rufe, ['warnungen:false', 'radar:true']);
		assert.equal(nach['wetter-warnungen-schalter'].an, true);
		assert.equal(nach['wetter-radar-schalter'].an, false);
		assert.equal(nach['wetter-warnungen-schalter'].titel, 'wetter.warnungen.titel');
		assert.equal(nach['wetter-radar-schalter'].titel, 'wetter.radar.titel');
	});
	test('Trip: nur die Warnungen-Zeile', () => {
		const a = aufzeichnung();
		const z = schalterZeilen({ warnungenAn: false, radarAn: true, mitRadar: false, onWarnungen: a.onWarnungen, onRadar: a.onRadar });
		assert.deepEqual(z.map((x) => x.testid), ['wetter-warnungen-schalter']);
		z[0].umlegen(true);
		assert.deepEqual(a.rufe, ['warnungen:true']);
	});
	test('SSR: die Komponente rendert je Testid den Zustand der eigenen Zeile', async () => {
		const K2 = (await import(pathToFileURL(path.join(WT, 'WarnungenRadarKarte.svelte')).href)).default;
		const noop = () => {};
		for (const [w, r] of [[true, false], [false, true]] as const) {
			const h = render(K2, { props: { warnungenAn: w, radarAn: r, mitRadar: true, onWarnungen: noop, onRadar: noop } }).body;
			const tag = (id: string) => h.match(new RegExp(`<span\\b[^>]*data-testid="${id}"[^>]*>`))?.[0] ?? '';
			assert.match(tag('wetter-warnungen-schalter'), new RegExp(`aria-checked="${w}"`));
			assert.match(tag('wetter-radar-schalter'), new RegExp(`aria-checked="${r}"`));
		}
	});
});

// ─── Verdrahtung in der Komponente (doc-compliance-test, Adversary F004/F005) ─

type Knoten = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
function alle(x: unknown, pred: (n: Knoten) => boolean, aus: Knoten[] = []): Knoten[] {
	if (Array.isArray(x)) x.forEach((y) => alle(y, pred, aus));
	else if (x && typeof x === 'object') {
		const n = x as Knoten;
		if (pred(n)) aus.push(n);
		for (const [k, v] of Object.entries(n)) if (k !== 'parent') alle(v, pred, aus);
	}
	return aus;
}
const quelleVon = (q: string, n: Knoten | undefined) => (n ? q.slice(n.start, n.end).replace(/\s+/g, ' ').trim() : '');
/** Wert eines Attributs: Ausdruck-Quelltext bzw. Text. */
function attr(q: string, el: Knoten, name: string): string | null {
	const a = (el.attributes as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name);
	if (!a) return null;
	const v = Array.isArray(a.value) ? a.value[0] : a.value;
	if (v === true) return 'true';
	if (v?.type === 'Text') return String(v.data);
	if (v?.type === 'ExpressionTag') return quelleVon(q, v.expression);
	return null;
}
/** Elternkette eines Knotens im Fragment (über eine eigene Suche, AST hat kein parent). */
function elternVon(wurzel: unknown, ziel: Knoten): Knoten[] {
	const pfad: Knoten[] = [];
	const such = (x: unknown, kette: Knoten[]): boolean => {
		if (x === ziel) {
			pfad.push(...kette);
			return true;
		}
		if (Array.isArray(x)) return x.some((y) => such(y, kette));
		if (x && typeof x === 'object') {
			const n = x as Knoten;
			const neu = n.type ? [...kette, n] : kette;
			return Object.entries(n).some(([k, v]) => k !== 'parent' && such(v, neu));
		}
		return false;
	};
	such(wurzel, []);
	return pfad;
}

describe('Verdrahtung AnpassenKarte (doc-compliance-test, F004)', () => {
	const q = readFileSync(path.join(WT, 'AnpassenKarte.svelte'), 'utf8');
	const a = parse(q, { modern: true }) as unknown as Knoten;
	const felder = alle(a.fragment, (n) => n.type === 'Component' && n.name === 'UhrzeitFeld');
	const feld = (id: string) => felder.find((f) => attr(q, f, 'testid') === id);

	test('Start-Feld onchange = steuerung.beiStart, Ende-Feld onchange = steuerung.beiEnde', () => {
		assert.equal(attr(q, feld('day-window-start-hour')!, 'onchange'), 'steuerung.beiStart');
		assert.equal(attr(q, feld('day-window-end-hour')!, 'onchange'), 'steuerung.beiEnde');
	});
	test('Ende-Feld steht in {#key endeAufbau}, Start-Feld nicht', () => {
		const keyEnde = elternVon(a.fragment, feld('day-window-end-hour')!).filter((n) => n.type === 'KeyBlock');
		assert.equal(keyEnde.length, 1, 'Ende-Feld nicht in genau einem {#key}');
		assert.equal(quelleVon(q, keyEnde[0].expression), 'endeAufbau');
		assert.equal(elternVon(a.fragment, feld('day-window-start-hour')!).filter((n) => n.type === 'KeyBlock').length, 0);
	});
	test('steuerung = $derived(tagesfensterSteuerung({ fenster, onStart, onEnde, onNeuAufbau })) mit richtiger Zuordnung', () => {
		const aufrufe = alle(a.instance, (n) => n.type === 'CallExpression' && n.callee?.type === 'Identifier' && n.callee.name === 'tagesfensterSteuerung');
		assert.equal(aufrufe.length, 1);
		const obj = aufrufe[0].arguments[0];
		assert.equal(obj?.type, 'ObjectExpression');
		const prop = (k: string) => quelleVon(q, (obj.properties as Knoten[]).find((p) => p.key?.name === k)?.value);
		assert.equal(prop('onStart'), 'onStart', 'onStart der Steuerung ist nicht der Prop onStart');
		assert.equal(prop('onEnde'), 'onEnde', 'onEnde der Steuerung ist nicht der Prop onEnde');
		assert.equal(prop('fenster'), '() => tagesfenster');
		assert.match(prop('onNeuAufbau'), /^\(\) => \(?endeAufbau \+= 1\)?$/);
		const dekl = alle(a.instance, (n) => n.type === 'VariableDeclarator' && n.id?.name === 'steuerung')[0];
		assert.match(quelleVon(q, dekl?.init), /^\$derived\(tagesfensterSteuerung\(/);
		const keyDekl = alle(a.instance, (n) => n.type === 'VariableDeclarator' && n.id?.name === 'endeAufbau')[0];
		assert.equal(quelleVon(q, keyDekl?.init), '$state(0)');
	});
});

describe('Verdrahtung WarnungenRadarKarte (doc-compliance-test, F005)', () => {
	const q = readFileSync(path.join(WT, 'WarnungenRadarKarte.svelte'), 'utf8');
	const a = parse(q, { modern: true }) as unknown as Knoten;

	test('schalterZeilen bekommt das unveränderte $props()-Objekt', () => {
		const aufrufe = alle(a.instance, (n) => n.type === 'CallExpression' && n.callee?.type === 'Identifier' && n.callee.name === 'schalterZeilen');
		assert.equal(aufrufe.length, 1);
		assert.equal(aufrufe[0].arguments.length, 1);
		const arg = aufrufe[0].arguments[0];
		assert.equal(arg.type, 'Identifier', 'schalterZeilen erhält kein unverändertes Props-Objekt');
		const dekl = alle(a.instance, (n) => n.type === 'VariableDeclarator' && n.id?.type === 'Identifier' && n.id.name === arg.name)[0];
		assert.equal(quelleVon(q, dekl?.init), '$props()', `${arg.name} ist nicht das $props()-Objekt`);
	});
	test('{#each zeilen as z}: Switch mit onchange={z.umlegen}, checked={z.an}, testid={z.testid}', () => {
		const each = alle(a.fragment, (n) => n.type === 'EachBlock');
		assert.equal(each.length, 1);
		assert.equal(quelleVon(q, each[0].expression), 'zeilen');
		assert.equal(quelleVon(q, each[0].context), 'z');
		const sw = alle(each[0].body, (n) => n.type === 'Component' && n.name === 'Switch');
		assert.equal(sw.length, 1);
		assert.equal(attr(q, sw[0], 'onchange'), 'z.umlegen');
		assert.equal(attr(q, sw[0], 'checked'), 'z.an');
		assert.equal(attr(q, sw[0], 'testid'), 'z.testid');
	});
});

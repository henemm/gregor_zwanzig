// Issue #3192 (Epic #2913): Wetter-Dialoge im Abgleich auf Mockup-Datenlage. Spec:
// docs/specs/modules/fix_3192_wetter_dialog_abgleich.md (AC-1, AC-2, AC-4).
// RED: die hier getesteten Funktionen sind in frontend/e2e/elementliste_abgleich_logik.ts NEU zu exportieren.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test src/lib/__tests__/elementliste_abgleich_mockuplage_3192.test.ts
//
// Festgelegte Signaturen (Developer baut sie exakt so):
//   datensatzFuerAbschnitt(abschnitt: string): 'mit_abweichung' | 'ohne_abweichung'
//       grenzen-* -> mit_abweichung; alles andere (vorlage-auswahl/-bestaetigung/-speichern/-speichern-fehler) -> ohne_abweichung
//   wetterOverrides(metriken: string[], eig: Record<string, { allowed_sides: string | null }>):
//       { metrics: Record<string, AmpelMetrik>; thunder?: { mittel: string; hoch: string } }
//       allowed_sides in { 'both', 'upper', 'lower', 'level' (nur Gewitter), null }.
//       both -> lower UND upper; upper -> nur upper; lower -> nur lower; null/unbekannt -> kein Override.
//       lower aufsteigend red<orange<yellow, upper aufsteigend yellow<orange<red, lower.yellow < upper.yellow.
//       'level' (Gewitter) -> kein metrics-Eintrag, stattdessen thunder = { mittel: 'yellow', hoch: 'orange' }.
//   wechselZiel(ctx: 'trip'|'orte'|string, vorlagen: string[], aktiv: string):
//       { art: 'ziel'; id: string } | { art: 'nicht_herstellbar'; grund: string }
//       trip -> 'wandern', orte -> 'alpen-trekking'; fehlt es -> nicht_herstellbar (Grund nennt die ID);
//       ctx ohne Mockup-Ziel -> erste Vorlage != aktiv, sonst nicht_herstellbar.
//   MOCKUP_LAGE = { trip: { aktiv: 'alpen-trekking', ziel: 'wandern' }, orte: { aktiv: 'allgemein', ziel: 'alpen-trekking', orte: 3 } }
//   eingabeText(el: { tag: string; ariaLabel: string | null; placeholder: string | null; value: string }): string
//       INPUT und TEXTAREA: aria-label || placeholder || value; andere Tags -> ''.
//       Hinweis: die Browserfunktion `sichtbareTexte` (page.evaluate, keine Imports) spiegelt diese Regel inline.
//   bedienPlan('vorlage-bestaetigung', lage) nutzt wechselZiel (Kontext-abhaengiges Ziel statt "erste andere").

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import * as L from '../../../e2e/elementliste_abgleich_logik.ts';

function fn<T extends (...a: never[]) => unknown>(name: string): T {
	const f = (L as Record<string, unknown>)[name];
	assert.equal(typeof f, 'function', `${name} fehlt in elementliste_abgleich_logik.ts`);
	return f as T;
}

type Seite = { red?: number; orange?: number; yellow?: number };
type Metrik = { lower?: Seite; upper?: Seite };
type Overrides = { metrics: Record<string, Metrik>; thunder?: { mittel: string; hoch: string } };
const EIG = {
	temperature: { allowed_sides: 'both' },
	wind: { allowed_sides: 'upper' },
	sunshine: { allowed_sides: 'lower' },
	thunder: { allowed_sides: 'level' },
	pressure: { allowed_sides: null }
};
const IDS = Object.keys(EIG);

describe('#3192 AC-1 datensatzFuerAbschnitt', () => {
	test('grenzen-* -> mit_abweichung', () => {
		const f = fn<(a: string) => string>('datensatzFuerAbschnitt');
		for (const a of ['grenzen-wind', 'grenzen-temperature', 'grenzen-thunder']) assert.equal(f(a), 'mit_abweichung', a);
	});
	test('vorlage-* -> ohne_abweichung', () => {
		const f = fn<(a: string) => string>('datensatzFuerAbschnitt');
		for (const a of ['vorlage-auswahl', 'vorlage-bestaetigung', 'vorlage-speichern', 'vorlage-speichern-fehler']) assert.equal(f(a), 'ohne_abweichung', a);
	});
});

describe('#3192 AC-1 wetterOverrides', () => {
	const bau = () => fn<(m: string[], e: typeof EIG) => Overrides>('wetterOverrides')(IDS, EIG);
	const aufsteigend = (w: number[]) => w.every((x, i) => i === 0 || x > w[i - 1]);

	test('nur erlaubte Seiten je Metrik', () => {
		const m = bau().metrics;
		assert.ok(m.temperature.lower && m.temperature.upper, 'both: beide Seiten');
		assert.ok(m.wind.upper && !m.wind.lower, 'upper: nur upper');
		assert.ok(m.sunshine.lower && !m.sunshine.upper, 'lower: nur lower');
		assert.equal(m.pressure, undefined, 'ohne Seiten: kein Override');
		assert.equal(m.thunder, undefined, 'Gewitter nicht in metrics');
	});
	test('Werte je Seite streng aufsteigend, lower.yellow < upper.yellow', () => {
		for (const [id, e] of Object.entries(bau().metrics)) {
			if (e.lower) assert.ok(aufsteigend([e.lower.red!, e.lower.orange!, e.lower.yellow!]), `${id} lower`);
			if (e.upper) assert.ok(aufsteigend([e.upper.yellow!, e.upper.orange!, e.upper.red!]), `${id} upper`);
			if (e.lower && e.upper) assert.ok(e.lower.yellow! < e.upper.yellow!, `${id} lower.yellow < upper.yellow`);
		}
	});
	test('Gewitter als thunder: hoch nie gelb, hoch >= mittel', () => {
		const t = bau().thunder;
		assert.deepEqual(t, { mittel: 'yellow', hoch: 'orange' });
	});
	test('ohne Gewitter-Metrik kein thunder', () => {
		const o = fn<(m: string[], e: typeof EIG) => Overrides>('wetterOverrides')(['wind'], EIG);
		assert.equal(o.thunder, undefined);
		assert.deepEqual(Object.keys(o.metrics), ['wind']);
	});
});

describe('#3192 AC-2 wechselZiel und MOCKUP_LAGE', () => {
	const API = ['alpen-trekking', 'wandern', 'skitouren', 'wintersport', 'radtour', 'wassersport', 'allgemein'];
	type Z = { art: 'ziel'; id: string } | { art: 'nicht_herstellbar'; grund: string };
	const ziel = (c: string, v: string[], a: string) => fn<(c: string, v: string[], a: string) => Z>('wechselZiel')(c, v, a);

	test('MOCKUP_LAGE', () => {
		assert.deepEqual((L as Record<string, unknown>).MOCKUP_LAGE, {
			trip: { aktiv: 'alpen-trekking', ziel: 'wandern' },
			orte: { aktiv: 'allgemein', ziel: 'alpen-trekking', orte: 3 }
		});
	});
	test('trip -> wandern, orte -> alpen-trekking', () => {
		assert.deepEqual(ziel('trip', API, 'alpen-trekking'), { art: 'ziel', id: 'wandern' });
		assert.deepEqual(ziel('orte', API, 'allgemein'), { art: 'ziel', id: 'alpen-trekking' });
	});
	test('Ziel fehlt -> nicht_herstellbar mit Grund, der die ID nennt', () => {
		const z = ziel('trip', API.filter((v) => v !== 'wandern'), 'alpen-trekking');
		assert.equal(z.art, 'nicht_herstellbar');
		assert.ok(z.art === 'nicht_herstellbar' && z.grund.includes('wandern'));
	});
	test('kein Mockup-Ziel -> erste Vorlage != aktiv; keine andere -> nicht_herstellbar', () => {
		assert.deepEqual(ziel('anderer', ['x', 'y'], 'x'), { art: 'ziel', id: 'y' });
		const z = ziel('anderer', ['x'], 'x');
		assert.equal(z.art, 'nicht_herstellbar');
		assert.ok(z.art === 'nicht_herstellbar' && z.grund.length > 0);
	});
});

describe('#3192 AC-2 bedienPlan nutzt das Mockup-Ziel', () => {
	const API = ['alpen-trekking', 'wandern', 'skitouren', 'wintersport', 'radtour', 'wassersport', 'allgemein'];
	type Pl = { art: string; schritte?: { testid?: string }[]; grund?: string };
	const plan = (lage: { ctx: string; briefing: string[]; vorlagen: string[]; aktiveVorlage: string }) =>
		fn<(a: string, l: typeof lage) => Pl>('bedienPlan')('vorlage-bestaetigung', lage);

	test('trip: wetter-vorlage-option-wandern', () => {
		const p = plan({ ctx: 'trip', briefing: [], vorlagen: API, aktiveVorlage: 'alpen-trekking' });
		assert.equal(p.art, 'plan');
		assert.ok(p.schritte!.some((s) => s.testid === 'wetter-vorlage-option-wandern'));
	});
	test('orte (aktiv allgemein): wetter-vorlage-option-alpen-trekking', () => {
		const p = plan({ ctx: 'orte', briefing: [], vorlagen: API, aktiveVorlage: 'allgemein' });
		assert.equal(p.art, 'plan');
		assert.ok(p.schritte!.some((s) => s.testid === 'wetter-vorlage-option-alpen-trekking'));
		assert.ok(!p.schritte!.some((s) => s.testid === 'wetter-vorlage-option-wandern'));
	});
	test('trip ohne wandern in der Liste -> nicht_herstellbar', () => {
		const p = plan({ ctx: 'trip', briefing: [], vorlagen: API.filter((v) => v !== 'wandern'), aktiveVorlage: 'alpen-trekking' });
		assert.equal(p.art, 'nicht_herstellbar');
		assert.ok((p.grund ?? '').includes('wandern'));
	});
});

describe('#3192 AC-4 eingabeText (Platzhalter auch aus textarea)', () => {
	const et = (el: { tag: string; ariaLabel: string | null; placeholder: string | null; value: string }) =>
		fn<(e: typeof el) => string>('eingabeText')(el);
	test('TEXTAREA liefert Platzhalter', () => {
		assert.equal(et({ tag: 'TEXTAREA', ariaLabel: null, placeholder: 'Beschreibung', value: '' }), 'Beschreibung');
	});
	test('INPUT: aria-label vor Platzhalter vor Wert', () => {
		assert.equal(et({ tag: 'INPUT', ariaLabel: 'Name', placeholder: 'P', value: 'V' }), 'Name');
		assert.equal(et({ tag: 'INPUT', ariaLabel: null, placeholder: 'P', value: 'V' }), 'P');
		assert.equal(et({ tag: 'INPUT', ariaLabel: null, placeholder: null, value: 'V' }), 'V');
	});
	test('andere Tags -> leer', () => {
		assert.equal(et({ tag: 'DIV', ariaLabel: 'x', placeholder: 'y', value: 'z' }), '');
	});
});

// Fix-Loop F001: die Staging-Spec gibt eingabeText per toString() in den Browser (addInitScript); die dort
// wirkende Regel ist nur dann die getestete, wenn die Funktion selbstenthalten serialisierbar ist.
describe('#3192 F001 eingabeText ist serialisierbar (Browser-Regel = getestete Regel)', () => {
	type E = { tag: string; ariaLabel: string | null; placeholder: string | null; value: string };
	const FAELLE: E[] = [
		{ tag: 'TEXTAREA', ariaLabel: null, placeholder: 'Beschreibung', value: '' },
		{ tag: 'TEXTAREA', ariaLabel: 'Notiz', placeholder: 'P', value: 'V' },
		{ tag: 'TEXTAREA', ariaLabel: null, placeholder: null, value: 'Inhalt' },
		{ tag: 'INPUT', ariaLabel: 'Name', placeholder: 'P', value: 'V' },
		{ tag: 'INPUT', ariaLabel: null, placeholder: 'P', value: 'V' },
		{ tag: 'INPUT', ariaLabel: null, placeholder: null, value: 'V' },
		{ tag: 'INPUT', ariaLabel: '', placeholder: '', value: '' },
		{ tag: 'DIV', ariaLabel: 'x', placeholder: 'y', value: 'z' },
		{ tag: 'BUTTON', ariaLabel: 'Speichern', placeholder: null, value: '' },
		{ tag: 'SELECT', ariaLabel: 'Wahl', placeholder: null, value: 'a' }
	];
	test('new Function(toString) liefert dieselben Ergebnisse wie eingabeText (inkl. TEXTAREA)', () => {
		const original = fn<(e: E) => string>('eingabeText');
		const quelle = original.toString();
		const kopie = new Function(`return ${quelle}`)() as (e: E) => string;
		assert.equal(typeof kopie, 'function');
		for (const f of FAELLE) assert.equal(kopie(f), original(f), JSON.stringify(f));
		assert.equal(kopie(FAELLE[0]), 'Beschreibung', 'TEXTAREA-Platzhalter auch im serialisierten Browser-Text');
	});
});

describe('#3192 F002 (a) seitenIdFuer: Abschnitt -> Prüf-Datensatz-ID', () => {
	const ids = { trip: { mit_abweichung: 'trip-mit', ohne_abweichung: 'trip-ohne' }, orte: { mit_abweichung: 'orte-mit', ohne_abweichung: 'orte-ohne' } };
	const sid = (a: string, c: string, w: Record<string, unknown>) => fn<(a: string, c: string, w: Record<string, unknown>) => string | null>('seitenIdFuer')(a, c, w);
	test('grenzen-* -> ID mit Abweichung (je Kontext)', () => {
		assert.equal(sid('grenzen-wind', 'trip', ids), 'trip-mit');
		assert.equal(sid('grenzen-thunder', 'orte', ids), 'orte-mit');
	});
	test('vorlage-* -> ID ohne Abweichung (je Kontext)', () => {
		for (const a of ['vorlage-auswahl', 'vorlage-bestaetigung', 'vorlage-speichern', 'vorlage-speichern-fehler']) {
			assert.equal(sid(a, 'trip', ids), 'trip-ohne', a);
			assert.equal(sid(a, 'orte', ids), 'orte-ohne', a);
		}
	});
	test('fehlender Kontext oder Datensatz -> null (nie ersetzen)', () => {
		assert.equal(sid('grenzen-wind', 'trip', { trip: null, orte: null }), null);
		assert.equal(sid('grenzen-wind', 'anderer', ids), null);
		assert.equal(sid('grenzen-wind', 'trip', { trip: { ohne_abweichung: 'trip-ohne' } }), null);
		assert.equal(sid('vorlage-auswahl', 'orte', { orte: { mit_abweichung: 'orte-mit' } }), null);
	});
});

describe('#3192 F002 (b) pruefReste: nur Prüf-Objekte zählen als Leck', () => {
	type B = { trips: Record<string, unknown>[]; vergleiche: Record<string, unknown>[]; orte: Record<string, unknown>[]; vorlagen: Record<string, unknown>[] };
	const reste = (b: B) => fn<(b: B) => string[]>('pruefReste')(b);
	const SEED: B = {
		trips: [{ id: 'gr221-mallorca', name: 'Mallorca Frühling' }, { id: 'gr221', name: 'GR221' }],
		vergleiche: [{ id: 'v1', name: 'Münsterland' }],
		orte: [{ id: 'o1', name: 'Münster' }, { id: 'o2', name: 'Deià' }],
		vorlagen: [{ id: 'p1', name: 'GR221', description: 'aus GR221 gespeichert' }, { id: 'p2', name: 'E2E-GZ andere Vorlage' }]
	};
	test('Prüfkonto-Seed allein -> kein Rest', () => {
		assert.deepEqual(reste(SEED), []);
	});
	test('F004: Trip allein über ABGLEICH_TRIP_ID (fremder Name) ist ein Rest', () => {
		const r = reste({ ...SEED, trips: [...SEED.trips, { id: 'e2e-gz-2913-abgleich', name: 'umbenannt' }] });
		assert.equal(r.length, 1, r.join('\n'));
		assert.ok(r[0].includes('e2e-gz-2913-abgleich'));
		assert.equal((L as Record<string, unknown>).ABGLEICH_TRIP_ID, 'e2e-gz-2913-abgleich');
	});
	test('jede Art von Prüf-Rest wird gemeldet, Seed nie', () => {
		const b: B = {
			trips: [...SEED.trips, { id: 'e2e-gz-2966-wetter-mit', name: 'irgendwas' }, { id: 'x', name: 'E2E-GZ #2966 Wetter-Prüfung (ohne Abweichung)' }, { id: 'e2e-gz-2913-abgleich', name: 'E2E-GZ #2913 Elementlisten-Abgleich' }],
			vergleiche: [...SEED.vergleiche, { id: 'v9', name: 'E2E-GZ #2966 Wetter-Prüfung (mit Abweichung)' }, { id: 'v8', name: 'E2E-GZ #2913 Orte-Abgleich' }],
			orte: [...SEED.orte, { id: 'o9', name: 'E2E-GZ #2966 Wetter-Prüfung Ort 2' }, { id: 'o8', name: 'E2E-GZ #2913 Ort' }],
			vorlagen: [...SEED.vorlagen, { id: 'p9', name: 'E2E-GZ #3192 eigene Vorlage' }]
		};
		const r = reste(b);
		assert.equal(r.length, 8, r.join('\n'));
		for (const id of ['e2e-gz-2966-wetter-mit', ' x ', 'e2e-gz-2913-abgleich', 'v9', 'v8', 'o9', 'o8', 'p9']) assert.ok(r.some((z) => z.includes(id.trim())), id);
		for (const s of ['Mallorca Frühling', 'Münsterland', 'Deià', 'GR221“', 'E2E-GZ andere Vorlage']) assert.ok(!r.some((z) => z.includes(s)), s);
	});
});

describe('#3192 F002 (c) Anlege-Payloads', () => {
	type Q = { liste: unknown[]; vorlagen: Record<string, unknown>[]; eig: Record<string, { allowed_sides: string | null }>; ortIds: string[]; datum: string };
	const payload = (ctx: 'trip' | 'orte', d: string, q: Q) => fn<(c: string, d: string, q: Q) => Record<string, any>>('wetterPruefPayload')(ctx, d, q);
	const el = (ctx: string, abschnitt: string) => ({ id: `${ctx}-${abschnitt}`, ctx, reiter: 'wetter', abschnitt, zustand: 'normal', text: 'x' });
	const Q: Q = {
		liste: [el('trip', 'grenzen-wind'), el('trip', 'grenzen-temperature'), el('trip', 'grenzen-thunder'), el('orte', 'grenzen-wind'), el('orte', 'grenzen-sunshine'), el('trip', 'vorlage-auswahl')],
		vorlagen: [
			{ id: 'alpen-trekking', ampel: { metrics: { wind: { enabled: true }, rain: { enabled: true }, temperature: { enabled: false } } } },
			{ id: 'allgemein', ampel: { metrics: { temperature: { enabled: true }, sunshine: { enabled: false }, cloud: { enabled: true } } } },
			{ id: 'wandern', ampel: { metrics: { gust: { enabled: true } } } }
		],
		eig: EIG,
		ortIds: ['o1', 'o2', 'o3'],
		datum: '2026-11-20'
	};
	const keineGrenzen = (ampel: Record<string, unknown>) => {
		assert.equal(ampel.thunder, undefined, 'kein thunder');
		const m = (ampel.metrics ?? {}) as Record<string, { lower?: unknown; upper?: unknown }>;
		for (const [id, e] of Object.entries(m)) assert.ok(!e?.lower && !e?.upper, `${id}: keine lower/upper`);
	};

	test('trip ohne_abweichung: genau die aktiven Metriken von alpen-trekking, Ampel nur Vorlage', () => {
		const p = payload('trip', 'ohne_abweichung', Q);
		assert.equal(p.id, 'e2e-gz-2966-wetter-ohne');
		assert.ok(String(p.name).startsWith('E2E-GZ #2966 Wetter-Prüfung'));
		assert.equal(p.display_config.preset_name, 'alpen-trekking');
		assert.deepEqual(p.display_config.metrics.map((m: { metric_id: string }) => m.metric_id).sort(), ['rain', 'wind']);
		assert.deepEqual(p.display_config.ampel, { template: 'alpen-trekking' });
		keineGrenzen(p.display_config.ampel);
		assert.equal(p.stages[0].date, '2026-11-20');
	});
	test('orte ohne_abweichung: genau die aktiven Metriken von allgemein, drei Orte, Ampel nur Vorlage', () => {
		const p = payload('orte', 'ohne_abweichung', Q);
		assert.deepEqual(p.display_config.active_metrics.map((m: { metric_id: string }) => m.metric_id).sort(), ['cloud', 'temperature']);
		assert.deepEqual(p.display_config.ampel, { template: 'allgemein' });
		keineGrenzen(p.display_config.ampel);
		assert.deepEqual(p.location_ids, ['o1', 'o2', 'o3']);
	});
	test('mit_abweichung: Grenzen-Metriken der Liste und wetterOverrides', () => {
		const t = payload('trip', 'mit_abweichung', Q);
		assert.equal(t.id, 'e2e-gz-2966-wetter-mit');
		assert.deepEqual(t.display_config.metrics.map((m: { metric_id: string }) => m.metric_id).sort(), ['temperature', 'thunder', 'wind']);
		const erwartet = fn<(m: string[], e: typeof EIG) => Overrides>('wetterOverrides')(['wind', 'temperature', 'thunder'], EIG);
		assert.deepEqual(t.display_config.ampel, { template: 'alpen-trekking', ...erwartet });
		assert.ok(t.display_config.ampel.metrics.wind.upper && t.display_config.ampel.thunder);
		const o = payload('orte', 'mit_abweichung', Q);
		assert.deepEqual(o.display_config.active_metrics.map((m: { metric_id: string }) => m.metric_id).sort(), ['sunshine', 'wind']);
		assert.equal(o.display_config.ampel.template, 'allgemein');
		assert.ok(o.display_config.ampel.metrics.sunshine.lower && o.display_config.ampel.metrics.wind.upper);
	});
	test('F004 aktiveMetrikenDerVorlage: nur enabled === true zählt (fehlend, undefined, false, Wahrheitswert-Ersatz nicht)', () => {
		// Echte Semantik von /api/templates (AMPEL_TEMPLATES): jede Metrik trägt enabled als bool; alles andere ist nie aktiv.
		const akt = fn<(v: Record<string, unknown>[], id: string) => string[]>('aktiveMetrikenDerVorlage');
		const vorlagen = [
			{ id: 'v', ampel: { metrics: { an: { enabled: true }, aus: { enabled: false }, ohne: {}, undef: { enabled: undefined }, eins: { enabled: 1 }, text: { enabled: 'true' }, leer: null } } },
			{ id: 'andere', ampel: { metrics: { fremd: { enabled: true } } } }
		];
		assert.deepEqual(akt(vorlagen, 'v'), ['an']);
		assert.deepEqual(akt(vorlagen, 'fehlt'), [], 'unbekannte Vorlage: keine Metriken');
		assert.deepEqual(akt([{ id: 'v' }], 'v'), [], 'Vorlage ohne ampel: keine Metriken');
	});
	test('F004 eigeneVorlagePayload: metrics nicht leer', () => {
		const ev = fn<(k: string) => Record<string, unknown>>('eigeneVorlagePayload');
		for (const kind of ['route', 'vergleich']) {
			const m = ev(kind).metrics;
			assert.ok(Array.isArray(m) && m.length > 0 && m.every((x) => typeof x === 'string' && x.length > 0), `${kind}: ${JSON.stringify(m)}`);
		}
	});
	test('eigeneVorlagePayload: Prüf-Name, Beschreibung exakt „aus GR221 gespeichert“, Art übernommen', () => {
		const ev = fn<(k: string) => Record<string, unknown>>('eigeneVorlagePayload');
		for (const kind of ['route', 'vergleich']) {
			const p = ev(kind);
			assert.equal(p.name, 'E2E-GZ #3192 eigene Vorlage');
			assert.equal(p.description, 'aus GR221 gespeichert');
			assert.equal(p.kind, kind);
			assert.equal(p.is_default, false);
		}
	});
});

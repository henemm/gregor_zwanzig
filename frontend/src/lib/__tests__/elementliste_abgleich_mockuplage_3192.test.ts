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

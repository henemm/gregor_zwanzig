// TDD RED — Issue #2913 (Einstellungen neu, Schritt 3: Bausteine), Teil 2.
// Spec: docs/specs/modules/feat_2913_s3_bausteine.md — AC-12, AC-15 (NichtImBriefing), AC-16,
// Klarstellungen K-2, K-6, K-7.
//
// Soll:
//   - AC-16: VorlageKarte, AlarmAbKopf, MetrikZeile, AmpelLeiste, GrenzenEditor, NichtImBriefing und (K-6) der
//     Organismus WetterTabInhalt enthalten kein rohes <button>/<input>/<select>/<textarea> mehr.
//     AlarmAbKopf und WarnungenRadarKarte bauen ihre Zeile aus dem Molekül Einstellungszeile (K-6);
//     WetterTabInhalt zeigt beim Laden das Atom Skelett (K-6).
//   - AC-12: AmpelLeiste färbt aus var(--g-ampel-*) statt der Behelfs-Tokens (--g-success, --g-wx-sun,
//     --g-accent, --g-danger). Server-Render: je Segment ein Element mit data-farbe und role="img" +
//     aria-label = Farbname aus dem Katalog (wetter.farbe.*), in der Reihenfolge aus ampelLeiste.ts
//     (leisteVon/gewitterLeiste, Logik unverändert).
//   - AC-15/K-2: NichtImBriefing baut auf molecules ChipLeiste: ein Btn-Chip je nicht ausgewählter Metrik
//     (Testid wetter-nicht-im-briefing-plus-<id> bleibt, Text aus dem Katalog).
//   - K-6/K-7: MetrikZeile — „Alarm ab“-Stufen bleiben role=radio mit aria-checked und Testids
//     wetter-alarm-ab-<id>-<stufe>; die Farbstufen (yellow/orange/red) tragen einen Farbpunkt data-farbe,
//     „never“ keinen. Entfernen und Grenzen-ändern sind Btn (data-slot="btn") mit erhaltenen Testids.
//     GrenzenEditor: Eingabefelder sind das Atom Input mit data-ampel=<Farbe des Felds>, Testids erhalten.
//
// Verhalten per Server-Render (svelte/server); Quellregeln (rohe Controls, Tokens, Importe):
// doc-compliance-test
//
// RED heute: rohe Controls, Behelfs-Tokens, kein data-farbe, keine Moleküle.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/wetter_tab_bausteine.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

import { leisteVon, gewitterLeiste } from '../../shared/wetter-tab/ampelLeiste.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> organisms -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const WT = path.resolve(HERE, '..', 'wetter-tab');
const I18N = path.join(FRONTEND, 'src', 'lib', 'i18n', 'messages', 'de');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

const WETTER: Record<string, string> = JSON.parse(readFileSync(path.join(I18N, 'wetter.json'), 'utf8'));
const datei = (n: string) => path.join(WT, `${n}.svelte`);
function quelle(n: string): string {
	assert.ok(existsSync(datei(n)), `TDD RED: organisms/wetter-tab/${n}.svelte fehlt`);
	return readFileSync(datei(n), 'utf8');
}
async function lade(n: string): Promise<any> {
	assert.ok(existsSync(datei(n)), `TDD RED: organisms/wetter-tab/${n}.svelte fehlt`);
	return (await import(pathToFileURL(datei(n)).href)).default;
}
const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
const text = (h: string) =>
	h
		.replace(/<[^>]*>/g, ' ')
		.replace(/&nbsp;/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
const noop = () => {};

type Knoten = Record<string, any>;
function ast(q: string): Knoten {
	return parse(q, { modern: true }) as unknown as Knoten;
}
const ROH = new Set(['button', 'input', 'select', 'textarea']);
function roheControls(q: string): string[] {
	const aus: string[] = [];
	const lauf = (x: unknown) => {
		if (Array.isArray(x)) return x.forEach(lauf);
		if (!x || typeof x !== 'object') return;
		const n = x as Knoten;
		if (n.type === 'RegularElement' && ROH.has(String(n.name))) aus.push(`<${n.name}>`);
		for (const [k, v] of Object.entries(n)) if (k !== 'parent') lauf(v);
	};
	lauf(ast(q).fragment);
	return aus;
}
/** Import-Quelle des lokalen Namens `name` (Instanz-Skript), sonst null. */
function importVon(q: string, name: string): string | null {
	for (const s of (ast(q).instance?.content?.body ?? []) as Knoten[]) {
		if (s.type !== 'ImportDeclaration') continue;
		if ((s.specifiers as Knoten[]).some((sp) => sp.local?.name === name)) return String(s.source.value);
	}
	return null;
}
/** Komponente `name` wird im Markup verwendet. */
function nutzt(q: string, name: string): boolean {
	let gefunden = false;
	const lauf = (x: unknown) => {
		if (gefunden) return;
		if (Array.isArray(x)) return x.forEach(lauf);
		if (!x || typeof x !== 'object') return;
		const n = x as Knoten;
		if (n.type === 'Component' && n.name === name) gefunden = true;
		for (const [k, v] of Object.entries(n)) if (k !== 'parent') lauf(v);
	};
	lauf(ast(q).fragment);
	return gefunden;
}

// ─── AC-16: keine rohen Controls ─────────────────────────────────────────────

describe('AC-16/K-6: Organismen ohne rohe Controls', () => {
	for (const n of ['VorlageKarte', 'AlarmAbKopf', 'MetrikZeile', 'AmpelLeiste', 'GrenzenEditor', 'NichtImBriefing', 'WetterTabInhalt']) {
		test(`${n}: kein rohes <button>/<input>/<select>/<textarea>`, () => {
			assert.deepEqual(roheControls(quelle(n)), [], `TDD RED: ${n} enthält rohe Controls`);
		});
	}
	for (const n of ['AlarmAbKopf', 'WarnungenRadarKarte']) {
		test(`${n}: Zeile aus dem Molekül Einstellungszeile`, () => {
			const q = quelle(n);
			const von = importVon(q, 'Einstellungszeile');
			assert.ok(von, `TDD RED: ${n} importiert Einstellungszeile nicht`);
			assert.match(von!, /^\$lib\/components\/molecules(\/Einstellungszeile\.svelte)?$/);
			assert.ok(nutzt(q, 'Einstellungszeile'), `${n} verwendet <Einstellungszeile> nicht`);
		});
	}
	test('WetterTabInhalt: Ladeanzeige aus dem Atom Skelett', () => {
		const q = quelle('WetterTabInhalt');
		const von = importVon(q, 'Skelett');
		assert.ok(von, 'TDD RED: WetterTabInhalt importiert Skelett nicht');
		assert.match(von!, /^\$lib\/components\/atoms(\/Skelett\.svelte)?$/);
		assert.ok(nutzt(q, 'Skelett'), 'WetterTabInhalt verwendet <Skelett> nicht');
	});
});

// ─── AC-12: AmpelLeiste ──────────────────────────────────────────────────────

const DE_TOKEN: Record<string, string> = { green: 'gruen', yellow: 'gelb', orange: 'orange', red: 'rot' };

/** Segment-Elemente der Leiste: [farbe, öffnender Tag] in Dokument-Reihenfolge. */
function segmenteIn(h: string): { farbe: string; tag: string }[] {
	return [...h.matchAll(/<[a-z]+\b[^>]*\sdata-farbe="([a-z]+)"[^>]*>/g)].map((m) => ({ farbe: m[1], tag: m[0] }));
}

describe('AC-12: AmpelLeiste aus --g-ampel-*, Stufe ohne Farbe erkennbar', () => {
	test('Quelle nutzt var(--g-ampel-gruen/-gelb/-orange/-rot)', () => {
		const q = quelle('AmpelLeiste');
		const fehlt = Object.values(DE_TOKEN).filter((t) => !q.includes(`var(--g-ampel-${t})`));
		assert.deepEqual(fehlt, [], `TDD RED: AmpelLeiste ohne var(--g-ampel-${fehlt.join('/')})`);
	});
	test('Quelle ohne Behelfs-Tokens --g-success/--g-wx-sun/--g-accent/--g-danger', () => {
		const q = quelle('AmpelLeiste');
		const treffer = ['--g-success', '--g-wx-sun', '--g-accent', '--g-danger'].filter((t) => new RegExp(`var\\(${t}\\)`).test(q));
		assert.deepEqual(treffer, [], `TDD RED: Behelfs-Tokens noch in AmpelLeiste: ${treffer.join(', ')}`);
	});

	const FAELLE: { name: string; props: Record<string, unknown>; soll: string[] }[] = [
		{
			name: 'nur oben (Wind)',
			props: { id: 'wind', eintrag: { upper: { yellow: 30, orange: 50, red: 70 } } },
			soll: leisteVon({ upper: { yellow: 30, orange: 50, red: 70 } }).segmente.map((s) => s.farbe)
		},
		{
			name: 'beidseitig (Temperatur)',
			props: { id: 'temp', eintrag: { lower: { red: -10, orange: -5, yellow: 0 }, upper: { yellow: 30 } } },
			soll: leisteVon({ lower: { red: -10, orange: -5, yellow: 0 }, upper: { yellow: 30 } }).segmente.map((s) => s.farbe)
		},
		{
			name: 'Gewitter (Stufen)',
			props: { id: 'thunder', eintrag: undefined, gewitter: { mittel: 'orange', hoch: 'red' } },
			soll: gewitterLeiste({ mittel: 'orange', hoch: 'red' }).map((s) => s.farbe)
		}
	];
	for (const f of FAELLE) {
		test(`SSR ${f.name}: je Segment data-farbe in Reihenfolge von ampelLeiste.ts`, async () => {
			const A = await lade('AmpelLeiste');
			const seg = segmenteIn(html(A, f.props));
			assert.deepEqual(seg.map((s) => s.farbe), f.soll, 'TDD RED: Segmente ohne data-farbe oder in anderer Reihenfolge');
		});
		test(`SSR ${f.name}: je Segment role="img" und aria-label = Farbname aus dem Katalog`, async () => {
			const A = await lade('AmpelLeiste');
			const seg = segmenteIn(html(A, f.props));
			assert.equal(seg.length, f.soll.length, 'TDD RED: Segmente ohne data-farbe');
			for (const s of seg) {
				assert.match(s.tag, /\srole="img"/, `Segment ${s.farbe} ohne role="img"`);
				const wort = WETTER[`wetter.farbe.${s.farbe}`];
				assert.ok(wort, `Katalogschlüssel wetter.farbe.${s.farbe} fehlt`);
				assert.match(s.tag, new RegExp(`\\saria-label="${wort}"`), `Segment ${s.farbe} ohne aria-label „${wort}“`);
			}
		});
	}
	test('SSR: Testid wetter-ampel-leiste-<id> bleibt (K-7)', async () => {
		const A = await lade('AmpelLeiste');
		assert.match(html(A, FAELLE[0].props), /data-testid="wetter-ampel-leiste-wind"/);
	});
});

// ─── AC-15/K-2: NichtImBriefing auf ChipLeiste ───────────────────────────────

describe('AC-15/K-2: NichtImBriefing baut auf ChipLeiste', () => {
	const METRIKEN = [
		{ id: 'wind', name: 'Wind' },
		{ id: 'gust', name: 'Böen' },
		{ id: 'uv_index', name: 'UV-Index' }
	];
	test('Quelle importiert ChipLeiste aus molecules und verwendet sie', () => {
		const q = quelle('NichtImBriefing');
		const von = importVon(q, 'ChipLeiste');
		assert.ok(von, 'TDD RED: NichtImBriefing importiert ChipLeiste nicht');
		assert.match(von!, /^\$lib\/components\/molecules(\/ChipLeiste\.svelte)?$/);
		assert.ok(nutzt(q, 'ChipLeiste'), 'NichtImBriefing verwendet <ChipLeiste> nicht');
	});
	test('SSR: je nicht ausgewählter Metrik ein Btn-Chip mit erhaltener Testid und Katalogtext', async () => {
		const N = await lade('NichtImBriefing');
		const h = html(N, { metriken: METRIKEN, hinzugefuegt: null, onHinzufuegen: noop });
		const chips = [...h.matchAll(/<button\b[^>]*data-slot="btn"[^>]*>([\s\S]*?)<\/button>/g)];
		assert.equal(chips.length, METRIKEN.length, `TDD RED: erwartet ${METRIKEN.length} Btn-Chips, gefunden ${chips.length}`);
		METRIKEN.forEach((m, i) => {
			assert.match(chips[i][0], new RegExp(`data-testid="wetter-nicht-im-briefing-plus-${m.id}"`));
			assert.equal(text(chips[i][1]), WETTER['wetter.nicht_im_briefing.hinzufuegen'].replace('{metrik}', m.name));
		});
		assert.match(h, /data-slot="chip-leiste"/, 'TDD RED: kein ChipLeiste-Markup');
	});
});

// ─── K-6/K-7: MetrikZeile und GrenzenEditor ──────────────────────────────────

const EIG = {
	id: 'wind',
	group: 'wind',
	alertable: true,
	is_precursor: false,
	allowed_sides: 'upper',
	display_only: false,
	unit: 'km/h'
};
const EINTRAG = { alarm_ab: 'orange', upper: { yellow: 30, orange: 50, red: 70 } };
const zeileProps = (offen = false) => ({
	id: 'wind',
	name: 'Wind',
	eig: EIG,
	eintrag: EINTRAG,
	thunder: undefined,
	offen,
	abweichend: false,
	vorlageLabel: 'Standard',
	fehler: [],
	onEntfernen: noop,
	onAlarmAb: noop,
	onGrenzen: noop,
	onWert: noop,
	onGewitter: noop
});
function radios(h: string): { tag: string; inhalt: string }[] {
	return [...h.matchAll(/(<button\b[^>]*\srole="radio"[^>]*>)([\s\S]*?)<\/button>/g)].map((m) => ({ tag: m[1], inhalt: m[2] }));
}
function tagMitTestid(h: string, testid: string): string | null {
	return h.match(new RegExp(`<[a-z]+\\b[^>]*data-testid="${testid}"[^>]*>`))?.[0] ?? null;
}

describe('K-6/K-7: MetrikZeile — Alarm-ab-Stufen mit Farbpunkt, Knöpfe als Btn', () => {
	const STUFEN = ['never', 'yellow', 'orange', 'red'];
	test('SSR: vier Stufen role=radio, aria-checked nur an der gewählten, Testids erhalten (Erhalt)', async () => {
		const Z = await lade('MetrikZeile');
		const r = radios(html(Z, zeileProps()));
		assert.equal(r.length, 4);
		STUFEN.forEach((s, i) => {
			assert.match(r[i].tag, new RegExp(`data-testid="wetter-alarm-ab-wind-${s}"`));
			assert.match(r[i].tag, new RegExp(`aria-checked="${s === 'orange'}"`));
		});
	});
	test('SSR: Farbstufen tragen einen Farbpunkt data-farbe, „never“ keinen', async () => {
		const Z = await lade('MetrikZeile');
		const r = radios(html(Z, zeileProps()));
		assert.equal(r.length, 4);
		assert.doesNotMatch(r[0].inhalt, /data-farbe/, '„never“ darf keinen Farbpunkt haben');
		for (let i = 1; i < 4; i++) {
			assert.match(r[i].inhalt, new RegExp(`data-farbe="${STUFEN[i]}"`), `TDD RED: Stufe ${STUFEN[i]} ohne Farbpunkt`);
		}
	});
	test('SSR: Entfernen und Grenzen-ändern sind Btn (data-slot="btn"), Testids erhalten', async () => {
		const Z = await lade('MetrikZeile');
		const h = html(Z, zeileProps());
		for (const id of ['wetter-zeile-entfernen-wind', 'wetter-grenzen-aendern-wind']) {
			const tag = tagMitTestid(h, id);
			assert.ok(tag, `Testid ${id} fehlt`);
			assert.match(tag!, /data-slot="btn"/, `TDD RED: ${id} ist kein Btn`);
		}
		assert.match(tagMitTestid(h, 'wetter-grenzen-aendern-wind')!, /aria-expanded="false"/);
		assert.match(h, /data-testid="wetter-zeile-wind"/);
	});
});

describe('K-6: GrenzenEditor — Eingaben als Input mit Ampel-Unterkante', () => {
	test('SSR: je Feld das Atom Input (data-slot="input") mit data-ampel der Feldfarbe, Testid erhalten', async () => {
		const G = await lade('GrenzenEditor');
		const h = html(G, {
			id: 'wind',
			erlaubt: 'upper',
			eintrag: EINTRAG,
			gewitter: null,
			abweichend: false,
			vorlageLabel: 'Standard',
			fehler: [],
			onWert: noop,
			onGewitter: noop
		});
		for (const f of ['yellow', 'orange', 'red']) {
			const tag = tagMitTestid(h, `wetter-grenze-wind-upper-${f}`);
			assert.ok(tag, `Feld wetter-grenze-wind-upper-${f} fehlt`);
			assert.match(tag!, /^<input\b/);
			assert.match(tag!, /data-slot="input"/, `TDD RED: Feld ${f} ist nicht das Atom Input`);
			assert.match(tag!, new RegExp(`data-ampel="${f}"`), `TDD RED: Feld ${f} ohne data-ampel="${f}"`);
		}
	});
});

// TDD RED — Issue #2913, Fix „Metrik-Liste nach Mockup“ (PO-Befund 12.11.2026).
// Spec: docs/specs/modules/fix_2913_metrikliste_mockup.md — AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-11.
// Soll: docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html (Fassung 3).
//
// Vertrag (hier festgelegt, /50 baut danach):
//   ampelModell.ts
//     HINWEIS_IDS: readonly string[]          Metriken mit eigenem Hinweis (Katalog wetter.hinweis.<id>)
//     hinweisSchluessel(id, eig) -> string|null
//         display_only  -> 'wetter.untertitel.nur_anzeige'   („nur Anzeige, keine Ampel“)
//         is_precursor  -> 'wetter.untertitel.vorbote'       („Vorbote, kein Alarm“)
//         id in HINWEIS_IDS -> `wetter.hinweis.${id}`
//         sonst null
//     untertitel(id, eig, uebersetze: (schluessel) => string) -> string
//         [eig.unit, Hinweistext].filter(Boolean).join(' · ')  — nie ein endender/führender Trennpunkt
//   MetrikZeile.svelte
//     <small> unter dem Namen zeigt untertitel(); „grün: …“-Span (wetter-gruen-<id>) enthält den Trennpunkt
//     selbst („· grün: …“, Mockup Z. 115/116, `.gr`); Entfernen und „Grenzen ändern“ sind Btn tap mit
//     data-tap="true" (sichtbar klein, Trefferfläche 44 px über das vorhandene ::before-Muster);
//     „Alarm ab“ ist <Segmented variant="kompakt"> (Ausgabe data-variant="kompakt").
//   Segmented.svelte   neues Prop `variant?: 'kompakt'` -> data-variant am Container; ohne Prop KEIN Attribut.
//   app.css            Variante nur unter [data-slot="segmented"][data-variant="kompakt"]; Standardregeln
//                      (aktives Segment var(--g-ink) auf var(--g-paper)) bleiben unverändert.
//
// Verhalten per Server-Render (svelte/server) bzw. reine Funktion mit echten /api/metrics-Daten und echtem
// Katalog. Layout ist CSS und im Server-Render nicht messbar; die Stil-Regeln werden gegen die echten
// CSS-Quellen geprüft (Token auf ihren Hell-Wert aufgelöst), die Messung im Browser folgt in /e2e-verify:
// doc-compliance-test
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/fix2913_metrikliste_mockup.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { live, ampelModell } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import { entzerreMarken, leisteVon } from '../../shared/wetter-tab/ampelLeiste.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> organisms -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const WT = path.resolve(HERE, '..', 'wetter-tab');
const MSG = path.join(FRONTEND, 'src', 'lib', 'i18n', 'messages');
const APP_CSS = readFileSync(path.join(FRONTEND, 'src', 'app.css'), 'utf8');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

const KAT = (sprache: 'de' | 'en'): Record<string, string> => JSON.parse(readFileSync(path.join(MSG, sprache, 'wetter.json'), 'utf8'));
const DE = KAT('de');
const EN = KAT('en');
const uebersetzer = (kat: Record<string, string>) => (k: string) => {
	assert.ok(k in kat, `Katalogschlüssel ${k} fehlt`);
	return kat[k];
};

const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
const text = (h: string) => h.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
const tagMitTestid = (h: string, id: string) => h.match(new RegExp(`<[a-z]+\\b[^>]*data-testid="${id}"[^>]*>`))?.[0] ?? null;
function elementMitTestid(h: string, id: string): string | null {
	const m = h.match(new RegExp(`<([a-z]+)\\b[^>]*data-testid="${id}"[^>]*>`));
	if (!m) return null;
	const tag = m[1];
	const start = m.index!;
	let tiefe = 0;
	const re = new RegExp(`<(/?)${tag}\\b[^>]*>`, 'g');
	re.lastIndex = start;
	for (let x; (x = re.exec(h)); ) {
		tiefe += x[1] ? -1 : 1;
		if (tiefe === 0) return h.slice(start, x.index + x[0].length);
	}
	return null;
}
const noop = () => {};
const ladeSvelte = async (datei: string): Promise<any> => (await import(pathToFileURL(datei).href)).default;

// ── CSS-Werkzeug: Token auf Hell-Wert auflösen, Regeln finden ────────────────

/** Erste Definition je Token in app.css = Hell-Theme (:root vor dem Dark-Block). */
const TOKENS: Record<string, string> = {};
for (const m of APP_CSS.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/gi)) if (!(m[1] in TOKENS)) TOKENS[m[1]] = m[2].replace(/\/\*.*?\*\//g, '').trim();
function aufloesen(wert: string, tiefe = 0): string {
	assert.ok(tiefe < 10, `Token-Zyklus in ${wert}`);
	const neu = wert.replace(/var\(\s*(--[a-z0-9-]+)\s*(?:,\s*([^)]+))?\)/gi, (_, name: string, ersatz?: string) => {
		if (name in TOKENS) return TOKENS[name];
		assert.ok(ersatz, `Token ${name} ist in app.css nicht definiert`);
		return ersatz!;
	});
	return neu === wert ? wert.replace(/\s+/g, ' ').replace(/\(\s*/g, '(').replace(/\s*\)/g, ')').replace(/\s*,\s*/g, ', ').trim().toLowerCase() : aufloesen(neu, tiefe + 1);
}
const stilVon = (datei: string) => readFileSync(datei, 'utf8').match(/<style[^>]*>([\s\S]*?)<\/style>/)?.[1] ?? '';
const ohneKommentare = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, '');

type Block = { kopf: string; inhalt: string };
/** Alle Blöcke (Regeln und At-Regeln) einer Ebene. */
function bloecke(css: string): Block[] {
	const aus: Block[] = [];
	let i = 0;
	let kopfStart = 0;
	while (i < css.length) {
		if (css[i] === '{') {
			let tiefe = 1;
			let j = i + 1;
			for (; j < css.length && tiefe > 0; j++) tiefe += css[j] === '{' ? 1 : css[j] === '}' ? -1 : 0;
			aus.push({ kopf: css.slice(kopfStart, i).replace(/[\s\S]*[;}]/, '').trim(), inhalt: css.slice(i + 1, j - 1) });
			i = j;
			kopfStart = j;
		} else if (css[i] === ';' || css[i] === '}') {
			i++;
			kopfStart = i;
		} else i++;
	}
	return aus;
}
const normSel = (s: string) => s.replace(/\s+/g, ' ').replace(/'/g, '"').trim();
/** Deklarationen der Regeln mit genau diesem Selektor (in der Selektorliste) auf oberster Ebene
 *  (Kaskaden-Ebenen `@layer` zählen als oberste Ebene, `@media`/`@container` nicht). */
function regel(css: string, selektor: string, aus: Record<string, string> = {}): Record<string, string> {
	for (const b of bloecke(ohneKommentare(css))) {
		if (b.kopf.startsWith('@layer')) {
			regel(b.inhalt, selektor, aus);
			continue;
		}
		if (b.kopf.startsWith('@')) continue;
		if (!b.kopf.split(',').map(normSel).includes(normSel(selektor))) continue;
		for (const d of b.inhalt.split(';')) {
			const k = d.indexOf(':');
			if (k > 0) aus[d.slice(0, k).trim()] = d.slice(k + 1).trim();
		}
	}
	return aus;
}
const atRegeln = (css: string, re: RegExp) => bloecke(ohneKommentare(css)).filter((b) => re.test(b.kopf));

// ── Daten: echte Metrik-Eigenschaften aus /api/metrics ───────────────────────

const M = await ampelModell();
const EIG: Record<string, any> = M.eigenschaftenAusKatalog(live().metrics);

// ─── AC-5: Untertitel `Einheit · Hinweis` aus dem Katalog ────────────────────

describe('AC-5: Untertitel `Einheit · Hinweis` aus dem Katalog DE/EN', () => {
	const SOLL_DE: [string, string][] = [
		['temperature', '°C · Tageshöchst · Tagestief'],
		['wind', 'km/h · Mittelwind'],
		['gust', 'km/h · Spitze'],
		['precipitation', 'mm · Summe'],
		['rain_probability', '% · Vorbote, kein Alarm'],
		// Einheit aus /api/metrics (km); km→m ist Nicht-Ziel dieser Scheibe (AC-13, #2946).
		['visibility', 'km · Minimum'],
		['freezing_level', 'm · m über höchster Stelle'],
		['thunder', 'Stufe'],
		['uv_index', 'Maximum']
	];
	for (const [id, soll] of SOLL_DE) {
		test(`DE ${id} -> „${soll}“ (Mockup Z. 280 ff.)`, () => {
			assert.equal(typeof M.untertitel, 'function', 'TDD RED: untertitel() fehlt in ampelModell.ts');
			assert.ok(EIG[id], `Metrik ${id} nicht in /api/metrics`);
			assert.equal(M.untertitel(id, EIG[id], uebersetzer(DE)), soll);
		});
	}

	test('Vorbote kommt aus is_precursor, nicht aus einem Eintrag je Metrik', () => {
		assert.equal(typeof M.hinweisSchluessel, 'function', 'TDD RED: hinweisSchluessel() fehlt');
		const vorboten = Object.values(EIG).filter((e: any) => e.is_precursor && !e.display_only);
		assert.ok(vorboten.length > 0, 'keine Vorbote-Metrik in /api/metrics');
		for (const e of vorboten) assert.equal(M.hinweisSchluessel(e.id, e), 'wetter.untertitel.vorbote', e.id);
		// Gegenprobe: dieselbe Metrik ohne Vorbote-Eigenschaft zeigt keinen Vorbote-Hinweis.
		const e = vorboten[0];
		assert.notEqual(M.hinweisSchluessel(e.id, { ...e, is_precursor: false }), 'wetter.untertitel.vorbote');
	});

	test('display_only zeigt „nur Anzeige, keine Ampel“ und hat Vorrang', () => {
		const e = { ...EIG.temperature, display_only: true, is_precursor: true };
		assert.equal(M.hinweisSchluessel('temperature', e), 'wetter.untertitel.nur_anzeige');
		assert.equal(M.untertitel('temperature', e, uebersetzer(DE)), '°C · nur Anzeige, keine Ampel');
	});

	test('Metrik ohne Hinweis: nur die Einheit, kein endender Trennpunkt', () => {
		const ohne = Object.values(EIG).find((e: any) => !e.is_precursor && !e.display_only && e.unit && !M.HINWEIS_IDS?.includes(e.id));
		assert.ok(ohne, 'keine Metrik ohne Hinweis gefunden (oder HINWEIS_IDS fehlt)');
		assert.equal(M.hinweisSchluessel(ohne.id, ohne), null);
		assert.equal(M.untertitel(ohne.id, ohne, uebersetzer(DE)), ohne.unit);
		assert.equal(M.untertitel('frei', { ...ohne, id: 'frei', unit: '' }, uebersetzer(DE)), '');
	});

	test('EN: Untertitel aus dem EN-Katalog, gleiche Einheit, anderer Text als DE', () => {
		const en = M.untertitel('temperature', EIG.temperature, uebersetzer(EN));
		assert.match(en, /^°C · \S/);
		assert.notEqual(en, '°C · Tageshöchst · Tagestief');
		assert.match(M.untertitel('rain_probability', EIG.rain_probability, uebersetzer(EN)), /^% · \S/);
	});

	test('HINWEIS_IDS deckt die Mockup-Hinweise ab', () => {
		for (const id of ['temperature', 'temperature_night', 'wind', 'gust', 'precipitation', 'thunder', 'visibility', 'cloud_low', 'uv_index', 'freezing_level', 'snowfall_limit', 'sunshine']) {
			assert.ok(M.HINWEIS_IDS?.includes(id), `TDD RED: ${id} fehlt in HINWEIS_IDS`);
		}
	});
});

describe('AC-5: Katalogvollständigkeit DE/EN', () => {
	test('jeder Hinweis- und abgeleitete Schlüssel existiert in DE und EN, nicht leer', () => {
		const schluessel = [...(M.HINWEIS_IDS ?? []).map((id: string) => `wetter.hinweis.${id}`), 'wetter.untertitel.vorbote', 'wetter.untertitel.nur_anzeige'];
		assert.ok(schluessel.length >= 14, 'TDD RED: HINWEIS_IDS fehlt oder ist zu kurz');
		for (const k of schluessel) {
			for (const [sprache, kat] of [['de', DE], ['en', EN]] as const) {
				assert.ok(typeof kat[k] === 'string' && kat[k].trim() !== '', `${sprache}: ${k} fehlt oder leer`);
			}
		}
		assert.equal(DE['wetter.untertitel.vorbote'], 'Vorbote, kein Alarm');
		assert.equal(DE['wetter.untertitel.nur_anzeige'], 'nur Anzeige, keine Ampel');
		assert.equal(DE['wetter.hinweis.snowfall_limit'], 'm über höchster Stelle');
		assert.equal(DE['wetter.hinweis.sunshine'], 'zu wenig ist schlecht');
	});
});

// ─── MetrikZeile im Server-Render: Untertitel, grün, Varianten ───────────────

const zeileProps = (id: string, eintrag: Record<string, unknown>) => ({
	id,
	name: id,
	eig: EIG[id],
	eintrag,
	thunder: undefined,
	offen: false,
	abweichend: false,
	vorlageLabel: 'Standard',
	fehler: [],
	onEntfernen: noop,
	onAlarmAb: noop,
	onGrenzen: noop,
	onWert: noop,
	onGewitter: noop
});
const TEMP = { enabled: true, alarm_ab: 'orange', lower: { red: -10, orange: -3, yellow: 2 }, upper: { yellow: 27, orange: 30, red: 33 } };

describe('MetrikZeile (Server-Render): Untertitel, „grün“, kompakte Bedienelemente', () => {
	test('AC-5: <small> unter dem Namen zeigt „°C · Tageshöchst · Tagestief“', async () => {
		const Z = await ladeSvelte(path.join(WT, 'MetrikZeile.svelte'));
		const h = html(Z, zeileProps('temperature', TEMP));
		const small = h.match(/<small\b[^>]*>([\s\S]*?)<\/small>/);
		assert.ok(small, '<small> fehlt');
		assert.equal(text(small![1]), '°C · Tageshöchst · Tagestief');
	});

	test('AC-6: Trennpunkt liegt in der „grün“-Span (Mockup `.gr`)', async () => {
		const Z = await ladeSvelte(path.join(WT, 'MetrikZeile.svelte'));
		const h = html(Z, zeileProps('temperature', TEMP));
		const gruen = elementMitTestid(h, 'wetter-gruen-temperature');
		assert.ok(gruen, 'grün-Span fehlt');
		assert.match(text(gruen!), /^· \S/, 'TDD RED: Trennpunkt steht vor der Span statt darin');
	});

	test('AC-7: „Alarm ab“ ist Segmented in der Variante kompakt', async () => {
		const Z = await ladeSvelte(path.join(WT, 'MetrikZeile.svelte'));
		const h = html(Z, zeileProps('temperature', TEMP));
		const seg = tagMitTestid(h, 'wetter-alarm-ab-temperature');
		assert.ok(seg, 'Segmented fehlt');
		assert.match(seg!, /\sdata-slot="segmented"/);
		assert.match(seg!, /\sdata-variant="kompakt"/, 'TDD RED: Segmented ohne data-variant="kompakt"');
	});

	test('AC-8: Entfernen und „Grenzen ändern“ sind Btn tap mit data-tap="true"', async () => {
		const Z = await ladeSvelte(path.join(WT, 'MetrikZeile.svelte'));
		const h = html(Z, zeileProps('temperature', TEMP));
		for (const id of ['wetter-zeile-entfernen-temperature', 'wetter-grenzen-aendern-temperature']) {
			const tag = tagMitTestid(h, id);
			assert.ok(tag, `${id} fehlt`);
			assert.match(tag!, /\sdata-size="tap"/, `${id} ohne data-size="tap"`);
			assert.match(tag!, /\sdata-tap="true"/, `TDD RED: ${id} ohne data-tap="true" (sichtbar 44 px statt ca. 29 px)`);
		}
	});
});

// ─── AC-7: Segmented-Variante, Standard bleibt unverändert ───────────────────

describe('AC-7: Segmented-Atom — Variante kompakt ohne Durchsickern', () => {
	const SEG = path.join(FRONTEND, 'src', 'lib', 'components', 'ui', 'segmented', 'Segmented.svelte');
	const OPT = [
		{ value: 'a', label: 'A' },
		{ value: 'b', label: 'B' }
	];
	test('variant="kompakt" -> data-variant am Container; ohne Prop kein Attribut', async () => {
		const S = await ladeSvelte(SEG);
		const mit = html(S, { options: OPT, value: 'a', variant: 'kompakt', testid: 'x' });
		const ohne = html(S, { options: OPT, value: 'a', testid: 'x' });
		assert.match(tagMitTestid(mit, 'x')!, /\sdata-variant="kompakt"/, 'TDD RED: Prop variant wird nicht ausgegeben');
		assert.doesNotMatch(tagMitTestid(ohne, 'x')!, /data-variant=/);
	});

	test('app.css: Hülle card-alt, Rahmen rule-soft, aktives Segment paper/accent-deep — nur unter dem Varianten-Selektor', () => {
		const huelle = regel(APP_CSS, '[data-slot="segmented"][data-variant="kompakt"]');
		assert.ok(Object.keys(huelle).length > 0, 'TDD RED: keine Regel [data-slot="segmented"][data-variant="kompakt"]');
		assert.equal(aufloesen(huelle['background'] ?? huelle['background-color'] ?? ''), TOKENS['--g-card-alt'].toLowerCase());
		assert.match(aufloesen(huelle['border'] ?? ''), new RegExp(TOKENS['--g-rule-soft'].toLowerCase()));
		const aktiv = regel(APP_CSS, '[data-slot="segmented"][data-variant="kompakt"] [data-slot="segmented-item"][data-active="true"]');
		assert.equal(aufloesen(aktiv['background'] ?? aktiv['background-color'] ?? ''), TOKENS['--g-paper'].toLowerCase(), 'aktives Segment nicht hell');
		assert.equal(aufloesen(aktiv['color'] ?? ''), TOKENS['--g-accent-deep'].toLowerCase());
		assert.ok(aktiv['box-shadow'] || aktiv['outline'] || aktiv['border'], 'aktives Segment ohne Ring');
		// Trefferfläche ≥ 44 px über ::before wie beim data-tap-Muster
		const vor = regel(APP_CSS, '[data-slot="segmented"][data-variant="kompakt"] [data-slot="segmented-item"]::before');
		assert.match(aufloesen(vor['width'] ?? ''), /44px/, 'Trefferfläche der Segmente < 44 px');
		assert.match(aufloesen(vor['height'] ?? ''), /44px/, 'Trefferfläche der Segmente < 44 px');
	});

	test('Standard-Segmented bleibt: aktives Segment dunkel gefüllt (CompareTabs, VersandTab …)', () => {
		const std = regel(APP_CSS, '[data-slot="segmented-item"][data-active="true"]');
		assert.equal(std['background'], 'var(--g-ink)');
		assert.equal(std['color'], 'var(--g-paper)');
		assert.equal(regel(APP_CSS, '[data-slot="segmented"]')['border'], '1px solid var(--g-ink-faint)');
	});

	test('MetrikZeile überschreibt die Segmente nicht mehr auf 44 px Mindesthöhe/schwarze Füllung', () => {
		const css = stilVon(path.join(WT, 'MetrikZeile.svelte'));
		assert.doesNotMatch(ohneKommentare(css), /segmented-item[^{]*\{[^}]*min-height/, 'TDD RED: Segment-Mindesthöhe 44 px noch in MetrikZeile');
	});
});

// ─── AC-1/AC-2/AC-4/AC-6: Zeilenraster, Container-Query, Typografie ──────────

describe('AC-1/2/4/6: Stil der Metrik-Zeile gegen das Mockup', () => {
	const css = stilVon(path.join(WT, 'MetrikZeile.svelte'));

	test('AC-1: Raster 32px minmax(130px, 190px) minmax(160px, 1fr) auto, Spaltenabstand 18 px', () => {
		const z = regel(css, '.wt-zeile');
		assert.equal(aufloesen(z['grid-template-columns'] ?? ''), '32px minmax(130px, 190px) minmax(160px, 1fr) auto');
		const gap = aufloesen(z['column-gap'] ?? (z['gap'] ?? '').split(' ').pop() ?? '');
		assert.equal(gap, '18px', 'Spaltenabstand nicht 18 px');
	});

	test('AC-2: Umbruch per Container-Query ≤ 700 px, keine Viewport-Media-Query', () => {
		assert.equal(atRegeln(css, /^@media\b[^{]*max-width/).length, 0, 'TDD RED: Umbruch hängt noch an der Viewportbreite');
		const cq = atRegeln(css, /^@container\b[^{]*(max-width:\s*700px|width\s*<=\s*700px)/);
		assert.equal(cq.length, 1, 'TDD RED: keine @container-Regel bei 700 px');
		const mobil = regel(cq[0].inhalt, '.wt-zeile');
		assert.match(aufloesen(mobil['grid-template-columns'] ?? ''), /^40px (1fr|minmax\(0(px)?, 1fr\))$/, 'Handy-Raster nicht 40px 1fr');
	});

	test('AC-4: Erklärung 12 px', () => {
		assert.equal(aufloesen(regel(css, '.wt-why')['font-size'] ?? ''), '12px');
	});

	// Fix-Runde 1 (F001): Text-Token --g-ok-fg statt Grafik-Token --g-ampel-gruen (dunkel nur 3,37:1 < 4,5:1);
	// Kontrast beider Modi sichert ampel_tokens_kontrast.test.ts.
	test('AC-6: „grün“ im grünen Text-Token --g-ok-fg (hell #166534), Gewicht 600', () => {
		const g = regel(css, '.wt-gruen');
		assert.equal(g['color'], 'var(--g-ok-fg)', 'TDD RED: „grün“ nicht im grünen Text-Token');
		assert.equal(aufloesen(g['color'] ?? ''), TOKENS['--g-ok-fg'].toLowerCase());
		assert.equal(g['font-weight'], '600');
	});
});

describe('AC-2/AC-3: Karte ist Container, kein doppeltes Innen-Padding', () => {
	const css = stilVon(path.join(WT, 'WetterTabInhalt.svelte'));
	const waagrecht = (p: string | undefined): string[] => {
		if (!p) return ['0px', '0px'];
		const t = aufloesen(p).split(' ');
		const r = t[1] ?? t[0];
		const l = t[3] ?? r;
		return [r, l];
	};
	test('AC-2: Metrik-Karte hat container-type: inline-size', () => {
		assert.equal(regel(css, '.wt-metriken')['container-type'], 'inline-size', 'TDD RED: Karte ist kein Container');
	});
	test('AC-3: .wt hat kein seitliches Innen-Padding (Desktop und mobil)', () => {
		for (const [r, l] of [waagrecht(regel(css, '.wt')['padding']), ...atRegeln(css, /^@media/).map((b) => waagrecht(regel(b.inhalt, '.wt')['padding']))]) {
			assert.ok(/^0(px)?$/.test(r) && /^0(px)?$/.test(l), `TDD RED: seitliches Padding ${r}/${l} zusätzlich zu main`);
		}
	});
});

// ─── AC-9: Ampel-Leiste ─────────────────────────────────────────────────────

describe('AC-9: Ampel-Leiste nach Mockup (.ticks/.band)', () => {
	const css = stilVon(path.join(WT, 'AmpelLeiste.svelte'));
	test('Grenzzahlen: 14 px Zeilenhöhe, 10,5 px, ink-3; Abstand 3 px', () => {
		const m = regel(css, '.wt-marken');
		assert.equal(aufloesen(m['height'] ?? ''), '14px');
		assert.equal(aufloesen(m['font-size'] ?? ''), '10.5px');
		assert.equal(aufloesen(m['color'] ?? ''), TOKENS['--g-ink-3'].toLowerCase());
		assert.equal(aufloesen(regel(css, '.wt-leiste')['gap'] ?? ''), '3px');
	});
	test('Leiste ohne Rahmen und ohne Fugen', () => {
		const b = regel(css, '.wt-band');
		assert.ok(!b['border'] || /^(none|0(px)?)$/.test(b['border']), `TDD RED: Leiste hat Rahmen ${b['border']}`);
		assert.equal(Object.keys(regel(css, '.wt-band span + span')).length, 0, 'TDD RED: Fugen zwischen den Zonen');
	});
});

// ─── Fix-Loop nach Staging-Messung (AC-4, AC-8, AC-9) ───────────────────────

describe('AC-9: Grenzzahlen überlappen sich auch bei 160 px Mittelspalte nicht (entzerreMarken)', () => {
	// Echte Vorlage „Alpen-Trekking“, Temperatur: 27/30/33 °C liegen bei 160 px nur 7 px auseinander.
	const temp = leisteVon({ lower: { red: -10, orange: -3, yellow: 2 }, upper: { yellow: 27, orange: 30, red: 33 } } as never);
	const pos = temp.marken.map((m) => m.pos);
	const breiten = temp.marken.map((m) => String(m.wert).length * 6); // Mono 10,5 px ≈ 6 px je Zeichen (gemessen)
	const kanten = (lagen: number[]) => lagen.map((x, i) => [x - breiten[i] / 2, x + breiten[i] / 2]);

	test('160 px: keine Überlappung (≥ 3 px Luft), keine Zahl über den Rand', () => {
		const k = kanten(entzerreMarken(pos, breiten, 160, 3));
		for (let i = 1; i < k.length; i++) assert.ok(k[i][0] - k[i - 1][1] >= 3 - 1e-6, `Zahl ${i} überlappt: ${JSON.stringify(k)}`);
		assert.ok(k[0][0] >= 0 && k[k.length - 1][1] <= 160, `ragt über den Rand: ${JSON.stringify(k)}`);
	});

	test('genug Platz: jede Zahl bleibt genau über ihrer Grenze (Mockup-Bild)', () => {
		const lagen = entzerreMarken(pos, breiten, 400, 3);
		lagen.forEach((x, i) => assert.ok(Math.abs(x - (pos[i] / 100) * 400) < 1e-9, `Zahl ${i} verschoben: ${x}`));
	});

	test('Gruppe wird um den Mittelwert ihrer Soll-Lagen auseinandergezogen, nicht einseitig verschoben', () => {
		const lagen = entzerreMarken([50, 50, 50], [12, 12, 12], 200, 3);
		assert.deepEqual(lagen, [85, 100, 115]);
	});
});

describe('AC-4/AC-8: Zeilenhöhe und Trefferflächen der Aktionsspalte (Messung Staging 12.11.)', () => {
	const css = stilVon(path.join(WT, 'MetrikZeile.svelte'));
	test('AC-8: Zeilenabstand der umbrechenden Aktionsspalte trennt die 44-px-Trefferflächen von Segment (29 px) und Knopf (28 px)', () => {
		const zeilenabstand = parseFloat(aufloesen(regel(css, '.wt-act')['gap'] ?? '').split(' ')[0]);
		assert.ok(zeilenabstand >= 44 - (29 + 28) / 2, `Zeilenabstand ${zeilenabstand} px: Trefferflächen überdecken sich`);
	});
	test('AC-4: 4 Zeilen Erklärung passen bei 1280 in 124 px (12 + 27 Leiste + 4 + 4 Zeilen + 12)', () => {
		const lh = parseFloat(regel(css, '.wt-why')['line-height'] ?? '');
		assert.ok(12 + 27 + 4 + 4 * 12 * lh + 12 <= 124, `Zeilenhöhe ${lh}: Zeile Temperatur > 124 px`);
	});
});

// ─── Staging-Abnahme Runde 2 (nach PR #2956): Befunde 1 und 2 ───────────────

describe('Befund 1: Gewitter-Leiste beschriftet „keins · mittel · hoch“ (Mockup Z. 344)', () => {
	const stufen = (h: string) => {
		const block = h.match(/<div class="wt-marken wt-marken--stufen[^"]*"[^>]*>([\s\S]*?)<\/div>/);
		assert.ok(block, 'Stufen-Beschriftung fehlt');
		return Array.from(block![1].matchAll(/<span\b[^>]*>([\s\S]*?)<\/span>/g)).map((m) => text(m[1]));
	};
	test('DE: über den drei Zonen stehen „keins“, „mittel“, „hoch“ — keine leere erste Zone', async () => {
		const L = await ladeSvelte(path.join(WT, 'AmpelLeiste.svelte'));
		const h = html(L, { id: 'thunder', eintrag: undefined, gewitter: { mittel: 'yellow', hoch: 'orange' } });
		assert.deepEqual(stufen(h), ['keins', 'mittel', 'hoch']);
	});
	test('Katalog: wetter.gewitter.keins in DE „keins“, in EN eigener Text', () => {
		assert.equal(DE['wetter.gewitter.keins'], 'keins');
		assert.ok(typeof EN['wetter.gewitter.keins'] === 'string' && EN['wetter.gewitter.keins'].trim() !== '' && EN['wetter.gewitter.keins'] !== 'keins', 'EN: wetter.gewitter.keins fehlt');
	});
});

describe('Befund 2: Karte 701–960 px (Viewport 1024/1100 mit Seitenleiste) — Aktionsspalte einzeilig', () => {
	// Kartenbreite = Viewport − 220 Seitenleiste − 2·24 Innenabstand von main (AC-3). Das Mockup-Raster braucht
	// für eine einzeilige Aktionsspalte (≈ 418 px: „Alarm ab“ 46 + Segmente 243 + Knopf 109 + 2·10) mindestens
	// 32 + 130 + 160 + 418 + 3·18 + 2·20 ≈ 834 px; bei 756 px bricht sie dreizeilig um, die Mitte fällt auf 160 px.
	const KARTE = { 390: 358, 1024: 756, 1100: 832, 1280: 1012, 1440: 1172 } as const;
	const css = stilVon(path.join(WT, 'MetrikZeile.svelte'));
	/** Wirksame Deklarationen eines Selektors bei Kartenbreite `w` (Quellreihenfolge, @container max-width). */
	function wirksam(selektor: string, w: number): Record<string, string> {
		const aus: Record<string, string> = {};
		for (const b of bloecke(ohneKommentare(css))) {
			if (!b.kopf.startsWith('@')) {
				if (b.kopf.split(',').map(normSel).includes(selektor)) Object.assign(aus, regel(`${b.kopf}{${b.inhalt}}`, selektor));
				continue;
			}
			const max = b.kopf.match(/^@container\b[^{]*max-width:\s*(\d+)px/);
			if (max && w <= Number(max[1])) Object.assign(aus, regel(b.inhalt, selektor));
		}
		return aus;
	}
	for (const vp of [1024, 1100] as const) {
		test(`${vp} px (Karte ${KARTE[vp]}): Raster bleibt, Mitte und Aktionen teilen sich Spalte 3 bis Ende, Aktionen einzeilig`, () => {
			assert.equal(aufloesen(wirksam('.wt-zeile', KARTE[vp])['grid-template-columns'] ?? ''), '32px minmax(130px, 190px) minmax(160px, 1fr) auto', 'AC-1: Raster verändert');
			assert.equal(wirksam('.wt-mitte', KARTE[vp])['grid-column'], '3 / -1', 'Mittelspalte nutzt die Breite der Aktionsspalte nicht');
			const akt = wirksam('.wt-act', KARTE[vp]);
			assert.equal(akt['grid-column'], '3 / -1', 'Aktionsspalte steht weiter rechts neben einer 160-px-Mitte');
			assert.equal(akt['flex-wrap'], 'nowrap', 'Aktionsspalte darf in dieser Breite nicht umbrechen');
			assert.equal(akt['justify-content'], 'flex-start');
		});
	}
	for (const vp of [1280, 1440] as const) {
		test(`${vp} px (Karte ${KARTE[vp]}): Mockup-Raster, Aktionsspalte rechts in Spalte 4`, () => {
			assert.equal(wirksam('.wt-mitte', KARTE[vp])['grid-column'], undefined);
			assert.equal(wirksam('.wt-act', KARTE[vp])['grid-column'], undefined);
		});
	}
	test('390 px: Handy-Layout bleibt (Mitte und Aktionen über die volle Breite)', () => {
		assert.equal(wirksam('.wt-mitte', KARTE[390])['grid-column'], '1 / -1');
		assert.equal(wirksam('.wt-act', KARTE[390])['grid-column'], '1 / -1');
		assert.equal(wirksam('.wt-act', KARTE[390])['flex-wrap'], 'wrap', 'Handy: Aktionen müssen umbrechen dürfen');
		assert.equal(aufloesen(wirksam('.wt-zeile', KARTE[390])['grid-template-columns'] ?? ''), '40px 1fr');
	});
});

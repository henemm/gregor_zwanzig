// Issue #2657 (i18n F8, Epic #2644) — AC-1, AC-2, AC-3, AC-4, AC-6: Layout-Reiter,
// Korridor-Editor (Wertebereiche, Desktop und mobil), Ausgabe-Layout, Ausblick,
// Mail-Inhalt und GPX-Seite sprechen die Sprache des angemeldeten Nutzers. Echte
// SSR-Renders (svelte/server, Pruefstand f8Pruefstand.ts):
//   * AC-6: Deutsch ist byte-gleich zur Ausgabe VOR der Umstellung
//     (tests/golden/f8_layout_korridor/*.de.html und funktionen.de.txt),
//   * AC-1: Layout-Reiter in Trip und Ortsvergleich englisch, Kanalnamen und
//     Kurzformen unveraendert,
//   * AC-2: Korridor-Editor in beiden Kontexten und Fassungen englisch, Einheiten,
//     Skalen und Standardgrenzen gleich,
//   * AC-3: ltCapNoteText / ltKanalAbwahlHinweisText je Sprache,
//   * AC-4: zwei Nutzer (en/de) durch den ECHTEN Layout-Loader (+layout.server.ts);
//     ersetzt ist nur die Netzgrenze (fetch je Sitzungs-Cookie).
// Jeder en-Fall rendert zuerst de und schaltet dann OHNE Neuladen auf en.
// Englische und deutsche Texte sind als feste Literale verankert (f8KatalogAnker.ts).
// Spec: docs/specs/modules/i18n_f8_layout_korridor_2657.md
//
//   cd frontend && npm test -- src/lib/components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts

import { test, describe, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import {
	FRONTEND,
	GOLDEN_DIR,
	CAP_FAELLE,
	COL_LABELS,
	ROUTE_KORRIDORE,
	ROUTE_EXTRA,
	VERGLEICH_DEFS,
	VERGLEICH_KORRIDORE,
	locale,
	trFor,
	lt,
	ce,
	CONTENT_MODULE_DESCRIPTIONS,
	layoutTabRendern,
	bausteineRendern,
	korridorRendern,
	routeZustand,
	vergleichZustand,
	htmlFaelle,
	funktionsTabelle,
	schreibeGolden
} from './f8Pruefstand.ts';
import { F8_ANKER } from './f8KatalogAnker.ts';

const base = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'src/routes/admin/__tests__/server-load-resolve.hooks.mjs')).href, base);
const layoutLoad = (await import(pathToFileURL(path.join(FRONTEND, 'src/routes/+layout.server.ts')).href)).load;

before(() => {
	// Die de-Golden sind der Ist-Stand VOR der Umstellung und werden nie neu geschrieben;
	// nur die en-Ansicht (Review-Hilfe, nicht verglichen) wird aktualisiert.
	if (process.env.GZ_GOLDEN_SCHREIBEN === 'en') schreibeGolden('en');
});
afterEach(() => locale.set('de'));

// Einzige Normalisierung: jede Leerraumfolge wird EIN Leerzeichen (mehrzeilige
// Fliesstexte standen vorher mit Zeilenumbruch+Tabs im Markup). Sonst byte-gleich.
const leerraum = (s: string) => s.replace(/\s+/g, ' ');
const sichtbar = (html: string) =>
	leerraum(html.replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<(?:"[^"]*"|'[^']*'|[^'">])*>/g, ' ').replace(/&amp;/g, '&')).trim();
const hat = (text: string, teil: string) => assert.ok(text.includes(teil), `fehlt: „${teil}"\nin: ${text.slice(0, 3000)}`);
const hatNicht = (text: string, teil: string) => assert.ok(!text.includes(teil), `steht noch: „${teil}"`);

/** Erst de rendern, dann OHNE Neuladen auf en schalten. */
function deDannEn<T>(f: () => T): { de: T; en: T } {
	locale.set('de');
	const de = f();
	locale.set('en');
	const en = f();
	return { de, en };
}

/**
 * Deutsche Festteile (>= 4 Buchstaben) der Paket-Schluessel, die im englischen Text
 * stehen. `layout.profil_metrik.*` rendert keine dieser Flaechen (Anlege-Assistent);
 * dieselben Woerter kommen als API-Metriknamen (F5) vor und zaehlen nicht.
 */
function deutscheReste(text: string, ausnahmen: string[] = []): string[] {
	const reste: string[] = [];
	for (const [k, de, en] of F8_ANKER) {
		if (de === en || k.startsWith('layout.profil_metrik.') || ausnahmen.some((a) => k === a || (a.endsWith('.') && k.startsWith(a)))) continue;
		const enTeile = new Set(en.split(/<[a-z0-9_]+>/).map((s) => s.trim()));
		for (const teil of de.split(/<[a-z0-9_]+>/).map((s) => s.trim())) {
			if ((teil.match(/[A-Za-zÄÖÜäöüß]/g) ?? []).length < 4 || enTeile.has(teil)) continue;
			if (text.includes(teil)) reste.push(`${k}: ${teil}`);
		}
	}
	return reste;
}
/** Fremdbausteine mit eigenem Deutsch (andere Pakete), deren Woerter Ankerteile treffen. */
const FREMD_REIHENFOLGE = ['layout.ausgabe.reihenfolge']; // WeatherV2Reihenfolge (F5) titelt selbst „Reihenfolge"
/** Der Fixture-Katalog des Layout-Reiters traegt API-Metriknamen (Böen, Niederschlag; F5),
 *  die zugleich Trip-Korridor-Zeilennamen sind — im Layout-Reiter keine Paket-Texte. */
const API_METRIKNAMEN = ['layout.korridor_zeile.']

describe('AC-6: Deutsch byte-gleich zum Ist-Stand vor der Umstellung (Golden golden-de)', () => {
	const FAELLE = htmlFaelle();
	for (const fall of Object.keys(FAELLE)) {
		test(`${fall}.de.html`, () => {
			const golden = readFileSync(path.join(GOLDEN_DIR, `${fall}.de.html`), 'utf-8');
			const { de } = deDannEn(() => FAELLE[fall]());
			locale.set('de');
			assert.equal(leerraum(FAELLE[fall]() + '\n'), leerraum(golden));
			assert.equal(leerraum(de + '\n'), leerraum(golden));
		});
	}
	test('funktionen.de.txt: Funktionsergebnisse unveraendert (byte-gleich, ohne Normalisierung)', () => {
		const golden = readFileSync(path.join(GOLDEN_DIR, 'funktionen.de.txt'), 'utf-8');
		locale.set('en');
		funktionsTabelle();
		locale.set('de');
		assert.equal(funktionsTabelle() + '\n', golden);
	});
	test('Messaufbau: Golden enthaelt die deutschen Texte aller Bausteine', () => {
		const alle = Object.keys(FAELLE).map((f) => readFileSync(path.join(GOLDEN_DIR, `${f}.de.html`), 'utf-8')).join('');
		for (const s of ['Kanal · Auswahl &amp; Kappung', 'Sag mir, welche Werte für dich passen', 'Sag mir, welche Werte dir ideal sind', 'Grat-kritisch', 'title="Grenze öffnen"', 'Metrik hinzufügen', '1 weiterer Eintrag bleibt erhalten', '2 weitere Einträge bleiben erhalten', 'Lade Metriken…', 'Preset-Auswahl', 'Detail-Werte', 'E-Mail-Inhalt', 'Erscheint nur in der E-Mail.', '✂ ab hier Telegram-Limit (max 7)', 'Etappen-Vorschau', 'Als Trip speichern', 'Trip wurde erfolgreich gespeichert.'])
			assert.ok(alle.includes(s), s);
	});
});

describe('AC-1: Layout-Reiter englisch in Trip und Ortsvergleich, Kanalnamen und Kurzformen unveraendert', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`${context}: erst de, dann ohne Neuladen en (E-Mail, Telegram, SMS)`, () => {
			const rendern = () => (['email', 'telegram', 'sms'] as const).map((k) => layoutTabRendern(context, k, 9)).join('\n');
			const { de, en } = deDannEn(() => sichtbar(rendern()));
			for (const s of ['Kanal · Auswahl & Kappung', 'Reihenfolge', 'Spalten', 'Detail-Werte', 'Preset-Auswahl']) hat(de, s);
			for (const s of ['Channel · selection & cutoff', 'Order', 'Columns', 'Detail values', 'Preset selection', 'In the briefing as a column', 'In the briefing as a detail', 'One table column per metric. Order = left to right.', 'Shown as a compact line directly below the table.', 'SMS · priority list', 'Characters', 'SMS has at most 140 characters. Order: top = more important. Anything that no longer fits the budget is left out automatically.'])
				hat(en, s);
			// Kanalnamen (Eigennamen) und Platzgrenzen stehen in beiden Sprachen gleich.
			const sms = context === 'route' ? '160' : '153';
			for (const s of ['Email ∞', 'Telegram 7', `SMS ${sms}`]) {
				hat(de, s);
				hat(en, s);
			}
			hat(en, 'Email shows everything · no limit');
			hat(en, `SMS: no grid, no table — plain text, ${sms} characters`);
			hat(en, context === 'route' ? 'Telegram: 9 Metriken · too wide — max 7, further forward = safer' : 'Telegram: 9 columns (label + 4 Orte) · too wide — max 7, further forward = safer');
			assert.deepEqual(deutscheReste(en, API_METRIKNAMEN), []);
		});
	}
	test('aria-Beschriftungen des Ausgabe-Layouts englisch', () => {
		const { de, en } = deDannEn(() => layoutTabRendern('route', 'sms'));
		hat(de, 'aria-label="SMS-Metriken, Reihenfolge"');
		hat(en, 'aria-label="SMS metrics, order"');
		const email = deDannEn(() => layoutTabRendern('route', 'email'));
		hat(email.en, 'aria-label="Columns, Reihenfolge"'); // „, Reihenfolge" haengt BucketSection (F9) an
		hatNicht(email.en, 'aria-label="Spalten, Reihenfolge"');
	});
	test('Spaltenkoepfe (col_label) und Kurzformen bleiben byte-gleich zur Eingabe', () => {
		const { de, en } = deDannEn(() => bausteineRendern());
		const kurz = (h: string) => [...h.matchAll(/class="badge-val[^"]*"[^>]*>([^<]*)</g)].map((m) => m[1]);
		assert.ok(kurz(de).length > 0, 'Messaufbau: keine Kurzform gerendert');
		assert.deepEqual(kurz(en), kurz(de));
		for (const c of COL_LABELS.slice(0, 2)) {
			hat(sichtbar(de), c);
			hat(sichtbar(en), c);
		}
	});
	test('Bausteine: Schnittlinie, Ausblick, Mail-Inhalt, Leer- und Ohne-Detail-Zustand englisch', () => {
		const { de, en } = deDannEn(() => bausteineRendern());
		const text = sichtbar(en);
		for (const s of [
			'✂ Telegram limit from here (max 7)',
			'3-day outlook',
			'Appears only in the email.',
			'3-Tages-Vorschau', // vom Trip-Aufrufer uebergebene Ueberschrift (F9) bleibt Aufrufer-Text
			'Email content',
			'Format',
			'Detailed (HTML)',
			'Compact (plain text)',
			'In compact mode, the metrics overview + outlook are always shown. The content blocks below are disabled.',
			'Outlook',
			'Weather pattern header, next stages and forecast confidence at the end of the email.',
			'Stage figures',
			'Distance, ascent/descent and maximum altitude of the stage as a number grid.',
			'Comparison with yesterday',
			"Today's weather compared with yesterday as a short line in the briefing.",
			'No metrics — add some from “Not in the briefing”.',
			'Columns'
		])
			hat(text, s);
		hatNicht(text, 'Detail values'); // hideDetailBucket
		assert.equal((sichtbar(de).match(/3-Tages-Ausblick/g) ?? []).length, 2);
		assert.equal((text.match(/3-day outlook/g) ?? []).length, 2, 'Ueberschrift und Schalter-Beschriftung');
		assert.deepEqual(deutscheReste(text, [...FREMD_REIHENFOLGE, ...API_METRIKNAMEN]), []);
	});
	test('Mail-Inhalt: Bausteintexte der Konstantenliste je Sprache (alle sieben)', () => {
		const { de, en } = deDannEn(() =>
			Object.fromEntries(Object.keys(CONTENT_MODULE_DESCRIPTIONS).map((k) => [k, { ...CONTENT_MODULE_DESCRIPTIONS[k] }]))
		);
		assert.deepEqual(Object.keys(en), Object.keys(de));
		assert.equal(de.show_outlook.label, 'Ausblick');
		assert.equal(en.show_outlook.label, 'Outlook');
		assert.equal(en.show_quick_take_tags.label, 'Quick-take chips');
		assert.equal(en.show_quick_take_tags.description, 'Coloured keyword pills at the top, e.g. “Dry”, “Windy”.');
		assert.equal(en.show_stability.label, 'Weather pattern');
		assert.equal(en.show_highlights.label, 'Summary');
		assert.equal(en.show_metrics_summary.label, 'Metrics overview');
		for (const k of Object.keys(de)) {
			assert.notEqual(en[k].label, de[k].label, k);
			assert.notEqual(en[k].description, de[k].description, k);
		}
	});
});

/** Einheiten, Skalen-Beschriftung, Eingabewerte und Band-Positionen eines Renders. */
function zahlenUndEinheiten(h: string): string[] {
	const muster = [/class="ce?m?-unit[^"]*"[^>]*>([^<]*)</g, /class="cem-step-unit[^"]*"[^>]*>([^<]*)</g, /class="cem-step-num[^"]*"[^>]*>([^<]*)</g, /value="([^"]*)"/g, /style="([^"]*)"/g, /step="([^"]*)"/g];
	const aus: string[] = [];
	for (const m of muster) for (const x of h.matchAll(m)) aus.push(x[1]);
	for (const x of h.matchAll(/class="cem-band-scale[^"]*"[^>]*>([\s\S]*?)<\/div>/g)) aus.push(sichtbar(x[1]));
	return aus;
}

describe('AC-2: Korridor-Editor englisch in Trip und Ortsvergleich, Desktop und mobil', () => {
	for (const fassung of ['desktop', 'mobil'] as const) {
		test(`Trip ${fassung}: Ueberschrift, Zeilen, Hinweise, Grenzen, Pool englisch`, () => {
			const { de, en } = deDannEn(() => korridorRendern('route', fassung, routeZustand(true)));
			const text = sichtbar(en);
			hat(sichtbar(de), 'Sag mir, welche Werte für dich passen');
			for (const s of [
				'Target ranges',
				'Tell me which values suit you',
				'One target range per metric sets which values you still accept on the trip. Values within the range are highlighted in the briefing. You set warnings between briefings in the Alerts tab.',
				'Additional metrics could not be loaded — the standard metrics are available to choose from.',
				'Retry',
				'within range = marked',
				'At least one limit (From or To) is required: Snow line',
				'Wind gusts',
				'Critical on ridges',
				'Temperature min',
				'Frost limit',
				'Snow line',
				'Snow instead of rain',
				'◂ open',
				'open ▸',
				'open · + limit',
				'Mark',
				'✕ remove',
				'Add metric',
				'＋ Precipitation',
				'＋ Temperature max',
				'2 × Mark'
			])
				hat(text, s);
			if (fassung === 'desktop') {
				hat(text, 'How to read a target range');
				hat(text, 'Add metric:');
				hat(text, 'From');
				hat(text, 'To');
			} else {
				hat(text, 'From');
				hat(text, '≥ -5 °C');
				hat(text, '≤ 70 km/h');
			}
			hat(en, 'title="Open limit"');
			hatNicht(en, 'title="Grenze öffnen"');
			// API-Metriknamen (Gewitter, Stufen kein/mittel/hoch) stellt F5 um, sie bleiben.
			hat(text, 'Gewitter');
			assert.deepEqual(deutscheReste(text), []);
			assert.deepEqual(zahlenUndEinheiten(en), zahlenUndEinheiten(de));
		});
		test(`Ortsvergleich ${fassung}: Ueberschrift, Neutralitaet, Plural exakt`, () => {
			for (const n of [1, 2] as const) {
				const { de, en } = deDannEn(() => korridorRendern('vergleich', fassung, vergleichZustand(n)));
				const text = sichtbar(en);
				for (const s of [
					'Target ranges · ideal ranges',
					'Tell me which values are ideal for you',
					'One target range per metric sets your ideal range. Values within the range are marked green per location in the briefing — no score, no ranking, just a reading aid.',
					'no score · no rank · target ranges only mark, they do not sort',
					'Add metric',
					'Mark'
				])
					hat(text, s);
				hat(en, 'title="Open limit"');
				const hinweis = (h: string) => sichtbar(/data-testid="corridor-editor(?:-mobile)?-unknown-hint"[^>]*>([\s\S]*?)<\/(?:span|div)>/.exec(h)?.[1] ?? '');
				const punkt = fassung === 'desktop' ? '· ' : '';
				assert.equal(hinweis(de), n === 1 ? `${punkt}1 weiterer Eintrag bleibt erhalten` : `${punkt}2 weitere Einträge bleiben erhalten`);
				assert.equal(hinweis(en), n === 1 ? `${punkt}1 more entry is kept` : `${punkt}2 more entries are kept`);
				assert.deepEqual(deutscheReste(text), []);
				assert.deepEqual(zahlenUndEinheiten(en), zahlenUndEinheiten(de));
			}
		});
	}
	test('Lade- und Fehlerzustaende beider Fassungen englisch', () => {
		const { en } = deDannEn(() => sichtbar(htmlFaelle().korridor_laden()));
		hat(en, 'Target ranges ⓘ Loading metrics…');
		hat(en, 'Target ranges · ideal ranges ⓘ Loading metrics…');
		hat(en, 'HTTP 503 Retry');
		assert.deepEqual(deutscheReste(en), []);
	});
	test('Zeilen in de aufgebaut, Anzeige nach Sprachwechsel ohne Neuladen englisch (Zeile, Hinweis, Pflicht-Fehler, Pool)', () => {
		locale.set('de');
		const zustand = routeZustand(false);
		assert.equal((zustand.rows as { label: string }[])[0].label, 'Böen', 'Messaufbau: Zeilen auf Deutsch aufgebaut');
		locale.set('en');
		for (const fassung of ['desktop', 'mobil'] as const) {
			const text = sichtbar(korridorRendern('route', fassung, zustand));
			for (const s of ['Wind gusts', 'Critical on ridges', 'At least one limit (From or To) is required: Snow line', '＋ Precipitation', '＋ Temperature max']) hat(text, s);
			hatNicht(text, 'Böen');
			hatNicht(text, 'Grat-kritisch');
			hatNicht(text, 'Schneefallgrenze');
		}
	});
	test('ROUTE_METRIC_DEFS: Beschriftung je Sprache, metric/unit/scale/step/defaultMin/defaultMax identisch', () => {
		const { de, en } = deDannEn(() => ce.ROUTE_METRIC_DEFS.map((d: Record<string, unknown>) => ({ ...d })));
		const fest = (l: Record<string, unknown>[]) => l.map(({ metric, unit, scale, step, defaultMin, defaultMax }) => ({ metric, unit, scale, step, defaultMin, defaultMax }));
		assert.deepEqual(fest(en), fest(de));
		assert.deepEqual(de.map((d: { label: string }) => d.label), ['Böen', 'Niederschlag', 'Temperatur Min', 'Temperatur Max', 'Schneefallgrenze']);
		assert.deepEqual(en.map((d: { label: string }) => d.label), ['Wind gusts', 'Precipitation', 'Temperature min', 'Temperature max', 'Snow line']);
		assert.deepEqual(en.map((d: { note: string }) => d.note), ['Critical on ridges', 'Wet / slip risk', 'Frost limit', 'Heat limit', 'Snow instead of rain']);
	});
	test('PROFILE_METRICS_WITH_SCALES: Beschriftung je Sprache, Schluessel identisch', () => {
		const lese = () => Object.fromEntries(Object.entries(ce.PROFILE_METRICS_WITH_SCALES as Record<string, { key: string; label: string }[]>).map(([p, l]) => [p, l.map((m) => ({ key: m.key, label: m.label }))]));
		const { de, en } = deDannEn(lese);
		for (const p of Object.keys(de)) assert.deepEqual(en[p].map((m: { key: string }) => m.key), de[p].map((m: { key: string }) => m.key), p);
		assert.deepEqual(en.WINTERSPORT.map((m: { label: string }) => m.label), ['Snow depth', 'Fresh snow', 'Sunshine hours', 'Peak wind', 'Cloud cover Ø']);
		assert.deepEqual(en.SUMMER_TREKKING.map((m: { label: string }) => m.label), ['Precipitation', 'Thunderstorm', 'Peak wind', 'UV index max', 'Visibility min']);
		assert.deepEqual(en.ALLGEMEIN.map((m: { label: string }) => m.label), ['Temperature max', 'Peak wind', 'Precipitation', 'Visibility min']);
	});
});

describe('AC-3: Kappungs- und Abwahl-Hinweis je Sprache (gleiche Zahlen und Kanaele, ohne Wertung)', () => {
	const ERWARTET: Record<string, [string, string]> = {
		email: ['Email zeigt alles · keine Begrenzung', 'Email shows everything · no limit'],
		telegram_passt: ['Telegram: 5 Metriken · passt (max 7)', 'Telegram: 5 Metriken · fits (max 7)'],
		telegram_zu_breit: ['Telegram: 9 Metriken · zu breit — max 7, weiter vorne = sicherer', 'Telegram: 9 Metriken · too wide — max 7, further forward = safer'],
		telegram_label_passt: ['Telegram: 5 Spalten (Label + 4 Orte) · passt (max 7)', 'Telegram: 5 columns (label + 4 Orte) · fits (max 7)'],
		telegram_label_eine: ['Telegram: 1 Spalten (Label + 0 Orte) · passt (max 7)', 'Telegram: 1 column (label + 0 Orte) · fits (max 7)'],
		telegram_label_zu_breit: ['Telegram: 9 Spalten (Label + 8 Orte) · zu breit — max 7, weiter vorne = sicherer', 'Telegram: 9 columns (label + 8 Orte) · too wide — max 7, further forward = safer'],
		sms_trip: ['SMS: kein Raster, keine Tabelle — Fließtext, 160 Zeichen', 'SMS: no grid, no table — plain text, 160 characters'],
		sms_vergleich: ['SMS: kein Raster, keine Tabelle — Fließtext, 153 Zeichen', 'SMS: no grid, no table — plain text, 153 characters']
	};
	const WERTUNG = /\b(only|unfortunately|bad|just|sadly|poor)\b/i;
	const kern = (s: string) => [...s.matchAll(/\d+|Email|Telegram|SMS/g)].map((m) => m[0]);
	for (const [fall, eingabe] of CAP_FAELLE) {
		test(`ltCapNoteText(${fall})`, () => {
			const { de, en } = deDannEn(() => lt.ltCapNoteText(eingabe));
			assert.equal(de, ERWARTET[fall][0]);
			assert.equal(en, ERWARTET[fall][1]);
			assert.deepEqual(kern(en), kern(de));
			assert.doesNotMatch(en, WERTUNG);
		});
	}
	test('ltKanalAbwahlHinweisText je Sprache', () => {
		const { de, en } = deDannEn(() => lt.ltKanalAbwahlHinweisText());
		assert.equal(de, 'Ein Kanal zeigt höchstens, was in der Grundauswahl gewählt ist. Was dort fehlt, erscheint in keinem Kanal.');
		assert.equal(en, 'A channel shows at most what is selected in the base selection. Anything missing there appears in no channel.');
		assert.doesNotMatch(en, WERTUNG);
	});
	test('Gegenprobe: die Wortliste erkennt eine wertende Formulierung', () => {
		assert.match('Telegram only shows the most important values', WERTUNG);
		assert.doesNotMatch(ERWARTET.telegram_zu_breit[1], WERTUNG);
	});
	test('LTCapNote im Layout-Reiter zeigt denselben Satz wie die Funktion (Wirkort)', () => {
		const limit = lt.ltLimitForChannel('telegram', 160);
		const { en } = deDannEn(() => ({ html: layoutTabRendern('route', 'telegram', 9), fn: lt.ltCapNoteText({ channel: 'telegram', limit, colCount: 9, subject: 'Metriken', hasLabelColumn: false }) }));
		assert.equal(en.fn, 'Telegram: 9 Metriken · too wide — max 7, further forward = safer');
		hat(sichtbar(en.html), en.fn);
	});
});

describe('AC-4: zwei Nutzer, zwei Sprachen, gleiche Wertebereiche, gleiche Speicher-Nutzlast', () => {
	const trip = (id: string) => ({ id, name: `Trip ${id}`, stages: [], corridors: ROUTE_KORRIDORE });
	const preset = (id: string) => ({ id, name: `Vergleich ${id}`, corridors: VERGLEICH_KORRIDORE.slice(0, 2), display_config: { ideal_ranges: { wind_max_kmh: { min: 0, max: 40 } }, active_metrics: ['wind_max_kmh', 'thunder_level_max'] } });
	const API: Record<string, Record<string, unknown>> = {
		A: { '/api/auth/profile': { id: 'anna', language: 'en' }, '/api/trips/anna-gr20': trip('anna-gr20'), '/api/compare/presets/anna-v': preset('anna-v') },
		B: { '/api/auth/profile': { id: 'bert', language: 'de' }, '/api/trips/bert-gr20': trip('bert-gr20'), '/api/compare/presets/bert-v': preset('bert-v') }
	};

	/** Ersetzt nur die Netzgrenze: `fetch` antwortet je Sitzungs-Cookie mit eigenen Daten (sonst 404). */
	async function mitApi<T>(lauf: () => Promise<T>): Promise<T> {
		const echt = globalThis.fetch;
		globalThis.fetch = (async (u: string, init?: { headers?: Record<string, string> }) => {
			const sitzung = /gz_session=([^;]+)/.exec(init?.headers?.Cookie ?? '')?.[1] ?? '';
			const daten = API[sitzung]?.[new URL(String(u)).pathname];
			return new Response(JSON.stringify(daten ?? null), { status: daten === undefined ? 404 : 200 });
		}) as unknown as typeof fetch;
		try {
			return await lauf();
		} finally {
			globalThis.fetch = echt;
		}
	}
	const cookies = (s: string) => ({ get: (n: string) => (n === 'gz_session' ? s : undefined) });
	const holen = async (sitzung: string, pfad: string) => {
		const r = await fetch(`http://core${pfad}`, { headers: { Cookie: `gz_session=${sitzung}` } });
		return r.status === 200 ? await r.json() : null;
	};

	/** Echter Layout-Loader (Sprache) + Daten der Sitzung → Reiter, geaenderte Grenze, Nutzlast. */
	async function sichtFuer(sitzung: 'A' | 'B', tripId: string, presetId: string) {
		const { lang, t, p, fremd } = await mitApi(async () => {
			const layout = await layoutLoad({ locals: { userId: sitzung, lang: 'de' }, cookies: cookies(sitzung) } as never);
			const fremdeId = sitzung === 'A' ? 'bert-gr20' : 'anna-gr20';
			return { lang: layout.lang as 'de' | 'en', t: await holen(sitzung, `/api/trips/${tripId}`), p: await holen(sitzung, `/api/compare/presets/${presetId}`), fremd: await holen(sitzung, `/api/trips/${fremdeId}`) };
		});
		locale.set(lang);
		const route = ce.buildRoutePool(t.corridors, undefined, ROUTE_EXTRA);
		const vergleich = ce.buildComparePool(p.corridors, VERGLEICH_DEFS);
		const zeilen = ce.patchRow(route.rows, 'wind_gust', { max: 60 });
		const vZeilen = ce.patchRow(vergleich.rows, 'wind_max_kmh', { max: 45 });
		return {
			lang,
			fremd,
			layout: sichtbar(layoutTabRendern('route', 'email')),
			korridor: sichtbar(korridorRendern('route', 'desktop', { ...routeZustand(false), rows: zeilen })),
			vergleich: sichtbar(korridorRendern('vergleich', 'mobil', { ...vergleichZustand(1), rows: vZeilen, unknownCorridors: [] })),
			nutzlast: ce.buildCorridorSavePayload(zeilen, {}, route.unknownCorridors),
			vNutzlast: ce.buildCompareCorridorSavePayload(vZeilen, [], { idealRanges: p.display_config.ideal_ranges, activeMetricKeys: p.display_config.active_metrics, metricAlertLevels: {} }, vergleich.unknownCorridors)
		};
	}

	test('A englisch, B deutsch; jeder nur eigene Daten; Nutzlast identisch und ohne Anzeige-Texte', async () => {
		locale.set('de');
		const a = await sichtFuer('A', 'anna-gr20', 'anna-v');
		const b = await sichtFuer('B', 'bert-gr20', 'bert-v');
		assert.equal(a.lang, 'en');
		assert.equal(b.lang, 'de');
		assert.equal(a.fremd, null, 'A liest den Trip von B');
		assert.equal(b.fremd, null, 'B liest den Trip von A');
		hat(a.layout, 'Channel · selection & cutoff');
		hat(b.layout, 'Kanal · Auswahl & Kappung');
		hat(a.korridor, 'Wind gusts');
		hat(a.korridor, 'Tell me which values suit you');
		hat(b.korridor, 'Böen');
		hat(b.korridor, 'Sag mir, welche Werte für dich passen');
		hat(a.vergleich, 'Tell me which values are ideal for you');
		hat(b.vergleich, 'Sag mir, welche Werte dir ideal sind');
		assert.deepEqual(deutscheReste(a.korridor), []);
		assert.deepEqual(a.nutzlast, b.nutzlast);
		assert.equal(JSON.stringify(a.nutzlast), JSON.stringify(b.nutzlast));
		assert.deepEqual(a.vNutzlast, b.vNutzlast);
		assert.equal(a.nutzlast.corridors.find((c: { metric: string }) => c.metric === 'wind_gust').range[1], 60, 'geaenderte Grenze gespeichert');
		assert.deepEqual(a.vNutzlast.idealRanges.wind_max_kmh, { min: 0, max: 45 });
		for (const s of [JSON.stringify(a.nutzlast), JSON.stringify(a.vNutzlast)]) {
			for (const wort of ['Wind gusts', 'Böen', 'Critical', 'Grat', 'Snow line', 'Schneefallgrenze', 'label', 'note']) hatNicht(s, wort);
		}
	});
});

describe('Anker: jeder F8-Katalogwert ist als festes de/en-Literal verankert', () => {
	/** Platzhalter des Literals (<name>) werden als Parameter `<name>` eingesetzt. */
	const params = (literal: string) =>
		Object.fromEntries([...literal.matchAll(/<([a-z0-9_]+)>/g)].map((m) => [m[1], `<${m[1]}>`]));
	for (const [k, de, en] of F8_ANKER) {
		test(k, () => {
			assert.equal(trFor('de', k, params(de)), de, `de ${k}`);
			assert.equal(trFor('en', k, params(en)), en, `en ${k}`);
		});
	}

	test('statischer Gegencheck: Anker-Tabelle == Schluessel von layout.json (de und en)', () => {
		const MSG = path.join(FRONTEND, 'src', 'lib', 'i18n', 'messages');
		for (const lang of ['de', 'en']) {
			const schluessel = Object.keys(JSON.parse(readFileSync(path.join(MSG, lang, 'layout.json'), 'utf-8')));
			assert.deepEqual([...schluessel].sort(), F8_ANKER.map(([k]) => k).sort(), `${lang}: Schluessel ohne Anker oder Anker ohne Schluessel`);
		}
		assert.equal(new Set(F8_ANKER.map(([k]) => k)).size, F8_ANKER.length, 'doppelte Anker');
	});

	test('Plural: weitere_erhalten und spalten_* unterscheiden one/other exakt', () => {
		assert.equal(trFor('en', 'layout.korridor.weitere_erhalten.one', { count: 1 }), '1 more entry is kept');
		assert.equal(trFor('en', 'layout.korridor.weitere_erhalten.other', { count: 3 }), '3 more entries are kept');
		assert.equal(trFor('de', 'layout.korridor.weitere_erhalten.one', { count: 1 }), '1 weiterer Eintrag bleibt erhalten');
		assert.equal(trFor('de', 'layout.korridor.weitere_erhalten.other', { count: 3 }), '3 weitere Einträge bleiben erhalten');
	});
});

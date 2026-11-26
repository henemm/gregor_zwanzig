// Paket #3419 (#3420, #3421, #3422; Teil von #2795): Elementlisten-Nachzug „Was steht wo“.
// Spec: docs/specs/modules/feat_3419_elementliste_nachzug.md (AC-1 bis AC-5, Test Plan).
// Kontext: docs/context/paket-3419-elementliste-nachzug.md
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test e2e/feat3419_abgleich_nachzug.test.ts
//
// Kern-Schicht: deterministisch, ohne Netz, gegen die exportierten Funktionen von
// frontend/e2e/elementliste_abgleich_logik.ts und die versionierten Daten (Elementliste, Mockup,
// Metriknamen-Schnappschuss, Server-Katalog). Kein Mock.
//
// Festgelegte Signaturen (RED, Developer übernimmt sie so; alle neuen Parameter optional und
// rückwärtskompatibel, bestehende Aufrufer bleiben unverändert):
//
//   bewerteAbschnitt(liste, befund, sprache, abschnitt)            -- unverändert
//       #3420 Zeilenbindung: Zellmuster-Element (Muster `{metrik} in|im <Stelle>`) ist an seine Zeile
//       gebunden; Zeile im Soll = Metrikteil von `text_de`. Ist das vorige Zellmuster-Element derselben
//       Zeile gefunden, muss der Live-Treffer denselben Metrikteil tragen wie dessen Live-Treffer; sonst
//       { status: 'abweichend', grund: 'Text nicht sichtbar' } für genau dieses Element, Cursor bleibt.
//       #3419 Nr. 6: ein gefundenes `{wert}`-Element trägt den angenommenen Live-Text (normalisiert) in
//       `ist` ({ status: 'gefunden', ist: '<Live-Text>' }); daraus sammelt der Aufrufer `angenommen`.
//
//   wetterOverrides(metriken, eig, soll?)                           -- neuer 3. Parameter `soll`
//       soll: Record<metricId, { lower?: Array<number|null> | null; upper?: Array<number|null> | null }>
//       in der Reihenfolge des Mockups: lower = [rot, orange, gelb], upper = [gelb, orange, rot]
//       (Spalten 6/7 von TRIP_METRICS / ORTE_METRICS in mockup-hub-fassung4.html).
//       Jeder Mockup-Zahlenwert einer erlaubten Seite wird übernommen (auch Minuswerte); fehlende
//       Werte (null, ganze Seite oder ganze Metrik ohne Mockup-Eintrag) bekommen einen gültigen Ersatz.
//       Gültigkeit wie #3192 AC-1: je Seite alle drei Werte gesetzt und streng aufsteigend
//       (lower rot<orange<gelb, upper gelb<orange<rot), lower.gelb < upper.gelb; nur `allowed_sides`.
//   WetterPruefQuelle bekommt das optionale Feld `grenzen` (gleicher Typ wie `soll`);
//       wetterPruefPayload('…', 'mit_abweichung', q) reicht q.grenzen an wetterOverrides durch.
//
//   findeZusaetzliche(befund, liste, ausnahmen, kontoTexte, sprache, metrikNamen = [], zusatz = {})
//   werteGegenrichtungAus(befund, liste, ausnahmen, kontoTexte, sprache, metrikNamen = [], zusatz = {})
//       zusatz: {
//         namenDeEn?: Array<{ de: string; en: string }>;   // #3422: DE-Name -> EN-Name, ein DE-Name darf
//                                                          // mehrere EN-Namen haben (jeder ergibt eine Form)
//         angenommen?: Array<{ ctx: string; reiter: string; text: string }>; // #3419 Nr. 6
//       }
//       #3422: im EN-Lauf wird die Beispielform eines `{wert}`-Elements zusätzlich aus `text_de` mit
//       übersetztem Metriknamen gebildet (Zahlen beliebig): „Böen 51 km/h“ + Böen->Gusts => „Gusts {zahl} km/h“.
//       #3419 Nr. 6: ein Text aus `angenommen` mit gleichem ctx UND gleichem Reiter wie der Befund gilt als
//       erklärt; jeder andere Text bleibt „zusätzlich“.
//       Quelle der Namenspaare im Test (und im Staging-Lauf): Schnappschuss
//       docs/context/einstellungen_neu/daten/metrik_namen.json (label_de/label_en) PLUS die Zeilennamen
//       des Server-Katalogs `vergleich.zeile.*` (src/i18n/messages/{de,en}/vergleich.json), denn die
//       Kurz-Namen der Beispielzeilen („Gusts“, „Rain“, „Clouds“, „Sun“) stehen nicht im Schnappschuss
//       (dort „Böen“ -> „Wind gusts“).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as L from './elementliste_abgleich_logik.ts';
import type { ListenElement, Ergebnis, ZusaetzlichEintrag, Sprache } from './elementliste_abgleich_logik.ts';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, '..', '..');
const EINST = join(REPO, 'docs', 'context', 'einstellungen_neu');

// ------------------------------------------------------------------ Hilfen

let nr = 0;
/** Listen-Element des Abschnitts was-steht-wo (Trip, Wetter, normal); Felder wie die Elementliste. */
function el(text_de: string, text_en: string, muster: string | null = null, extra: Partial<ListenElement> = {}): ListenElement {
	nr += 1;
	return {
		id: `t3419-${nr}`,
		ctx: 'trip',
		reiter: 'wetter',
		zustand: 'normal',
		segment: null,
		abschnitt: 'was-steht-wo',
		ordnung: nr,
		rolle: muster ? 'eingabe' : 'text',
		text_de,
		muster,
		i18n_key: null,
		text_en,
		luecke: false,
		...extra
	};
}
/** Zellmuster-Element `{metrik} in <Stelle>` (DE) mit EN-Muster. */
const zelle = (metrik: string, stelleDe: string, stelleEn: string) =>
	el(`${metrik} in ${stelleDe}`, `{metrik} in ${stelleEn}`, `{metrik} in ${stelleDe}`);
/** Beispieltext `{wert}` (sprachneutral, wie der Generator ihn ablegt). */
const beispiel = (text: string) => el(text, '{wert}', '{wert}', { rolle: 'beispiel', sprachneutral: true });

function bewerte(liste: ListenElement[], texte: string[], sprache: Sprache): Map<string, Ergebnis> {
	return L.bewerteAbschnitt(liste, { marker: true, texte }, sprache, 'was-steht-wo');
}
const abweichend = (m: Map<string, Ergebnis>) => [...m.entries()].filter(([, e]) => e.status === 'abweichend');

type Zusatz = { namenDeEn?: Array<{ de: string; en: string }>; angenommen?: Array<{ ctx: string; reiter: string; text: string }> };
type FindeMitZusatz = (
	befund: { ctx: string; reiter: string; texte: string[] },
	liste: ListenElement[],
	ausnahmen: L.Ausnahme[],
	kontoTexte: string[],
	sprache: Sprache,
	metrikNamen?: string[],
	zusatz?: Zusatz
) => ZusaetzlichEintrag[];
const finde = L.findeZusaetzliche as unknown as FindeMitZusatz;
const zusaetzlicheTexte = (z: ZusaetzlichEintrag[]) => z.map((e) => e.text).sort();

const elementliste = (): ListenElement[] =>
	(JSON.parse(readFileSync(join(EINST, 'elementliste.json'), 'utf8')) as { elemente: ListenElement[] }).elemente;

/**
 * Namenspaare DE -> EN über die Produktfunktion `namenPaareAus` (dieselbe, die der Staging-Lauf nutzt) aus den
 * echten Dateien: Schnappschuss metrik_namen.json + Server-Katalog vergleich.zeile.* (siehe Kopf).
 */
const liesJson = (...teile: string[]): unknown => JSON.parse(readFileSync(join(...teile), 'utf8'));
function namenPaare(): Array<{ de: string; en: string }> {
	return L.namenPaareAus(
		liesJson(EINST, 'daten', 'metrik_namen.json'),
		liesJson(REPO, 'src', 'i18n', 'messages', 'de', 'vergleich.json'),
		liesJson(REPO, 'src', 'i18n', 'messages', 'en', 'vergleich.json')
	);
}

// ------------------------------------------------------------------ AC-1 (#3420) Zeilenbindung

describe('#3420 AC-1: ein fehlendes Kästchen ergibt genau eine Abweichung, keine Kaskade', () => {
	// GIVEN Zeile „Temperatur“ mit drei Zellmuster-Kästchen und Folgezeile „Wind“; im Live-Bild fehlt
	//       „Temperatur in SMS“ (live gesperrt, #3373)
	// WHEN  der Abschnitt bewertet wird
	// THEN  genau das SMS-Kästchen der Temperatur-Zeile ist „Text nicht sichtbar“, alle Wind-Elemente gefunden
	const baue = () => {
		nr = 0;
		const temp = el('Temperatur', 'Temperature');
		const tMail = zelle('Temperatur', 'E-Mail', 'email');
		const tTg = zelle('Temperatur', 'Telegram', 'Telegram');
		const tSms = zelle('Temperatur', 'SMS', 'SMS');
		const wind = el('Wind', 'Wind');
		const wMail = zelle('Wind', 'E-Mail', 'email');
		const wTg = zelle('Wind', 'Telegram', 'Telegram');
		const wSms = zelle('Wind', 'SMS', 'SMS');
		return { liste: [temp, tMail, tTg, tSms, wind, wMail, wTg, wSms], tSms, wind: [wind, wMail, wTg, wSms] };
	};

	test('DE: genau eine Abweichung (Temperatur in SMS), Wind-Zeile vollständig gefunden', () => {
		const { liste, tSms, wind } = baue();
		const live = ['Temperatur', 'Temperatur in E-Mail', 'Temperatur in Telegram', 'Wind', 'Wind in E-Mail', 'Wind in Telegram', 'Wind in SMS'];
		const erg = bewerte(liste, live, 'de');
		assert.deepEqual(abweichend(erg).map(([id]) => id), [tSms.id], JSON.stringify([...erg]));
		assert.equal(erg.get(tSms.id)?.grund, 'Text nicht sichtbar');
		for (const w of wind) assert.equal(erg.get(w.id)?.status, 'gefunden', `${w.text_de}: ${JSON.stringify(erg.get(w.id))}`);
	});

	test('EN: genau eine Abweichung (Temperature in SMS), Wind-Zeile vollständig gefunden', () => {
		const { liste, tSms, wind } = baue();
		const live = ['Temperature', 'Temperature in email', 'Temperature in Telegram', 'Wind', 'Wind in email', 'Wind in Telegram', 'Wind in SMS'];
		const erg = bewerte(liste, live, 'en');
		assert.deepEqual(abweichend(erg).map(([id]) => id), [tSms.id], JSON.stringify([...erg]));
		assert.equal(erg.get(tSms.id)?.grund, 'Text nicht sichtbar');
		for (const w of wind) assert.equal(erg.get(w.id)?.status, 'gefunden', `${w.text_en}: ${JSON.stringify(erg.get(w.id))}`);
	});

	test('DE, Trip-Lage aus dem Rohbericht: Sperrzelle mit Beispieltext, Folgezeilen ohne Reihenfolge-Kaskade', () => {
		// GIVEN Soll alt (Kästchen „Temperatur in SMS“ + Beispiel „D10/15“), live gesperrt: Beispiel + „kein Kürzel“
		// WHEN  bewertet wird
		// THEN  nur „Temperatur in SMS“ fehlt; Beispiel, Ausblick-Kästchen und die Nacht-Zeile sind gefunden
		nr = 0;
		const liste = [
			el('Temperatur', 'Temperature'),
			zelle('Temperatur', 'E-Mail', 'email'),
			beispiel('Temp 14.4'),
			zelle('Temperatur', 'Telegram', 'Telegram'),
			beispiel('T 9.6-15.2'),
			zelle('Temperatur', 'SMS', 'SMS'),
			beispiel('D10/15'),
			el('Temperatur im 3-Tages-Ausblick', '{metrik} in the 3-day outlook', '{metrik} im 3-Tages-Ausblick'),
			el('Tiefsttemperatur Nacht', 'Night low'),
			el('keine eigene Spalte', 'no column of its own'),
			zelle('Tiefsttemperatur Nacht', 'Telegram', 'Telegram'),
			zelle('Tiefsttemperatur Nacht', 'SMS', 'SMS'),
			beispiel('N10')
		];
		const live = [
			'Temperatur', 'Temperatur in E-Mail', 'Temp 14.4', 'Temperatur in Telegram', 'T 9.6-15.2', 'D10/15', 'kein Kürzel',
			'Temperatur im 3-Tages-Ausblick', 'Tiefsttemperatur Nacht', 'keine eigene Spalte',
			'Tiefsttemperatur Nacht in Telegram', 'Tiefsttemperatur Nacht in SMS', 'N10'
		];
		const erg = bewerte(liste, live, 'de');
		const ab = abweichend(erg);
		assert.equal(ab.length, 1, `genau eine Abweichung erwartet: ${JSON.stringify(ab)}`);
		assert.equal(liste.find((e) => e.id === ab[0][0])?.text_de, 'Temperatur in SMS');
		assert.equal(ab[0][1].grund, 'Text nicht sichtbar');
	});
});

describe('#3420 AC-1: Live-Treffer mit anderem Metrikteil wird nicht angenommen, Cursor bleibt', () => {
	test('DE: „Temperatur in Telegram“ trifft nur „Wind in Telegram“ -> nicht sichtbar; „Temperatur in SMS“ danach gefunden', () => {
		// GIVEN Zeile Temperatur (E-Mail, Telegram, SMS); live steht zwischen den Temperatur-Kästchen „Wind in Telegram“
		// WHEN  bewertet wird
		// THEN  „Temperatur in Telegram“ = Text nicht sichtbar (anderer Metrikteil als der Vorgänger der Zeile),
		//       der Cursor bleibt stehen, das Folgeelement „Temperatur in SMS“ derselben Zeile wird gefunden
		nr = 0;
		const tMail = zelle('Temperatur', 'E-Mail', 'email');
		const tTg = zelle('Temperatur', 'Telegram', 'Telegram');
		const tSms = zelle('Temperatur', 'SMS', 'SMS');
		const liste = [el('Temperatur', 'Temperature'), tMail, tTg, tSms];
		const erg = bewerte(liste, ['Temperatur', 'Temperatur in E-Mail', 'Wind in Telegram', 'Temperatur in SMS'], 'de');
		assert.equal(erg.get(tMail.id)?.status, 'gefunden');
		assert.equal(erg.get(tTg.id)?.status, 'abweichend', JSON.stringify(erg.get(tTg.id)));
		assert.equal(erg.get(tTg.id)?.grund, 'Text nicht sichtbar');
		assert.equal(erg.get(tSms.id)?.status, 'gefunden', JSON.stringify(erg.get(tSms.id)));
	});

	test('EN: dieselbe Lage auf Englisch', () => {
		nr = 0;
		const tMail = zelle('Temperatur', 'E-Mail', 'email');
		const tTg = zelle('Temperatur', 'Telegram', 'Telegram');
		const tSms = zelle('Temperatur', 'SMS', 'SMS');
		const liste = [el('Temperatur', 'Temperature'), tMail, tTg, tSms];
		const erg = bewerte(liste, ['Temperature', 'Temperature in email', 'Wind in Telegram', 'Temperature in SMS'], 'en');
		assert.equal(erg.get(tMail.id)?.status, 'gefunden');
		assert.equal(erg.get(tTg.id)?.grund, 'Text nicht sichtbar', JSON.stringify(erg.get(tTg.id)));
		assert.equal(erg.get(tSms.id)?.status, 'gefunden', JSON.stringify(erg.get(tSms.id)));
	});

	test('Gegenprobe: vollständige Zeile bleibt ganz gefunden (Bindung verwirft keinen richtigen Treffer)', () => {
		nr = 0;
		const liste = [el('Temperatur', 'Temperature'), zelle('Temperatur', 'E-Mail', 'email'), zelle('Temperatur', 'Telegram', 'Telegram'), zelle('Temperatur', 'SMS', 'SMS')];
		const erg = bewerte(liste, ['Temperatur', 'Temperatur in E-Mail', 'Temperatur in Telegram', 'Temperatur in SMS'], 'de');
		assert.deepEqual(abweichend(erg), []);
	});
});

// ------------------------------------------------------------------ AC-2 (#3421) Grenzen aus dem Mockup

type Seite = { red?: number; orange?: number; yellow?: number };
type AmpelM = { lower?: Seite; upper?: Seite };
type Overrides = { metrics: Record<string, AmpelM>; thunder?: { mittel: string; hoch: string } };
type SollGrenzen = Record<string, { lower?: Array<number | null> | null; upper?: Array<number | null> | null }>;
type OverridesMitSoll = (m: string[], eig: Record<string, { allowed_sides: string | null }>, soll?: SollGrenzen) => Overrides;
const overrides = L.wetterOverrides as unknown as OverridesMitSoll;

/** `allowed_sides` je Metrik wie /api/metrics (src/app/metric_catalog.py, _REITER_WETTER). */
const EIG: Record<string, { allowed_sides: string | null }> = {
	temperature: { allowed_sides: 'both' }, temperature_night: { allowed_sides: 'both' }, wind_chill: { allowed_sides: 'both' },
	humidity: { allowed_sides: 'upper' }, dewpoint: { allowed_sides: 'upper' }, wind: { allowed_sides: 'both' },
	gust: { allowed_sides: 'upper' }, precipitation: { allowed_sides: 'upper' }, thunder: { allowed_sides: 'level' },
	rain_probability: { allowed_sides: 'upper' }, visibility: { allowed_sides: 'lower' }, cloud_total: { allowed_sides: 'upper' },
	cloud_low: { allowed_sides: 'upper' }, uv_index: { allowed_sides: 'upper' }, sunshine: { allowed_sides: 'lower' },
	freezing_level: { allowed_sides: 'both' }, snowfall_limit: { allowed_sides: 'both' }, fresh_snow: { allowed_sides: 'upper' },
	snow_depth: { allowed_sides: 'both' }, wind_direction: { allowed_sides: null }
};

/** TRIP_METRICS / ORTE_METRICS aus dem Mockup: Spalte 6 = lower [rot, orange, gelb], Spalte 7 = upper [gelb, orange, rot]. */
function mockupGrenzen(name: 'TRIP_METRICS' | 'ORTE_METRICS'): SollGrenzen {
	const html = readFileSync(join(EINST, 'seiten', 'mockup-hub-fassung4.html'), 'utf8');
	const block = html.match(new RegExp(`const ${name}=\\[([\\s\\S]*?)\\n\\];`));
	assert.ok(block, `${name} nicht im Mockup gefunden`);
	const zeilen = JSON.parse('[' + block![1].replace(/'/g, '"') + ']') as unknown[][];
	const out: SollGrenzen = {};
	for (const z of zeilen) out[z[0] as string] = { lower: z[5] as Array<number | null> | null, upper: z[6] as Array<number | null> | null };
	return out;
}

const aufsteigend = (w: Array<number | undefined>) => w.every((x) => typeof x === 'number' && Number.isFinite(x)) && w.every((x, i) => i === 0 || x! > w[i - 1]!);
/** #3192 AC-1: nur erlaubte Seiten, je Seite drei Zahlen streng aufsteigend, lower.gelb < upper.gelb. */
function pruefeGueltig(o: Overrides): void {
	for (const [id, e] of Object.entries(o.metrics)) {
		const s = EIG[id]?.allowed_sides;
		if (e.lower) {
			assert.ok(s === 'both' || s === 'lower', `${id}: lower nicht erlaubt (${s})`);
			assert.ok(aufsteigend([e.lower.red, e.lower.orange, e.lower.yellow]), `${id} lower ungültig: ${JSON.stringify(e.lower)}`);
		}
		if (e.upper) {
			assert.ok(s === 'both' || s === 'upper', `${id}: upper nicht erlaubt (${s})`);
			assert.ok(aufsteigend([e.upper.yellow, e.upper.orange, e.upper.red]), `${id} upper ungültig: ${JSON.stringify(e.upper)}`);
		}
		if (e.lower && e.upper) assert.ok(e.lower.yellow! < e.upper.yellow!, `${id}: lower.gelb < upper.gelb verletzt`);
	}
}
/** Jeder Mockup-Zahlenwert einer erlaubten Seite steht an seiner Stelle im Override. */
function pruefeMockupWerte(o: Overrides, soll: SollGrenzen, metriken: string[]): void {
	for (const id of metriken) {
		const s = EIG[id]?.allowed_sides;
		const m = soll[id];
		if (!m || s === 'level' || !s) continue;
		const lo = m.lower ?? [];
		const hi = m.upper ?? [];
		(['red', 'orange', 'yellow'] as const).forEach((k, i) => {
			if (typeof lo[i] === 'number' && (s === 'both' || s === 'lower')) assert.equal(o.metrics[id]?.lower?.[k], lo[i], `${id} lower.${k}`);
		});
		(['yellow', 'orange', 'red'] as const).forEach((k, i) => {
			if (typeof hi[i] === 'number' && (s === 'both' || s === 'upper')) assert.equal(o.metrics[id]?.upper?.[k], hi[i], `${id} upper.${k}`);
		});
	}
}

describe('#3421 AC-2: Prüfdatensatz übernimmt die Grenzwerte des Mockups (auch Minuswerte)', () => {
	test('Trip: Mockup-Werte inkl. -10, -8, -15, -300, -500 übernommen, Datensatz bleibt gültig (#3192)', () => {
		// GIVEN die Grenzen-Metriken des Trips aus der Elementliste und TRIP_METRICS des Mockups
		// WHEN  der Prüfdatensatz (mit Abweichung) gebaut wird
		// THEN  enthält er jeden Mockup-Wert an seiner Stelle und erfüllt die Gültigkeitsregel #3192 AC-1
		const soll = mockupGrenzen('TRIP_METRICS');
		const metriken = L.wetterPruefMetriken(elementliste(), 'trip');
		const o = overrides(metriken, EIG, soll);
		assert.deepEqual(o.metrics.temperature?.lower, { red: -10, orange: -3, yellow: 2 });
		assert.deepEqual(o.metrics.freezing_level?.lower, { red: -300, orange: 0, yellow: 300 });
		assert.equal(o.metrics.snowfall_limit?.lower?.red, -500);
		assert.equal(o.metrics.wind_chill?.lower?.red, -15);
		assert.equal(o.metrics.temperature_night?.lower?.red, -8);
		pruefeMockupWerte(o, soll, metriken);
		pruefeGueltig(o);
	});

	test('Orte: Mockup-Werte inkl. -15 übernommen, Datensatz bleibt gültig', () => {
		const soll = mockupGrenzen('ORTE_METRICS');
		const metriken = L.wetterPruefMetriken(elementliste(), 'orte');
		const o = overrides(metriken, EIG, soll);
		assert.deepEqual(o.metrics.temperature?.lower, { red: -15, orange: -5, yellow: 0 });
		assert.deepEqual(o.metrics.wind?.upper, { yellow: 30, orange: 50, red: 70 });
		pruefeMockupWerte(o, soll, metriken);
		pruefeGueltig(o);
	});

	test('Ersatz: Metrik ohne Mockup-Wert, Teil-Lücken und leere Seiten bekommen gültige Werte', () => {
		// GIVEN humidity (nicht im Mockup), sunshine lower [null,1,3], cloud_low upper [50,80,null],
		//       freezing_level upper ganz leer (both)
		// WHEN  der Datensatz gebaut wird
		// THEN  jede erlaubte Seite ist vollständig und gültig, Mockup-Werte bleiben stehen
		const soll = { ...mockupGrenzen('TRIP_METRICS'), ...mockupGrenzen('ORTE_METRICS') };
		const o = overrides(['humidity', 'sunshine', 'cloud_low', 'freezing_level'], EIG, mockupGrenzen('TRIP_METRICS'));
		assert.ok(o.metrics.humidity?.upper, 'humidity ohne Mockup-Wert bekommt Ersatz');
		assert.equal(o.metrics.cloud_low?.upper?.yellow, 50);
		assert.equal(o.metrics.cloud_low?.upper?.orange, 80);
		assert.equal(o.metrics.freezing_level?.lower?.yellow, 300);
		pruefeGueltig(o);
		const orte = overrides(['sunshine'], EIG, soll);
		assert.equal(orte.metrics.sunshine?.lower?.orange, 1);
		assert.equal(orte.metrics.sunshine?.lower?.yellow, 3);
		pruefeGueltig(orte);
	});

	test('Payload: wetterPruefPayload(trip, mit_abweichung) reicht die Mockup-Grenzen bis in die Ampel durch', () => {
		// GIVEN WetterPruefQuelle mit dem neuen Feld `grenzen` (Mockup-Werte)
		// WHEN  der Anlege-Payload gebaut wird (das, was an Staging geht)
		// THEN  trägt display_config.ampel die Mockup-Werte (Wirkort der Zusicherung)
		const q = { liste: elementliste(), vorlagen: [], eig: EIG, ortIds: [], datum: '2026-02-23', grenzen: mockupGrenzen('TRIP_METRICS') };
		const p = L.wetterPruefPayload('trip', 'mit_abweichung', q as L.WetterPruefQuelle) as { display_config: { ampel: Overrides } };
		assert.deepEqual(p.display_config.ampel.metrics.temperature?.lower, { red: -10, orange: -3, yellow: 2 });
		assert.equal(p.display_config.ampel.metrics.freezing_level?.lower?.red, -300);
		pruefeGueltig(p.display_config.ampel);
	});
});

// ------------------------------------------------------------------ AC-3 (#3422) EN-Gegenrichtung

describe('#3422 AC-3: EN-Gegenrichtung bildet die Beispielform mit englischem Metriknamen', () => {
	const tgBeispiel = () => {
		nr = 0;
		return [el('Böen in Telegram', '{metrik} in Telegram', '{metrik} in Telegram', { ctx: 'orte' }), beispiel('Böen 51 km/h')].map((e) => ({ ...e, ctx: 'orte' }));
	};

	test('„Gusts 62 km/h“ gilt als erklärt, „Rain 62 km/h“ (falscher Metrikname) bleibt zusätzlich', () => {
		// GIVEN Listen-Element `{wert}` mit text_de „Böen 51 km/h“; Namenspaare aus Schnappschuss + Server-Katalog
		// WHEN  die EN-Gegenrichtung läuft
		// THEN  „Gusts 62 km/h“ ist erklärt, „Rain 62 km/h“ zusätzlich
		const z = finde({ ctx: 'orte', reiter: 'wetter', texte: ['Gusts 62 km/h', 'Rain 62 km/h'] }, tgBeispiel(), [], [], 'en', [], { namenDeEn: namenPaare() });
		assert.deepEqual(zusaetzlicheTexte(z), ['Rain 62 km/h']);
	});

	test('Mechanik ohne Katalog: explizites Paar Böen -> Gusts genügt', () => {
		const z = finde({ ctx: 'orte', reiter: 'wetter', texte: ['Gusts 62 km/h'] }, tgBeispiel(), [], [], 'en', [], { namenDeEn: [{ de: 'Böen', en: 'Gusts' }] });
		assert.deepEqual(zusaetzlicheTexte(z), []);
	});

	test('Gegenprobe: ohne Namenspaare bleibt „Gusts 62 km/h“ zusätzlich (fail-closed)', () => {
		const z = finde({ ctx: 'orte', reiter: 'wetter', texte: ['Gusts 62 km/h'] }, tgBeispiel(), [], [], 'en', [], {});
		assert.deepEqual(zusaetzlicheTexte(z), ['Gusts 62 km/h']);
	});

	test('echte Elementliste (Orte): „Gusts 62 km/h“, „Rain 3.4 mm“ erklärt, „Rain 62 km/h“ zusätzlich', () => {
		// GIVEN die Orte-Elemente der versionierten Elementliste (Beispiele „Böen 51 km/h“, „Regen 1.8 mm“)
		// WHEN  die EN-Gegenrichtung mit den Live-Texten aus dem Rohbericht läuft
		// THEN  sind die Beispiele mit EN-Namen erklärt, der falsche Name nicht
		const z = finde({ ctx: 'orte', reiter: 'wetter', texte: ['Gusts 62 km/h', 'Rain 3.4 mm', 'Rain 62 km/h'] }, elementliste(), [], [], 'en', [], { namenDeEn: namenPaare() });
		assert.deepEqual(zusaetzlicheTexte(z), ['Rain 62 km/h']);
	});
});

// ------------------------------------------------------------------ AC-4 (#3419 Nr. 6) angenommene Beispielwerte

describe('#3419 Nr. 6 AC-4: von der Hinrichtung angenommene Beispielwerte sind in der Gegenrichtung erklärt', () => {
	const liste = () => {
		nr = 0;
		return [zelle('Niederschlag', 'SMS', 'SMS'), beispiel('R1.8@15(2.1@16)')];
	};
	const SEITE = { ctx: 'trip', reiter: 'wetter' };

	test('Hinrichtung: gefundenes `{wert}`-Element trägt den angenommenen Live-Text in `ist`', () => {
		// GIVEN Kästchen „Niederschlag in SMS“ + Beispiel „R1.8@15(2.1@16)“; live echte Prognose „R 0.0-1.3@16“
		// WHEN  die Hinrichtung den Abschnitt bewertet
		// THEN  ist das Beispiel gefunden und `ist` nennt den angenommenen Live-Text
		const l = liste();
		const erg = bewerte(l, ['Niederschlag in SMS', 'R 0.0-1.3@16'], 'de');
		assert.deepEqual(erg.get(l[1].id), { status: 'gefunden', ist: 'R 0.0-1.3@16' });
	});

	test('angenommen + gleiche Seite: „R 0.0-1.3@16“ ist erklärt', () => {
		// GIVEN der Text wurde auf derselben Seite (trip/wetter) als Beispielwert angenommen
		// WHEN  die Gegenrichtung läuft
		// THEN  ist er nicht zusätzlich
		const z = finde({ ...SEITE, texte: ['R 0.0-1.3@16'] }, liste(), [], [], 'de', [], { angenommen: [{ ...SEITE, text: 'R 0.0-1.3@16' }] });
		assert.deepEqual(zusaetzlicheTexte(z), []);
	});

	test('nicht angenommener Text bleibt zusätzlich', () => {
		const z = finde({ ...SEITE, texte: ['R 0.0-1.3@16', 'TH mittel'] }, liste(), [], [], 'de', [], { angenommen: [{ ...SEITE, text: 'R 0.0-1.3@16' }] });
		assert.deepEqual(zusaetzlicheTexte(z), ['TH mittel']);
	});

	test('derselbe Text, aber auf anderer Seite angenommen (anderer ctx bzw. Reiter), bleibt zusätzlich', () => {
		const andererCtx = finde({ ...SEITE, texte: ['R 0.0-1.3@16'] }, liste(), [], [], 'de', [], { angenommen: [{ ctx: 'orte', reiter: 'wetter', text: 'R 0.0-1.3@16' }] });
		assert.deepEqual(zusaetzlicheTexte(andererCtx), ['R 0.0-1.3@16']);
		const andererReiter = finde({ ...SEITE, texte: ['R 0.0-1.3@16'] }, liste(), [], [], 'de', [], { angenommen: [{ ctx: 'trip', reiter: 'zustellung', text: 'R 0.0-1.3@16' }] });
		assert.deepEqual(zusaetzlicheTexte(andererReiter), ['R 0.0-1.3@16']);
	});

	test('werteGegenrichtungAus reicht `zusatz` durch (Weg des Staging-Laufs)', () => {
		type Aus = (b: { ctx: string; reiter: string; anker: L.HubAnker; texte: string[] }, l: ListenElement[], a: L.Ausnahme[], k: string[], s: Sprache, m?: string[], z?: Zusatz) => { zusaetzlich: ZusaetzlichEintrag[] };
		const r = (L.werteGegenrichtungAus as unknown as Aus)({ ...SEITE, anker: { kopf: 1, flaeche: 1 }, texte: ['R 0.0-1.3@16'] }, liste(), [], [], 'de', [], { angenommen: [{ ...SEITE, text: 'R 0.0-1.3@16' }] });
		assert.deepEqual(zusaetzlicheTexte(r.zusaetzlich), []);
	});
});

// ------------------------------------------------------------------ AC-5 (#3419) nachgezogene Elementliste

describe('#3419 AC-5: die neu erzeugte Elementliste enthält den Live-Stand', () => {
	const ws = (ctx: string) =>
		elementliste()
			.filter((e) => e.ctx === ctx && e.reiter === 'wetter' && e.abschnitt === 'was-steht-wo' && e.zustand === 'normal' && e.segment === null)
			.sort((a, b) => a.ordnung - b.ordnung);
	const texte = (ctx: string) => ws(ctx).map((e) => e.text_de);

	test('Trip: Temperatur in SMS ist Sperrzelle „kein Kürzel“ (#3373), kein Kästchen', () => {
		// GIVEN das nachgezogene Mockup  WHEN die Elementliste erzeugt ist
		// THEN  steht in der Temperatur-Zeile „kein Kürzel“ und kein Kästchen „Temperatur in SMS“
		const l = ws('trip');
		const von = l.findIndex((e) => e.text_de === 'Temperatur');
		const bis = l.findIndex((e) => e.text_de === 'Tiefsttemperatur Nacht');
		assert.ok(von >= 0 && bis > von, 'Zeilen Temperatur / Tiefsttemperatur Nacht fehlen');
		const zeile = l.slice(von, bis).map((e) => e.text_de);
		assert.ok(zeile.includes('kein Kürzel'), `Sperrzelle fehlt: ${JSON.stringify(zeile)}`);
		assert.ok(!zeile.includes('Temperatur in SMS'), 'gesperrte Zelle hat kein Kästchen');
	});

	test('Trip: Kürzel-Legende zusammengeführt wie live (#3284), kein FL-Paar', () => {
		const l = ws('trip');
		const t = l.map((e) => e.text_de);
		assert.ok(t.includes('Tagestiefstwert/Tageshöchstwert'), 'Tagestiefstwert/Tageshöchstwert fehlt');
		assert.ok(t.includes('L gefühlt/D gefühlt'), 'L gefühlt/D gefühlt fehlt');
		assert.ok(!l.some((e) => e.rolle === 'bedeutung' && (e.text_de === 'Tagestiefstwert' || e.text_de === 'Tageshöchstwert')), 'getrennte Legende steht noch drin');
		assert.ok(!l.some((e) => e.rolle === 'kuerzel' && e.text_de === 'FL'), '„FL“ entfällt');
	});

	test('Trip: Blöcke Kurz-Zusammenfassung und Großwetterlage (#3036)', () => {
		const t = texte('trip');
		assert.ok(t.includes('Kurz-Zusammenfassung'), 'Kurz-Zusammenfassung fehlt');
		assert.ok(t.includes('Großwetterlage'), 'Großwetterlage fehlt');
	});

	test('Orte: E-Mail-Format-Zeile (#3059) und zusammengeführte Legende', () => {
		const t = texte('orte');
		for (const s of ['E-Mail: Format', 'Ausführlich (HTML)', 'Kompakt (Nur-Text)', 'Tagestiefstwert/Tageshöchstwert']) assert.ok(t.includes(s), `${s} fehlt bei Orten`);
	});

	test('AC-6: Trip-Vorlagen-Picker zeigt „▾ 1 Abweichung“ wie live, Orte bleiben „▾ unverändert“', () => {
		// GIVEN Seed-Trip weicht von „Alpen-Trekking“ genau in Bewölkung ab (Soll-Bild: Bewölkung nicht im Briefing)
		// WHEN  die Elementliste aus dem nachgezogenen Mockup erzeugt ist
		// THEN  enthält trip/wetter/normal Abschnitt „vorlage“ „▾ 1 Abweichung“ und nicht „▾ unverändert“;
		//       bei Orten (Seed = Vorlage „Allgemein“) bleibt „▾ unverändert“
		const vorlage = (ctx: string) =>
			elementliste()
				.filter((e) => e.ctx === ctx && e.reiter === 'wetter' && e.abschnitt === 'vorlage' && e.zustand === 'normal' && e.segment === null)
				.map((e) => e.text_de);
		const trip = vorlage('trip');
		assert.ok(trip.includes('▾ 1 Abweichung'), `Trip: „▾ 1 Abweichung“ fehlt: ${JSON.stringify(trip)}`);
		assert.ok(!trip.includes('▾ unverändert'), 'Trip: „▾ unverändert“ steht noch drin');
		const orte = vorlage('orte');
		assert.ok(orte.includes('▾ unverändert'), `Orte: „▾ unverändert“ fehlt: ${JSON.stringify(orte)}`);
		assert.ok(!orte.includes('▾ 1 Abweichung'), 'Orte: keine Abweichung im Soll');
	});

	test('Orte: Kopf „Orte · Münsterland“ bleibt (Seed zieht nach, nicht das Mockup)', () => {
		const kopf = elementliste().filter((e) => e.ctx === 'orte' && e.abschnitt === 'kopf' && e.zustand === 'normal').map((e) => e.text_de);
		assert.ok(kopf.includes('Orte · Münsterland'), JSON.stringify(kopf));
	});
});

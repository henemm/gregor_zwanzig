// Issue #3154 (Epic #3122): Abnahme-Abgleich der Karte „Was steht wo“.
// Spec: docs/specs/modules/feat_3154_karte_abgleich.md (AC-4 bis AC-11; Test Plan Abgleich/Generator).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test e2e/feat3154_karte_abgleich.test.ts
//
// FESTGELEGTE SCHNITTSTELLEN (Tech-Lead-Entscheidung in RED, Developer baut sie exakt so):
//
//   Abgleich (frontend/e2e/elementliste_abgleich_logik.ts)
//   - Ein Element mit `muster: '{wert}'` (oder `Text {wert}`) steht für einen Beispieltext der Zelle. `erwartung`
//     (DE und EN), `neutralMuster` und `gegenMuster` lassen `{wert}` NICHT auf einen Zellennamen passen
//     (… in/im E-Mail|Telegram|SMS|Stundenverlauf|3-Tages-Ausblick, `Darstellung …`, `Format of …`, EN
//     `… in email|the hourly view|the 3-day outlook`). Fehlt der Beispieltext, ist genau dieses Element
//     abweichend („Text nicht sichtbar“); der folgende Zellenname bleibt `gefunden`, keine Kaskade
//     „Reihenfolge im Abschnitt“ (`bewerteAbschnitt` darf ein `{wert}` nicht über Zellennamen hinweg
//     zuordnen).
//
//   Generator (scripts/elementliste_aus_mockup.ts, `baueElemente`; Browser-Auslese `ausleseImBrowser`)
//   - Neue Roh-Rolle `beispiel` (Beispielzelle `.kex` in E-Mail/Telegram/SMS/Ausblick sowie die SMS-Beispielzeile):
//     `baueElemente` macht daraus `muster: '{wert}'`, `text_en: '{wert}'`, `sprachneutral: true`, `luecke: false`,
//     `i18n_key: null`, `text_de` bleibt das Beispiel. Mehrere Beispiele gleicher Zahlenform werden NICHT
//     zusammengefasst (jedes bleibt ein Element in Dokumentfolge).
//   - „{n} von {max} Zeichen“ steht als EIGENES Element (Roh-Rolle `text`) mit `muster: '{n} von {max} Zeichen'`,
//     `i18n_key: 'wetter.wsw.sms.zeichen'`.
//   - EN-Namen: neuer Schnappschuss `docs/context/einstellungen_neu/daten/metrik_namen.json`
//     (aus src/app/metric_catalog.py, Tabelle der EN-Namen); `ermittleEn` löst damit auf
//     „Regenwahrscheinlichkeit“ -> „Rain probability“, „Tiefe Wolken“ -> „Low clouds“,
//     „UV-Index“ -> „UV index“, „Bewölkung“ -> „Cloud cover“ (`luecke: false`).
//
//   Elementliste (docs/context/einstellungen_neu/elementliste.json = Ausgabe des Generators; er liest das
//   Mockup per Browser (Playwright), daher wird hier die im Repo liegende, neu erzeugte Datei geprüft, die
//   per Prüfsumme an das angeglichene Mockup gebunden ist: elementliste_aktuell.test.ts)
//   - Sechs Fensterzeilen (Nacht, Tages-Tief, Tages-Hoch, gefühlte Nacht/Tages-Tief/Tages-Hoch), Trip, Zustand
//     normal: in E-Mail und 3-Tages-Ausblick KEIN Element „<Zeile> in E-Mail“ / „… im 3-Tages-Ausblick“,
//     stattdessen Sperr-Grund-Texte `keine eigene Spalte` (E-Mail) und `kein Tageswert` (Ausblick) mit
//     Katalogschlüssel `wetter.wsw.grund.keine_eigene_spalte` / `wetter.wsw.grund.kein_tageswert`.
//   - Gewitter: „Darstellung Gewitter in E-Mail: Einfach“ nur in der E-Mail; kein Darstellungs-Knopf in
//     Telegram, Stundenverlauf, 3-Tages-Ausblick.
//   - Orte-SMS: Token-Zeile ohne „+N“ und ohne den Satz „Dafür steht …“.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as L from './elementliste_abgleich_logik.ts';
import * as G from '../../scripts/elementliste_aus_mockup.ts';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..', '..');
const lese = (rel: string) => JSON.parse(readFileSync(join(REPO, rel), 'utf-8'));

type Eintrag = {
	id: string;
	ctx: string;
	reiter: string;
	zustand: string;
	segment: string | null;
	abschnitt: string;
	ordnung: number;
	rolle: string;
	text_de: string;
	muster: string | null;
	i18n_key: string | null;
	text_en: string | null;
	luecke: boolean;
	sprachneutral?: boolean;
};
const liste = (): Eintrag[] => lese('docs/context/einstellungen_neu/elementliste.json').elemente;
const wsw = (ctx: string) =>
	liste()
		.filter((e) => e.abschnitt === 'was-steht-wo' && e.zustand === 'normal' && e.ctx === ctx && e.reiter === 'wetter')
		.sort((a, b) => a.ordnung - b.ordnung);

/** Zellennamen und Darstellungs-Knöpfe, die ein `{wert}` nie verschlucken darf (AC-9). */
const ZELLENNAMEN_DE = [
	'Temperatur in E-Mail',
	'Wind in Telegram',
	'Wind in SMS',
	'Wind im Stundenverlauf',
	'Wind im 3-Tages-Ausblick',
	'Darstellung Wind in E-Mail: Roh'
];
const ZELLENNAMEN_EN = [
	'Temperature in email',
	'Wind in Telegram',
	'Wind in SMS',
	'Wind in the hourly view',
	'Wind in the 3-day outlook',
	'Format of Wind in email: Raw'
];

function el(ordnung: number, text: string, extra: Partial<L.ListenElement> = {}): L.ListenElement {
	return {
		id: `t.${ordnung}`,
		ctx: 'trip',
		reiter: 'wetter',
		zustand: 'normal',
		segment: null,
		abschnitt: 'was-steht-wo',
		ordnung,
		rolle: 'text',
		text_de: text,
		muster: null,
		i18n_key: null,
		text_en: text,
		luecke: false,
		...extra
	};
}
const beispiel = (ordnung: number, text: string) =>
	el(ordnung, text, { muster: '{wert}', text_en: '{wert}', sprachneutral: true });

// ------------------------------------------------------------------ AC-9: {wert} im Abgleich

describe('#3154 AC-9: {wert} mit Negativvorschau gegen Zellennamen', () => {
	test('DE: {wert} passt auf Beispieltexte, nie auf einen Zellennamen', () => {
		const re = L.erwartung(beispiel(1, 'Temp 14.4'), 'de');
		assert.ok(re);
		for (const ok of ['Temp 14.3', 'T 9.6-15.2', 'D10/15', 'W30@10(43@16)', '● gelb']) assert.ok(re.test(ok), `soll passen: ${ok}`);
		for (const nein of ZELLENNAMEN_DE) assert.ok(!re.test(nein), `darf Zellennamen nicht verschlucken: ${nein}`);
	});

	test('DE: Muster „Temp {wert}“ passt auf „Temp 14.3“, nicht auf einen Zellennamen dahinter', () => {
		const re = L.erwartung(el(1, 'Temp 14.4', { muster: 'Temp {wert}' }), 'de');
		assert.ok(re);
		assert.ok(re.test('Temp 14.3'));
		assert.ok(!re.test('Temp in E-Mail'));
		assert.ok(!re.test('Temp im 3-Tages-Ausblick'));
	});

	test('EN: sprachneutrales {wert} passt auf Beispieltexte, nie auf einen Zellennamen', () => {
		const re = L.erwartung(beispiel(1, 'Temp 14.4'), 'en');
		assert.ok(re);
		for (const ok of ['Temp 14.3', 'T 9.6-15.2', 'D10/15']) assert.ok(re.test(ok), `soll passen: ${ok}`);
		for (const nein of ZELLENNAMEN_EN) assert.ok(!re.test(nein), `darf Zellennamen nicht verschlucken: ${nein}`);
	});

	test('Gegenrichtung: {wert} erklärt keinen Zellennamen als „bekannt“', () => {
		const l = [beispiel(1, 'Temp 14.4')];
		const zus = L.findeZusaetzliche({ ctx: 'trip', reiter: 'wetter', texte: ['Temp 14.3', 'Wind in Telegram', 'Darstellung Wind in E-Mail: Roh'] }, l, [], [], 'de');
		assert.deepEqual(zus.map((z) => z.text).sort(), ['Darstellung Wind in E-Mail: Roh', 'Wind in Telegram']);
	});

	// Aufbau wie die Live-Karte: Zellenname, dann Beispieltext. Das Beispiel der Telegram-Zelle fehlt (Einfach, kein Text).
	const elemente = (): L.ListenElement[] => [
		el(1, 'Temperatur'),
		el(2, 'Temperatur in E-Mail', { rolle: 'eingabe', text_en: 'Temperature in email' }),
		beispiel(3, 'Temp 14.4'),
		el(4, 'Temperatur in Telegram', { rolle: 'eingabe', text_en: 'Temperature in Telegram' }),
		beispiel(5, 'T 9.6-15.2'),
		el(6, 'Temperatur in SMS', { rolle: 'eingabe', text_en: 'Temperature in SMS' }),
		beispiel(7, 'D10/15')
	];

	test('fehlender Beispieltext: genau eine Abweichung, keine Reihenfolge-Kaskade (DE)', () => {
		const texte = ['Temperatur', 'Temperatur in E-Mail', 'Temp 14.3', 'Temperatur in Telegram', 'Temperatur in SMS', 'D10/15'];
		// Beispiel Nr. 5 fehlt: ein {wert} darf nicht über den Zellennamen „Temperatur in SMS“ hinweg „D10/15“ nehmen.
		const erg = L.bewerteAbschnitt(elemente(), { marker: true, texte }, 'de', 'was-steht-wo');
		const abw = [...erg.entries()].filter(([, e]) => e.status !== 'gefunden');
		assert.equal(abw.length, 1, `genau eine Abweichung erwartet, ist: ${JSON.stringify(abw)}`);
		assert.equal(abw[0][0], 't.5');
		assert.notEqual(abw[0][1].grund, 'Reihenfolge im Abschnitt');
		assert.equal(erg.get('t.6')?.status, 'gefunden');
		assert.equal(erg.get('t.7')?.status, 'gefunden');
	});

	test('fehlender Beispieltext: genau eine Abweichung, keine Reihenfolge-Kaskade (EN)', () => {
		const texte = ['Temperature', 'Temperature in email', 'Temp 14.3', 'Temperature in Telegram', 'Temperature in SMS', 'D10/15'];
		const en = elemente().map((e) => (e.sprachneutral ? e : { ...e, text_en: e.text_de.replace('Temperatur', 'Temperature').replace('in E-Mail', 'in email') }));
		const erg = L.bewerteAbschnitt(en, { marker: true, texte }, 'en', 'was-steht-wo');
		const abw = [...erg.entries()].filter(([, e]) => e.status !== 'gefunden');
		assert.equal(abw.length, 1, `genau eine Abweichung erwartet, ist: ${JSON.stringify(abw)}`);
		assert.equal(abw[0][0], 't.5');
		assert.notEqual(abw[0][1].grund, 'Reihenfolge im Abschnitt');
	});

	test('alle Beispiele vorhanden: alles gefunden (Gegenprobe, DE)', () => {
		const texte = ['Temperatur', 'Temperatur in E-Mail', 'Temp 14.3', 'Temperatur in Telegram', 'T 9.6-15.2', 'Temperatur in SMS', 'D10/15'];
		const erg = L.bewerteAbschnitt(elemente(), { marker: true, texte }, 'de', 'was-steht-wo');
		assert.deepEqual([...erg.values()].map((e) => e.status), Array(7).fill('gefunden'));
	});
});

// ------------------------------------------------------------------ AC-7: Generator, reine Funktion

describe('#3154 AC-7/AC-10: Generator (baueElemente, ermittleEn)', () => {
	const katalog = () => G.ladeKatalog(G.STANDARD_MESSAGES);
	const gruppe = (roh: G.Roh[]): G.Rohgruppe[] => [{ ctx: 'trip', reiter: 'wetter', zustand: 'normal', segment: null, roh }];
	const r = (rolle: string, text: string): G.Roh => ({ abschnitt: 'was-steht-wo', rolle, text });

	test('Beispielzelle wird {wert}-Muster, Zeichenzahl ein eigenes Element', () => {
		const e = G.baueElemente(
			gruppe([r('beispiel', 'Temp 14.4'), r('beispiel', 'W 20-38@15'), r('text', 'SMS-Beispiel:'), r('beispiel', 'O1 D19 W30@10(43@16)'), r('text', '123 von 160 Zeichen')]),
			katalog()
		);
		assert.equal(e.length, 5, 'Beispiele werden nie zusammengefasst');
		for (const i of [0, 1, 3]) {
			assert.equal(e[i].muster, '{wert}', `Element ${i}`);
			assert.equal(e[i].text_en, '{wert}');
			assert.equal(e[i].sprachneutral, true);
			assert.equal(e[i].luecke, false);
		}
		assert.equal(e[0].text_de, 'Temp 14.4');
		assert.equal(e[4].muster, '{n} von {max} Zeichen');
		assert.equal(e[4].i18n_key, 'wetter.wsw.sms.zeichen');
	});

	test('Beispiel in Dokumentfolge: Zahlenform gleicher Beispiele bleibt je ein Element', () => {
		const e = G.baueElemente(gruppe([r('beispiel', 'W 20-38@15'), r('beispiel', 'W 21-40@16')]), katalog());
		assert.equal(e.length, 2);
	});

	test('ermittleEn: die vier bisherigen EN-Lücken haben einen EN-Namen aus dem Schnappschuss', () => {
		assert.ok(existsSync(join(REPO, 'docs/context/einstellungen_neu/daten/metrik_namen.json')), 'Schnappschuss metrik_namen.json fehlt');
		const soll: Record<string, string> = {
			Regenwahrscheinlichkeit: 'Rain probability',
			'Tiefe Wolken': 'Low clouds',
			'UV-Index': 'UV index',
			Bewölkung: 'Cloud cover'
		};
		for (const [de, en] of Object.entries(soll)) {
			const erg = G.ermittleEn(de, katalog());
			assert.equal(erg.luecke, false, `${de}: weiter EN-Lücke`);
			assert.equal(erg.text_en, en, de);
		}
	});
});

// ------------------------------------------------------------------ Elementliste (Ausgabe des Generators)

describe('#3154 AC-7: SMS-Beispiel und Zeichenzahl in der erzeugten Elementliste', () => {
	for (const ctx of ['trip', 'orte']) {
		test(`${ctx}: Zeichenzahl ist ein eigenes Element, das SMS-Beispiel ein {wert}-Muster`, () => {
			const es = wsw(ctx);
			const zeichen = es.filter((e) => /\d+ von \d+ Zeichen/.test(e.text_de));
			assert.equal(zeichen.length, 1, `${ctx}: genau ein Zeichenzahl-Element`);
			assert.equal(zeichen[0].text_de.replace(/\d+/g, 'N'), 'N von N Zeichen', 'nur die Zeichenzahl, kein SMS-Beispiel im selben Text');
			assert.equal(zeichen[0].muster, '{n} von {max} Zeichen');
			const i = es.indexOf(zeichen[0]);
			const davor = es[i - 1];
			assert.equal(davor.muster, '{wert}', `${ctx}: SMS-Beispielzeile direkt vor der Zeichenzahl ist {wert}`);
			assert.ok(davor.text_de.length >= 10, 'echtes Beispiel');
		});
	}

	test('Beispielzellen der Tabelle sind {wert}-Muster (E-Mail, Telegram, SMS)', () => {
		const es = wsw('trip');
		for (const text of ['Temp 14.4', 'T 9.6-15.2', 'D10/15']) {
			const e = es.find((x) => x.text_de === text);
			assert.ok(e, `Beispielzelle „${text}“ fehlt in der Elementliste`);
			assert.equal(e.muster, '{wert}', text);
		}
	});
});

describe('#3154 AC-4: gesperrte Fensterzellen tragen den Sperr-Grund', () => {
	const FENSTER = [
		'Tiefsttemperatur Nacht',
		'Tages-Tiefsttemperatur (Gehzeit)',
		'Tages-Höchsttemperatur (Gehzeit)',
		'Gefühlte Tiefsttemperatur Nacht',
		'Gefühlte Tages-Tiefsttemperatur (Gehzeit)',
		'Gefühlte Tages-Höchsttemperatur (Gehzeit)'
	];

	test('sechs Zeilen: keine Haken-Elemente für E-Mail und 3-Tages-Ausblick, aber Telegram und SMS bleiben', () => {
		const texte = new Set(wsw('trip').map((e) => e.text_de));
		for (const n of FENSTER) {
			assert.ok(!texte.has(`${n} in E-Mail`), `${n}: E-Mail-Haken statt Sperre`);
			assert.ok(!texte.has(`${n} im 3-Tages-Ausblick`), `${n}: Ausblick-Haken statt Sperre`);
			assert.ok(texte.has(`${n} in Telegram`), `${n}: Telegram-Haken fehlt`);
			assert.ok(texte.has(`${n} in SMS`), `${n}: SMS-Haken fehlt`);
		}
	});

	test('je sechs Sperr-Grund-Elemente mit Katalogschlüssel, in Zeilenfolge hinter dem Zeilennamen', () => {
		const es = wsw('trip');
		const email = es.filter((e) => e.text_de === 'keine eigene Spalte');
		const ausblick = es.filter((e) => e.text_de === 'kein Tageswert');
		assert.equal(email.length, 6);
		assert.equal(ausblick.length, 6);
		for (const e of email) assert.equal(e.i18n_key, 'wetter.wsw.grund.keine_eigene_spalte');
		for (const e of ausblick) assert.equal(e.i18n_key, 'wetter.wsw.grund.kein_tageswert');
		for (const n of FENSTER) {
			const name = es.find((e) => e.text_de === n);
			assert.ok(name, `${n}: Zeilenname fehlt`);
			const folge = es.filter((e) => e.ordnung > name.ordnung).slice(0, 12).map((e) => e.text_de);
			assert.ok(folge.includes('keine eigene Spalte') && folge.includes('kein Tageswert'), `${n}: Sperr-Gründe nicht in der eigenen Zeile`);
		}
	});
});

describe('#3154 AC-5: Gewitter hat die Einfach-Darstellung nur in der E-Mail', () => {
	for (const ctx of ['trip', 'orte']) {
		test(`${ctx}: Darstellungs-Knopf Gewitter nur in der E-Mail`, () => {
			const knoepfe = wsw(ctx)
				.filter((e) => e.rolle === 'knopf' && e.text_de.startsWith('Darstellung Gewitter '))
				.map((e) => e.text_de);
			assert.equal(knoepfe.length, 1, `${ctx}: ${JSON.stringify(knoepfe)}`);
			assert.match(knoepfe[0], /^Darstellung Gewitter in E-Mail: /);
		});
	}

	test('Gegenprobe: andere Metriken behalten ihre Darstellungs-Knöpfe in Telegram', () => {
		const wind = wsw('trip').filter((e) => e.rolle === 'knopf' && e.text_de.startsWith('Darstellung Wind in Telegram'));
		assert.equal(wind.length, 1);
	});
});

describe('#3154 AC-6: Orte-SMS als Token-Zeile (ADR-0125)', () => {
	test('keine „+N“-Zeile und kein Satz „Dafür steht …“, SMS-Beispiel in Token-Form', () => {
		const es = wsw('orte');
		assert.ok(!es.some((e) => e.text_de.includes('Dafür steht')), 'Satz „Dafür steht +N je Ort“ ist noch da');
		assert.ok(!es.some((e) => /^Orte \d/.test(e.text_de) || / \+\d/.test(e.text_de)), 'Alt-Form „Orte 18.11.: … +5“ ist noch da');
		const zeichen = es.find((e) => /\d+ von \d+ Zeichen/.test(e.text_de));
		assert.ok(zeichen);
		const sms = es[es.indexOf(zeichen) - 1];
		assert.match(sms.text_de, /^O1 D\d+ /, 'Token-Zeile beginnt mit O1 D…');
	});
});

describe('#3154 AC-10/AC-11: EN-Namen und Besitzer in der erzeugten Liste', () => {
	test('keine EN-Lücke bei den vier Zeilennamen', () => {
		for (const ctx of ['trip', 'orte']) {
			for (const e of wsw(ctx).filter((x) => ['Regenwahrscheinlichkeit', 'Tiefe Wolken', 'UV-Index', 'Bewölkung'].includes(x.text_de))) {
				assert.equal(e.luecke, false, `${ctx}: ${e.text_de}`);
				assert.ok(e.text_en, `${ctx}: ${e.text_de}`);
			}
		}
	});

	test('die zwei veralteten Besitzer-Einträge „was-steht-wo“ (noch nicht gebaut) sind entfernt', () => {
		const text = readFileSync(join(REPO, 'docs/context/einstellungen_neu/elementliste_besitzer.json'), 'utf-8');
		const b = JSON.parse(text) as { eintraege?: Array<Record<string, unknown>> } | Array<Record<string, unknown>>;
		const alle = Array.isArray(b) ? b : (b.eintraege ?? Object.values(b).flat());
		const alt = (alle as Array<Record<string, unknown>>).filter((x) => x.abschnitt === 'was-steht-wo' && /noch nicht gebaut/.test(JSON.stringify(x)));
		assert.equal(alt.length, 0);
	});
});

// Issue #2913 Scheibe (c), Fix-Loop 2 — Elementlisten-Abgleich: EN-Muster (C5), Kontodaten-Chips (C5),
// freigegebene Abweichungen (Trip-Radar-Freigabe abgelöst durch #2800 AC-9), Sprachprüfung (C3). Reine Logik, ohne Browser.
// Spec: docs/specs/modules/feat_2913_scheibe_c_wetter_rest.md
//
//   cd frontend && npm test -- src/lib/__tests__/elementliste_abgleich_fixloop2.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	erwartung,
	bewerteAbschnitt,
	istKontoChip,
	leseFreigaben,
	wendeFreigabenAn,
	sprachGrund,
	wiederherzustellendeSprache,
	stelleSpracheWieder,
	baueBericht,
	exitCode,
	abschluss,
	berichtAlsMarkdown,
	type Ergebnis,
	type ListenElement
} from '../../../e2e/elementliste_abgleich_logik.ts';
import { ladeKatalog, chipEn, ermittleEn, CHIP_SCHLUESSEL } from '../../../../scripts/elementliste_aus_mockup.ts';

const REPO = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..', '..');
const katalog = ladeKatalog(join(REPO, 'frontend/src/lib/i18n/messages'));
const FREIGABEN_TEXT = readFileSync(join(REPO, 'docs/context/einstellungen_neu/elementliste_freigaben.json'), 'utf8');

const el = (id: string, ordnung: number, text_de: string, extra: Partial<ListenElement> = {}): ListenElement => ({
	id,
	ctx: 'trip',
	reiter: 'wetter',
	zustand: 'normal',
	segment: null,
	abschnitt: 'metriken',
	ordnung,
	rolle: 'text',
	text_de,
	muster: null,
	i18n_key: null,
	text_en: null,
	luecke: false,
	...extra
});
const chip = (id: string, ordnung: number, name: string) =>
	el(id, ordnung, `+ ${name}`, { rolle: 'chip', muster: '+ {metrik}', i18n_key: CHIP_SCHLUESSEL, text_en: '+ {metrik}' });

describe('C5: EN-Erwartung mit Platzhalter ist ein Muster', () => {
	test('„Alert when rain is coming towards {orte} …“ passt auf beliebige Orte, aber nicht auf Deutsch', () => {
		const e = el('r', 1, 'Alarm, wenn …', { text_en: 'Alert when rain is coming towards {orte} within the next hour' });
		const re = erwartung(e, 'en')!;
		assert.ok(re.test('Alert when rain is coming towards your places within the next hour'));
		assert.ok(!re.test('Alarm, wenn in der nächsten Stunde Regen auf deine Orte zukommt'));
	});
	test('EN ohne Platzhalter bleibt exakt (Zahlen frei)', () => {
		const re = erwartung(el('x', 1, 'Zustellung', { text_en: 'Delivery' }), 'en')!;
		assert.ok(re.test('Delivery'));
		assert.ok(!re.test('Delivery options'));
	});
});

describe('C5: Generator — Chips als Muster, keine DE-Werte im EN', () => {
	test('Chip „+ Windrichtung“ → Muster „+ {metrik}“ mit EN-Muster, kein Lückenposten', () => {
		const r = chipEn('chip', '+ Windrichtung', katalog)!;
		assert.equal(r.i18n_key, CHIP_SCHLUESSEL);
		assert.equal(r.muster, '+ {metrik}');
		assert.equal(r.text_en, '+ {metrik}');
		assert.equal(r.luecke, false);
	});
	test('nur Rolle chip, nur mit Präfix und Namen', () => {
		assert.equal(chipEn('knopf', '+ Windrichtung', katalog), null);
		assert.equal(chipEn('chip', 'Windrichtung', katalog), null);
		assert.equal(chipEn('chip', '+ ', katalog), null);
	});
	test('Musterabgleich setzt keine deutschen Werte in den EN-Text', () => {
		const r = ermittleEn('Alarm, wenn in der nächsten Stunde Regen auf deine Etappe zukommt', katalog);
		assert.equal(r.i18n_key, 'wetter.radar.beschreibung');
		assert.match(r.text_en ?? '', /\{orte\}/);
		assert.doesNotMatch(r.text_en ?? '', /Etappe/);
	});
	test('eingecheckte Liste: kein EN-Text enthält den deutschen Füllwert eines Musters', () => {
		const liste: ListenElement[] = JSON.parse(readFileSync(join(REPO, 'docs/context/einstellungen_neu/elementliste.json'), 'utf8')).elemente;
		const chips = liste.filter((e) => e.rolle === 'chip' && e.text_de.startsWith('+ '));
		assert.ok(chips.length > 0, 'keine Chips in der Liste');
		for (const c of chips) assert.equal(c.text_en, '+ {metrik}', `${c.id}: ${c.text_en}`);
		const rad = liste.find((e) => e.i18n_key === 'wetter.radar.beschreibung');
		assert.ok(rad && rad.text_en && /\{orte\}/.test(rad.text_en), JSON.stringify(rad));
	});
});

describe('C5: Kontodaten-Chips — Präfix + Vorhandensein, nicht Menge/Reihenfolge', () => {
	const liste = [el('t', 1, 'Nicht im Briefing:'), chip('c1', 2, 'Windrichtung'), chip('c2', 3, 'Sichtweite'), chip('c3', 4, 'Taupunkt')];
	test('DE: exakt sichtbarer Chip gefunden, fehlender nicht_pruefbar mit Grund, Reihenfolge egal', () => {
		const r = bewerteAbschnitt(liste, { marker: true, texte: ['Nicht im Briefing:', '+ Taupunkt', '+ Luftdruck'] }, 'de', 'metriken');
		assert.equal(r.get('t')!.status, 'gefunden');
		assert.equal(r.get('c3')!.status, 'gefunden');
		assert.equal(r.get('c1')!.status, 'gefunden', 'erstes Chip-Element steht für die Chip-Zeile');
		assert.match(r.get('c1')!.grund ?? '', /Kontodaten/);
		assert.equal(r.get('c2')!.status, 'nicht_pruefbar');
		assert.match(r.get('c2')!.grund ?? '', /Kontodaten/);
	});
	test('ohne jeden Chip: alle Chip-Elemente abweichend (nicht still grün)', () => {
		const r = bewerteAbschnitt(liste, { marker: true, texte: ['Nicht im Briefing:'] }, 'de', 'metriken');
		for (const id of ['c1', 'c2', 'c3']) assert.equal(r.get(id)!.status, 'abweichend', id);
	});
	test('ohne Abschnitt-Haken: Chips abweichend', () => {
		const r = bewerteAbschnitt(liste, { marker: false, texte: ['+ Taupunkt'] }, 'de', 'metriken');
		assert.equal(r.get('c3')!.status, 'abweichend');
	});
	// #3241: EN prüft Einzelchips über die Namenspaare (vorher nur das Muster, Grund „nur das Muster“).
	test('EN: Muster vorhanden ⇒ Chip-Zeile gefunden, nicht sichtbare Einzelchips nicht_pruefbar; Chips zählen nicht in die Reihenfolge', () => {
		const en = [el('t', 1, 'Nicht im Briefing:', { text_en: 'Not in the briefing:' }), chip('c1', 2, 'Windrichtung'), chip('c2', 3, 'Sichtweite')];
		const paare = [{ de: 'Windrichtung', en: 'Wind direction' }, { de: 'Sichtweite', en: 'Visibility' }];
		const r = bewerteAbschnitt(en, { marker: true, texte: ['+ Dew point', 'Not in the briefing:'] }, 'en', 'metriken', paare);
		assert.equal(r.get('t')!.status, 'gefunden');
		assert.equal(r.get('c1')!.status, 'gefunden');
		assert.equal(r.get('c2')!.status, 'nicht_pruefbar');
		assert.match(r.get('c2')!.grund ?? '', /„\+ Visibility“ ist in diesem Konto kein Chip/);
	});
	test('istKontoChip nur für chip mit Platzhalter-Muster', () => {
		assert.equal(istKontoChip(chip('c', 1, 'X')), true);
		assert.equal(istKontoChip(el('k', 1, '+ Spalte', { rolle: 'knopf', muster: '+ {x}' })), false);
		assert.equal(istKontoChip(el('k', 1, '+ Spalte', { rolle: 'chip' })), false);
	});
});

// abgelöst durch #2800 (feat_2800_trip_radar_alarm AC-9): die Freigabe „Trip ohne Radar" (feat_2913 AC-3)
// entfällt, der Trip-Reiter Wetter hat die Radar-Zeile. Der Freigabe-MECHANISMUS bleibt geprüft, aber an
// einer Muster-Freigabe (gleiche Form wie die entfernte), nicht mehr an der echten Datei.
describe('Trip-Radar: keine freigegebene Abweichung mehr (#2800 AC-9)', () => {
	const freigaben = leseFreigaben(FREIGABEN_TEXT);
	const radarTitel = el('rt', 4, 'Radar-Regen', { abschnitt: 'warnungen-radar', i18n_key: 'wetter.radar.titel' });
	const radarText = el('rb', 5, 'Alarm …', { abschnitt: 'warnungen-radar', i18n_key: 'wetter.radar.beschreibung' });
	const warn = el('w', 1, 'Amtliche Warnungen', { abschnitt: 'warnungen-radar', i18n_key: 'alarme.gruppe.amtlich' });
	const alle = [radarTitel, radarText, warn];
	const ab = (): Ergebnis => ({ status: 'abweichend', grund: 'Text nicht sichtbar', ist: 'nicht gefunden' });
	const ELEMENTE = (JSON.parse(readFileSync(join(REPO, 'docs/context/einstellungen_neu/elementliste.json'), 'utf8')) as { elemente: ListenElement[] }).elemente;

	test('Datei: jede Freigabe mit Grund und Spec-Verweis (Liste darf leer sein)', () => {
		assert.ok(freigaben.length <= 5, 'Liste klein halten');
		for (const f of freigaben) assert.match(f.spec, /docs\/specs\/.+AC-\d+/);
		assert.throws(() => leseFreigaben('{"freigaben":[{"ctx":"trip","reiter":"wetter","abschnitt":"x","i18n_keys":["a"],"grund":"","spec":"s"}]}'), /grund/);
	});
	test('Datei: keine Freigabe deckt die Trip-Radar-Zeile mehr ab', () => {
		const trip = freigaben.filter(
			(f) => f.ctx === 'trip' && f.reiter === 'wetter' && f.abschnitt === 'warnungen-radar' && f.i18n_keys.some((k) => k.startsWith('wetter.radar.'))
		);
		assert.deepEqual(trip, [], `#2800 AC-9: Freigabe „Trip ohne Radar" besteht noch: ${JSON.stringify(trip)}`);
	});
	test('fehlende Trip-Radarzeilen ⇒ abweichend (nicht mehr freigegeben); Warnungen ebenso', () => {
		const erg = new Map<string, Ergebnis>(alle.map((e) => [e.id, ab()]));
		const r = wendeFreigabenAn(alle, erg, freigaben);
		assert.equal(r.get('rt')!.status, 'abweichend', '#2800 AC-9: fehlender Radar-Titel im Trip wird noch freigegeben');
		assert.equal(r.get('rb')!.status, 'abweichend', '#2800 AC-9: fehlender Radar-Text im Trip wird noch freigegeben');
		assert.equal(r.get('w')!.status, 'abweichend');
	});
	test('Elementliste verlangt im Trip-Kontext die Radar-Zeile (Titel + „deine Etappe") in jedem Zustand', () => {
		const tripRadar = ELEMENTE.filter((e) => e.ctx === 'trip' && e.reiter === 'wetter' && e.abschnitt === 'warnungen-radar');
		const zustaende = [...new Set(tripRadar.map((e) => e.zustand))];
		assert.ok(zustaende.length >= 1, 'Messaufbau: keine Trip-Elemente in warnungen-radar');
		for (const z of zustaende) {
			const imZustand = tripRadar.filter((e) => e.zustand === z);
			assert.ok(imZustand.some((e) => e.i18n_key === 'wetter.radar.titel'), `Zustand ${z}: Radar-Titel fehlt`);
			assert.ok(
				imZustand.some((e) => e.i18n_key === 'wetter.radar.beschreibung' && /deine Etappe/.test(e.text_de)),
				`Zustand ${z}: Radar-Text „deine Etappe" fehlt`
			);
		}
	});
});

describe('Freigabe-Mechanismus (Muster-Freigabe, unabhängig von der echten Datei)', () => {
	const freigaben = leseFreigaben(
		JSON.stringify({
			freigaben: [
				{
					ctx: 'trip',
					reiter: 'wetter',
					abschnitt: 'warnungen-radar',
					i18n_keys: ['wetter.radar.titel', 'wetter.radar.beschreibung'],
					grund: 'Muster-Abweichung (#9999)',
					spec: 'docs/specs/modules/muster.md AC-1'
				}
			]
		})
	);
	const radarTitel = el('rt', 4, 'Radar-Regen', { abschnitt: 'warnungen-radar', i18n_key: 'wetter.radar.titel' });
	const radarText = el('rb', 5, 'Alarm …', { abschnitt: 'warnungen-radar', i18n_key: 'wetter.radar.beschreibung' });
	const warn = el('w', 1, 'Amtliche Warnungen', { abschnitt: 'warnungen-radar', i18n_key: 'alarme.gruppe.amtlich' });
	const orteRadar = { ...radarTitel, id: 'ort', ctx: 'orte' };
	const alle = [radarTitel, radarText, warn, orteRadar];
	const ab = (): Ergebnis => ({ status: 'abweichend', grund: 'Text nicht sichtbar', ist: 'nicht gefunden' });

	test('gedeckte Elemente ⇒ freigegeben mit Grund und Spec; nicht gedeckte bleiben abweichend', () => {
		const erg = new Map<string, Ergebnis>(alle.map((e) => [e.id, ab()]));
		const r = wendeFreigabenAn(alle, erg, freigaben);
		assert.equal(r.get('rt')!.status, 'freigegeben');
		assert.equal(r.get('rb')!.status, 'freigegeben');
		assert.match(r.get('rt')!.grund ?? '', /#9999/);
		assert.match(r.get('rt')!.grund ?? '', /AC-1/);
		assert.equal(r.get('w')!.status, 'abweichend');
		assert.equal(r.get('ort')!.status, 'abweichend', 'anderer Kontext ist nicht freigegeben');
	});
	test('F004: dieselben Schlüssel in einem anderen Abschnitt oder Reiter werden NICHT freigegeben', () => {
		const anderswo = { ...radarTitel, id: 'a1', abschnitt: 'metriken' };
		const andererReiter = { ...radarText, id: 'a2', reiter: 'zustellung' };
		const erg = new Map<string, Ergebnis>([
			['a1', ab()],
			['a2', ab()]
		]);
		const r = wendeFreigabenAn([anderswo, andererReiter], erg, freigaben);
		assert.equal(r.get('a1')!.status, 'abweichend');
		assert.equal(r.get('a2')!.status, 'abweichend');
	});
	test('gefunden bleibt gefunden, nicht_pruefbar bleibt nicht_pruefbar', () => {
		const erg = new Map<string, Ergebnis>([
			['rt', { status: 'gefunden' }],
			['rb', { status: 'nicht_pruefbar', grund: 'x' }]
		]);
		const r = wendeFreigabenAn([radarTitel, radarText], erg, freigaben);
		assert.equal(r.get('rt')!.status, 'gefunden');
		assert.equal(r.get('rb')!.status, 'nicht_pruefbar');
	});
	test('Bericht zählt freigegeben getrennt; strict besteht damit, nicht aber mit abweichend', () => {
		const erg = wendeFreigabenAn([radarTitel, warn], new Map([['rt', ab()], ['w', { status: 'gefunden' as const }]]), freigaben);
		const b = baueBericht([radarTitel, warn], erg);
		assert.deepEqual(b.zaehler, { gefunden: 1, abweichend: 0, nicht_pruefbar: 0, freigegeben: 1, zusaetzlich: 0 });
		assert.equal(exitCode(b, { strict: true }), 0);
		assert.match(abschluss(b, [radarTitel, warn], { strict: true }).meldung, /freigegeben 1/);
		assert.match(berichtAlsMarkdown(b), /\| freigegeben \|/);
		const b2 = baueBericht([radarTitel, warn], new Map([['rt', ab()], ['w', { status: 'gefunden' as const }]]));
		assert.equal(exitCode(b2, { strict: true }), 1);
	});
	test('freigegeben ohne Grund wird abgelehnt', () => {
		assert.throws(() => baueBericht([radarTitel], new Map([['rt', { status: 'freigegeben' as const }]])), /ohne Grund/);
	});
});

describe('F005: Profilsprache zurückstellen — vorheriger Wert, nie still', () => {
	const antwort = (status: number) => ({ ok: () => status >= 200 && status < 300, status: () => status });
	const mitStummemFehlerlog = async <T>(f: () => Promise<T>): Promise<{ wert: T; log: string[] }> => {
		const log: string[] = [];
		const orig = console.error;
		console.error = (...a: unknown[]) => void log.push(a.map(String).join(' '));
		try {
			return { wert: await f(), log };
		} finally {
			console.error = orig;
		}
	};
	test('setzt genau die Sprache VOR dem Lauf (Lauf in en, vorher de ⇒ PUT de)', async () => {
		const gesendet: unknown[] = [];
		const vorher = wiederherzustellendeSprache({ language: 'de' });
		const r = await stelleSpracheWieder(async (d) => (gesendet.push(d), antwort(200)), vorher);
		assert.deepEqual(r, { ok: true });
		assert.deepEqual(gesendet, [{ language: 'de' }]);
	});
	test('vorher en ⇒ PUT en', async () => {
		const gesendet: unknown[] = [];
		await stelleSpracheWieder(async (d) => (gesendet.push(d), antwort(204)), 'en');
		assert.deepEqual(gesendet, [{ language: 'en' }]);
	});
	test('HTTP-Fehler ⇒ ok false, Meldung nennt Sprache und Status, console.error', async () => {
		const { wert, log } = await mitStummemFehlerlog(() => stelleSpracheWieder(async () => antwort(500), 'de'));
		assert.equal(wert.ok, false);
		assert.match(!wert.ok ? wert.meldung : '', /NICHT auf „de“.*HTTP 500/);
		assert.equal(log.length, 1);
		assert.match(log[0], /HTTP 500/);
	});
	test('Ausnahme (Netz) ⇒ ok false mit Meldung, wird nicht verschluckt', async () => {
		const { wert, log } = await mitStummemFehlerlog(() =>
			stelleSpracheWieder(async () => {
				throw new Error('socket hang up');
			}, 'de')
		);
		assert.equal(wert.ok, false);
		assert.match(!wert.ok ? wert.meldung : '', /socket hang up/);
		assert.equal(log.length, 1);
	});
});

describe('C3: Sprache der Seite', () => {
	test('html lang passt ⇒ kein Grund; Abweichung ⇒ Grund', () => {
		assert.equal(sprachGrund('en', 'en'), null);
		assert.equal(sprachGrund('en', 'en-GB'), null);
		assert.equal(sprachGrund('de', 'de'), null);
		assert.match(sprachGrund('en', 'de') ?? '', /„de“ statt „en“/);
		assert.match(sprachGrund('en', null) ?? '', /unbekannt/);
	});
	test('wiederherzustellende Profilsprache: en bleibt en, sonst de', () => {
		assert.equal(wiederherzustellendeSprache({ language: 'en' }), 'en');
		assert.equal(wiederherzustellendeSprache({ language: 'de' }), 'de');
		assert.equal(wiederherzustellendeSprache({}), 'de');
		assert.equal(wiederherzustellendeSprache(null), 'de');
	});
});

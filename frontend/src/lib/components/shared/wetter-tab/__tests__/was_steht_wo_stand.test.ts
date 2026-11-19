// TDD RED — Issue #3122 Scheibe B3b: Aufbau des gespeicherten `placements`-Objekts aus den Ereignissen der
// Karte „Was steht wo“ und der Grundauswahl („−“/„+“). Spec docs/specs/modules/feat_3122_was_steht_wo.md
// Teil A Nr. 1 (Speicherformat), Teil B Nr. 13 (Speichern); AC-23 bis AC-25, AC-29, AC-32.
//
// Reine Logik, ohne DOM: shared/wetter-tab/wasStehtWoStand.ts.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/was_steht_wo_stand.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
	mitHaken,
	mitFormat,
	mitReihenfolge,
	mitAusblick,
	ohneZeile,
	mitZeileHinten,
	mitGrundauswahl,
	antwortMitHaken,
	antwortMitFormat,
	antwortMitReihenfolge,
	antwortOhneZeile,
	type Placements,
	type PlacementsAntwort
} from '../wasStehtWoStand.ts';

const gespeichert = (): Placements => ({
	version: 1,
	rows: [
		{ metric_id: 'temperature', places: { sms: false } },
		{ metric_id: 'wind', places: { email: true }, formats: { email: 'simplified', telegram: 'raw' }, zukunft: { x: 1 } },
		{ metric_id: 'gust' }
	],
	outlook_reports: ['evening'],
	unbekannt: 'bleibt'
});
const ANZEIGE = ['temperature', 'wind', 'gust', 'precipitation'];

describe('Haken (Teil A Nr. 1: fehlt = angehakt, false = abgewählt)', () => {
	test('Abwahl schreibt false genau an dieser Stelle, sonst bleibt alles gleich', () => {
		const p = mitHaken(gespeichert(), ANZEIGE, 'gust', 'telegram', false);
		assert.deepEqual(p.rows[2], { metric_id: 'gust', places: { telegram: false } });
		assert.deepEqual(p.rows[0], { metric_id: 'temperature', places: { sms: false } });
		assert.equal(p.unbekannt, 'bleibt');
		assert.deepEqual(p.rows[1].zukunft, { x: 1 }, 'unbekanntes Feld einer Zeile bleibt erhalten');
		assert.deepEqual(p.outlook_reports, ['evening']);
	});
	test('Wiederwahl entfernt das false; ein fehlender Haken bleibt fehlend', () => {
		const p = mitHaken(gespeichert(), ANZEIGE, 'temperature', 'sms', true);
		assert.equal('sms' in (p.rows[0].places ?? {}), false, 'false wird entfernt, nicht durch true ersetzt');
		const q = mitHaken(gespeichert(), ANZEIGE, 'gust', 'email', true);
		assert.deepEqual(q.rows[2], { metric_id: 'gust' }, 'Haken auf einer angehakten Stelle legt nichts an');
	});
	test('ein gespeichertes true bleibt bei Wiederwahl unverändert', () => {
		const p = mitHaken(gespeichert(), ANZEIGE, 'wind', 'email', true);
		assert.deepEqual(p.rows[1].places, { email: true });
	});
	test('Metrik ohne Zeile: fehlende Zeilen kommen in Anzeigefolge hinten dazu, die Reihenfolge bleibt', () => {
		const p = mitHaken(gespeichert(), ['temperature', 'wind', 'gust', 'precipitation', 'thunder'], 'thunder', 'sms', false);
		assert.deepEqual(p.rows.map((r) => r.metric_id), ['temperature', 'wind', 'gust', 'precipitation', 'thunder']);
		assert.deepEqual(p.rows[3], { metric_id: 'precipitation' });
		assert.deepEqual(p.rows[4], { metric_id: 'thunder', places: { sms: false } });
	});
	test('der Eingang bleibt unverändert (keine Mutation)', () => {
		const vorher = gespeichert();
		const kopie = JSON.stringify(vorher);
		mitHaken(vorher, ANZEIGE, 'gust', 'telegram', false);
		assert.equal(JSON.stringify(vorher), kopie);
	});
	test('ohne gespeicherte Version wird version 1 gesetzt', () => {
		const p = mitHaken({ rows: [] } as unknown as Placements, ['wind'], 'wind', 'sms', false);
		assert.equal(p.version, 1);
	});
});

describe('Roh/Einfach (Teil A Nr. 1: formats nur email, telegram, hourly, outlook)', () => {
	test('Format an einer erlaubten Stelle, andere Stellen unverändert', () => {
		const p = mitFormat(gespeichert(), ANZEIGE, 'wind', 'telegram', 'simplified');
		assert.deepEqual(p.rows[1].formats, { email: 'simplified', telegram: 'simplified' });
		const q = mitFormat(gespeichert(), ANZEIGE, 'gust', 'outlook', 'raw');
		assert.deepEqual(q.rows[2], { metric_id: 'gust', formats: { outlook: 'raw' } });
	});
	test('SMS und unbekannte Stellen bekommen nie ein Format', () => {
		assert.deepEqual(mitFormat(gespeichert(), ANZEIGE, 'gust', 'sms', 'simplified'), gespeichert());
		assert.deepEqual(mitFormat(gespeichert(), ANZEIGE, 'gust', 'premium_sms', 'simplified'), gespeichert());
	});
});

describe('Reihenfolge = Listenposition', () => {
	test('Zeilen in neuer Folge, fehlende angelegt, Zeilen außerhalb der Anzeige behalten Inhalt und stehen hinten', () => {
		const p = mitReihenfolge(
			{ version: 1, rows: [{ metric_id: 'alt', places: { sms: false } }, { metric_id: 'wind', formats: { email: 'raw' } }, { metric_id: 'gust' }] },
			['gust', 'precipitation', 'wind']
		);
		assert.deepEqual(p.rows, [
			{ metric_id: 'gust' },
			{ metric_id: 'precipitation' },
			{ metric_id: 'wind', formats: { email: 'raw' } },
			{ metric_id: 'alt', places: { sms: false } }
		]);
	});
});

describe('3-Tages-Ausblick: outlook_reports', () => {
	test('Morgen und Abend werden als Liste geschrieben, Zeilen bleiben', () => {
		assert.deepEqual(mitAusblick(gespeichert(), { morning: true, evening: true }).outlook_reports, ['morning', 'evening']);
		assert.deepEqual(mitAusblick(gespeichert(), { morning: false, evening: false }).outlook_reports, []);
		assert.deepEqual(mitAusblick(gespeichert(), { morning: true, evening: false }).rows, gespeichert().rows);
	});
});

describe('Fix-Loop F2: Wechsel der Grundauswahl (auch Vorlage)', () => {
	test('weggefallene Metriken verlieren ihre Zeile, neue stehen hinten überall angehakt, gemeinsame behalten Abwahlen', () => {
		const p = mitGrundauswahl(gespeichert(), ['temperature', 'wind', 'gust'], ['wind', 'precipitation', 'temperature']);
		assert.deepEqual(p.rows.map((r) => r.metric_id), ['temperature', 'wind', 'precipitation'], 'Böen weg, Niederschlag hinten');
		assert.deepEqual(p.rows[0].places, { sms: false }, 'gemeinsame Metrik behält ihre Abwahl');
		assert.deepEqual(p.rows[1].places, { email: true });
		assert.deepEqual(p.rows[2], { metric_id: 'precipitation' });
		assert.equal(p.unbekannt, 'bleibt');
	});
	test('Zurückwechseln bringt die Metrik ohne alte Abwahlen zurück', () => {
		const hin = mitGrundauswahl(gespeichert(), ['temperature', 'wind', 'gust'], ['wind', 'gust']);
		const zurueck = mitGrundauswahl(hin, ['wind', 'gust'], ['temperature', 'wind', 'gust']);
		assert.deepEqual(zurueck.rows.find((r) => r.metric_id === 'temperature'), { metric_id: 'temperature' });
		assert.equal(zurueck.rows[zurueck.rows.length - 1].metric_id, 'temperature');
	});
	test('neu hinzugekommene Metrik mit Altzeile (Abwahl) kommt überall angehakt zurück', () => {
		const alt = { version: 1, rows: [{ metric_id: 'wind' }, { metric_id: 'gust', places: { telegram: false } }] };
		const p = mitGrundauswahl(alt, ['wind'], ['wind', 'gust']);
		assert.deepEqual(p.rows, [{ metric_id: 'wind' }, { metric_id: 'gust' }]);
	});
	test('unveränderte Grundauswahl ändert nichts', () => {
		assert.deepEqual(mitGrundauswahl(gespeichert(), ['wind', 'gust'], ['gust', 'wind']), gespeichert());
	});
});

describe('Grundauswahl „−“/„+“ (AC-32)', () => {
	test('„−“ entfernt die Zeile der Metrik, sonst nichts', () => {
		const p = ohneZeile(gespeichert(), 'wind');
		assert.deepEqual(p.rows.map((r) => r.metric_id), ['temperature', 'gust']);
		assert.equal(p.unbekannt, 'bleibt');
	});
	test('„+“ hängt die Metrik hinten an, überall angehakt; eine alte Zeile verschwindet', () => {
		const p = mitZeileHinten(gespeichert(), 'temperature');
		assert.deepEqual(p.rows.map((r) => r.metric_id), ['wind', 'gust', 'temperature']);
		assert.deepEqual(p.rows[2], { metric_id: 'temperature' }, 'kein places: überall angehakt');
	});
});

// ── Sofortanzeige der Antwort (bis das frische GET kommt) ─────────────────────────────
const zelle = (state: string, format: string | null = null, example: string | null = null) => ({ state, format, reason: null, example, ampel: null, mark: null });
const antwort = (): PlacementsAntwort =>
	({
		kind: 'vergleich',
		lang: 'de',
		stored: true,
		placements: { version: 1, rows: [{ metric_id: 'wind', places: { hourly: false } }] },
		location_count: 3,
		columns: [],
		fixed_rows: [],
		rows: [
			{ metric_id: 'wind', name: 'Wind', position: 0, parent: null, cells: { email: zelle('on', 'raw', '30 km/h'), telegram: zelle('on', 'raw'), sms: zelle('on'), hourly: zelle('off', 'raw'), outlook: zelle('on', 'raw') } },
			{ metric_id: 'sunshine', name: 'Sonnenstunden', position: 1, parent: null, cells: { email: zelle('on'), telegram: zelle('on'), sms: zelle('on'), hourly: { ...zelle('locked'), reason: 'kein_stundenwert' }, outlook: zelle('on') } }
		],
		sms_example: null,
		outlook_reports: ['evening'],
		blocks: {},
		legend: { metrics: [], fixed: [] },
		example_version: 1
	}) as unknown as PlacementsAntwort;

describe('Sofortanzeige', () => {
	test('E-Mail ab: Stundenverlauf und Ausblick „nicht in der E-Mail“; gesperrt bleibt gesperrt', () => {
		const a = antwortMitHaken(antwortMitHaken(antwort(), 'wind', 'email', false), 'sunshine', 'email', false);
		assert.equal(a.rows[0].cells.email.state, 'off');
		assert.equal(a.rows[0].cells.hourly.state, 'not_in_email');
		assert.equal(a.rows[0].cells.outlook.state, 'not_in_email');
		assert.equal(a.rows[1].cells.hourly.state, 'locked');
	});
	test('E-Mail wieder an: Haken aus placements zurück (abgewählt bleibt abgewählt)', () => {
		const ab = antwortMitHaken(antwort(), 'wind', 'email', false);
		const an = antwortMitHaken(ab, 'wind', 'email', true);
		assert.equal(an.rows[0].cells.hourly.state, 'off', 'hourly war abgewählt');
		assert.equal(an.rows[0].cells.outlook.state, 'on');
	});
	test('Format und Reihenfolge; „−“ nimmt die Zeile aus der Anzeige', () => {
		assert.equal(antwortMitFormat(antwort(), 'wind', 'email', 'simplified').rows[0].cells.email.format, 'simplified');
		assert.deepEqual(antwortMitReihenfolge(antwort(), ['sunshine', 'wind']).rows.map((r) => r.metric_id), ['sunshine', 'wind']);
		assert.deepEqual(antwortOhneZeile(antwort(), 'wind').rows.map((r) => r.metric_id), ['sunshine']);
	});
});

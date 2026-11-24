// TDD RED — Issue #3306 (Teil C von #3041, Epic #3122): der eine Anlege-POST des Ortsvergleichs trägt
// Tabelle und Schalter der Karte „Was steht wo“.
// Spec docs/specs/modules/feat_3306_tabelle_orte_anlegen.md, Test Plan Nr. 1 (AC-2, AC-3), Nr. 2 (AC-5),
// Nr. 3 (AC-9). Pendant zu trip-new/__tests__/trip_anlegen_karte_payload_3305.test.ts.
//
// FESTGELEGTE SCHNITTSTELLE (der Implementierer folgt diesen Namen):
//   baueVergleichAnlegeRumpf(wiz, wetter) / legeVergleichAn(api, wiz, wetter)
//     wetter.karte?: KarteAnlegeStand   (Typ aus shared/wetter-tab/wasStehtWoSpeicherung.ts)
//       KarteAnlegeStand = { placements: Placements; felder: Felder; felderStart: Felder }
//     - `karte` gesetzt: display_config.placements = karte.placements; dazu die Schalter-Differenz
//       felderNutzlast('vergleich', karte.felder, karte.felderStart) per Read-Modify-Write in den Rumpf
//       (hourly_enabled top-level, telegram_style in display_config). Alles andere (Versandzeiten, Kanäle,
//       Orte, Ampel, Auswahl, Alarm-Felder) bleibt genau wie ohne Karte. Keine Altschlüssel.
//     - `karte` nicht gesetzt: Rumpf bitgleich zu heute (keine placements, keine Schalterfelder aus der Karte).
//
// Echte Funktionen `baueVergleichAnlegeRumpf`/`legeVergleichAn`, keine Doubles; der POST wird an einem
// gesäten Client mitgeschnitten (Netzgrenze, kein Nachbau der Logik).
//
//   cd frontend && npm test -- src/lib/components/compare/__tests__/vergleich_anlegen_karte_payload_3306.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { baueVergleichAnlegeRumpf, legeVergleichAn, compareFeldsatzStandard } from '../compareEditorSave.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any

const ALTSCHLUESSEL = ['channel_layouts', 'outlook_metrics', 'outlook_metric_formats', 'channel_active_metrics', 'hourly_metrics', 'hourly_metric_formats'];

const START_FELDER = { show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, email_format: 'full', telegram_style: 'rich', hourly_enabled: true };
const PLACEMENTS = {
	version: 1,
	rows: [
		{ metric_id: 'wind', formats: { email: 'raw' } },
		{ metric_id: 'gust', places: { telegram: false } },
		{ metric_id: 'temperature' }
	],
	outlook_reports: ['morning']
};
const AMPEL = { template: 'allgemein' };
const AUSWAHL = [{ metric_id: 'wind', aggregation: 'max' }, { metric_id: 'gust', aggregation: 'max' }, { metric_id: 'temperature', aggregation: 'max' }];

/** Anlege-Feldsatz wie CompareNewEditor ihn hält, mit Orten, Versandzeiten und Kanälen. */
function feldsatz(extra: Record<string, unknown> = {}): J {
	return {
		...compareFeldsatzStandard(),
		name: 'Neu-3306',
		region: 'Tirol',
		pickedIds: ['ort-a', 'ort-b'],
		sendEmail: true,
		sendTelegram: true,
		sendSms: false,
		morningEnabled: true,
		morningTime: '06:30',
		eveningEnabled: true,
		eveningTime: '19:00',
		...extra
	};
}
function rumpf(wiz: J, wetter: J = { ampel: AMPEL, auswahl: AUSWAHL }): J {
	return JSON.parse(JSON.stringify(baueVergleichAnlegeRumpf(wiz, wetter)));
}
/** Alle Blattpfade, deren Wert sich zwischen a und b unterscheidet. */
function abweichungen(a: J, b: J, pfad = ''): string[] {
	const istObj = (x: unknown) => x !== null && typeof x === 'object' && !Array.isArray(x);
	if (istObj(a) && istObj(b)) {
		const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
		return [...keys].flatMap((k) => abweichungen(a[k], b[k], pfad ? `${pfad}.${k}` : k));
	}
	return JSON.stringify(a) === JSON.stringify(b) ? [] : [pfad];
}
const karte = (felder: J = { ...START_FELDER }, felderStart: J = { ...START_FELDER }, placements: J = PLACEMENTS) => ({ placements, felder, felderStart });
const altIn = (r: J) => [...ALTSCHLUESSEL.filter((k) => k in r), ...ALTSCHLUESSEL.filter((k) => k in (r.display_config ?? {})).map((k) => `display_config.${k}`)];

describe('#3306 Test 1 (AC-2, AC-3): karte gesetzt — placements und Schalter-Differenz im POST', () => {
	test('Tabelle der Karte steht unverändert in display_config.placements (Reihenfolge, Haken, Formate, Ausblick)', () => {
		const r = rumpf(feldsatz(), { ampel: AMPEL, auswahl: AUSWAHL, karte: karte() });
		assert.deepEqual(r.display_config?.placements, PLACEMENTS, 'bediente Karte, aber Rumpf ohne ihren Stand');
		assert.deepEqual(r.display_config.placements.outlook_reports, ['morning'], 'Ausblick reist als outlook_reports der Tabelle');
	});

	test('Stundenverlauf und Telegram-Kurzstil geändert: Werte an ihrem Ort, sonst weicht nichts ab', () => {
		const ohne = rumpf(feldsatz());
		const felder = { ...START_FELDER, hourly_enabled: false, telegram_style: 'kurzform' };
		const mit = rumpf(feldsatz(), { ampel: AMPEL, auswahl: AUSWAHL, karte: karte(felder) });
		assert.equal(mit.hourly_enabled, false, 'hourly_enabled (top-level) nicht aus der Karte');
		assert.equal(mit.display_config?.telegram_style, 'kurzform', 'display_config.telegram_style nicht aus der Karte');
		assert.deepEqual(
			abweichungen(ohne, mit).sort(),
			['display_config.placements', 'display_config.telegram_style', 'hourly_enabled'],
			'nur Tabelle und die geänderten Schalter weichen ab'
		);
		for (const k of ['morning_enabled', 'morning_time', 'evening_enabled', 'evening_time', 'schedule', 'send_email', 'send_telegram', 'send_sms', 'send_premium_sms'])
			assert.deepEqual(mit[k], ohne[k], `Versandfeld ${k} verändert`);
		assert.deepEqual(mit.location_ids, ['ort-a', 'ort-b'], 'Orte verändert');
		assert.deepEqual(mit.display_config.ampel, AMPEL, 'Ampel verändert');
		assert.deepEqual(mit.display_config.active_metrics, AUSWAHL, 'Auswahl verändert');
	});

	test('keiner der sechs Altschlüssel im Rumpf mit Karte (#3276)', () => {
		const felder = { ...START_FELDER, hourly_enabled: false, telegram_style: 'kurzform' };
		const mit = rumpf(feldsatz(), { ampel: AMPEL, auswahl: AUSWAHL, karte: karte(felder) });
		assert.deepEqual(altIn(mit), []);
	});

	test('Tabelle bedient, Schalter unverändert: keine Schalterfelder aus der Karte im POST', () => {
		const ohne = rumpf(feldsatz());
		const mit = rumpf(feldsatz(), { ampel: AMPEL, auswahl: AUSWAHL, karte: karte() });
		assert.deepEqual(abweichungen(ohne, mit), ['display_config.placements']);
	});

	test('Karte ohne Ampel aus dem Reiter: Tabelle und Schalter trotzdem im Rumpf (display_config wird angelegt)', () => {
		const felder = { ...START_FELDER, telegram_style: 'kurzform' };
		const mit = rumpf(feldsatz(), { karte: karte(felder) });
		assert.deepEqual(mit.display_config?.placements, PLACEMENTS);
		assert.equal(mit.display_config?.telegram_style, 'kurzform');
	});

	test('der Eingabezustand bleibt unverändert (reine Funktion)', () => {
		const wiz = feldsatz();
		const wetter = { ampel: AMPEL, auswahl: AUSWAHL, karte: karte({ ...START_FELDER, hourly_enabled: false }) };
		const vorher = JSON.stringify({ wiz, wetter });
		rumpf(wiz, wetter);
		assert.equal(JSON.stringify({ wiz, wetter }), vorher);
	});

	test('legeVergleichAn sendet genau einen POST auf /api/compare/presets mit Tabelle und Schaltern', async () => {
		const gesendet: Array<{ url: string; body: J }> = [];
		const api = { post: async <T>(url: string, body: unknown): Promise<T> => (gesendet.push({ url, body: JSON.parse(JSON.stringify(body)) }), { id: 'neu-3306' } as T) };
		const felder = { ...START_FELDER, hourly_enabled: false };
		const neu = await legeVergleichAn(api, feldsatz(), { ampel: AMPEL, auswahl: AUSWAHL, karte: karte(felder) } as J);
		assert.equal(neu.id, 'neu-3306');
		assert.equal(gesendet.length, 1);
		assert.equal(gesendet[0].url, '/api/compare/presets');
		assert.deepEqual(gesendet[0].body.display_config?.placements, PLACEMENTS, 'legeVergleichAn reicht die Karte nicht durch');
		assert.equal(gesendet[0].body.hourly_enabled, false);
	});
});

describe('#3306 Test 2 (AC-5): karte nicht gesetzt — Rumpf wie heute (Regressionsschutz)', () => {
	test('keine placements und keine Schalterfelder aus der Karte', () => {
		const r = rumpf(feldsatz());
		assert.equal('placements' in r.display_config, false);
		assert.equal('telegram_style' in r.display_config, false, 'telegram_style nur bei Abweichung von rich aus dem Feldsatz');
		assert.equal(r.hourly_enabled, true, 'hourly_enabled nur aus dem Feldsatz');
	});

	test('karte: undefined ist bitgleich zu einem Aufruf ohne das Feld', () => {
		assert.deepEqual(rumpf(feldsatz(), { ampel: AMPEL, auswahl: AUSWAHL, karte: undefined }), rumpf(feldsatz()));
	});
});

describe('#3306 Test 3 (AC-9): zwei Bedienstellen bis #3307 — nur gegenüber dem Kartenstart Geändertes gilt', () => {
	test('Altblock hat Kurzstil und Stundenverlauf gesetzt, Karte unverändert: Altblock-Werte gelten', () => {
		const wiz = feldsatz({ telegramStyle: 'kurzform', hourlyEnabled: false });
		const start = { ...START_FELDER, telegram_style: 'kurzform', hourly_enabled: false };
		const mit = rumpf(wiz, { ampel: AMPEL, auswahl: AUSWAHL, karte: karte({ ...start }, start) });
		assert.equal(mit.display_config.telegram_style, 'kurzform', 'unveränderter Kartenwert überschreibt den Altblock');
		assert.equal(mit.hourly_enabled, false, 'unveränderter Kartenwert überschreibt den Altblock');
		assert.deepEqual(abweichungen(rumpf(wiz), mit), ['display_config.placements']);
	});

	test('Karte startete mit dem Altblock-Wert, wurde dann geändert: Karten-Wert gilt', () => {
		const wiz = feldsatz({ telegramStyle: 'kurzform', hourlyEnabled: false });
		const start = { ...START_FELDER, telegram_style: 'kurzform', hourly_enabled: false };
		const mit = rumpf(wiz, { ampel: AMPEL, auswahl: AUSWAHL, karte: karte({ ...start, telegram_style: 'rich', hourly_enabled: true }, start) });
		assert.equal(mit.display_config.telegram_style, 'rich', 'geänderter Kartenwert gilt nicht');
		assert.equal(mit.hourly_enabled, true, 'geänderter Kartenwert gilt nicht');
	});

	test('nur ein Schalter in der Karte geändert: der andere bleibt beim Altblock-Wert', () => {
		const wiz = feldsatz({ telegramStyle: 'kurzform', hourlyEnabled: true });
		const start = { ...START_FELDER, telegram_style: 'kurzform', hourly_enabled: true };
		const mit = rumpf(wiz, { ampel: AMPEL, auswahl: AUSWAHL, karte: karte({ ...start, hourly_enabled: false }, start) });
		assert.equal(mit.hourly_enabled, false);
		assert.equal(mit.display_config.telegram_style, 'kurzform', 'Kurzstil des Altblocks verloren');
		assert.deepEqual(abweichungen(rumpf(wiz), mit).sort(), ['display_config.placements', 'hourly_enabled']);
	});
});

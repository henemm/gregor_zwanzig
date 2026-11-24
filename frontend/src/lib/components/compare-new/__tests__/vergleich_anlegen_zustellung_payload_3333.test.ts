// TDD RED — Issue #3333 (Teil D2 von #3307, Epic #3122): der Stand des Reiters „Zustellung“ im einen
// Anlege-POST des Ortsvergleichs. Spec docs/specs/modules/feat_3333_zustellung_anlegen_orte.md,
// Test Plan Nr. 1 bis 4 (AC-2, AC-3, AC-4, AC-5, AC-8) — reiner Helfer, Orte-Pendant zu `mitZustellung` (#3332).
//
// FESTGELEGTE SCHNITTSTELLE (compare/compareEditorSave.ts):
//   mitZustellungVergleich(wiz: CompareFeldsatz, stand: ZustellungStand | undefined): void
//     Schreibt Feld für Feld in `wiz` (der Feldsatz des Editors ist ein `$state`-Objekt, Read-Modify-Write,
//     kein Replace): morningEnabled/morningTime, eveningEnabled/eveningTime („HH:MM“, nur rastergültige
//     Zeiten — eine rasterfremde Zeit lässt den vorhandenen Wert stehen), sendEmail/sendTelegram/sendSms/
//     sendPremiumSms (aus stand.briefing), endDate, channels (vier Kanäle, aus stand.alarme),
//     channelThresholds (vier Kanäle), alertQuietFrom/alertQuietTo (Stille aus = undefined),
//     alertCooldownMinutes. Alle übrigen Felder bleiben unberührt; der Stand selbst wird nicht verändert und
//     nicht geteilt (spätere Änderungen am Stand wirken nicht in `wiz`). stand === undefined: nichts ändert sich.
//   baueVergleichAnlegeRumpf / legeVergleichAn: `send_email` IMMER aus `wiz.sendEmail` (AC-4).
//
// REFERENZ für AC-5 (bitgleich zu heute bis auf `send_email: true`):
//   fixtures/vergleich_anlegen_ohne_zustellung_3333.json — der POST-Körper des HEUTIGEN Codes ohne jede
//   Bedienung (Standard-Feldsatz + Name + zwei Orte, `baueVergleichAnlegeRumpf` wie im Editor ohne Stand des
//   Reiters Wetter). Erzeugt vor der Umsetzung; neu erzeugen NUR bei bewusster Rumpf-Änderung:
//     cd frontend && GZ_FIXTURE_SCHREIBEN=1 npm test -- src/lib/components/compare-new/__tests__/vergleich_anlegen_zustellung_payload_3333.test.ts
//
// Echte Funktionen, keine Doubles.
//
//   cd frontend && npm test -- src/lib/components/compare-new/__tests__/vergleich_anlegen_zustellung_payload_3333.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as C from '../../compare/compareEditorSave.ts';
import { standAusPreset, type ZustellungStand } from '../../shared/zustellung-tab/zustellungModell.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const klon = <T>(v: T): T => (v === undefined ? v : JSON.parse(JSON.stringify(v)));

const HIER = dirname(fileURLToPath(import.meta.url));
const FIXTURE_3333 = join(HIER, 'fixtures', 'vergleich_anlegen_ohne_zustellung_3333.json');
const NAME_3333 = 'Neu-3333';
const ORTE_3333 = ['loc-a', 'loc-b'];

function mitZustellungVergleich(wiz: J, stand: J): void {
	const f = (C as J).mitZustellungVergleich;
	assert.equal(typeof f, 'function', 'compareEditorSave.ts exportiert keinen reinen Helfer `mitZustellungVergleich`');
	const r = f(wiz, stand);
	assert.ok(r === undefined || r === wiz, 'mitZustellungVergleich schreibt in den übergebenen Feldsatz (kein Ersatzobjekt)');
}

/** Feldsatz, wie der Anlege-Editor ihn vor dem POST hält (Stammdaten + Werte aus dem Reiter Wetter). */
function wiz0(): J {
	return {
		...C.compareFeldsatzStandard(),
		name: NAME_3333,
		pickedIds: [...ORTE_3333],
		region: 'Gallura',
		dayWindowStartHour: 5,
		dayWindowEndHour: 20,
		metricAlertLevels: { wind: 'HIGH' },
		radarAlertEnabled: true,
		telegramStyle: 'kurzform'
	};
}

/** Startstand des Reiters im Orte-Anlegen: Abo-Sicht aus den heutigen Wizard-Standardwerten. */
const START: ZustellungStand = standAusPreset({ id: '', name: NAME_3333, location_ids: ORTE_3333, alert_channels: { email: true, telegram: true, sms: false, premium_sms: false } } as J);

function bedient(): ZustellungStand {
	return {
		...klon(START),
		morgenAn: true,
		morgenZeit: '06:45',
		abendAn: true,
		abendZeit: '19:30',
		// Briefing- und Alarm-Kanäle GETRENNT belegt (Lehre #3332 F004): sonst bliebe unbemerkt, wenn der
		// Helfer die eine Auswahl aus der anderen liest.
		briefing: { email: false, telegram: true, sms: true, premium_sms: false },
		alarme: { email: true, telegram: false, sms: false, premium_sms: true },
		dringlichkeit: { email: 'LOW', telegram: 'HIGH', sms: 'MODERATE', premium_sms: 'LOW' },
		stilleAn: true,
		stilleVon: '22:30',
		stilleBis: '06:15',
		cooldown: 45,
		endDate: '2027-03-01'
	};
}

const ZUSTELLUNGS_FELDER = [
	'morningEnabled', 'morningTime', 'eveningEnabled', 'eveningTime', 'sendEmail', 'sendTelegram', 'sendSms',
	'sendPremiumSms', 'endDate', 'channels', 'channelThresholds', 'alertQuietFrom', 'alertQuietTo', 'alertCooldownMinutes'
];

describe('#3333 Test 1 (AC-2, AC-3): mitZustellungVergleich schreibt den Stand Feld für Feld in den Feldsatz', () => {
	test('Zeiten, Schalter, Briefing-Kanäle, Laufzeit', () => {
		const w = wiz0();
		mitZustellungVergleich(w, bedient());
		assert.equal(w.morningEnabled, true);
		assert.equal(w.morningTime, '06:45', 'Morgen-Zeit');
		assert.equal(w.eveningEnabled, true, 'Abend-Schalter');
		assert.equal(w.eveningTime, '19:30', 'Abend-Zeit');
		assert.equal(w.sendEmail, false, 'Briefing E-Mail (aus stand.briefing, nicht aus stand.alarme)');
		assert.equal(w.sendTelegram, true, 'Briefing Telegram (aus stand.briefing, nicht aus stand.alarme)');
		assert.equal(w.sendSms, true, 'Briefing SMS (aus stand.briefing)');
		assert.equal(w.sendPremiumSms, false, 'Briefing Premium-SMS (aus stand.briefing, nicht aus stand.alarme)');
		assert.equal(w.endDate, '2027-03-01', 'Laufzeit (end_date)');
	});

	test('Alarm-Kanäle, Dringlichkeit, Stille, Cooldown', () => {
		const w = wiz0();
		mitZustellungVergleich(w, bedient());
		assert.deepEqual(klon(w.channels), { email: true, telegram: false, sms: false, premium_sms: true }, 'Alarm-Kanäle (aus stand.alarme, nicht aus stand.briefing)');
		assert.deepEqual(klon(w.channelThresholds), { email: 'LOW', telegram: 'HIGH', sms: 'MODERATE', premium_sms: 'LOW' });
		assert.equal(w.alertQuietFrom, '22:30');
		assert.equal(w.alertQuietTo, '06:15');
		assert.equal(w.alertCooldownMinutes, 45);
	});

	test('Read-Modify-Write: alle übrigen Felder des Feldsatzes bleiben (Name, Orte, Tagesfenster, Metrik-Stufen, Radar, Kurzstil …)', () => {
		const w = wiz0();
		const vorher = klon(w);
		mitZustellungVergleich(w, bedient());
		for (const [k, v] of Object.entries(vorher)) {
			if (ZUSTELLUNGS_FELDER.includes(k)) continue;
			assert.deepEqual(klon(w[k]), v, `Bestandsfeld ${k} verändert`);
		}
		assert.deepEqual(Object.keys(w).sort(), [...new Set([...Object.keys(vorher), ...ZUSTELLUNGS_FELDER])].sort(), 'fremde Schlüssel im Feldsatz');
	});

	test('Stille Stunden aus: alertQuietFrom/To leer, im POST keine Stille-Zeiten', () => {
		const w = wiz0();
		mitZustellungVergleich(w, bedient());
		mitZustellungVergleich(w, { ...bedient(), stilleAn: false });
		assert.equal(w.alertQuietFrom ?? null, null);
		assert.equal(w.alertQuietTo ?? null, null);
		const p = C.baueVergleichAnlegeRumpf(w);
		assert.equal(p.alert_quiet_from ?? null, null, 'Stille-von im POST, obwohl aus');
		assert.equal(p.alert_quiet_to ?? null, null, 'Stille-bis im POST, obwohl aus');
	});

	test('Laufzeit zurück auf „bis auf Weiteres“: endDate null, kein end_date im POST', () => {
		const w = wiz0();
		mitZustellungVergleich(w, bedient());
		mitZustellungVergleich(w, { ...bedient(), endDate: null });
		assert.equal(w.endDate ?? null, null);
		assert.equal('end_date' in C.baueVergleichAnlegeRumpf(w), false);
	});

	test('Stand nicht verändert und nicht geteilt (spätere Änderung am Stand wirkt nicht im Feldsatz)', () => {
		const w = wiz0();
		const s = bedient();
		const vorher = JSON.stringify(s);
		mitZustellungVergleich(w, s);
		assert.equal(JSON.stringify(s), vorher, 'Helfer verändert den gemeldeten Stand');
		s.alarme.sms = true;
		s.dringlichkeit.email = 'HIGH';
		assert.equal(w.channels.sms, false, 'Feldsatz teilt das Alarm-Kanal-Objekt mit dem Stand');
		assert.equal(w.channelThresholds.email, 'LOW', 'Feldsatz teilt das Dringlichkeits-Objekt mit dem Stand');
	});

	test('Reiter nie bedient (stand undefined): Feldsatz unverändert', () => {
		const w = wiz0();
		mitZustellungVergleich(w, undefined);
		assert.deepEqual(klon(w), klon(wiz0()));
	});

	test('im POST: genau die eingestellten Werte (Zeiten, Kanäle, Dringlichkeit HIGH, Stille, Cooldown, Laufzeit)', () => {
		const w = wiz0();
		mitZustellungVergleich(w, bedient());
		const p = C.baueVergleichAnlegeRumpf(w);
		assert.equal(p.morning_enabled, true);
		assert.equal(p.morning_time, '06:45:00');
		assert.equal(p.evening_enabled, true);
		assert.equal(p.evening_time, '19:30:00');
		assert.equal(p.send_email, false, 'POST: Briefing E-Mail aus');
		assert.equal(p.send_telegram, true);
		assert.equal(p.send_sms, true);
		assert.equal(p.send_premium_sms, false);
		assert.equal(p.end_date, '2027-03-01');
		assert.deepEqual(p.alert_channels, { email: true, telegram: false, sms: false, premium_sms: true });
		assert.equal((p.alert_channel_thresholds as J)?.telegram, 'HIGH', 'AC-3: Dringlichkeit Telegram');
		assert.equal(p.alert_quiet_from, '22:30');
		assert.equal(p.alert_quiet_to, '06:15');
		assert.equal(p.alert_cooldown_minutes, 45);
		// Read-Modify-Write bis in den POST: Felder anderer Reiter bleiben.
		assert.equal(p.day_window_start_hour, 5);
		assert.equal((p.display_config as J)?.metric_alert_levels?.wind, 'HIGH');
		assert.equal((p.display_config as J)?.telegram_style, 'kurzform');
		assert.equal(p.radar_alert_enabled, true);
	});
});

describe('#3333 Test 2 (AC-8): rasterfremde Uhrzeit wird nie übernommen', () => {
	test('06:45, dann 06:50: Feldsatz behält 06:45, POST 06:45:00, 06:50 nirgends', () => {
		const w = wiz0();
		mitZustellungVergleich(w, { ...bedient(), morgenZeit: '06:45' });
		mitZustellungVergleich(w, { ...bedient(), morgenZeit: '06:50' });
		assert.equal(w.morningTime, '06:45', 'letzte gültige Zeit überschrieben');
		const p = C.baueVergleichAnlegeRumpf(w);
		assert.equal(p.morning_time, '06:45:00');
		assert.ok(!JSON.stringify(p).includes('06:50'), 'rasterfremde Uhrzeit im POST (Server antwortet 400)');
	});

	test('nur 06:50 / 18:07: Startzeiten bleiben; gültige Änderungen derselben Meldung gehen durch', () => {
		const w = wiz0();
		mitZustellungVergleich(w, { ...bedient(), morgenZeit: '06:50', abendZeit: '18:07', cooldown: 30 });
		assert.equal(w.morningTime, '07:00', 'Start-Morgenzeit nicht erhalten');
		assert.equal(w.eveningTime, '18:00', 'Start-Abendzeit nicht erhalten');
		assert.equal(w.alertCooldownMinutes, 30, 'gültige Änderung derselben Meldung verloren');
		assert.equal(w.sendTelegram, true);
	});
});

describe('#3333 Test 3 (AC-4): send_email reist immer im Anlege-POST', () => {
	for (const an of [true, false]) {
		test(`wiz.sendEmail = ${an}: baueVergleichAnlegeRumpf sendet send_email: ${an}`, () => {
			const p = C.baueVergleichAnlegeRumpf({ ...wiz0(), sendEmail: an });
			assert.equal('send_email' in p, true, 'send_email fehlt im POST (Server nähme still „an“)');
			assert.equal(p.send_email, an);
		});

		test(`wiz.sendEmail = ${an}: legeVergleichAn postet send_email: ${an} an /api/compare/presets`, async () => {
			const gesendet: Array<{ url: string; body: J }> = [];
			const api = { post: async <T,>(url: string, body: unknown): Promise<T> => (gesendet.push({ url, body: klon(body) }), { id: 'neu' } as T) };
			await C.legeVergleichAn(api, { ...wiz0(), sendEmail: an });
			assert.equal(gesendet.length, 1);
			assert.equal(gesendet[0].url, '/api/compare/presets');
			assert.equal(gesendet[0].body.send_email, an);
		});
	}

	test('E-Mail im Reiter abgewählt: über den Helfer send_email: false im POST', () => {
		const w = wiz0();
		mitZustellungVergleich(w, { ...klon(START), briefing: { ...START.briefing, email: false } });
		assert.equal(C.baueVergleichAnlegeRumpf(w).send_email, false);
	});
});

// ── Referenz „heute“ ─────────────────────────────────────────────────────────
function heutigerRumpf(): J {
	return klon(C.baueVergleichAnlegeRumpf({ ...C.compareFeldsatzStandard(), name: NAME_3333, pickedIds: [...ORTE_3333] }));
}
function referenz3333(): J {
	assert.ok(fs.existsSync(FIXTURE_3333), `Referenz-Fixture fehlt: ${FIXTURE_3333}`);
	return JSON.parse(fs.readFileSync(FIXTURE_3333, 'utf-8'));
}

describe('#3333 Referenz-Fixture (Messaufbau)', () => {
	test('Fixture liegt vor, trägt Zeiten, Kanäle, Alarm-Kanäle und (noch) kein send_email', () => {
		if (process.env.GZ_FIXTURE_SCHREIBEN === '1') {
			fs.mkdirSync(dirname(FIXTURE_3333), { recursive: true });
			const heute = heutigerRumpf();
			delete heute.send_email; // Referenz = Körper VOR #3333; das neue Feld prüft Test 4 ausdrücklich
			fs.writeFileSync(FIXTURE_3333, JSON.stringify(heute, null, 2) + '\n', 'utf-8');
		}
		const ref = referenz3333();
		for (const f of ['morning_enabled', 'morning_time', 'evening_enabled', 'evening_time', 'send_telegram', 'send_sms', 'send_premium_sms', 'alert_channels', 'official_warnings'])
			assert.ok(f in ref, `Fixture ohne ${f}`);
		assert.equal('send_email' in ref, false, 'Referenz muss der Körper von heute sein (ohne send_email)');
		assert.equal(ref.alert_channels.email, true);
	});
});

describe('#3333 Test 4 (AC-5): Reiter nie bedient — POST bitgleich zu heute plus send_email: true', () => {
	test('Standard-Feldsatz: Körper = Referenz + send_email: true', () => {
		assert.deepEqual(heutigerRumpf(), { ...referenz3333(), send_email: true });
	});

	test('Startstand des Reiters über den Helfer zurückgeschrieben: Zeiten, Kanäle, Alarm-Felder wie heute', () => {
		// Der Startstand (Abo-Sicht aus den Standardwerten) zurück in den Feldsatz darf keinen Wert der
		// Referenz verändern; nur die Felder, die der Reiter ab jetzt ausdrücklich führt, kommen hinzu.
		const w = { ...C.compareFeldsatzStandard(), name: NAME_3333, pickedIds: [...ORTE_3333] };
		mitZustellungVergleich(w, klon(START));
		const p = klon(C.baueVergleichAnlegeRumpf(w));
		const ref = referenz3333();
		for (const [k, v] of Object.entries(ref)) assert.deepEqual(p[k], v, `Feld ${k} weicht vom heutigen Körper ab`);
		assert.equal(p.send_email, true);
	});
});

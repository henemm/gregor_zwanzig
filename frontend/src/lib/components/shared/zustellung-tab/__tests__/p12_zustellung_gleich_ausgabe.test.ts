// Issue #3047 Runde 7, Paket p12 — Testluecken TL1, TL2, TL3, TL7 (Editor-Inventar): Mutationen,
// die bisher alle Tests ueberlebten, bei heute korrektem Verhalten.
// Spec: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md, „Nachtrag Runde 7“ (AC-26:
// die Einstellungsseite zeigt genau, was die Ausgabe tut).
//
// Kette ohne Nachbau: echte Lade-Funktionen des Reiters Zustellung (standAusTrip/standAusPreset,
// kanalStilStart) gegen die ECHTEN Python-Entscheider desselben gespeicherten Abos:
//   TL1 Abend-Briefing Orte      -> compare_slot_scheduler.resolve_preset_slots
//   TL2 Stille Stunden           -> DeviationAlertEngine.is_quiet_hours (Trip nach load_trip_from_dict, Orte roh)
//   TL3 Orte-Telegram-Kurzstil   -> compare_alert_channels.effective_compare_telegram_style
//   TL7 Trip-Briefing per E-Mail -> TripReportSchedulerService._resolve_channel_flags (nach load_trip_from_dict)
// Orts-Abos im Go-Ladeformat (Slot-Migration erledigt: `morning_time` gesetzt). Zwei Nutzer (a_/b_)
// mit verschiedenen Konfigurationen.
//
//   cd frontend && npm test -- src/lib/components/shared/zustellung-tab/__tests__/p12_zustellung_gleich_ausgabe.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';

import { REPO } from '../../wetter-tab/__tests__/wetterTabDaten.ts';
import { standAusPreset, standAusTrip } from '../zustellungModell.ts';
import type { ComparePreset, Trip } from '../../../../types.ts';

type Abo = Record<string, unknown>;

const PY = `
import sys, json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
sys.path.insert(0, 'src'); sys.path.insert(0, '.')
from app.loader import load_trip_from_dict
from services.compare_slot_scheduler import resolve_preset_slots
from services.compare_alert_channels import effective_compare_telegram_style
from services.deviation_alert_engine import DeviationAlertEngine
from services.trip_report_scheduler import TripReportSchedulerService
UTC = ZoneInfo("UTC")
def stille(von, bis):
    tag = [datetime(2026, 7, 15, h, m, tzinfo=timezone.utc) for h in range(24) for m in (0, 30)]
    return any(DeviationAlertEngine.is_quiet_hours(t, von, bis, UTC) for t in tag)
K = json.loads(sys.stdin.read())
aus = {"trip": {}, "orte": {}}
for kid, roh in K["trip"].items():
    trip = load_trip_from_dict({"id": kid, "name": kid, "stages": [], **roh})
    flags = TripReportSchedulerService._resolve_channel_flags(None, trip.report_config, "p12-" + kid)
    aus["trip"][kid] = {"email": bool(flags[0]), "stille": stille(trip.alert_quiet_from, trip.alert_quiet_to)}
for kid, roh in K["orte"].items():
    p = {"id": kid, "name": kid, "location_ids": [], **roh}
    s = resolve_preset_slots(p)
    aus["orte"][kid] = {"morgen": s.morning_enabled, "abend": s.evening_enabled,
                        "stil": effective_compare_telegram_style(p),
                        "stille": stille(p.get("alert_quiet_from"), p.get("alert_quiet_to"))}
print(json.dumps(aus))
`;

// ── Gespeicherte Abos (Persistenzformat), je Nutzer eigene ─────────────────────────────────
const TRIPS: Record<string, Abo> = {
	a_report_ohne_send_email: { report_config: { morning_time: '06:30:00' } },
	b_ohne_report_config: {},
	a_send_email_aus: { report_config: { send_email: false, send_telegram: true } },
	b_send_email_an: { report_config: { send_email: true } },
	a_stille_nur_von: { report_config: {}, alert_quiet_from: '22:00' },
	b_stille_nur_bis: { report_config: {}, alert_quiet_to: '06:00' },
	a_stille_paar: { report_config: {}, alert_quiet_from: '22:00', alert_quiet_to: '06:00' }
};

const ORTE: Record<string, Abo> = {
	a_abend_nie_eingestellt: { morning_time: '07:00:00', display_config: {} },
	b_abend_an: { morning_time: '06:00:00', morning_enabled: false, evening_enabled: true, evening_time: '19:00:00', display_config: {} },
	a_kurzstil: { morning_time: '07:00:00', display_config: { telegram_style: 'kurzform' } },
	b_stil_nie_eingestellt: { morning_time: '07:00:00', display_config: {} },
	a_stille_nur_von: { morning_time: '07:00:00', display_config: {}, alert_quiet_from: '21:00' },
	b_stille_paar: { morning_time: '07:00:00', display_config: {}, alert_quiet_from: '21:00', alert_quiet_to: '05:30' }
};

const AUS: { trip: Record<string, { email: boolean; stille: boolean }>; orte: Record<string, { morgen: boolean; abend: boolean; stil: string; stille: boolean }> } =
	JSON.parse(
		execFileSync('uv', ['run', 'python3', '-c', PY], {
			cwd: REPO,
			input: JSON.stringify({ trip: TRIPS, orte: ORTE }),
			encoding: 'utf-8',
			maxBuffer: 8 * 1024 * 1024,
			stdio: ['pipe', 'pipe', 'ignore']
		})
			.trim()
			.split('\n')
			.pop()!
	);

const trip = (id: string): Trip => ({ id, name: id, stages: [], ...structuredClone(TRIPS[id]) }) as unknown as Trip;
const ort = (id: string): ComparePreset => ({ id, name: id, location_ids: [], ...structuredClone(ORTE[id]) }) as unknown as ComparePreset;

describe('p12 Trip: Reiter Zustellung zeigt, was der Versand tut', () => {
	for (const id of Object.keys(TRIPS)) {
		test(`tl7_briefing_email_gleich_versand_${id}`, () => {
			assert.equal(standAusTrip(trip(id)).briefing.email, AUS.trip[id].email);
		});
		test(`tl2_stille_gleich_alarm_${id}`, () => {
			assert.equal(standAusTrip(trip(id)).stilleAn, AUS.trip[id].stille);
		});
	}
});

describe('p12 Orte: Reiter Zustellung zeigt, was Versand und Alarm tun', () => {
	for (const id of Object.keys(ORTE)) {
		test(`tl1_slots_gleich_versand_${id}`, () => {
			const s = standAusPreset(ort(id));
			assert.deepEqual([s.morgenAn, s.abendAn], [AUS.orte[id].morgen, AUS.orte[id].abend]);
		});
		test(`tl2_stille_gleich_alarm_${id}`, () => {
			assert.equal(standAusPreset(ort(id)).stilleAn, AUS.orte[id].stille);
		});
		// #3297: TL3 (kanalStilStart) entfaellt — der Leser hatte keinen Produktions-Aufrufer mehr; den
		// Kurzstil liest die Karte „Was steht wo“ aus der Server-Antwort (felderAusAntwort).
	}

	test('messaufbau_faelle_decken_beide_werte', () => {
		const werte = (f: (v: (typeof AUS.orte)[string]) => unknown) => new Set(Object.values(AUS.orte).map(f)).size;
		assert.equal(werte((v) => v.abend), 2);
		assert.equal(werte((v) => v.stil), 2);
		assert.equal(werte((v) => v.stille), 2);
		assert.equal(new Set(Object.values(AUS.trip).map((v) => v.email)).size, 2);
		assert.equal(new Set(Object.values(AUS.trip).map((v) => v.stille)).size, 2);
	});
});

// TDD RED — Issue #3297 (+ #3020, Epic #3122): der Trip-Pfad schreibt keinen der sechs Altschluessel
// mehr; die Home-Anzeige „Layout je Kanal“ liest allein `display_config.placements.rows`.
// Spec: docs/specs/modules/feat_3297_trip_pfad_ohne_altfelder.md (AC-1, AC-2, AC-3, AC-4, AC-6)
//
// Reine Verhaltenstests ohne Mocks: die echten Bildner (ergaenzeStandardwerteReportConfig,
// buildCreateTripPayload, mitZustellung, tripNutzlast, zustellungNutzlast, buildAlarmeDeliveryPayload,
// kanalStilNutzlast, setupStepTrip) werden mit echten Eingaben getrieben; die Reiter-PUTs laufen gegen
// den Go-Merge-Ersatzserver (fakeTripServer, merge: true), der Bestand vorher/nachher wird verglichen.
//
// RED heute (Stand vor dem Rueckbau):
//   - AC-1/AC-2: der Anlege-Rumpf traegt `report_config.multi_day_trend_reports` (Vorbelegung #3155)
//     und `report_config.show_outlook` (ladeMailZustand).
//   - AC-3: der Reiter Wetter reicht die Bestands-`report_config` samt `show_outlook` und
//     `multi_day_trend_reports` im PUT /api/trips/{id} durch (ampelSchreiben.tripSpeicherPayload, klon).
//     Zustellung, Alarme und Kanal-Stil mit Vorher-Stand sind heute schon sauber (Regressionsschutz).
//   - AC-4: kanalStilNutzlast('route', …) ohne Vorher-Stand schreibt die drei Trend-Felder;
//     `kanalStilStart` ist noch exportiert.
//   - AC-6: setupStepTrip wertet `placements.rows` nicht aus (Layout bleibt offen).
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/components/trip-new/__tests__/trip_pfad_ohne_altfelder_3297.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import {
	buildCreateTripPayload,
	ergaenzeStandardwerteReportConfig,
	ergaenzeVersandStandard,
	initialCreateTripAlarmState,
	mitZustellung,
	type CreateTripState,
	type KarteAnlegeStand
} from '../tripNewLogic.ts';
import { felderAusAntwort, felderNutzlast } from '../../shared/wetter-tab/wasStehtWoSpeicherung.ts';
import * as kanalStil from '../../shared/zustellung-tab/kanalStilSpeicherung.ts';
import { kanalStilNutzlast } from '../../shared/zustellung-tab/kanalStilSpeicherung.ts';
import { standAusTrip } from '../../shared/zustellung-tab/zustellungModell.ts';
import { zustellungNutzlast } from '../../shared/zustellung-tab/zustellungSpeicherung.ts';
import { buildAlarmeDeliveryPayload } from '../../shared/alarme-tab/alarmeDeliveryPayload.ts';
import { tripNutzlast } from '../../shared/wetter-tab/wetterTabSpeicherung.ts';
import { standAusAbo, type AboSicht } from '../../shared/wetter-tab/wetterZustand.ts';
import { vorlagenAusTemplates } from '../../shared/wetter-tab/ampelModell.ts';
import { live } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import { setupStepTrip } from '../../../utils/cockpitHelpers568.ts';
import type { DisplayConfig, Trip } from '../../../types.ts';

const ALTSCHLUESSEL = [
	'channel_layouts',
	'channel_layouts_per_report',
	'outlook_metrics',
	'outlook_metric_formats',
	'show_outlook',
	'multi_day_trend_reports'
] as const;

/** Alle Fundstellen eines Altschluessels in beliebiger Tiefe (gefuellt ODER leer zaehlt). */
function altschluesselFunde(wert: unknown, pfad = ''): string[] {
	if (Array.isArray(wert)) return wert.flatMap((v, i) => altschluesselFunde(v, `${pfad}[${i}]`));
	if (!wert || typeof wert !== 'object') return [];
	const funde: string[] = [];
	for (const [k, v] of Object.entries(wert as Record<string, unknown>)) {
		const hier = pfad ? `${pfad}.${k}` : k;
		if ((ALTSCHLUESSEL as readonly string[]).includes(k)) funde.push(hier);
		funde.push(...altschluesselFunde(v, hier));
	}
	return funde;
}

// ── Anlage ────────────────────────────────────────────────────────────────────

function anlegeStand(extra: Partial<CreateTripState> = {}): CreateTripState {
	return {
		name: 'GR20 Nord 3297',
		startDate: '2027-07-01',
		stages: [{ id: 1, name: 'Calenzana – Ortu di u Piobbu' }],
		weatherMetrics: [{ metric_id: 'wind', enabled: true } as never],
		channels: { email: true, telegram: false, sms: false },
		alarm: initialCreateTripAlarmState(),
		...extra
	};
}

const KARTE: KarteAnlegeStand = (() => {
	const felder = felderAusAntwort({ blocks: {} } as never);
	return {
		placements: {
			version: 1,
			rows: [{ metric_id: 'temp_max_c', places: { email: ['tabelle'], telegram: true } }],
			outlook_reports: ['evening']
		},
		felder: { ...felder, telegram_style: 'kurzform' },
		felderStart: felder
	};
})();

describe('#3297 AC-1: Trip-Anlage (POST) ohne Altschluessel', () => {
	test('Anlege-Rumpf (Speicherweg wie TripNewEditor.buildAndSave) traegt keinen Altschluessel', () => {
		const body = buildCreateTripPayload(anlegeStand({ reportConfig: ergaenzeStandardwerteReportConfig(undefined) }));
		assert.deepEqual(altschluesselFunde(body), [], 'POST /api/trips enthaelt Altschluessel');
	});

	test('mit bedientem Reiter Zustellung (mitZustellung) bleibt der Rumpf frei von Altschluesseln', () => {
		const leer = initialCreateTripAlarmState();
		const stand = { ...standAusTrip({ id: 'neu', name: 'x', stages: [] } as unknown as Trip), morgenAn: true, abendAn: false };
		const r = mitZustellung(undefined, leer, stand);
		const body = buildCreateTripPayload(anlegeStand({ reportConfig: ergaenzeStandardwerteReportConfig(r.reportConfig), alarm: r.alarm }));
		assert.deepEqual(altschluesselFunde(body), [], 'POST /api/trips enthaelt Altschluessel');
		assert.equal((body.report_config as Record<string, unknown>).morning_enabled, true, 'Zustellungs-Stand fehlt im POST');
	});

	test('Versand-Standard belegt den Ausblick nicht mehr vor (kein multi_day_trend_reports, auch nicht leer)', () => {
		const rc = ergaenzeVersandStandard(undefined) as Record<string, unknown>;
		assert.ok(!('multi_day_trend_reports' in rc), 'Vorbelegung multi_day_trend_reports noch im Versand-Standard');
		assert.equal(rc.enabled, true, 'Standard-Versandeinstellungen fehlen');
	});
});

describe('#3297 AC-2: Anlage „Mit Standardwerten“ ohne Altschluessel, placements aus der Karte', () => {
	test('Standardwerte-Rumpf ohne Altschluessel, Tabelle der Karte steht in display_config.placements', () => {
		const body = buildCreateTripPayload(anlegeStand({ reportConfig: ergaenzeStandardwerteReportConfig(undefined), karte: KARTE }));
		assert.deepEqual(altschluesselFunde(body), [], 'POST (Standardwerte) enthaelt Altschluessel');
		const dc = body.display_config as Record<string, unknown>;
		assert.deepEqual(dc.placements, KARTE.placements, 'placements der Karte fehlen im POST');
		assert.equal((body.report_config as Record<string, unknown>).telegram_style, 'kurzform', 'Karten-Schalter fehlt');
	});

	test('Standardwerte ergaenzen weiterhin die Mail-Inhalt-Felder (ohne show_outlook)', () => {
		const rc = ergaenzeStandardwerteReportConfig(undefined) as Record<string, unknown>;
		assert.ok(!('show_outlook' in rc), 'show_outlook noch in den Standardwerten');
		assert.equal(rc.show_stage_stats, true, 'Mail-Inhalt-Standard show_stage_stats fehlt');
		assert.equal(rc.email_format, 'full', 'Mail-Inhalt-Standard email_format fehlt');
	});
});

// ── Reiter-PUTs gegen den Go-Merge-Ersatzserver ──────────────────────────────

const ID = 'trip-3297';
const BESTAND = {
	name: 'Bestand mit Altfeldern',
	stages: [{ id: 's1', name: 'Tag 1', date: '2027-07-01', waypoints: [] }],
	report_config: {
		enabled: true,
		morning_enabled: true,
		morning_time: '07:00:00',
		evening_enabled: true,
		evening_time: '18:00:00',
		send_email: true,
		telegram_style: 'rich',
		show_outlook: true,
		multi_day_trend_reports: ['evening'],
		day_window_start_hour: 6,
		day_window_end_hour: 20
	},
	display_config: {
		metrics: [{ metric_id: 'wind', enabled: true }],
		placements: { version: 1, rows: [{ metric_id: 'wind_max_kmh', places: { email: ['tabelle'] } }], outlook_reports: ['evening'] },
		channel_layouts: { email: ['wind_max_kmh'] },
		channel_layouts_per_report: { morning: { email: ['wind_max_kmh'] } },
		outlook_metrics: ['temp_max_c'],
		outlook_metric_formats: { temp_max_c: true }
	}
};

let server: FakeTripServer;
beforeEach(() => {
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(ID, structuredClone(BESTAND));
});
afterEach(() => server.restore());

const put = (pfad: string, body: unknown) =>
	fetch(pfad, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

async function abo(): Promise<Trip> {
	return (await (await fetch(`/api/trips/${ID}`)).json()) as Trip;
}

/** Bestand nach dem Speichern: jedes nicht geaenderte Bestandsfeld steht noch (Read-Modify-Write). */
function bestandErhalten(geaendert: Record<string, string[]> = {}): void {
	const s = server.stand(ID) as Record<string, Record<string, unknown>>;
	for (const teil of ['report_config', 'display_config'] as const) {
		for (const [k, v] of Object.entries(BESTAND[teil])) {
			if ((geaendert[teil] ?? []).includes(k)) continue;
			assert.deepEqual(s[teil][k], v, `${teil}.${k} nach dem Go-Merge verloren/veraendert`);
		}
	}
}

describe('#3297 AC-3: Reiter-PUTs ohne Altschluessel, Bestand bleibt (Go-Merge)', () => {
	test('Reiter Wetter: beide PUTs ohne Altschluessel, Bestand sonst erhalten', async () => {
		const trip = (await abo()) as unknown as AboSicht;
		const v = vorlagenAusTemplates(live().templates);
		const stand = standAusAbo('route', trip, v);
		const n = tripNutzlast({ client: null as never, stand: () => stand, vorlagen: () => v, abo: () => trip });
		assert.deepEqual(altschluesselFunde(n.weatherConfig), [], 'PUT /weather-config enthaelt Altschluessel');
		assert.deepEqual(altschluesselFunde(n.tripFelder), [], 'PUT /api/trips enthaelt Altschluessel (Bestand durchgereicht)');
		assert.ok((await put(`/api/trips/${ID}/weather-config`, n.weatherConfig)).ok);
		assert.ok((await put(`/api/trips/${ID}`, n.tripFelder)).ok);
		bestandErhalten({ display_config: ['metrics'] });
	});

	test('Reiter Zustellung (Regressionsschutz, heute gruen): PUT ohne Altschluessel, Bestand bleibt', async () => {
		const vorher = standAusTrip(await abo());
		const n = zustellungNutzlast('route', vorher, { ...vorher, abendAn: false, cooldown: 45 });
		assert.ok(n.versand && n.alarme);
		assert.deepEqual(altschluesselFunde(n), [], 'Zustellungs-PUT enthaelt Altschluessel');
		assert.ok((await put(`/api/trips/${ID}`, n.versand)).ok);
		assert.ok((await put(`/api/trips/${ID}`, n.alarme)).ok);
		assert.equal((server.stand(ID).report_config as Record<string, unknown>).evening_enabled, false);
		bestandErhalten({ report_config: ['evening_enabled', 'enabled'] });
	});

	test('Reiter Alarme (Regressionsschutz, heute gruen): PUT ohne Altschluessel, Bestand bleibt', async () => {
		const a = initialCreateTripAlarmState();
		const body = buildAlarmeDeliveryPayload({
			officialWarningsEnabled: true,
			cooldownMinutes: 90,
			channels: a.channels,
			channelThresholds: a.channelThresholds,
			metricLevels: { wind: 'hoch' }
		});
		assert.deepEqual(altschluesselFunde(body), [], 'Alarme-PUT enthaelt Altschluessel');
		assert.ok((await put(`/api/trips/${ID}`, body)).ok);
		bestandErhalten();
	});

	test('Karte „Was steht wo“, Schalter Kurzstil (Regressionsschutz, heute gruen): nur telegram_style', async () => {
		const alt = felderAusAntwort({ blocks: {} } as never);
		const body = felderNutzlast('route', { ...alt, telegram_style: 'kurzform' }, alt);
		assert.deepEqual(body, { report_config: { telegram_style: 'kurzform' } });
		assert.ok((await put(`/api/trips/${ID}`, body)).ok);
		bestandErhalten({ report_config: ['telegram_style'] });
	});
});

// ── Kanal-Stil ────────────────────────────────────────────────────────────────

describe('#3297 AC-4: Kanal-Stil-Nutzlast nur mit telegram_style', () => {
	test('ohne Vorher-Stand: Body traegt nur telegram_style, keine Trend-Felder', () => {
		const body = kanalStilNutzlast('route', { stil: 'kurzform' } as never);
		assert.deepEqual(body, { report_config: { telegram_style: 'kurzform' } });
	});

	test('mit Vorher-Stand (Stilwechsel): nur telegram_style', () => {
		const body = kanalStilNutzlast('route', { stil: 'rich' } as never, { stil: 'kurzform' } as never);
		assert.deepEqual(body, { report_config: { telegram_style: 'rich' } });
	});

	test('kanalStilStart (ohne Produktions-Aufrufer, las multi_day_trend_reports) ist nicht mehr exportiert', () => {
		assert.ok(!('kanalStilStart' in kanalStil), 'kanalStilStart ist noch exportiert');
	});
});

// ── Typ + Verhalten Home-Anzeige ──────────────────────────────────────────────

describe('#3297 AC-6: DisplayConfig kennt placements, hasLayout wertet es aus', () => {
	test('typisierter Trip mit placements (rows + outlook_reports) gilt als „Layout je Kanal“ erledigt', () => {
		// Kein Cast auf display_config: der Typ-Check (svelte-check) prueft per Ueberschuss-Pruefung des
		// Objekt-Literals, dass `placements` ein bekanntes Feld von DisplayConfig ist.
		const dc: DisplayConfig = {
			placements: { rows: [{ metric_id: 'wind_max_kmh', places: { email: ['tabelle'] } }], outlook_reports: ['evening'] }
		};
		const t = { id: 't-3297', name: 'Typ 3297', stages: [], display_config: dc } as unknown as Trip;
		assert.equal(setupStepTrip(t)[3].done, true, 'placements.rows werden fuer „Layout“ nicht ausgewertet');
	});
});

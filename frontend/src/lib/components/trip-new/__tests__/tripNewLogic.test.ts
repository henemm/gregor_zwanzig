// TDD RED — Issue #622 Slice 1: Progressive Tab Editor /trips/new
//
// Pure-Logik-Verträge für den Anlege-Flow, 1:1 gespiegelt aus der verbindlichen
// JSX `docs/design-requests/trip-anlegen-2026-06-06/screen-trip-new-v2.jsx`
// (TN_unlocked / TN_doneSet / TN_stageDate / TN_Progress).
//
// Echte Verhaltens-Tests (kein Mock). VOR der Implementierung SCHEITERN sie (RED),
// weil `tripNewLogic.ts` noch nicht existiert.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-new/__tests__/tripNewLogic.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
	unlockedTabs,
	doneTabs,
	stageDate,
	progressCount,
	canSave,
	buildCreateTripPayload,
	type CreateTripState,
} from '../tripNewLogic.ts';
// TDD RED — Issue #2277 Scheibe S1: initialCreateTripAlarmState()/applyAlarm*()
// existieren in tripNewLogic.ts noch nicht. Namespace-Import statt Named-Import
// (Muster docs/reference/gates_und_ratschen.md-Lehre "Import ueber Namespace"):
// ein Named-Import eines nicht existierenden Exports scheitert beim Modul-Linking
// und reisst ALLE Tests dieser Datei mit — auch die laengst gruenen oben. Ueber
// den Namespace bleibt der Import selbst gruen; erst der tatsaechliche Aufruf
// eines (noch) fehlenden Exports scheitert je Testfall einzeln.
import * as tripNewLogicNs from '../tripNewLogic.ts';
import {
	resolveAlertChannels,
	resolveAlertChannelThresholds,
} from '../../shared/alarme-tab/alertChannelState.ts';
import { reconstructTripAlertChannels } from '../../shared/alarme-tab/tripChannelReconstruction.ts';
// Issue #2277 S2a — echte Editor-Zeilenlogik (kein Hand-Fixture fuer corridors).
import {
	buildRoutePool,
	addRow,
	patchRow,
	buildCorridorSavePayload,
} from '../../shared/corridor-editor/corridorEditorState.ts';

// ── AC-2/AC-3: Progressiver Lock-State (TN_unlocked) ────────────────────────
//
// Issue #2277 Scheibe S3 (Spec feat_2277_s3_reiter_angleichung_rueckbau.md,
// AC-2/AC-4): die Kette laeuft jetzt wie beim Ortsvergleich
// (geteilter Kern `shared/anlegeLockEngine.ts`) ueber Wertebereiche -> Alarme -> Versand. Signatur:
//   unlockedTabs/doneTabs(name, startDate, etDone, wtVisited, wbVisited, alVisited, vsVisited)
// `alVisited` = Reiter Alarme besucht, `vsVisited` = Reiter Versand besucht.
// Tab-IDs `alarme`/`versand` ersetzen `alerts`/`zeitplan` (gleich wie CompareNewEditor).

describe('AC-2/3: unlockedTabs — progressive Freischaltung', () => {
	test('Leerzustand: nur Route offen', () => {
		const u = unlockedTabs('', '', false, false, false, false, false);
		assert.deepEqual([...u].sort(), ['route']);
	});

	test('Name + Startdatum → Etappen schaltet frei', () => {
		const u = unlockedTabs('GR20', '2026-06-15', false, false, false, false, false);
		assert.ok(u.has('etappen'), 'Etappen muss frei sein');
		assert.ok(!u.has('metriken'), 'Wetter noch gesperrt');
	});

	test('Name ohne Startdatum schaltet Etappen NICHT frei', () => {
		const u = unlockedTabs('GR20', '', false, false, false, false, false);
		assert.ok(!u.has('etappen'));
	});

	test('etDone → Wegpunkte UND Wetter schalten gleichzeitig frei', () => {
		const u = unlockedTabs('GR20', '2026-06-15', true, false, false, false, false);
		assert.ok(u.has('wegpunkte'), 'Wegpunkte frei');
		assert.ok(u.has('metriken'), 'Wetter frei');
		assert.ok(!u.has('alarme'), 'Alarme noch gesperrt');
		assert.ok(!u.has('versand'), 'Versand noch gesperrt');
	});

	test('AC-2: Wertebereiche besucht → Alarme frei, Versand bleibt GESPERRT', () => {
		const u = unlockedTabs('GR20', '2026-06-15', true, true, true, false, false);
		assert.ok(u.has('alarme'), 'AC-2 FAIL: Alarme muss nach Besuch von Wertebereiche frei sein.');
		assert.ok(
			!u.has('versand'),
			'AC-2 FAIL: Versand ist schon nach Wertebereiche frei — er muss an den Besuch von Alarme gekoppelt sein.'
		);
	});

	test('AC-2: Alarme besucht → Versand frei', () => {
		const u = unlockedTabs('GR20', '2026-06-15', true, true, true, true, false);
		assert.ok(u.has('versand'), 'AC-2 FAIL: Versand muss nach Besuch von Alarme frei sein.');
	});

	test('AC-1: die alten IDs zeitplan/alerts kommen in der Kette nicht mehr vor', () => {
		const ids = [...unlockedTabs('GR20', '2026-06-15', true, true, true, true, true)] as string[];
		assert.ok(!ids.includes('zeitplan'), `AC-1 FAIL: alte Tab-ID "zeitplan" noch freigeschaltet: ${ids.join(', ')}`);
		assert.ok(!ids.includes('alerts'), `AC-1 FAIL: alte Tab-ID "alerts" noch freigeschaltet: ${ids.join(', ')}`);
	});
});

// ── doneSet (TN_doneSet) ────────────────────────────────────────────────────

describe('doneTabs — Done-Zustand', () => {
	test('Name+Datum → route done; etDone → etappen done', () => {
		const d = doneTabs('GR20', '2026-06-15', true, false, false, false, false);
		assert.ok(d.has('route'));
		assert.ok(d.has('etappen'));
		assert.ok(!d.has('metriken'));
	});

	test('wtVisited → metriken; alVisited → alarme; vsVisited → versand done', () => {
		const d = doneTabs('GR20', '2026-06-15', true, true, true, true, true);
		assert.ok(d.has('metriken'));
		assert.ok(d.has('alarme'));
		assert.ok(d.has('versand'));
	});

	test('Alarme besucht, Versand nicht → versand NICHT done', () => {
		const d = doneTabs('GR20', '2026-06-15', true, true, true, true, false);
		assert.ok(d.has('alarme'));
		assert.ok(!d.has('versand'));
	});
});

// ── AC-1 (#622) / AC-4 (#2277 S3): Fortschrittsbalken — 4 Pflicht-Abschnitte ─

describe('AC-4: progressCount — bleibt „/4" mit Meilenstein Versand', () => {
	test('alle Reiter besucht → 4 (Alarme zählt NICHT als eigener Meilenstein)', () => {
		const done = doneTabs('GR20', '2026-06-15', true, true, true, true, true);
		assert.equal(progressCount(done), 4, 'AC-4 FAIL: Fortschritt muss bei „/4" bleiben.');
	});
	test('Versand nicht besucht → 3 (Versand ist der vierte Meilenstein)', () => {
		const done = doneTabs('GR20', '2026-06-15', true, true, true, true, false);
		assert.equal(progressCount(done), 3, 'AC-4 FAIL: der vierte Meilenstein muss Versand sein.');
	});
	test('Leerzustand = 0', () => {
		assert.equal(progressCount(doneTabs('', '', false, false, false, false, false)), 0);
	});
});

// ── AC-4: Etappen-Auto-Datum (TN_stageDate) ─────────────────────────────────

describe('AC-4: stageDate — Startdatum + Index-Tage', () => {
	test('Offset 0 = Startdatum (DD.MM.)', () => {
		assert.equal(stageDate('2026-06-15', 0), '15.06.');
	});
	test('Offset 3 Tage', () => {
		assert.equal(stageDate('2026-06-15', 3), '18.06.');
	});
	test('Monatswechsel korrekt', () => {
		assert.equal(stageDate('2026-06-29', 3), '02.07.');
	});
	test('Leeres Startdatum → null', () => {
		assert.equal(stageDate('', 0), null);
	});
});

// ── AC-7: Speichern (canSave + buildCreateTripPayload) ──────────────────────

describe('AC-4 (#2277 S3): canSave — erst nach Versand-Besuch', () => {
	test('Wertebereiche besucht, Alarme nicht → false', () => {
		assert.equal(canSave(doneTabs('GR20', '2026-06-15', true, true, true, false, false)), false);
	});
	test('Alarme besucht, Versand nicht → false', () => {
		assert.equal(
			canSave(doneTabs('GR20', '2026-06-15', true, true, true, true, false)),
			false,
			'AC-4 FAIL: „Anlegen" ist schon nach Alarme aktiv — es muss an den Besuch von Versand gekoppelt sein.'
		);
	});
	test('Versand besucht → true', () => {
		assert.equal(canSave(doneTabs('GR20', '2026-06-15', true, true, true, true, true)), true);
	});
});

// Issue #2277 Scheibe S1 (AC-7): `alertRules` ist Alt-Modell (AlertRulesEditor,
// bind:rules) und wird aus CreateTripState entfernt — der Alarme-Reiter von
// /trips/new schreibt seit dieser Scheibe ueber den `alarm`-Schatten-State
// (siehe unten), nicht mehr ueber ein Regel-Array. Die alte Payload-Assertion
// auf `p.alert_rules` ist deshalb ersatzlos entfernt (Affected-Files-Auflage
// der Spec), nicht auf eine neue Erwartung umgeschrieben.
function baseTripState(): CreateTripState {
	return {
		name: 'Karnischer Höhenweg',
		region: 'Karnische Alpen',
		startDate: '2026-06-15',
		stages: [
			{ id: 1, name: 'Toblach → Helmhotel' },
			{ id: 2, name: 'Helmhotel → Sillianer Hütte' },
		],
		weatherMetrics: [{ key: 'temp', enabled: true }],
		channels: { email: true, telegram: true, sms: false },
		reportConfig: { enabled: true, morning_time: '06:00', evening_time: '18:00' },
	};
}

describe('AC-7: buildCreateTripPayload — vollständiger POST-Payload, kein Datenverlust', () => {
	const state: CreateTripState = baseTripState();

	test('Name/Region/Startdatum übernommen', () => {
		const p = buildCreateTripPayload(state);
		assert.equal(p.name, 'Karnischer Höhenweg');
		assert.equal(p.region, 'Karnische Alpen');
	});

	test('Etappen tragen Auto-Datum (Start + Index, ISO)', () => {
		const p = buildCreateTripPayload(state);
		assert.equal(p.stages.length, 2);
		assert.equal(p.stages[0].name, 'Toblach → Helmhotel');
		assert.equal(p.stages[0].date, '2026-06-15');
		assert.equal(p.stages[1].date, '2026-06-16');
	});

	test('display_config trägt Metriken + Kanäle (AC-6 Kanal-Binding)', () => {
		const p = buildCreateTripPayload(state);
		assert.ok(p.display_config, 'display_config vorhanden');
		assert.deepEqual(p.display_config!.channels, { email: true, telegram: true, sms: false });
		assert.ok(Array.isArray(p.display_config!.metrics));
	});

	test('report_config durchgereicht (kein Datenverlust)', () => {
		const p = buildCreateTripPayload(state);
		assert.ok(p.report_config, 'report_config vorhanden');
		assert.equal(p.report_config!.enabled, true);
	});

	test('jede Trip bekommt eine id', () => {
		const p = buildCreateTripPayload(state);
		assert.ok(typeof p.id === 'string' && p.id.length > 0);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// Issue #2277 Scheibe S1 — Alarm-Schatten-State fuer /trips/new
// (createMode-Ersatz fuer den Selbst-Speicherpfad von AlarmeTab.svelte)
// ═══════════════════════════════════════════════════════════════════════════

describe('initialCreateTripAlarmState — Startwert des Alarm-Schatten-States', () => {
	test('officialWarningsEnabled startet mit false — NICHT dem route-Bestands-Default true (AC-4)', () => {
		// Bewusst der ECHTE Aufruf, kein Hand-Literal (AC-4-Testrezept): eine
		// Mutation am produktiven Default muss GENAU hier auffallen.
		const s = tripNewLogicNs.initialCreateTripAlarmState!();
		assert.equal(s.officialWarningsEnabled, false);
	});

	test('channels/channelThresholds kommen aus denselben geteilten Default-Funktionen wie AlarmeTab.svelte', () => {
		const s = tripNewLogicNs.initialCreateTripAlarmState!();
		assert.deepEqual(s.channels, resolveAlertChannels(undefined));
		assert.deepEqual(s.channelThresholds, resolveAlertChannelThresholds(undefined));
	});

	test('metricLevels startet leer, Cooldown/Stille-Stunden sind nicht gesetzt', () => {
		const s = tripNewLogicNs.initialCreateTripAlarmState!();
		assert.deepEqual(s.metricLevels, {});
		assert.equal(s.cooldownMinutes, undefined);
		assert.equal(s.quietFrom, undefined);
		assert.equal(s.quietTo, undefined);
	});
});

describe('applyAlarmChannelToggle/applyAlarmThresholdChange/applyAlarmMetricLevelChange — reine Delta-Funktionen', () => {
	test('applyAlarmChannelToggle kehrt genau den einen genannten Kanal um', () => {
		const s0 = tripNewLogicNs.initialCreateTripAlarmState!();
		const s1 = tripNewLogicNs.applyAlarmChannelToggle!(s0, 'premium_sms');
		assert.equal(s1.channels.premium_sms, !s0.channels.premium_sms);
		assert.equal(s1.channels.telegram, s0.channels.telegram);
		assert.equal(s1.channels.sms, s0.channels.sms);
		assert.equal(s1.channels.email, s0.channels.email);
	});

	test('applyAlarmThresholdChange setzt den gespeicherten WERT ("HIGH"), nicht das Label ("hoch")', () => {
		// Memory reference_alarm_schalter_zwei_bauarten_hinter_aehnlichen_testids:
		// "hoch" ist nur CHANNEL_THRESHOLD_LABELS — der gespeicherte Wert ist 'HIGH'.
		const s0 = tripNewLogicNs.initialCreateTripAlarmState!();
		const s1 = tripNewLogicNs.applyAlarmThresholdChange!(s0, 'sms', 'HIGH');
		assert.equal(s1.channelThresholds.sms, 'HIGH');
		assert.equal(s1.channelThresholds.telegram, s0.channelThresholds.telegram);
	});

	test('applyAlarmMetricLevelChange setzt die Stufe NUR der genannten Metrik', () => {
		const s0 = tripNewLogicNs.initialCreateTripAlarmState!();
		const s1 = tripNewLogicNs.applyAlarmMetricLevelChange!(s0, 'wind_gust', 'sensibel');
		assert.deepEqual(s1.metricLevels, { wind_gust: 'sensibel' });
	});
});

describe('AC-5: vollständiger Anlege-Durchlauf — Rundreise ohne Verlust über die DREI echten Lesewege', () => {
	// Premium-SMS an, eine Metrik-Stufe gesetzt, eine Kanal-Schwelle auf "hoch"
	// (Wert 'HIGH') — ausschließlich über die drei reinen Reducer-Funktionen.
	function gebauterPayload() {
		let alarm = tripNewLogicNs.initialCreateTripAlarmState!();
		alarm = tripNewLogicNs.applyAlarmChannelToggle!(alarm, 'premium_sms');
		alarm = tripNewLogicNs.applyAlarmThresholdChange!(alarm, 'sms', 'HIGH');
		alarm = tripNewLogicNs.applyAlarmMetricLevelChange!(alarm, 'wind_gust', 'sensibel');
		const payload = buildCreateTripPayload({ ...baseTripState(), alarm } as CreateTripState);
		return { payload, alarm };
	}

	test('Kanäle: reconstructTripAlertChannels(payload) zeigt exakt den gesetzten Kanal-Stand', () => {
		const { payload, alarm } = gebauterPayload();
		const kanaele = reconstructTripAlertChannels(payload);
		assert.deepEqual(kanaele, alarm.channels);
	});

	test('Kanal-Schwellen: trip.alert_channel_thresholds.sms === "HIGH"', () => {
		const { payload } = gebauterPayload();
		assert.equal(
			(payload.alert_channel_thresholds as Record<string, string> | undefined)?.sms,
			'HIGH'
		);
	});

	test('Metrik-Level: trip.display_config.metric_alert_levels trägt die gesetzte Stufe', () => {
		const { payload } = gebauterPayload();
		assert.deepEqual(
			(payload.display_config as Record<string, unknown> | undefined)?.metric_alert_levels,
			{ wind_gust: 'sensibel' }
		);
	});

	test('Read-Modify-Write: display_config.channels/metrics bleiben beim Alarm-Merge erhalten (CLAUDE.md „Daten-Schema-Reworks")', () => {
		const { payload } = gebauterPayload();
		const dc = payload.display_config as Record<string, unknown> | undefined;
		assert.ok(dc?.channels, 'display_config.channels fehlt nach dem Alarm-Merge (Ersetzen statt Mergen)');
		assert.ok(Array.isArray(dc?.metrics), 'display_config.metrics fehlt nach dem Alarm-Merge (Ersetzen statt Mergen)');
	});
});

describe('AC-5 Zusatz: official_warnings/Cooldown/Stille-Stunden landen im Payload', () => {
	test('official_warnings.enabled, alert_cooldown_minutes, alert_quiet_from/to werden übernommen', () => {
		const alarm = {
			...tripNewLogicNs.initialCreateTripAlarmState!(),
			officialWarningsEnabled: true,
			cooldownMinutes: 30,
			quietFrom: '22:00',
			quietTo: '07:00',
		};
		const payload = buildCreateTripPayload({ ...baseTripState(), alarm } as CreateTripState);
		assert.equal((payload.official_warnings as Record<string, unknown> | undefined)?.enabled, true);
		assert.equal(payload.alert_cooldown_minutes, 30);
		assert.equal(payload.alert_quiet_from, '22:00');
		assert.equal(payload.alert_quiet_to, '07:00');
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// Issue #2277 Scheibe S2a — Reiter „Wertebereiche" in /trips/new
// Spec: docs/specs/modules/fix_2277_s2a_wertebereiche_trip_anlegen.md
// Signatur seit #2277 S3: unlockedTabs/doneTabs(name, startDate, etDone, wtVisited, wbVisited, alVisited, vsVisited)
// ═══════════════════════════════════════════════════════════════════════════

// Issue #2277 S3: die S2a-Kette „Wertebereiche → Zeitplan" ist abgeloest
// (Spec feat_2277_s3, Abschnitt „Abgeloeste freigegebene ACs") — hinter
// Wertebereiche folgt jetzt Alarme. Die Wertebereiche-Zusicherungen selbst bleiben.
describe('AC-1 (S2a, Kette nach S3): Wetter-Metriken → Wertebereiche → Alarme', () => {
	test('etDone, Wetter noch nicht besucht → Wertebereiche gesperrt', () => {
		const u = unlockedTabs('GR20', '2026-06-15', true, false, false, false, false);
		assert.ok(!u.has('wertebereiche' as never), 'Wertebereiche darf vor dem Wetter-Besuch nicht frei sein');
	});

	test('Wetter besucht → Wertebereiche frei, Alarme NOCH gesperrt', () => {
		const u = unlockedTabs('GR20', '2026-06-15', true, true, false, false, false);
		assert.ok(u.has('wertebereiche' as never), 'AC-1 FAIL: Wertebereiche nach Wetter-Besuch nicht frei');
		assert.ok(
			!u.has('alarme'),
			'AC-1 FAIL: Alarme ist schon nach dem Wetter-Reiter frei — die Kette muss ueber Wertebereiche laufen'
		);
	});

	test('Wertebereiche besucht → Alarme frei, Versand noch gesperrt', () => {
		const u = unlockedTabs('GR20', '2026-06-15', true, true, true, false, false);
		assert.ok(u.has('alarme'), 'AC-1 FAIL: Alarme nach Wertebereiche-Besuch nicht frei');
		assert.ok(!u.has('versand'), 'Versand erst nach Alarme-Besuch');
	});

	test('doneTabs markiert wertebereiche erst bei wbVisited', () => {
		assert.ok(!doneTabs('GR20', '2026-06-15', true, true, false, false, false).has('wertebereiche' as never));
		assert.ok(
			doneTabs('GR20', '2026-06-15', true, true, true, false, false).has('wertebereiche' as never),
			'AC-1 FAIL: doneTabs markiert den besuchten Wertebereiche-Reiter nicht als erledigt'
		);
	});

	test('progressCount bleibt bei 4 Segmenten (Wertebereiche ist kein eigenes Segment)', () => {
		assert.equal(progressCount(doneTabs('GR20', '2026-06-15', true, true, true, true, true)), 4);
	});
});

describe('AC-2/AC-6 (S2a): buildCreateTripPayload traegt corridors', () => {
	test('AC-6: ohne corridors im State → payload.corridors ist exakt [] (nie undefined/null)', () => {
		const p = buildCreateTripPayload(baseTripState()) as { corridors?: unknown };
		assert.ok('corridors' in p, 'AC-6 FAIL: payload hat kein corridors-Feld — der POST-Body liesse es weg');
		assert.deepEqual(p.corridors, [], 'AC-6 FAIL: payload.corridors ist nicht []');
	});

	test('AC-2: corridors aus der echten Editor-Zeilenlogik landen unveraendert im Payload', () => {
		// Zeilen ueber die ECHTEN Editor-Funktionen (addRow/patchRow/buildCorridorSavePayload),
		// kein von Hand gebautes Corridor-Array.
		const pool = buildRoutePool([], [{ metric_id: 'gust', enabled: true }] as never, []);
		let rows = addRow(pool.rows, pool.poolLeft, 'wind_gust').rows;
		rows = patchRow(rows, 'wind_gust', { max: 80 });
		const corridors = buildCorridorSavePayload(rows, {}).corridors;
		const p = buildCreateTripPayload({ ...baseTripState(), corridors } as CreateTripState) as {
			corridors?: unknown;
		};
		assert.deepEqual(
			p.corridors,
			[{ metric: 'wind_gust', range: [null, 80], notify: true, mark: false }],
			'AC-2 FAIL: der eingestellte Wertebereich steht nicht exakt im POST-Payload'
		);
	});

	test('corridors ist additiv — display_config/report_config bleiben erhalten', () => {
		const corridors = [{ metric: 'wind_gust', range: [null, 80], notify: true, mark: false }];
		const p = buildCreateTripPayload({ ...baseTripState(), corridors } as CreateTripState);
		assert.deepEqual(p.display_config!.channels, { email: true, telegram: true, sms: false });
		assert.equal(p.report_config!.enabled, true);
		assert.deepEqual((p as { corridors?: unknown }).corridors, corridors);
	});
});

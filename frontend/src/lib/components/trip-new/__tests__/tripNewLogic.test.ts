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

// ── AC-2/AC-3: Progressiver Lock-State (TN_unlocked) ────────────────────────

describe('AC-2/3: unlockedTabs — progressive Freischaltung', () => {
	test('Leerzustand: nur Route offen', () => {
		const u = unlockedTabs('', '', false, false, false);
		assert.deepEqual([...u].sort(), ['route']);
	});

	test('Name + Startdatum → Etappen schaltet frei', () => {
		const u = unlockedTabs('GR20', '2026-06-15', false, false, false);
		assert.ok(u.has('etappen'), 'Etappen muss frei sein');
		assert.ok(!u.has('metriken'), 'Wetter noch gesperrt');
	});

	test('Name ohne Startdatum schaltet Etappen NICHT frei', () => {
		const u = unlockedTabs('GR20', '', false, false, false);
		assert.ok(!u.has('etappen'));
	});

	test('etDone → Wegpunkte UND Wetter schalten gleichzeitig frei', () => {
		const u = unlockedTabs('GR20', '2026-06-15', true, false, false);
		assert.ok(u.has('wegpunkte'), 'Wegpunkte frei');
		assert.ok(u.has('metriken'), 'Wetter frei');
		assert.ok(!u.has('zeitplan'), 'Zeitplan noch gesperrt');
	});

	test('Wetter besucht → Zeitplan frei; Zeitplan besucht → Alerts frei', () => {
		const u1 = unlockedTabs('GR20', '2026-06-15', true, true, false);
		assert.ok(u1.has('zeitplan'));
		assert.ok(!u1.has('alerts'));
		const u2 = unlockedTabs('GR20', '2026-06-15', true, true, true);
		assert.ok(u2.has('alerts'));
	});
});

// ── doneSet (TN_doneSet) ────────────────────────────────────────────────────

describe('doneTabs — Done-Zustand', () => {
	test('Name+Datum → route done; etDone → etappen done', () => {
		const d = doneTabs('GR20', '2026-06-15', true, false, false);
		assert.ok(d.has('route'));
		assert.ok(d.has('etappen'));
		assert.ok(!d.has('metriken'));
	});

	test('wtVisited → metriken done; ztVisited → zeitplan done', () => {
		const d = doneTabs('GR20', '2026-06-15', true, true, true);
		assert.ok(d.has('metriken'));
		assert.ok(d.has('zeitplan'));
	});
});

// ── AC-1: Fortschrittsbalken (TN_Progress) — 4 Pflicht-Abschnitte ───────────

describe('AC-1: progressCount — 4 Segmente (kein Wegpunkte-Segment)', () => {
	test('zählt nur route/etappen/metriken/zeitplan', () => {
		const done = doneTabs('GR20', '2026-06-15', true, true, true);
		assert.equal(progressCount(done), 4);
	});
	test('Leerzustand = 0', () => {
		assert.equal(progressCount(doneTabs('', '', false, false, false)), 0);
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

describe('AC-7: canSave — erst nach Zeitplan-Besuch', () => {
	test('Zeitplan nicht besucht → false', () => {
		assert.equal(canSave(doneTabs('GR20', '2026-06-15', true, true, false)), false);
	});
	test('Zeitplan besucht → true', () => {
		assert.equal(canSave(doneTabs('GR20', '2026-06-15', true, true, true)), true);
	});
});

describe('AC-7: buildCreateTripPayload — vollständiger POST-Payload, kein Datenverlust', () => {
	const state: CreateTripState = {
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
		alertRules: [{ metric: 'rain', threshold: 5 }],
	};

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

	test('report_config + alert_rules durchgereicht (kein Datenverlust)', () => {
		const p = buildCreateTripPayload(state);
		assert.ok(p.report_config, 'report_config vorhanden');
		assert.equal(p.report_config!.enabled, true);
		assert.equal(p.alert_rules?.length, 1);
	});

	test('jede Tour bekommt eine id', () => {
		const p = buildCreateTripPayload(state);
		assert.ok(typeof p.id === 'string' && p.id.length > 0);
	});
});

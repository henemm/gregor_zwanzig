// TDD RED — Issue #3197 Fix-Loop 2 (Validierung Punkt 1): Trip-Anlegen verliert das
// Etappen-Tempo still.
//
// Spec: docs/specs/modules/feat_3197_tempo_je_etappe.md (AC-2, AC-4, AC-5, AC-6)
// PO-Regel: Anlegen und Bearbeiten = derselbe Code und dasselbe Verhalten.
//
// Im Anlege-Flow zeigt der eingebettete Etappen-Editor (EditStagesPanelNew) je Etappe
// „Tempo ändern". Die dort gesetzte Überschreibung muss
//   (a) den Tab-Wechsel überleben (Brücke Editor-Etappen ⇄ Anlege-Zustand),
//   (b) im POST-Rumpf landen (`buildCreateTripPayload`),
//   (c) beim Wechsel der Fortbewegung (Tempo-Karte im Reiter Etappen) verworfen und
//       gezählt werden (AC-6, wie im Bearbeiten).
// Echte Logik ohne Mock: dieselben reinen Funktionen, die TripNewEditor.svelte aufruft.
//
// Ausführung: cd frontend && npm test -- src/lib/components/trip-new/__tests__/tempo_je_etappe_3197_anlegen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
// Namespace-Import: fehlende Exporte scheitern je Testfall, nicht beim Modul-Linking.
import * as logik from '../tripNewLogic.ts';
import { ohneEtappenTempo } from '../../../utils/naismith.ts';
import type { Stage, Waypoint } from '../../../types.ts';

const wps = (p: string): Waypoint[] => [
	{ id: `${p}a`, name: 'A', lat: 47, lon: 11, elevation_m: 1000 },
	{ id: `${p}b`, name: 'B', lat: 47.02, lon: 11.02, elevation_m: 1600 },
];

type Lokal = logik.CreateTripStage;

function anlage(): Lokal[] {
	return [
		{ id: 1, name: 'Tag 1', waypoints: wps('s1') },
		{ id: 2, name: 'Tag 2', waypoints: wps('s2') },
		{ id: 3, name: 'Tag 3', waypoints: wps('s3') },
	];
}

/** Was der Knopf „Tempo ändern" im Editor tut (EditStagesPanelNew.etappenTempoSetzen). */
function setzeImEditor(editor: Stage[], idx: number, kmh: number): Stage[] {
	return editor.map((s, i) => (i === idx ? { ...s, grundtempo_kmh: kmh } : s));
}

describe('#3197 Anlegen: Etappen-Tempo geht nicht verloren', () => {
	test('POST-Rumpf trägt grundtempo_kmh der überschriebenen Etappe, die anderen ohne Feld', () => {
		const stages: Lokal[] = anlage();
		(stages[2] as Lokal & { grundtempo_kmh?: number }).grundtempo_kmh = 3;
		const trip = logik.buildCreateTripPayload({
			name: 'GR20',
			startDate: '2026-07-01',
			stages,
			channels: { email: true, telegram: false, sms: false },
			tempo: { fortbewegung: 'fuss', grundtempo_kmh: 4 },
		});
		assert.equal(trip.stages[2].grundtempo_kmh, 3, 'Etappe 3 muss ihr Tempo im POST tragen');
		assert.ok(!('grundtempo_kmh' in trip.stages[0]), 'Etappe 1 ohne Feld');
		assert.ok(!('grundtempo_kmh' in trip.stages[1]), 'Etappe 2 ohne Feld');
	});

	test('Editor → Anlege-Zustand → Editor: Überschreibung überlebt den Tab-Wechsel', () => {
		const editor = logik.editorEtappenAusAnlage(anlage(), '2026-07-01');
		assert.equal(editor.length, 3);
		assert.equal(editor[1].date, '2026-07-02');
		const geaendert = setzeImEditor(editor, 2, 3);
		const zurueck = logik.anlageAusEditorEtappen(anlage(), geaendert);
		assert.equal(zurueck[2].grundtempo_kmh, 3, 'Rückweg verliert das Etappen-Tempo');
		assert.ok(!('grundtempo_kmh' in zurueck[0]));
		// Erneutes Öffnen des Reiters baut die Editor-Etappen aus dem Anlege-Zustand neu.
		const wieder = logik.editorEtappenAusAnlage(zurueck, '2026-07-01');
		assert.equal(wieder[2].grundtempo_kmh, 3, 'Neuaufbau verliert das Etappen-Tempo');
		assert.deepEqual(wieder[2].waypoints, wps('s3'), 'Wegpunkte bleiben');
	});

	test('Wegpunkt-Änderungen aus dem Etappen-Editor werden übernommen (AC-5, #658, Adversary R3 F003)', () => {
		const lokal = anlage();
		const editor = logik.editorEtappenAusAnlage(lokal, '2026-07-01');
		// Im Editor: Etappe 2 Wegpunkt umbenannt, Etappe 3 um einen Wegpunkt ergänzt.
		const geaendert = editor.map((s, i) =>
			i === 1
				? { ...s, waypoints: s.waypoints.map((w, j) => (j === 0 ? { ...w, name: 'Hütte' } : w)) }
				: i === 2
					? { ...s, waypoints: [...s.waypoints, { id: 's3c', name: 'C', lat: 47.04, lon: 11.04, elevation_m: 1200 }] }
					: s
		);
		const zurueck = logik.anlageAusEditorEtappen(lokal, geaendert);
		assert.equal(zurueck[1].waypoints?.[0].name, 'Hütte', 'umbenannter Wegpunkt geht im Anlegen verloren');
		assert.equal(zurueck[2].waypoints?.length, 3, 'ergänzter Wegpunkt geht im Anlegen verloren');
		assert.deepEqual(zurueck[0].waypoints, wps('s1'), 'unberührte Etappe unverändert');
		// … und landet im POST-Rumpf.
		const trip = logik.buildCreateTripPayload({
			name: 'GR20',
			startDate: '2026-07-01',
			stages: zurueck,
			channels: { email: true, telegram: false, sms: false },
			tempo: { fortbewegung: 'fuss', grundtempo_kmh: 4 },
		});
		assert.equal(trip.stages[1].waypoints[0].name, 'Hütte');
		assert.equal(trip.stages[2].waypoints.length, 3);
	});

	test('„Trip-Tempo verwenden" im Editor entfernt das Feld auch im Anlege-Zustand (AC-4)', () => {
		const lokal = anlage();
		const mitTempo = logik.anlageAusEditorEtappen(lokal, setzeImEditor(logik.editorEtappenAusAnlage(lokal, '2026-07-01'), 1, 3));
		assert.equal(mitTempo[1].grundtempo_kmh, 3);
		const editor = logik.editorEtappenAusAnlage(mitTempo, '2026-07-01');
		const ohne = editor.map((s, i) => (i === 1 ? ohneEtappenTempo(s) : s));
		const zurueck = logik.anlageAusEditorEtappen(mitTempo, ohne);
		assert.ok(!('grundtempo_kmh' in zurueck[1]), 'Zurücknehmen muss das Feld entfernen');
	});

	test('Wechsel der Fortbewegung verwirft alle Überschreibungen und zählt sie (AC-6)', () => {
		const lokal = anlage().map((s, i) => (i === 0 || i === 2 ? { ...s, grundtempo_kmh: 3 } : s));
		const r = logik.tempoImAnlegenWechseln(
			lokal,
			{ fortbewegung: 'fuss', grundtempo_kmh: 4 },
			{ fortbewegung: 'rad', grundtempo_kmh: 18 }
		);
		assert.equal(r.anzahl, 2, 'Hinweis muss „2 Etappen" nennen');
		assert.ok(r.stages.every((s) => !('grundtempo_kmh' in s)), 'alle Überschreibungen verworfen');
		assert.deepEqual(r.stages[0].waypoints, wps('s1'), 'übrige Etappenfelder bleiben');
	});

	test('Nur Grundtempo des Trips geändert (gleiche Fortbewegung): Überschreibungen bleiben, kein Hinweis', () => {
		const lokal = anlage().map((s, i) => (i === 1 ? { ...s, grundtempo_kmh: 3 } : s));
		const r = logik.tempoImAnlegenWechseln(
			lokal,
			{ fortbewegung: 'fuss', grundtempo_kmh: 4 },
			{ fortbewegung: 'fuss', grundtempo_kmh: 5 }
		);
		assert.equal(r.anzahl, 0);
		assert.equal(r.stages[1].grundtempo_kmh, 3);
	});
});

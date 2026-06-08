// TDD RED — Issue #658 Slice 2 / AC-5+AC-6: Wegpunkte-Persistenz im Anlege-Flow.
//
// Spec: docs/specs/modules/issue_658_trip_new_wegpunkte_tab.md
//
// Echter Verhaltensnachweis (kein Mock): `buildCreateTripPayload` MUSS die je Etappe
// gehaltenen Wegpunkte in den POST-Payload übernehmen. VOR dem Fix scheitern diese
// Tests (RED), weil `CreateTripStage` kein `waypoints`-Feld kennt und
// `buildCreateTripPayload` hart `waypoints: []` setzt — die aus GPX berechneten
// Wegpunkte gehen beim Speichern verloren (stille Datenlücke aus Slice 1).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-new/__tests__/issue_658_waypoint_persistence.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
	buildCreateTripPayload,
	type CreateTripState,
} from '../tripNewLogic.ts';

// Zwei Etappen mit aus GPX berechneten (und einer manuell umbenannten) Wegpunkten.
const stateWithWaypoints: CreateTripState = {
	name: 'Karnischer Höhenweg',
	startDate: '2026-06-15',
	stages: [
		{
			id: 1,
			name: 'Toblach → Helmhotel',
			waypoints: [
				{ id: 'wp1a', name: 'Start Toblach', lat: 46.73, lon: 12.22, elevation_m: 1210 },
				{ id: 'wp1b', name: 'Gipfelkreuz (umbenannt)', lat: 46.70, lon: 12.30, elevation_m: 2100 },
				{ id: 'wp1c', name: 'Helmhotel', lat: 46.68, lon: 12.40, elevation_m: 1810 },
			],
		},
		{
			id: 2,
			name: 'Helmhotel → Sillianer Hütte',
			waypoints: [
				{ id: 'wp2a', name: 'Helmhotel', lat: 46.68, lon: 12.40, elevation_m: 1810 },
				{ id: 'wp2b', name: 'Sillianer Hütte', lat: 46.66, lon: 12.46, elevation_m: 2447 },
			],
		},
	],
	channels: { email: true, telegram: true, sms: false },
};

describe('AC-5/AC-6: buildCreateTripPayload — Wegpunkte je Etappe persistiert (kein Datenverlust)', () => {
	test('AC-6: GPX-Wegpunkte landen im Payload statt eines leeren Arrays', () => {
		const p = buildCreateTripPayload(stateWithWaypoints);
		assert.equal(p.stages.length, 2);
		assert.equal(
			p.stages[0].waypoints.length,
			3,
			'Etappe 1 muss ihre 3 GPX-Wegpunkte behalten — nicht leer',
		);
		assert.equal(
			p.stages[1].waypoints.length,
			2,
			'Etappe 2 muss ihre 2 GPX-Wegpunkte behalten — nicht leer',
		);
	});

	test('AC-5: bearbeiteter Wegpunkt-Name bleibt im Payload erhalten', () => {
		const p = buildCreateTripPayload(stateWithWaypoints);
		const names = p.stages[0].waypoints.map((w) => w.name);
		assert.ok(
			names.includes('Gipfelkreuz (umbenannt)'),
			'Die manuelle Umbenennung muss im POST-Payload ankommen',
		);
	});

	test('AC-5: Wegpunkt-Koordinaten + Höhe werden vollständig durchgereicht', () => {
		const p = buildCreateTripPayload(stateWithWaypoints);
		const wp = p.stages[1].waypoints[1];
		assert.equal(wp.name, 'Sillianer Hütte');
		assert.equal(wp.lat, 46.66);
		assert.equal(wp.lon, 12.46);
		assert.equal(wp.elevation_m, 2447);
	});

	test('AC-6: Etappe ganz ohne Wegpunkte bleibt leer (kein Crash)', () => {
		const empty: CreateTripState = {
			name: 'Leer-Tour',
			startDate: '2026-06-15',
			stages: [{ id: 1, name: 'Etappe ohne GPX', waypoints: [] }],
			channels: { email: true, telegram: false, sms: false },
		};
		const p = buildCreateTripPayload(empty);
		assert.equal(p.stages[0].waypoints.length, 0);
	});
});

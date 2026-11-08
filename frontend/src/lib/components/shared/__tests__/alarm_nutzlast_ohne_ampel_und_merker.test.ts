// Issue #2793 S2b, Fix-Loop 2 (Adversary F106) — AC-19.
//
// Spec: docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md (AC-19)
//
// Die Alarm-Empfindlichkeit ist bis S3a nur lesbar. Speichert der Nutzer im
// Alarme-Reiter des Orts-Vergleichs eine ANDERE Einstellung, darf die
// Nutzlast weder die Profil-Ampel (`ampel`) noch den Migrations-Merker
// (`alarm_ab_migration`) mitschicken, und `metric_alert_levels` ist der
// geladene Bestand (kein Regler aendert ihn). Gemessen an der echten Kette
// des Reiters: Hydration aus dem Preset -> Snapshot -> Nutzlast.
//
// Pfadregel #1409: Prüflinge relativ zu DIESER Datei aufgelöst.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/alarm_nutzlast_ohne_ampel_und_merker.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
	alarmSnapshotAus,
	baueAlarmNutzlast,
	type AlarmHydrationTarget
} from '../alarmeVergleichSpeicherung.ts';
import { hydrateAlarmFieldsFromPreset } from '../../compare/compareHubHydration.ts';
import type { ComparePreset } from '../../../types.ts';

const BESTAND = { wind_gust: 'sensibel', precipitation_sum: 'standard', thunder_level: 'entspannt' };

function _preset(): ComparePreset {
	return {
		id: 'cp-2793-f106',
		name: 'F106-Test',
		location_ids: ['loc-a'],
		schedule: 'manual',
		profil: 'ALLGEMEIN',
		hour_from: 8,
		hour_to: 17,
		empfaenger: ['a@example.com'],
		forecast_hours: 48,
		created_at: '2026-01-01T00:00:00Z',
		corridors: [],
		alert_cooldown_minutes: 60,
		display_config: {
			active_metrics: ['gust_max_kmh'],
			metric_alert_levels: { ...BESTAND },
			ampel: { template: 'allgemein', metrics: { gust: { alarm_ab: 'yellow' } } },
			alarm_ab_migration: { version: 1, migrated_at: '2026-11-01T00:00:00Z' }
		}
	} as unknown as ComparePreset;
}

/** Reiter laedt das Preset, der Nutzer aendert eine ANDERE Einstellung. */
function _nutzlastNachAndererAenderung(): Record<string, unknown> {
	const preset = _preset();
	const reiter: AlarmHydrationTarget = {};
	hydrateAlarmFieldsFromPreset(reiter, preset);
	reiter.alertCooldownMinutes = 120;
	const { body } = baueAlarmNutzlast(preset, alarmSnapshotAus(reiter));
	return body as unknown as Record<string, unknown>;
}

describe('AC-19: Alarm-Nutzlast im Orts-Vergleich ohne Ampel und Merker', () => {
	test('die geaenderte Einstellung steht in der Nutzlast (Kontrolle)', () => {
		const body = _nutzlastNachAndererAenderung();
		assert.equal(body.alert_cooldown_minutes, 120);
	});

	test('metric_alert_levels ist genau der geladene Bestand', () => {
		const dc = _nutzlastNachAndererAenderung().display_config as Record<string, unknown>;
		assert.ok(dc, 'display_config fehlt in der Alarm-Nutzlast');
		assert.deepEqual(dc.metric_alert_levels, BESTAND);
	});

	test('weder ampel noch alarm_ab_migration werden mitgeschickt', () => {
		const body = _nutzlastNachAndererAenderung();
		const dc = (body.display_config as Record<string, unknown>) ?? {};
		assert.ok(!('ampel' in dc), `ampel in der Nutzlast: ${JSON.stringify(dc)}`);
		assert.ok(!('alarm_ab_migration' in dc), `Merker in der Nutzlast: ${JSON.stringify(dc)}`);
		assert.ok(!('ampel' in body) && !('alarm_ab_migration' in body), JSON.stringify(body));
	});
});

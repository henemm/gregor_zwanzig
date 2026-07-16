// TDD RED — Issue #1268 (AC-9): "Nächster Versand" wird aus den echten
// Versand-Slots (morning_time/evening_time) abgeleitet, NICHT aus hour_from.
//
// Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md § AC-9
//
// Befund (GREEN-Phase, PO-bestätigt): deriveNextSend() rechnete mit
// `hour_from` — dem Start des Bewertungs-Zeitfensters. Die Versand-Wahrheit
// sind seit #1232 Scheibe 2a die Slot-Felder (types.ts:304: "die einzige
// Wahrheit für den Versand"). Die Anzeige behauptete 09:00, obwohl um 07:00
// verschickt wurde. Seit #1268 schickt der Wizard `hour_from` nicht mehr mit →
// Go legt neue Presets mit HourFrom = 0 an (Zero-Value) → die Anzeige hätte
// "00:00" behauptet. Fall (b) ist genau diese verhinderte Regression.
//
// Auflösungs-Semantik (Referenz, muss deckungsgleich bleiben):
//   src/services/compare_slot_scheduler.py::resolve_preset_slots
//
// Reine Verhaltenstests auf der Pure-Function (kein Mock, kein Netz, kein DOM).
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/utils/__tests__/compare_next_send_slots.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { deriveNextSend } from '../cockpitHelpers568.ts';
import type { ComparePreset } from '../../types.ts';

function makeCompare(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cp-1268',
		name: 'Skigebiet Vergleich',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		empfaenger: ['test@henemm.com'],
		profil: 'winter_skiing' as never,
		created_at: '2026-01-01T00:00:00Z',
		...overrides
	} as ComparePreset;
}

describe('#1268 AC-9: deriveNextSend liest die Versand-Slots, nicht hour_from', () => {
	test('(a) Versand 07:00 bei Bewertungsfenster ab 09:00 → Anzeige 07:00, nicht 09:00', () => {
		// GIVEN: Versand-Slot 07:00, altes Bewertungsfenster hour_from=9
		// WHEN: die Anzeige den nächsten Versand ableitet (jetzt 04:00)
		// THEN: 07:00 — die echte Versandzeit
		// RED vor Fix: liefert 09:00 (hour_from), die Anzeige log den Nutzer an.
		const now = new Date('2026-06-05T04:00:00');
		const preset = makeCompare({
			schedule: 'daily',
			hour_from: 9,
			morning_enabled: true,
			morning_time: '07:00:00'
		});

		const result = deriveNextSend(preset, now);

		assert.ok(result !== null, 'daily-Preset muss einen nächsten Versand liefern');
		assert.strictEqual(result!.getHours(), 7, 'Stunde muss die Versandzeit 07:00 sein, nicht hour_from=9');
		assert.strictEqual(result!.getMinutes(), 0);
		assert.strictEqual(result!.getDate(), now.getDate(), 'heute, da 07:00 noch bevorsteht');
	});

	test('(b) neu angelegtes Preset ohne hour_from → 07:00, niemals 00:00', () => {
		// GIVEN: ein nach #1268 angelegtes Preset — der Wizard schickt hour_from
		//        nicht mehr, Go schreibt den Zero-Value 0 (oder das Feld fehlt).
		// WHEN: die Anzeige den nächsten Versand ableitet
		// THEN: 07:00 aus dem Slot — die Anzeige darf nicht "00:00" behaupten.
		// RED vor Fix: hour_from=0 → 00:00 (bzw. null wenn Feld fehlt).
		const now = new Date('2026-06-05T04:00:00');
		const zeroValue = makeCompare({ schedule: 'daily', hour_from: 0, morning_time: '07:00:00' });
		const missing = makeCompare({ schedule: 'daily', morning_time: '07:00:00' });

		for (const [label, preset] of [
			['hour_from=0 (Go-Zero-Value)', zeroValue],
			['hour_from fehlt komplett', missing]
		] as const) {
			const result = deriveNextSend(preset, now);
			assert.ok(result !== null, `${label}: muss einen nächsten Versand liefern`);
			assert.strictEqual(result!.getHours(), 7, `${label}: muss 07:00 zeigen, nicht 00:00`);
		}
	});

	test('(c) nur Abend-Slot aktiv → Anzeige nimmt den Abend-Slot', () => {
		// GIVEN: Morgen-Slot aus, Abend-Slot an um 18:00
		// WHEN: die Anzeige den nächsten Versand ableitet (jetzt 04:00)
		// THEN: 18:00 heute — nicht der deaktivierte Morgen-Slot
		const now = new Date('2026-06-05T04:00:00');
		const preset = makeCompare({
			schedule: 'daily',
			hour_from: 9,
			morning_enabled: false,
			morning_time: '07:00:00',
			evening_enabled: true,
			evening_time: '18:00:00'
		});

		const result = deriveNextSend(preset, now);

		assert.ok(result !== null);
		assert.strictEqual(result!.getHours(), 18, 'muss den aktiven Abend-Slot zeigen');
		assert.strictEqual(result!.getDate(), now.getDate(), 'heute, da 18:00 noch bevorsteht');
	});

	test('(d) schedule "manual" → weiterhin null', () => {
		const now = new Date('2026-06-05T04:00:00');
		const preset = makeCompare({ schedule: 'manual', morning_time: '07:00:00' });
		assert.strictEqual(deriveNextSend(preset, now), null, 'manual liefert keinen nächsten Versand');
	});
});

describe('#1268 AC-9: Slot-Auflösung deckungsgleich mit resolve_preset_slots', () => {
	test('beide Slots aktiv → der nächste bevorstehende gewinnt', () => {
		const preset = makeCompare({
			schedule: 'daily',
			morning_enabled: true,
			morning_time: '07:00:00',
			evening_enabled: true,
			evening_time: '18:00:00'
		});

		// 04:00 → als nächstes der Morgen-Slot
		assert.strictEqual(deriveNextSend(preset, new Date('2026-06-05T04:00:00'))!.getHours(), 7);
		// 12:00 → Morgen-Slot vorbei, als nächstes der Abend-Slot (heute)
		const midday = deriveNextSend(preset, new Date('2026-06-05T12:00:00'))!;
		assert.strictEqual(midday.getHours(), 18);
		assert.strictEqual(midday.getDate(), 5, 'Abend-Slot heute, nicht morgen');
		// 20:00 → beide vorbei → Morgen-Slot morgen früh
		const evening = deriveNextSend(preset, new Date('2026-06-05T20:00:00'))!;
		assert.strictEqual(evening.getHours(), 7);
		assert.strictEqual(evening.getDate(), 6, 'morgen früh');
	});

	test('Alt-Preset ohne morning_time → Migrations-Fallback 06:00 (Morgen-Intention)', () => {
		// resolve_preset_slots: morning_time fehlt = "nie migriert" → Morgen-Slot
		// 06:00 aktiv (verhaltensidentisch zum bisherigen 06:00-Cron).
		const now = new Date('2026-06-05T04:00:00');
		const preset = makeCompare({ schedule: 'daily', hour_from: 9 });
		const result = deriveNextSend(preset, now);
		assert.ok(result !== null);
		assert.strictEqual(result!.getHours(), 6, 'Fallback-Morgen-Slot 06:00, nicht hour_from=9');
	});

	test('Alt-Preset ohne morning_time mit schedule "daily_evening" → Fallback Abend 18:00', () => {
		// resolve_preset_slots KL-6: Alt-Wert daily_evening → Abend-Intention.
		const now = new Date('2026-06-05T04:00:00');
		const preset = makeCompare({ schedule: 'daily_evening' as never });
		const result = deriveNextSend(preset, now);
		assert.ok(result !== null);
		assert.strictEqual(result!.getHours(), 18, 'Fallback-Abend-Slot 18:00');
	});

	test('weekly: nächster passender Wochentag zur echten Versandzeit', () => {
		// 2026-06-05 ist ein Freitag (weekday=4). Ziel: Montag (weekday=0).
		const now = new Date('2026-06-05T04:00:00');
		const preset = makeCompare({ schedule: 'weekly', weekday: 0, hour_from: 9, morning_time: '07:00:00' });
		const result = deriveNextSend(preset, now);
		assert.ok(result !== null);
		assert.strictEqual(result!.getHours(), 7, 'Versandzeit aus dem Slot, nicht hour_from');
		assert.strictEqual(result!.getDay(), 1, 'JS-Wochentag Montag');
	});
});

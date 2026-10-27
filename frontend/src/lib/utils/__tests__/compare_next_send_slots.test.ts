// Issue #1268 (AC-9): "Nächster Versand" folgt den echten Versand-Slots
// (morning_time/evening_time), NICHT hour_from.
//
// Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md § AC-9
// Umgestellt mit Issue #1969 (AC-23/AC-24, docs/specs/modules/feat_1969_naechstes_briefing.md):
// `deriveNextSend` ist entfernt — den nächsten Termin rechnet ausschließlich das
// Backend (GET /api/next-briefings; Python-Ableitung `next_compare_briefing`,
// bewacht in tests/tdd/test_next_briefing.py inkl. weekly/manual/Pause). Die
// Zusicherung „Anzeige = Versandzeit, nie hour_from" bleibt hier an ZWEI
// Stellen bewacht:
//   1. Anzeige-Ebene: die Startseiten-Zeile „Nächster · …" zeigt den
//      Backend-Wert, auch wenn hour_from etwas anderes behauptet.
//   2. Slot-Auflösung `resolvePresetSlots`/`primarySendSlot` (Zeitplan-Label,
//      deckungsgleich mit compare_slot_scheduler.py::resolve_preset_slots).
//
// Reine Verhaltenstests (kein Mock, kein Netz, kein DOM).
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/utils/__tests__/compare_next_send_slots.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { resolvePresetSlots, primarySendSlot } from '../cockpitHelpers568.ts';
import { homeCompareTimeline } from '../../../routes/_home/cockpitHelpers.ts';
import type { ComparePreset } from '../../types.ts';

process.env.TZ = 'America/Los_Angeles';

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

/** Backend-Wert „heute 07:00 (CEST)" — Fr 05.06.2026. */
const NB = (local_time: string, slot: 'morning' | 'evening' = 'morning') => ({
	at: `2026-06-05T${local_time}:00+02:00`,
	local_date: '2026-06-05',
	local_time,
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot
});

const naechster = (preset: ComparePreset, nb: unknown) =>
	homeCompareTimeline(preset, nb as never).find((r) => r.when.startsWith('Nächster · '))?.when;

describe('#1268 AC-9 / #1969: Anzeige zeigt die Versandzeit (Backend-Wert), nicht hour_from', () => {
	test('(a) Versand 07:00 bei Bewertungsfenster ab 09:00 → Anzeige 07:00, nicht 09:00', () => {
		const preset = makeCompare({ schedule: 'daily', hour_from: 9, morning_enabled: true, morning_time: '07:00:00' });
		const zeile = naechster(preset, NB('07:00'));
		assert.ok(zeile, 'daily-Preset mit Backend-Termin muss eine Nächster-Zeile liefern');
		assert.ok(zeile!.includes('Fr 07:00 (CEST)'), `Versandzeit 07:00 fehlt: ${zeile}`);
		assert.ok(!zeile!.includes('09:00'), `hour_from=9 sichtbar: ${zeile}`);
	});

	test('(b) neu angelegtes Preset ohne hour_from → 07:00, niemals 00:00', () => {
		for (const preset of [
			makeCompare({ schedule: 'daily', hour_from: 0, morning_time: '07:00:00' }),
			makeCompare({ schedule: 'daily', morning_time: '07:00:00' })
		]) {
			const zeile = naechster(preset, NB('07:00'));
			assert.ok(zeile?.includes('07:00'), `07:00 fehlt: ${zeile}`);
			assert.ok(!zeile!.includes('00:00 ') && !zeile!.includes(' 00:00'), `00:00 sichtbar: ${zeile}`);
		}
	});

	test('(c) nur Abend-Slot aktiv → Anzeige nimmt den Abend-Termin des Backends', () => {
		const preset = makeCompare({
			schedule: 'daily',
			hour_from: 9,
			morning_enabled: false,
			morning_time: '07:00:00',
			evening_enabled: true,
			evening_time: '18:00:00'
		});
		assert.ok(naechster(preset, NB('18:00', 'evening'))?.includes('Fr 18:00 (CEST)'));
	});

	test('(d) schedule "manual" (Backend: reason manual) → keine Nächster-Zeile', () => {
		const preset = makeCompare({ schedule: 'manual', morning_time: '07:00:00' });
		assert.equal(naechster(preset, { at: null, reason: 'manual' }), undefined);
	});
});

describe('#1268 AC-9: Slot-Auflösung deckungsgleich mit resolve_preset_slots (Zeitplan-Label)', () => {
	test('Versand-Slot 07:00 schlägt hour_from=9', () => {
		const preset = makeCompare({ hour_from: 9, morning_enabled: true, morning_time: '07:00:00' });
		assert.deepEqual(primarySendSlot(preset), { hour: 7, minute: 0 });
	});

	test('nur Abend-Slot aktiv → Abend-Slot', () => {
		const preset = makeCompare({
			hour_from: 9,
			morning_enabled: false,
			morning_time: '07:00:00',
			evening_enabled: true,
			evening_time: '18:00:00'
		});
		assert.deepEqual(resolvePresetSlots(preset), [{ hour: 18, minute: 0 }]);
	});

	test('beide Slots aktiv → beide aufgelöst, frühester ist der primäre', () => {
		const preset = makeCompare({
			morning_enabled: true,
			morning_time: '07:00:00',
			evening_enabled: true,
			evening_time: '18:00:00'
		});
		assert.deepEqual(resolvePresetSlots(preset), [
			{ hour: 7, minute: 0 },
			{ hour: 18, minute: 0 }
		]);
		assert.deepEqual(primarySendSlot(preset), { hour: 7, minute: 0 });
	});

	test('Alt-Preset ohne morning_time → Migrations-Fallback 06:00 (Morgen-Intention)', () => {
		assert.deepEqual(resolvePresetSlots(makeCompare({ schedule: 'daily', hour_from: 9 })), [{ hour: 6, minute: 0 }]);
	});

	test('Alt-Preset ohne morning_time mit schedule "daily_evening" → Fallback Abend 18:00', () => {
		assert.deepEqual(resolvePresetSlots(makeCompare({ schedule: 'daily_evening' as never })), [
			{ hour: 18, minute: 0 }
		]);
	});
});

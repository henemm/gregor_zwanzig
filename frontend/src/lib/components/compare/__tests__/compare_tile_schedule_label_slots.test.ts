// TDD RED — Issue #1268 (AC-10): Die Vergleichs-Kachel und der Startseiten-Hero
// zeigen die echte Versandzeit aus den Slot-Feldern, nicht `hour_from`.
//
// Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md § AC-10
//
// Herkunft: Adversary-Fund F002. Gleiche Bug-Klasse wie AC-9 — AC-9 hat nur
// deriveNextSend() (cockpitHelpers568.ts) repariert, waehrend direkt daneben
// zwei weitere LIVE-Flaechen weiter `hour_from` lasen:
//   - presetTileScheduleLabel() (subscriptionHelpers.ts:182), gerendert ueber
//     CompareTile.svelte:68 → sichtbar auf /compare  → "tägl. 00"
//   - routes/+page.svelte:485 (Startseiten-Hero)                → "· 00:00"
// Beide nutzen jetzt dieselbe Slot-Aufloesung wie deriveNextSend (primarySendSlot),
// damit die Semantik an EINER Stelle lebt — kein Nachbau.
//
// Reine Verhaltenstests auf den Pure-Functions (kein Mock, kein Netz, kein DOM).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { presetTileScheduleLabel } from '../subscriptionHelpers.ts';
import { primarySendSlot } from '../../../utils/cockpitHelpers568.ts';
import type { ComparePreset } from '../../../types.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
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

describe('#1268 AC-10: presetTileScheduleLabel nutzt die Versand-Slots', () => {
	test('neu angelegter Vergleich (kein hour_from) mit Versand 07:00 → "tägl. 07", nie "tägl. 00"', () => {
		// GIVEN: ein nach #1268 angelegtes Preset — der Wizard schickt hour_from
		//        nicht mehr, Go schreibt den Zero-Value 0.
		// WHEN: die Kachel auf /compare gerendert wird
		// THEN: das Label nennt die echte Versandzeit 07
		// RED vor Fix: "tägl. 00" — der Nutzer sieht eine Uhrzeit, zu der nichts passiert.
		const preset = makePreset({ schedule: 'daily', hour_from: 0, morning_time: '07:00:00' });

		const label = presetTileScheduleLabel(preset);

		assert.equal(label, 'tägl. 07', 'Label muss die Versandzeit 07 zeigen, nicht hour_from=0');
	});

	test('Bestands-Preset: Versand 07:00 schlaegt Bewertungsfenster hour_from=9', () => {
		// GIVEN: Alt-Preset mit hour_from=9 (Bewertungsfenster) und Slot 07:00
		// THEN: die Kachel zeigt den Versand (07), nicht das Fenster (09)
		const preset = makePreset({ schedule: 'daily', hour_from: 9, morning_time: '07:00:00' });
		assert.equal(presetTileScheduleLabel(preset), 'tägl. 07');
	});

	test('nur Abend-Slot aktiv → Label nennt den Abend-Slot', () => {
		const preset = makePreset({
			schedule: 'daily',
			hour_from: 9,
			morning_enabled: false,
			morning_time: '07:00:00',
			evening_enabled: true,
			evening_time: '18:00:00'
		});
		assert.equal(presetTileScheduleLabel(preset), 'tägl. 18');
	});

	test('Alt-Preset ohne morning_time → Migrations-Fallback 06:00 (wie resolve_preset_slots)', () => {
		const preset = makePreset({ schedule: 'daily', hour_from: 9 });
		assert.equal(presetTileScheduleLabel(preset), 'tägl. 06');
	});

	test('weekly/manual bleiben unveraendert (keine Uhrzeit im Label)', () => {
		assert.equal(presetTileScheduleLabel(makePreset({ schedule: 'weekly', weekday: 0 })), 'Montag');
		assert.equal(presetTileScheduleLabel(makePreset({ schedule: 'manual' })), 'manuell');
	});
});

describe('#1268 AC-10: primarySendSlot ist die geteilte Ableitung (Startseiten-Hero)', () => {
	test('liefert den fruehesten aktiven Slot, unabhaengig von hour_from', () => {
		// Der Startseiten-Hero (routes/+page.svelte) baut seine "· HH:00"-Angabe
		// aus derselben Funktion — daher hier mitgeprueft.
		const preset = makePreset({ hour_from: 0, morning_time: '07:00:00' });
		assert.deepEqual(primarySendSlot(preset), { hour: 7, minute: 0 });
	});

	test('beide Slots aktiv → der fruehere gewinnt', () => {
		const preset = makePreset({
			morning_enabled: true,
			morning_time: '07:00:00',
			evening_enabled: true,
			evening_time: '18:00:00'
		});
		assert.deepEqual(primarySendSlot(preset), { hour: 7, minute: 0 });
	});

	test('kein aktiver Slot → null (Hero zeigt dann keine Uhrzeit)', () => {
		const preset = makePreset({
			morning_enabled: false,
			morning_time: '07:00:00',
			evening_enabled: false
		});
		assert.equal(primarySendSlot(preset), null);
	});
});

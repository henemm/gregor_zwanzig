// TDD RED — Issue #2229 (AC-1, AC-6): Kanal-Anzeige des Ortsvergleichs nennt Premium-SMS.
//
// Spec: docs/specs/bugfix/fix_2229_premium_sms_kanallisten.md (Test 1)
//
// Ist: presetChannels() (subscriptionHelpers.ts) kennt nur Email/Telegram/SMS —
// ein Vergleich mit eingeschalteter Premium-SMS zeigt sie weder in der Kachel
// noch in der Hub-Stat „Kanäle". Soll: „Premium-SMS" nach „SMS", allein am
// Opt-in `send_premium_sms` (Muster Trip-Pendant cockpitHelpers.ts:142-144).
//
// Echte Funktionsaufrufe, kein Mock. Pfadregel #1409: relativ zur Testdatei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_preset_channels_premium_sms.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import type { ComparePreset } from '../../../types.ts';

const { presetChannels, channelNamesLabel } = await import('../subscriptionHelpers.ts');

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-2229',
		name: 'Huettenvergleich',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		weekday: 0,
		profil: 'allgemein',
		hour_from: 9,
		hour_to: 16,
		forecast_hours: 48,
		empfaenger: [],
		letzter_versand: undefined,
		top_ort_letzter_versand: null,
		created_at: '2026-10-01T00:00:00Z',
		display_config: {},
		...overrides
	} as ComparePreset;
}

describe('AC-1: Premium-SMS erscheint in der Kanal-Anzeige, wenn eingeschaltet', () => {
	test('alle vier Kanaele an → Premium-SMS steht nach SMS', () => {
		const preset = makePreset({ send_telegram: true, send_sms: true, send_premium_sms: true });
		assert.deepEqual(presetChannels(preset), ['Email', 'Telegram', 'SMS', 'Premium-SMS']);
	});

	test('nur Premium-SMS als Zusatzkanal → Email · Premium-SMS', () => {
		const preset = makePreset({ send_premium_sms: true });
		assert.deepEqual(presetChannels(preset), ['Email', 'Premium-SMS']);
		assert.equal(channelNamesLabel(preset), 'Email · Premium-SMS');
	});

	test('Hub-Stat „Kanäle" endet auf „· Premium-SMS"', () => {
		const preset = makePreset({ send_telegram: true, send_sms: true, send_premium_sms: true });
		assert.equal(channelNamesLabel(preset), 'Email · Telegram · SMS · Premium-SMS');
	});
});

describe('AC-1/AC-6 Gegenprobe: ohne Opt-in kein Eintrag, Dreier-Anzeige byte-gleich', () => {
	// Diese Faelle sind schon heute gruen — absichtlich: sie bewachen, dass der
	// Fix die Anzeige fuer Presets ohne Premium-SMS nicht veraendert.
	test('send_premium_sms fehlt → unveraendert drei Kanaele', () => {
		const preset = makePreset({ send_telegram: true, send_sms: true });
		assert.deepEqual(presetChannels(preset), ['Email', 'Telegram', 'SMS']);
		assert.equal(channelNamesLabel(preset), 'Email · Telegram · SMS');
	});

	test('send_premium_sms=false → kein Eintrag', () => {
		const preset = makePreset({ send_sms: true, send_premium_sms: false });
		assert.deepEqual(presetChannels(preset), ['Email', 'SMS']);
	});
});

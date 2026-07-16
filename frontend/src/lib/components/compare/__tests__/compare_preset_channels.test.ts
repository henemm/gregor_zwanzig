// TDD RED — Issue #1270 Scheibe 1 (AC-8, Test 1).
//
// Spec: docs/specs/modules/compare_channel_preview_dispatch.md (AC-8)
// Kontext: docs/context/fix-1270-compare-channel-preview.md (KB-6)
//
// Ist: subscriptionHelpers.ts:217 leitet die Kanal-Liste aus den Keys von
// `display_config.channel_layouts` ab. `channel_layouts` haelt aber nur
// Metrik-Layouts je Kanal, und CompareEditor.svelte:605-606 legt die
// telegram/sms-Keys IMMER an (auch leer) — der Kanal-Umschalter im
// Vorschau-Tab zeigt darum Telegram/SMS unabhaengig vom echten Opt-in.
//
// Soll: Ableitung aus den Opt-in-Feldern `send_telegram`/`send_sms`
// (E-Mail implizit, sobald ein Empfaenger mit "@" existiert).
//
// RED: presetChannels() liefert heute fuer ein Preset ohne Opt-ins, aber mit
// gefuellten channel_layouts-Keys, alle drei Kanaele zurueck.
//
// Reine Verhaltenstests (echter Funktionsaufruf, KEIN Mock, KEINE
// Datei-Inhalt-Pruefung — im Projekt existiert keine Svelte-Rendering-Harness,
// Praezedenz: channel_names_label.test.ts).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_preset_channels.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import type { ComparePreset } from '../../../types.ts';

const { presetChannels } = await import('../subscriptionHelpers.ts');

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-1270',
		name: 'Urlaubsorte',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		weekday: 0,
		profil: 'allgemein',
		hour_from: 9,
		hour_to: 16,
		forecast_hours: 48,
		empfaenger: ['urlauber@example.com'],
		letzter_versand: undefined,
		top_ort_letzter_versand: null,
		created_at: '2026-07-01T00:00:00Z',
		display_config: {},
		...overrides
	} as ComparePreset;
}

/** Kanal-Keys normalisiert vergleichen — die Gross-/Kleinschreibung der
 *  Labels ("Email") ist nicht Gegenstand von AC-8. */
function channelKeys(preset: ComparePreset): string[] {
	return presetChannels(preset).map((c) => c.toLowerCase());
}

describe('AC-8: presetChannels — Opt-in entscheidet, nicht channel_layouts-Keys', () => {
	test('send_telegram=false/send_sms=false trotz gefuellter channel_layouts fuer alle drei Kanaele → nur email', () => {
		const preset = makePreset({
			send_telegram: false,
			send_sms: false,
			display_config: {
				channel_layouts: {
					email: { columns: ['temp_max_c'] },
					telegram: { columns: ['temp_max_c'] },
					sms: { columns: ['temp_max_c'] }
				}
			}
		} as Partial<ComparePreset>);

		const keys = channelKeys(preset);
		assert.deepEqual(
			keys,
			['email'],
			`AC-8: Ohne Telegram-/SMS-Opt-in darf nur der E-Mail-Kanal erscheinen — ` +
				`presetChannels() leitet heute aus channel_layouts-Keys ab und lieferte: ${JSON.stringify(keys)}`
		);
	});

	test('send_telegram=true → telegram erscheint (auch ohne channel_layouts-Eintrag)', () => {
		const preset = makePreset({ send_telegram: true, display_config: {} } as Partial<ComparePreset>);
		const keys = channelKeys(preset);
		assert.ok(
			keys.includes('telegram'),
			`Aktives Telegram-Opt-in muss den Kanal zeigen, war: ${JSON.stringify(keys)}`
		);
		assert.ok(!keys.includes('sms'), `Ohne SMS-Opt-in darf SMS nicht erscheinen, war: ${JSON.stringify(keys)}`);
	});

	test('send_sms=true → sms erscheint (auch ohne channel_layouts-Eintrag)', () => {
		const preset = makePreset({ send_sms: true, display_config: {} } as Partial<ComparePreset>);
		const keys = channelKeys(preset);
		assert.ok(
			keys.includes('sms'),
			`Aktives SMS-Opt-in muss den Kanal zeigen, war: ${JSON.stringify(keys)}`
		);
		assert.ok(
			!keys.includes('telegram'),
			`Ohne Telegram-Opt-in darf Telegram nicht erscheinen, war: ${JSON.stringify(keys)}`
		);
	});

	test('beide Opt-ins aktiv → email, telegram und sms', () => {
		const preset = makePreset({
			send_telegram: true,
			send_sms: true,
			display_config: {}
		} as Partial<ComparePreset>);
		const keys = channelKeys(preset);
		assert.deepEqual(
			[...keys].sort(),
			['email', 'sms', 'telegram'],
			`Bei beiden Opt-ins muessen alle drei Kanaele erscheinen, war: ${JSON.stringify(keys)}`
		);
	});

	test('Signal-Opt-in existiert nicht — ein signal-Layout-Key bleibt unsichtbar (PO #610)', () => {
		const preset = makePreset({
			send_telegram: false,
			send_sms: false,
			display_config: { channel_layouts: { signal: { columns: [] } } }
		} as Partial<ComparePreset>);
		const keys = channelKeys(preset);
		assert.ok(!keys.includes('signal'), `Signal darf nie erscheinen, war: ${JSON.stringify(keys)}`);
		assert.deepEqual(keys, ['email'], `Erwartet nur email, war: ${JSON.stringify(keys)}`);
	});
});

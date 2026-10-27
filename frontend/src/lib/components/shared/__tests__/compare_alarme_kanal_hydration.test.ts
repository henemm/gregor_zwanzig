// TDD RED — Issue #2293 Scheibe S2 (AC-11), Epic #1374/#2345.
//
// Spec: docs/specs/modules/feat_2293_s2_compare_alarm_kanaele.md
//   Implementation Details Abschnitt 3 ("Hydration (alarmePropsAus.ts)").
//
// `reconstructCompareAlertChannels(preset)` rekonstruiert den ANGEZEIGTEN
// Alarm-Kanal-Zustand beim ersten Oeffnen des Alarme-Reiters im Ortsvergleich
// — Vorrang `preset.alert_channels` (seit der Go-Materialisierung bei JEDEM
// geladenen Preset gesetzt), Defense-in-Depth-Rueckfall auf die flachen
// `send_telegram`/`send_sms`/`send_premium_sms`-Felder (E-Mail dabei immer
// `true`, KEIN stiller Kanal-Wechsel) fuer den nur noch theoretischen Fall
// eines Rohobjekts ohne `alert_channels`. Vorbild:
// `shared/alarme-tab/tripChannelReconstruction.ts::reconstructTripAlertChannels`.
//
// RED-Grund heute (gemessen): `reconstructCompareAlertChannels` existiert
// nicht in `compare/alarmePropsAus.ts` — der benannte Import schlaegt unter
// nativer ESM-Semantik bereits beim Laden fehl (SyntaxError "does not
// provide an export named"), dieselbe RED-Bauform wie ein fehlendes
// Go-Struct-Feld (Compile-Error) bzw. ein Python-ImportError.
//
// Pfadregel #1409: Pruefling relativ zu DIESER Datei aufgeloest.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/compare_alarme_kanal_hydration.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { reconstructCompareAlertChannels } from '../../compare/alarmePropsAus.ts';

describe('AC-11: reconstructCompareAlertChannels — Vorrang alert_channels', () => {
	test('preset.alert_channels gesetzt → wird 1:1 uebernommen (E-Mail NICHT fest an)', () => {
		const preset = {
			alert_channels: { email: false, telegram: true, sms: false, premium_sms: false },
			send_telegram: false,
			send_sms: true,
			send_premium_sms: true
		};
		const result = reconstructCompareAlertChannels(preset as never);
		assert.deepStrictEqual(
			result,
			{ email: false, telegram: true, sms: false, premium_sms: false },
			'AC-11: bei gesetztem alert_channels muss GENAU dieses Objekt uebernommen werden — ' +
				'die widersprechenden send_*-Flachwerte duerfen NICHT durchschlagen, und email darf ' +
				'NICHT fest auf true stehen (bisherige Sonderableitung mit hartem email:true, ' +
				'AlarmeTab.svelte Zeilen 295-305).'
		);
	});

	test('preset.alert_channels mit allen vier Kanaelen aus bleibt erhalten (kein Default-Rueckfall)', () => {
		const preset = {
			alert_channels: { email: false, telegram: false, sms: false, premium_sms: false }
		};
		const result = reconstructCompareAlertChannels(preset as never);
		assert.deepStrictEqual(
			result,
			{ email: false, telegram: false, sms: false, premium_sms: false },
			'AC-12-Vertraeglichkeit: "alle vier Kanaele aus" ist eine zulaessige Konfiguration, ' +
				'die Hydration darf sie nicht durch einen Default ersetzen.'
		);
	});
});

describe('AC-11: reconstructCompareAlertChannels — Defense-in-Depth-Rueckfall ohne alert_channels', () => {
	test('preset ohne alert_channels faellt auf die flachen send_*-Felder zurueck, E-Mail immer true', () => {
		const preset = {
			send_telegram: true,
			send_sms: false,
			send_premium_sms: true
		};
		const result = reconstructCompareAlertChannels(preset as never);
		assert.deepStrictEqual(
			result,
			{ email: true, telegram: true, sms: false, premium_sms: true },
			'Rueckfall (nur noch theoretisch nach der Go-Materialisierung): E-Mail bleibt true, ' +
				'die drei anderen Kanaele uebernehmen die flachen send_*-Felder.'
		);
	});
});

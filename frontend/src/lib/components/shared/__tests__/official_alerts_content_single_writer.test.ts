// TDD RED — Scheibe D2 von #1301 (#1292 P4): „Amtliche Warnungen im Bericht"
// (Feld official_alerts_enabled) hat genau EINEN Schreiber — den Inhalt-Bereich.
// Der geteilte Alarm-Tab darf das Feld nicht mehr mitsenden, sonst überschreibt
// sein Save beim Trip einen im Inhalt-Tab gesetzten Wert (Last-Writer-Wins).
//
// VERHALTENS-Nachweis (Kern-Schicht, deterministisch, kein Mock): geprüft wird
// die echte Payload-Funktion buildAlarmeDeliveryPayload — sie ist der einzige
// zweite Schreibweg für official_alerts_enabled.
//
// Spec: docs/specs/modules/d2_1301_official_alerts_single_control.md (AC-2, AC-5)
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/official_alerts_content_single_writer.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildAlarmeDeliveryPayload } from '../alarme-tab/alarmeDeliveryPayload.ts';

describe('D2 AC-2/AC-5: Alarm-Payload schreibt official_alerts_enabled nicht mehr', () => {
	test('AC-2: gebaute Payload enthält keinen Key official_alerts_enabled mehr', () => {
		const payload = buildAlarmeDeliveryPayload({
			officialWarningsEnabled: false,
			cooldownMinutes: 45,
			quietFrom: '22:00',
			quietTo: '06:00',
			channels: { email: true, telegram: false, sms: false }
		} as never);
		assert.ok(
			!Object.prototype.hasOwnProperty.call(payload, 'official_alerts_enabled'),
			'official_alerts_enabled darf NICHT mehr in der Alarm-Payload stehen — der ' +
				'Inhalt-Bereich ist alleiniger Schreiber (Doppel-Writer-Race, D2).'
		);
	});

	test('AC-5: Payload-Aufbau ohne officialAlertsEnabled wirft nicht (kein Pflichtfeld mehr)', () => {
		assert.doesNotThrow(() => {
			buildAlarmeDeliveryPayload({
				officialWarningsEnabled: true,
				channels: { email: true, telegram: false, sms: false }
			} as never);
		}, 'officialAlertsEnabled ist kein Payload-Feld des Alarm-Tabs mehr — kein Guard-Wurf.');
	});

	test('AC-5: verbleibende Pflichtfelder bleiben scharf — Nicht-boolean officialWarningsEnabled wirft', () => {
		assert.throws(
			() =>
				buildAlarmeDeliveryPayload({
					officialWarningsEnabled: 'true' as unknown as boolean,
					channels: { email: true, telegram: false, sms: false }
				} as never),
			/officialWarningsEnabled/
		);
	});

	test('AC-5: verbleibende Pflichtfelder bleiben scharf — Nicht-boolean channels wirft', () => {
		assert.throws(
			() =>
				buildAlarmeDeliveryPayload({
					officialWarningsEnabled: false,
					channels: { email: 'yes' as unknown as boolean, telegram: false, sms: false }
				} as never),
			/channels/
		);
	});

	test('AC-2: official_warnings + übrige Alarm-Felder bleiben unverändert erhalten', () => {
		const payload = buildAlarmeDeliveryPayload({
			officialWarningsEnabled: true,
			cooldownMinutes: 30,
			quietFrom: '23:00',
			quietTo: '07:00',
			channels: { email: true, telegram: true, sms: false }
		} as never) as Record<string, unknown>;
		assert.deepEqual(payload.official_warnings, { enabled: true });
		assert.equal(payload.alert_cooldown_minutes, 30);
		assert.equal(payload.alert_quiet_from, '23:00');
		assert.equal(payload.alert_quiet_to, '07:00');
		assert.deepEqual(payload.alert_channels, { email: true, telegram: true, sms: false });
	});
});

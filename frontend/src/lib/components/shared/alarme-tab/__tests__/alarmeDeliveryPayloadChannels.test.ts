// TDD RED — Issue #1745 Scheibe A (AC-12): der Trip-Speicherweg trägt den
// vierten Kanal — als PFLICHTFELD, nicht als stillen Default (D7).
// Spec: docs/specs/modules/fix_1745_a_alarm_kanal_premium_sms_ui.md (AC-12, D7)
//
// 🔴 ABWEICHUNG VON DER SPEC (bewusst, vom Orchestrierer angeordnet):
// Die Spec nennt für AC-12 die Bestandsdatei
// `shared/alarme-tab/alertChannelThresholds.test.ts`. Die liegt NICHT in einem
// `__tests__`-Ordner; der `edit_gate` lässt in Phase `phase5_tdd_red`
// ausschliesslich Schreibzugriffe in Verzeichnissen zu, deren Pfadkomponente
// `test`/`tests`/`__tests__`/`spec`/`e2e` heisst — ein Dateiname auf `.test.ts`
// genügt dafür nicht. Der AC-12-Nachweis steht deshalb hier; die Bestandsdatei
// wird in Phase 6 mitgezogen (ihre Zeilen 45-48/71-82 laufen dann rot, das ist
// gewollt und in der Spec so vermerkt).
//
// RED HEUTE: `buildAlarmeDeliveryPayload()` kennt nur drei Kanäle
// (alarmeDeliveryPayload.ts:85-94 Guard, :100-104 Payload) — der Aufruf mit
// vier Werten liefert ein dreifeldiges `alert_channels`, und der Aufruf OHNE
// `premium_sms` wirft nicht.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/alarme-tab/__tests__/alarmeDeliveryPayloadChannels.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildAlarmeDeliveryPayload } from '../alarmeDeliveryPayload.ts';

/** Kanal-Objekt mit allen VIER Werten (die Form nach dieser Scheibe). */
function vierKanaele(overrides: Record<string, boolean> = {}): Record<string, boolean> {
	return { email: true, telegram: true, sms: false, premium_sms: true, ...overrides };
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-12 (a): vier übergebene Werte landen vollständig im Body.
// Mutation (Spec, zugleich AC-14): buildAlarmeDeliveryPayload() nimmt
// `premium_sms` entgegen, schreibt es aber nicht in das `alert_channels`-Objekt.
// ─────────────────────────────────────────────────────────────────────────────
describe('#1745 AC-12: alarme_delivery_payload_verlangt_vier_kanal_werte', () => {
	test('vier übergebene Kanal-Werte stehen vollständig in alert_channels', () => {
		const payload = buildAlarmeDeliveryPayload({
			officialWarningsEnabled: true,
			channels: vierKanaele() as never
		}) as { alert_channels: Record<string, boolean> };

		assert.deepEqual(
			payload.alert_channels,
			{ email: true, telegram: true, sms: false, premium_sms: true },
			'Der gesendete Kanal-Satz muss alle vier Kanäle explizit tragen — fehlt `premium_sms`, ' +
				'ist der Haken in der Oberfläche sichtbar und wirkungslos (genau der gemeldete Bug ' +
				`in neuer Form). Erhalten: ${JSON.stringify(payload.alert_channels)}`
		);
	});

	test('ein AUSGESCHALTETER vierter Kanal wird ebenfalls explizit gesendet (kein weggelassener Schlüssel)', () => {
		// D7: der Go-Merge ist feldweise — ein weggelassener Schlüssel behält den
		// Server-Bestand. „Abwählen" muss deshalb als explizites `false` reisen,
		// sonst lässt sich der Kanal nie wieder abschalten.
		const payload = buildAlarmeDeliveryPayload({
			officialWarningsEnabled: true,
			channels: vierKanaele({ premium_sms: false }) as never
		}) as { alert_channels: Record<string, boolean> };

		assert.ok(
			Object.prototype.hasOwnProperty.call(payload.alert_channels, 'premium_sms'),
			`alert_channels muss den Schlüssel premium_sms IMMER führen — erhalten: ${JSON.stringify(payload.alert_channels)}`
		);
		assert.strictEqual(payload.alert_channels.premium_sms, false);
	});

	// ───────────────────────────────────────────────────────────────────────────
	// AC-12 (b): der Laufzeit-Guard verlangt VIER explizite boolean-Werte.
	// Mutation (Spec): der Guard prüft weiterhin nur email/telegram/sms.
	// ───────────────────────────────────────────────────────────────────────────
	test('ein Aufruf OHNE premium_sms wirft, statt den Kanal still wegzulassen', () => {
		assert.throws(
			() =>
				buildAlarmeDeliveryPayload({
					officialWarningsEnabled: true,
					channels: { email: true, telegram: true, sms: false } as never
				}),
			/premium_sms|channels/,
			'Der Laufzeit-Guard muss den dreifeldigen Alt-Aufruf abfangen (D7: Pflichtfeld, keine ' +
				'stille Lücke) — sonst schreibt ein vergessener Aufrufer den Kanal beim nächsten ' +
				'Speichern nicht mit, ohne dass es jemand bemerkt.'
		);
	});

	test('ein Aufruf mit nicht-boolean premium_sms wirft ebenfalls (kein truthy-Durchrutschen)', () => {
		assert.throws(
			() =>
				buildAlarmeDeliveryPayload({
					officialWarningsEnabled: true,
					channels: { email: true, telegram: true, sms: false, premium_sms: 'ja' } as never
				}),
			/premium_sms|channels/,
			'Der Guard prüft `typeof === "boolean"`, nicht Wahrheitswert — ein String würde sonst ' +
				'ungeprüft im PUT-Body landen.'
		);
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// Geschwister-Feld: `alert_channel_thresholds`. Gehört fachlich zu AC-8/AC-14
// (die Schwelle des vierten Kanals muss den Trip-Speicherweg überleben) und
// steht in der Spec unter der nicht beschreibbaren Bestandsdatei — hier
// mitgeprüft, damit der vierte Kanal nicht mit Haken, aber ohne Schwelle
// ausgeliefert wird.
// ─────────────────────────────────────────────────────────────────────────────
describe('#1745 AC-12 (Geschwister): alert_channel_thresholds trägt den vierten Kanal mit', () => {
	test('eine für Premium-SMS gesetzte Stufe steht unverändert im gesendeten Body', () => {
		const payload = buildAlarmeDeliveryPayload({
			officialWarningsEnabled: true,
			channels: vierKanaele() as never,
			channelThresholds: {
				email: 'LOW',
				telegram: 'HIGH',
				sms: 'MODERATE',
				premium_sms: 'HIGH'
			} as never
		}) as { alert_channel_thresholds: Record<string, string> };

		assert.deepEqual(
			payload.alert_channel_thresholds,
			{ email: 'LOW', telegram: 'HIGH', sms: 'MODERATE', premium_sms: 'HIGH' },
			'Die Schwelle des vierten Kanals wird beim Speichern weggeschnitten — der Regler wäre ' +
				`sichtbar und wirkungslos. Erhalten: ${JSON.stringify(payload.alert_channel_thresholds)}`
		);
	});
});

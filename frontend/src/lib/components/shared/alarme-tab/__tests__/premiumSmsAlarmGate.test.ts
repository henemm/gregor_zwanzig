// TDD RED — Issue #1745 Scheibe A: Tarif-Gate der Premium-SMS-Zeile im
// ALARM-Reiter (nicht im Versand-Reiter).
// Spec: docs/specs/modules/fix_1745_a_alarm_kanal_premium_sms_ui.md
//   AC-5 (gesperrt ohne Premium-Tarif), AC-6 (Rückadresse ist KEINE Bedingung),
//   AC-13 (Tarif-Auskunft steht noch aus -> gesperrt, aber mit ehrlichem Grund).
//
// RED HEUTE: `shared/alarme-tab/premiumSmsAlarmGate.ts` existiert nicht — der
// Import schlägt fehl, die ganze Datei ist rot. Phase 6 legt das Modul an.
//
// WARUM EIN EIGENER HELFER und nicht `premiumSmsChannelState()` aus
// `shared/versand-tab/`: der dortige Helfer verrechnet zusätzlich die Frische
// der gelernten Rückadresse (`premium_sms_reply_state`) zu `disabled`. Für den
// Versand-Reiter ist das richtig; im Alarmpfad stellt das Backend diese Frage
// bewusst NICHT (trip_alert.py:847-855, notification_service.py:1499) — volle
// Wiederverwendung würde also einen Haken sperren, den das Backend anstandslos
// bedienen würde. Genau das prüft AC-6 unten am Verhalten, nicht an der Absicht.
//
// Reine Funktionsprüfung, kein Mount, kein Netz (ADR-0020).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/alarme-tab/__tests__/premiumSmsAlarmGate.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { derivePremiumSmsAlarmGate } from '../premiumSmsAlarmGate.ts';

/** Profilform wie sie GET /api/auth/profile liefert (ConnectionProfile). Der
 *  Alarm-Helfer darf davon AUSSCHLIESSLICH `premium_sms_allowed` auswerten. */
interface ProfileLike {
	premium_sms_allowed?: boolean;
	premium_sms_reply_to?: string;
	premium_sms_reply_at?: string;
	premium_sms_reply_state?: 'none' | 'stale' | 'fresh';
	sms_allowed?: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-5 — Tarif `standard`: sichtbar, aber gesperrt (D3), mit Hinweis.
// Mutation (Spec): derivePremiumSmsAlarmGate() liefert `disabled: false`
// unabhängig vom Tarif.
// ─────────────────────────────────────────────────────────────────────────────
describe('#1745 AC-5: ohne Premium-Tarif ist die Premium-SMS-Zeile gesperrt', () => {
	test('gesperrt_ohne_premium_tarif', () => {
		const gate = derivePremiumSmsAlarmGate({ premium_sms_allowed: false } as ProfileLike);

		assert.strictEqual(
			gate.disabled,
			true,
			'Bei Tarif `standard` (premium_sms_allowed === false) muss die Zeile gesperrt sein — ' +
				'das Tarif-Gate sitzt serverseitig (user_tier.py:33); ein hier setzbarer Haken wäre ' +
				'vorgespiegelte Kontrolle.'
		);
		assert.equal(
			typeof gate.hint,
			'string',
			'Eine gesperrte Zeile ohne Begründung ist eine Sackgasse — es muss ein Hinweistext da sein.'
		);
		assert.ok((gate.hint ?? '').trim().length >= 10, `Hinweistext zu dünn: ${JSON.stringify(gate.hint)}`);
	});

	test('gesperrt_ohne_premium_tarif — eine frische Rückadresse hebt die Tarif-Sperre NICHT auf', () => {
		// Reihenfolge-Beweis: Tarif zuerst. Ein Nutzer mit gelerntem Garmin, der
		// auf `standard` zurückgestuft wurde, darf den Kanal nicht schalten.
		const gate = derivePremiumSmsAlarmGate({
			premium_sms_allowed: false,
			premium_sms_reply_state: 'fresh',
			premium_sms_reply_to: '15551234567'
		} as ProfileLike);

		assert.strictEqual(gate.disabled, true);
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-6 — Premium-Tarif, aber das Gerät hat sich nie gemeldet: TROTZDEM
// aktivierbar. Der Alarmpfad stellt die Bereitschaftsfrage nicht.
// Mutation (Spec): derivePremiumSmsAlarmGate() bekommt zusätzlich einen
// `reply_state`-Parameter und sperrt bei `!== 'fresh'`.
// ─────────────────────────────────────────────────────────────────────────────
describe('#1745 AC-6: mit Premium-Tarif entscheidet die Rückadresse NICHT mit', () => {
	test('aktivierbar_ohne_gelernte_rueckadresse', () => {
		const gate = derivePremiumSmsAlarmGate({ premium_sms_allowed: true } as ProfileLike);

		assert.strictEqual(
			gate.disabled,
			false,
			'Mit Premium-Tarif muss die Zeile aktivierbar sein, auch wenn sich das Gerät noch nie ' +
				'gemeldet hat — sonst sperrt die Oberfläche einen Kanal, den das Backend ' +
				'(notification_service.py:1499, ohne jede Vorprüfung) sehr wohl bedient.'
		);
		assert.strictEqual(
			gate.hint,
			null,
			`eine nicht gesperrte Zeile braucht keinen Sperr-Hinweis — erhalten: ${JSON.stringify(gate.hint)}`
		);
	});

	test('aktivierbar_ohne_gelernte_rueckadresse — für JEDEN Rückadress-Zustand identisch', () => {
		// Das ist die eigentliche Mutations-Falle: würde die Funktion (per Feld im
		// Profil ODER per zusätzlichem Parameter) die Frische mitrechnen, wäre
		// genau EINER dieser drei Fälle gesperrt.
		for (const state of ['none', 'stale', 'fresh'] as const) {
			const gate = derivePremiumSmsAlarmGate({
				premium_sms_allowed: true,
				premium_sms_reply_state: state,
				premium_sms_reply_at: '2020-01-01T00:00:00Z'
			} as ProfileLike);
			assert.strictEqual(
				gate.disabled,
				false,
				`premium_sms_reply_state="${state}" darf den Alarm-Kanal nicht sperren (AC-6/D2) — ` +
					'diese Bereitschaftsfrage stellt allein der Versand-Reiter.'
			);
		}
	});

	test('aktivierbar_ohne_gelernte_rueckadresse — die Funktion nimmt nur EIN Argument entgegen', () => {
		// Strukturelle Zusatzsicherung gegen die wörtlich in der Spec benannte
		// Mutation („bekommt zusätzlich einen reply_state-Parameter"). Der
		// Verhaltenstest oben trägt die Zusicherung; diese Zeile macht den
		// Signatur-Umbau sofort sichtbar, statt ihn nur indirekt zu bemerken.
		assert.strictEqual(
			derivePremiumSmsAlarmGate.length,
			1,
			'derivePremiumSmsAlarmGate darf ausschliesslich das Profil entgegennehmen (D2) — ' +
				`erhaltene Stelligkeit: ${derivePremiumSmsAlarmGate.length}`
		);
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-13 — Tarif-Auskunft liegt (noch) nicht vor: Server-Rendering, erster
// Frame, oder die Abfrage schlug fehl. Dann gesperrt (fail-closed), aber MIT
// ehrlichem Grund — nicht mit der Behauptung, dem Nutzer fehle der Tarif.
// Mutation (Spec): liefert bei fehlendem Profil `disabled: false`.
// ─────────────────────────────────────────────────────────────────────────────
describe('#1745 AC-13: solange die Tarif-Auskunft aussteht, ist die Zeile gesperrt', () => {
	test('gesperrt_solange_tarif_unbekannt', () => {
		for (const profile of [null, undefined]) {
			const gate = derivePremiumSmsAlarmGate(profile);
			assert.strictEqual(
				gate.disabled,
				true,
				`derivePremiumSmsAlarmGate(${String(profile)}) muss fail-closed sperren — beim ` +
					'Server-Rendering läuft onMount nie, das Profil ist dort IMMER unbekannt. Ein in ' +
					'diesem Zustand klickbarer Haken liesse sich setzen und speichern, ohne je zu wirken.'
			);
			assert.equal(typeof gate.hint, 'string', 'auch dieser Zustand braucht einen Hinweistext');
		}
	});

	test('gesperrt_solange_tarif_unbekannt — der Hinweis ist NICHT der Tarif-Hinweis aus AC-5', () => {
		const unbekannt = derivePremiumSmsAlarmGate(null).hint;
		const ohneTarif = derivePremiumSmsAlarmGate({ premium_sms_allowed: false } as ProfileLike).hint;

		assert.notStrictEqual(
			unbekannt,
			ohneTarif,
			'„Auskunft steht aus" und „Tarif fehlt" sind zwei verschiedene Sachverhalte. Denselben ' +
				'Text zu zeigen behauptet einem Premium-Nutzer beim ersten Frame, ihm fehle der Tarif ' +
				'— eine Falschaussage über sein eigenes Konto.'
		);
	});

	test('gesperrt_solange_tarif_unbekannt — ein leeres Profil ohne das Feld zählt ebenfalls als unbekannt', () => {
		// `{}` kommt vor: das Profil ist geladen, aber die Go-Antwort trug das
		// Feld nicht (ältere Instanz). Fail-closed, wie null/undefined.
		assert.strictEqual(derivePremiumSmsAlarmGate({} as ProfileLike).disabled, true);
	});
});

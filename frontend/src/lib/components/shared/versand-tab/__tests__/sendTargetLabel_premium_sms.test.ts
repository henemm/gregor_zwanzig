// TDD RED — Issue #2229 (AC-2, AC-6, AC-7): „Jetzt senden" nennt Premium-SMS als Ziel.
//
// Spec: docs/specs/bugfix/fix_2229_premium_sms_kanallisten.md (Test 2, Test 3)
//
// Ist: sendTargetLabel() kennt nur E-Mail/Telegram/SMS — der Dialog sagt
// „Geht an E-Mail …", obwohl der Sofort-Versand auch Premium-SMS verschickt.
// Soll: „Premium-SMS" genau dann, wenn eingeschaltet UND zustellbar
// (premiumSmsChannelState(profile).disabled === false); gesperrt oder aus ⇒ nicht genannt.
//
// Reine Funktion, echt aufgerufen, kein Mock. Pfadregel #1409: relativ zur Testdatei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/versand-tab/__tests__/sendTargetLabel_premium_sms.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { sendTargetLabel } from '../sendTargetLabel.ts';

const MAIL = 'wanderer@example.org';

const ZUSTELLBAR = {
	mail_to: MAIL,
	email_verified: true,
	premium_sms_allowed: true,
	premium_sms_reply_state: 'fresh' as const,
	premium_sms_reply_to: '+491700000000'
};

describe('AC-2: Premium-SMS an + zustellbar ⇒ im Ziel-Text genannt', () => {
	test('frische Rueckadresse, Tarif Premium → „Premium-SMS" im Text', () => {
		const ziel = sendTargetLabel(ZUSTELLBAR, { send_premium_sms: true });
		assert.equal(ziel.text, `Geht an E-Mail (${MAIL}) · Premium-SMS.`);
		assert.equal(ziel.deliverable, true);
	});
});

describe('AC-2 Gegenprobe: gesperrt oder aus ⇒ nicht genannt', () => {
	// Absichtlich schon heute gruen — sie bewachen die Sperr-Zweige gegen einen
	// Fix, der allein am Opt-in haengt (Falschaussage wie #1471).
	test('Rueckadresse verfallen (stale) → nicht genannt', () => {
		const ziel = sendTargetLabel(
			{ ...ZUSTELLBAR, premium_sms_reply_state: 'stale' },
			{ send_premium_sms: true }
		);
		assert.equal(ziel.text, `Geht an E-Mail (${MAIL}).`);
	});

	test('nie gemeldet (none) → nicht genannt', () => {
		const ziel = sendTargetLabel(
			{ ...ZUSTELLBAR, premium_sms_reply_state: 'none' },
			{ send_premium_sms: true }
		);
		assert.equal(ziel.text, `Geht an E-Mail (${MAIL}).`);
	});

	test('Tarif ohne Premium-SMS → nicht genannt', () => {
		const ziel = sendTargetLabel(
			{ ...ZUSTELLBAR, premium_sms_allowed: false },
			{ send_premium_sms: true }
		);
		assert.equal(ziel.text, `Geht an E-Mail (${MAIL}).`);
	});

	test('send_premium_sms=false → nicht genannt (AC-6 byte-gleich)', () => {
		const ziel = sendTargetLabel(ZUSTELLBAR, { send_premium_sms: false });
		assert.equal(ziel.text, `Geht an E-Mail (${MAIL}).`);
	});
});

describe('AC-7: zwei Nutzer, dasselbe Preset — jeder Text folgt nur seinem Profil', () => {
	test('A zustellbar, B gesperrt → Texte unterscheiden sich genau um „ · Premium-SMS"', () => {
		const preset = { send_premium_sms: true };
		const profilB = {
			mail_to: 'andere@example.org',
			email_verified: true,
			premium_sms_allowed: true,
			premium_sms_reply_state: 'stale' as const
		};

		const a = sendTargetLabel(ZUSTELLBAR, preset);
		const b = sendTargetLabel(profilB, preset);
		// Reihenfolge umgekehrt erneut — kein Durchschlagen eines vorherigen Aufrufs.
		const b2 = sendTargetLabel(profilB, preset);
		const a2 = sendTargetLabel(ZUSTELLBAR, preset);

		assert.equal(a.text, `Geht an E-Mail (${MAIL}) · Premium-SMS.`);
		assert.equal(b.text, 'Geht an E-Mail (andere@example.org).');
		assert.equal(a2.text, a.text);
		assert.equal(b2.text, b.text);
	});
});

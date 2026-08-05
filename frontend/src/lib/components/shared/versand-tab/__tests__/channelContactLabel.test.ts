// TDD RED — Bugfix "Kontakt-Beschriftung + Verbindungsstatus der Kanal-
// Checkboxen bündeln" (#1510).
// Spec: docs/specs/modules/fix_1510_versand_ziel_dedupe.md — AC-1.
//
// Reine Verhaltenstests der neuen geteilten Ableitung `channelContactLabel(profile)`.
// Reine Funktion, kein Netz, kein DOM, keine Attrappe — der Prüfling wird echt
// aufgerufen und sein Rückgabewert bewertet.
//
// RED heute: `../channelContactLabel.ts` existiert nicht (ERR_MODULE_NOT_FOUND) —
// die sechs Ternary-Duplikate in VTBriefingChannels.svelte/EditReportConfigSection.svelte
// sind bislang der einzige Ort, an dem diese Ableitung passiert.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/shared/versand-tab/__tests__/channelContactLabel.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { channelContactLabel } from '../channelContactLabel.ts';

const MAIL = 'anna@example.org';
const CHAT_ID = '4711';
const SMS = '+49150000000';

describe('AC-1: channelContactLabel liefert je Kanal den Kontakt-Suffix oder ""', () => {
	test('E-Mail vorhanden → Suffix " (<Adresse>)"', () => {
		const { email } = channelContactLabel({ mail_to: MAIL });
		assert.equal(email, ` (${MAIL})`, `Erwartet Suffix mit Adresse, erhielt "${email}" (AC-1).`);
	});

	test('E-Mail fehlt → leerer Suffix', () => {
		const { email } = channelContactLabel({});
		assert.equal(email, '', `Erwartet leeren Suffix ohne mail_to, erhielt "${email}" (AC-1).`);
	});

	test('Telegram vorhanden → Suffix " (<Chat-ID>)"', () => {
		const { telegram } = channelContactLabel({ telegram_chat_id: CHAT_ID });
		assert.equal(
			telegram,
			` (${CHAT_ID})`,
			`Erwartet Suffix mit Chat-ID, erhielt "${telegram}" (AC-1).`
		);
	});

	test('Telegram fehlt → leerer Suffix', () => {
		const { telegram } = channelContactLabel({});
		assert.equal(telegram, '', `Erwartet leeren Suffix ohne telegram_chat_id, erhielt "${telegram}" (AC-1).`);
	});

	test('SMS vorhanden → Suffix " (<Nummer>)"', () => {
		const { sms } = channelContactLabel({ sms_to: SMS });
		assert.equal(sms, ` (${SMS})`, `Erwartet Suffix mit Nummer, erhielt "${sms}" (AC-1).`);
	});

	test('SMS fehlt → leerer Suffix', () => {
		const { sms } = channelContactLabel({});
		assert.equal(sms, '', `Erwartet leeren Suffix ohne sms_to, erhielt "${sms}" (AC-1).`);
	});

	test('alle drei Kanäle unabhängig voneinander gefüllt', () => {
		const labels = channelContactLabel({ mail_to: MAIL, telegram_chat_id: CHAT_ID, sms_to: SMS });
		assert.deepEqual(
			labels,
			{ email: ` (${MAIL})`, telegram: ` (${CHAT_ID})`, sms: ` (${SMS})` },
			`Erwartet alle drei Suffixe gefüllt, erhielt ${JSON.stringify(labels)} (AC-1).`
		);
	});

	test('profile = null → alle drei Felder ""', () => {
		const labels = channelContactLabel(null);
		assert.deepEqual(
			labels,
			{ email: '', telegram: '', sms: '' },
			`Erwartet alle drei Felder leer bei profile=null, erhielt ${JSON.stringify(labels)} (AC-1).`
		);
	});

	test('profile = undefined → alle drei Felder ""', () => {
		const labels = channelContactLabel(undefined);
		assert.deepEqual(
			labels,
			{ email: '', telegram: '', sms: '' },
			`Erwartet alle drei Felder leer bei profile=undefined, erhielt ${JSON.stringify(labels)} (AC-1).`
		);
	});
});

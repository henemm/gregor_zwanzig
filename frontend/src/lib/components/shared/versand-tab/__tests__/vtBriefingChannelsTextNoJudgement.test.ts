// TDD — Issue #1719 Scheibe S3, AC-5a (Adversary-Fund F002, BROKEN,
// verifiziert nach GREEN, 2026-08-11): die Hinweistexte im Trip-Versand-
// Reiter (VTBriefingChannels.svelte, "Geplantes Briefing · Kanäle") waren
// bislang durch KEINEN Test abgedeckt. `channelHintTextNoJudgement.test.ts`
// prüft laut eigenem Kopfkommentar ausschließlich `ltCapNoteText`
// (Trip-Kanal-Reiter, LayoutTab) — nicht den Versand-Reiter. Ausgerechnet
// dort stand die ursprüngliche Bevormundung ("SMS läuft flach" /
// "SMS wird flach").
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md AC-5a
//
// Geprüft wird der ERZEUGTE TEXT reiner Funktionen (kein
// read_text()-Dateiinhalt-Check — im Projekt verboten). Die Text-Erzeugung
// ist aus VTBriefingChannels.svelte nach vtBriefingChannelsText.ts
// ausgelagert (Vorbild: channelConnectionStatus.ts/channelContactLabel.ts/
// premiumSmsChannelState.ts, bereits geteilte Ableitungen im selben
// Verzeichnis).
//
// Dieselbe Verbotsliste wie channelHintTextNoJudgement.test.ts (Spec AC-5,
// Commit 3da43cad) — beide Kontexte (route UND vergleich).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/versand-tab/__tests__/vtBriefingChannelsTextNoJudgement.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { vtBriefingLeadText, vtBriefingSubTexts, vtBriefingSmsCharLimit } from '../vtBriefingChannelsText.ts';

// Identisch zu channelHintTextNoJudgement.test.ts (Spec AC-5, Commit 3da43cad).
const BANNED_WERTUNG = [
	'entscheidungskritisch',
	'nur das wesentliche',
	'nur die wichtigsten',
	'läuft flach',
	'wird flach'
];

function assertNoWertung(text: string, label: string) {
	const lower = text.toLowerCase();
	for (const phrase of BANNED_WERTUNG) {
		assert.equal(
			lower.includes(phrase.toLowerCase()),
			false,
			`AC-5a FAIL: Hinweistext (${label}) enthaelt die verbotene Wertung "${phrase}": "${text}"`
		);
	}
}

describe('AC-5a: VTBriefingChannels-Hinweistexte enthalten keine Wertung (Trip- UND Vergleichskontext)', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`Einleitungstext (${context}) — kein verbotener Wertungsbegriff`, () => {
			const text = vtBriefingLeadText(context);
			assertNoWertung(text, `lead/${context}`);
		});

		test(`Kanal-Unterzeilen (${context}) — kein verbotener Wertungsbegriff, insbesondere SMS`, () => {
			const sub = vtBriefingSubTexts(context);
			assertNoWertung(sub.email, `sub.email/${context}`);
			assertNoWertung(sub.telegram, `sub.telegram/${context}`);
			assertNoWertung(sub.sms, `sub.sms/${context}`);
		});
	}

	test('SMS-Zeichengrenze ist kontextabhängig: 160 im Trip, 153 im Vergleich', () => {
		assert.equal(
			vtBriefingSmsCharLimit('route'),
			160,
			'AC-6 FAIL: der Trip-Versand-Reiter muss die Trip-Zeichengrenze (160) nennen'
		);
		assert.equal(
			vtBriefingSmsCharLimit('vergleich'),
			153,
			'AC-6 FAIL: der Vergleichs-Versand-Reiter muss die Vergleichs-Zeichengrenze (153) nennen'
		);
	});

	test('die SMS-Unterzeile nennt die kontextabhängige Zeichenzahl, nicht "140"', () => {
		const routeSub = vtBriefingSubTexts('route');
		const compareSub = vtBriefingSubTexts('vergleich');
		assert.match(routeSub.sms, /160 Zeichen/);
		assert.match(compareSub.sms, /153 Zeichen/);
		assert.equal(routeSub.sms.includes('140'), false, 'AC-5a FAIL: "140" ist im Trip-Kontext falsch');
		assert.equal(compareSub.sms.includes('140'), false, 'AC-5a FAIL: "140" ist im Vergleichs-Kontext falsch');
	});
});

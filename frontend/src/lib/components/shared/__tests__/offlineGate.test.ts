// TDD — Issue #2131 Adversary-Finding F002: `deriveOfflineGate` ist im eigenen
// Kommentar als „node:testbar" beschrieben (../offlineGate.ts:6) und folgt dem
// Vorbild `alarme-tab/premiumSmsAlarmGate.ts` — fuer das Vorbild existiert
// `alarme-tab/__tests__/premiumSmsAlarmGate.test.ts`, hier bisher nicht. Alle
// vier Zweige wurden bislang nur transitiv ueber E2E erreicht.
// Spec: docs/specs/modules/pwa_offline_ansicht_letzter_stand.md, Abschnitt H
//   (AC-9, AC-10, AC-11).
//
// Reine Funktionspruefung, kein Mount, kein Netz, kein DOM (ADR-0020).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/offlineGate.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
	deriveOfflineGate,
	OFFLINE_HINT_AUS_SPEICHER,
	OFFLINE_HINT_NETZ_WEG,
	OFFLINE_KURZ_AUS_SPEICHER,
	OFFLINE_KURZ_NETZ_WEG
} from '../offlineGate.ts';

describe('#2131 AC-9: Ansicht aus dem Geraetespeicher ist gesperrt', () => {
	test('ausSpeicher_true_sperrtMitSpeicherHinweis', () => {
		const gate = deriveOfflineGate({ ausSpeicher: true, offline: false });
		assert.strictEqual(gate.disabled, true);
		assert.strictEqual(gate.hint, OFFLINE_HINT_AUS_SPEICHER);
	});
});

describe('#2131 AC-11: live geladen, dann Netzverlust, ist gesperrt', () => {
	test('offline_true_ausSpeicher_false_sperrtMitNetzHinweis', () => {
		const gate = deriveOfflineGate({ offline: true, ausSpeicher: false });
		assert.strictEqual(gate.disabled, true);
		assert.strictEqual(gate.hint, OFFLINE_HINT_NETZ_WEG);
	});
});

describe('#2131: online und live geladen ist bedienbar', () => {
	test('beideFalse_bedienbar', () => {
		const gate = deriveOfflineGate({ offline: false, ausSpeicher: false });
		assert.strictEqual(gate.disabled, false);
		assert.strictEqual(gate.hint, null);
	});

	test('keinZustand_wirdAlsNichtGesperrtBehandelt', () => {
		// Kein dritter, unbekannter Fall (offlineGate.ts:43-47): der Store setzt
		// beide Werte synchron beim Start. Ein fehlendes Argument ist ein
		// Programmfehler des Aufrufers, keine Sperre der gesamten Oberflaeche.
		for (const zustand of [null, undefined]) {
			const gate = deriveOfflineGate(zustand);
			assert.strictEqual(gate.disabled, false);
			assert.strictEqual(gate.hint, null);
		}
	});
});

describe('#2131 AC-9 (Adversary-Finding F005): die Kurzform am Element', () => {
	// Der Hinweis AN der Bedien-Gruppe kommt aus derselben Ableitung wie der
	// Balken oben. Zwei getrennte Quellen waeren zwei Wahrheiten: die Gruppe
	// koennte „ohne Verbindung" behaupten, waehrend oben der Speicher-Grund
	// steht — oder umgekehrt.
	test('jederSperrgrund_hatEineKurzform', () => {
		assert.strictEqual(
			deriveOfflineGate({ ausSpeicher: true }).kurz,
			OFFLINE_KURZ_AUS_SPEICHER
		);
		assert.strictEqual(deriveOfflineGate({ offline: true }).kurz, OFFLINE_KURZ_NETZ_WEG);
	});

	test('kurzformNenntDenGrund_nichtNurDenZustand', () => {
		for (const kurz of [OFFLINE_KURZ_AUS_SPEICHER, OFFLINE_KURZ_NETZ_WEG]) {
			assert.ok(
				kurz.length > 10,
				`"${kurz}" ist zu knapp, um eine Begruendung zu sein (AC-9 verlangt eine Begruendung, nicht nur ein Merkmal)`
			);
			assert.match(
				kurz,
				/Verbindung|Gerätespeicher/u,
				`"${kurz}" nennt den Sperrgrund nicht — ein blosses „gesperrt" erklaert nichts`
			);
		}
	});

	test('bedienbar_hatKeineKurzform', () => {
		assert.strictEqual(deriveOfflineGate({ offline: false, ausSpeicher: false }).kurz, null);
		assert.strictEqual(deriveOfflineGate(null).kurz, null);
	});
});

describe('#2131 Vorrangregel: ausSpeicher gewinnt vor offline', () => {
	test('beideTrue_liefertSpeicherHinweis_nichtNetzHinweis', () => {
		const gate = deriveOfflineGate({ ausSpeicher: true, offline: true });
		assert.strictEqual(gate.disabled, true);
		assert.strictEqual(
			gate.hint,
			OFFLINE_HINT_AUS_SPEICHER,
			'bei beiden Sperrgruenden gleichzeitig muss die Speicher-Begruendung gewinnen (offlineGate.ts:48-50 ' +
				'vor 51-53) — sonst behauptete der Text einer vorgehaltenen Ansicht faelschlich einen ' +
				'Netzverlust waehrend einer laufenden Sitzung'
		);
	});
});

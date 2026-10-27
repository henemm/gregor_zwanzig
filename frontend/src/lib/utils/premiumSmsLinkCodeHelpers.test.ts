// TDD RED — Issue #2154 Scheibe B: Premium-SMS-Verknüpfungscode im Konto.
// Spec: docs/specs/modules/fix_2154_s2_premium_sms_link_code_ui.md — AC-2 bis
// AC-6, AC-8 bis AC-11.
//
// `premiumSmsLinkCodeHelpers.ts` existiert in der RED-Phase noch NICHT → der
// Import wirft einen Modul-Resolve-Fehler (ERR_MODULE_NOT_FOUND) und alle
// Tests scheitern.
//
// Architektur: Pure-Funktionen liegen in `.ts` (hier testbar via node:test),
// die Svelte-Karte (`PremiumSmsLinkCard.svelte` + `+page.svelte`) verdrahtet
// diese Funktionen nur (Repo-Konvention: kein Svelte-Compiler im Test-Setup,
// Vorbild `presetCardHelpers.ts`/`.test.ts`).
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/premiumSmsLinkCodeHelpers.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
	shouldShowPremiumSmsLinkCard,
	needsRenewConfirmation,
	resolveGenerateClick,
	resolveDialogAction,
	deriveLinkCodeExists,
	errorMessageFrom,
} from './premiumSmsLinkCodeHelpers.ts';

// =========================================================================
// AC-8: Sichtbarkeit nur fuer Tier "premium"
// =========================================================================

describe('AC-8: shouldShowPremiumSmsLinkCard — nur Premium-Tier sieht die Karte', () => {
	test('tier "premium" → true', () => {
		assert.equal(shouldShowPremiumSmsLinkCard('premium'), true);
	});

	test('tier "free" → false', () => {
		assert.equal(shouldShowPremiumSmsLinkCard('free'), false);
	});

	test('tier "standard" → false', () => {
		assert.equal(shouldShowPremiumSmsLinkCard('standard'), false);
	});

	test('tier undefined (kein Profil geladen) → false', () => {
		assert.equal(shouldShowPremiumSmsLinkCard(undefined), false);
	});
});

// =========================================================================
// AC-3 / AC-4: "Erzeugen" vs. "Erneuern"
// =========================================================================

describe('AC-3/AC-4: needsRenewConfirmation — Bestätigung nur bei bestehendem Code', () => {
	test('kein Code vorhanden (exists=false) → keine Bestätigung nötig', () => {
		assert.equal(needsRenewConfirmation(false), false);
	});

	test('Code vorhanden (exists=true) → Bestätigung nötig', () => {
		assert.equal(needsRenewConfirmation(true), true);
	});
});

// =========================================================================
// AC-2 / AC-4 / AC-11: Klick-Verzweigung "Erzeugen"/"Erneuern"
// =========================================================================

describe('AC-2/AC-4/AC-11: resolveGenerateClick — Klickpfad je nach exists/busy', () => {
	test('kein Code, nicht busy → sofortiger POST', () => {
		assert.equal(resolveGenerateClick(false, false), 'call-post');
	});

	test('bestehender Code, nicht busy → erst Bestätigungsdialog, NIEMALS sofortiger POST', () => {
		assert.equal(resolveGenerateClick(true, false), 'confirm-dialog');
	});

	test('kein Code, aber busy (Request läuft bereits) → kein zweiter POST', () => {
		assert.equal(resolveGenerateClick(false, true), 'noop');
	});

	test('bestehender Code, busy → ebenfalls kein zweiter Vorgang', () => {
		assert.equal(resolveGenerateClick(true, true), 'noop');
	});
});

// =========================================================================
// AC-5 / AC-6: Dialog-Entscheidung "Bestätigen"/"Abbrechen"
// =========================================================================

describe('AC-5/AC-6: resolveDialogAction — Bestätigen postet, Abbrechen nie', () => {
	test('Bestätigen → derselbe Aktionscode wie Erst-Erzeugen ("call-post")', () => {
		assert.equal(resolveDialogAction('confirm'), 'call-post');
		assert.equal(resolveDialogAction('confirm'), resolveGenerateClick(false, false));
	});

	test('Abbrechen → niemals "call-post"', () => {
		assert.equal(resolveDialogAction('cancel'), 'none');
	});
});

// =========================================================================
// AC-10: Fail-closed Ableitung des Anfangszustands
// =========================================================================

describe('AC-10: deriveLinkCodeExists — fail-closed bei fehlender/kaputter Antwort', () => {
	test('Antwort null (Netzfehler/Non-200) → gilt als vorhanden', () => {
		assert.equal(deriveLinkCodeExists(null), true);
	});

	test('Antwort undefined → gilt als vorhanden', () => {
		assert.equal(deriveLinkCodeExists(undefined), true);
	});

	test('leeres Objekt (unerwartete Antwortform) → gilt als vorhanden', () => {
		assert.equal(deriveLinkCodeExists({}), true);
	});

	test('explizit {exists: false} → gilt NICHT als vorhanden', () => {
		assert.equal(deriveLinkCodeExists({ exists: false }), false);
	});

	test('explizit {exists: true} → gilt als vorhanden', () => {
		assert.equal(deriveLinkCodeExists({ exists: true }), true);
	});
});

// =========================================================================
// AC-9: Fehlermeldung — Backend-Fehler UND Netzfehler
// =========================================================================

describe('AC-9: errorMessageFrom — verständliche Meldung statt Rohtext/Absturz', () => {
	test('Backend-Fehler ohne JSON (client meldet "HTTP <status>") → fester Fallback-Text', () => {
		assert.equal(
			errorMessageFrom({ error: 'HTTP 500', status: 500 }, 'Code-Vorgang fehlgeschlagen'),
			'Code-Vorgang fehlgeschlagen'
		);
	});

	test('echter Servertext (.detail) hat Vorrang vor dem Fallback', () => {
		assert.equal(errorMessageFrom({ detail: 'Sitzung abgelaufen' }, 'fallback'), 'Sitzung abgelaufen');
	});

	test('Netzfehler (echtes Error-Objekt mit .message) wird durchgereicht', () => {
		assert.equal(
			errorMessageFrom(new Error('Ohne Verbindung zum Server.'), 'fallback'),
			'Ohne Verbindung zum Server.'
		);
	});

	test('unbekannte Fehlerform → fester Fallback-Text, kein Absturz', () => {
		assert.equal(errorMessageFrom({}, 'Code-Vorgang fehlgeschlagen'), 'Code-Vorgang fehlgeschlagen');
	});
});

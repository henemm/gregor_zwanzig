// Issue #2660 (i18n F11, Epic #2644) — AC-1: Fehlermeldung beim Speichern folgt
// der Nutzersprache, wenn der Server einen BEKANNTEN Fehlercode schickt; ohne
// oder mit unbekanntem Code bleibt die Server-Meldung unveraendert.
// Fehlerobjekte haben die echte Form der Go-API (docs/reference/api_contract.md,
// „Fehlerobjekt code/message"): {code, message, error (= code), detail}.
// Erwartete Texte kommen aus dem Katalog (trFor), nie aus Literalen; einzige
// Ausnahme sind die Golden-Literale der deutschen Anzeige (AC-5).
// Spec: docs/specs/modules/i18n_f11_bausteine_ts_2660.md
//
//   cd frontend && npm test -- src/lib/stores/__tests__/fehlermeldung_code_und_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { extractMessage } from '../saveStatusStore.svelte.ts';
import { locale, trFor } from '../../i18n/index.ts';
import { de } from '../../i18n/messages/de/index.ts';
import { en } from '../../i18n/messages/en/index.ts';

afterEach(() => locale.set('de'));

/** Fehlerobjekt wie es `api.ts` nach einer Go-Fehlerantwort wirft. */
function goFehler(code: string, message: string, status = 412) {
	return { code, message, error: code, detail: message, status };
}

const BEKANNT = 'etag_mismatch';
const SCHLUESSEL = `fehler.code.${BEKANNT}` as keyof typeof de;

describe('AC-1: Fehlermeldung mit und ohne code', () => {
	test('Vorbedingung: der bekannte Code steht in beiden Katalogen mit eigenem englischem Text', () => {
		assert.ok(de[SCHLUESSEL], `de: ${SCHLUESSEL} fehlt`);
		assert.ok((en as Record<string, string>)[SCHLUESSEL], `en: ${SCHLUESSEL} fehlt`);
		assert.notEqual(trFor('en', SCHLUESSEL), trFor('de', SCHLUESSEL));
	});

	test('en, ohne code: die Server-Meldung erscheint unveraendert', () => {
		locale.set('en');
		assert.equal(extractMessage({ error: 'Etappe 3 hat kein Datum', status: 422 }), 'Etappe 3 hat kein Datum');
		assert.equal(extractMessage({ detail: 'Serverdetail', error: 'x' }), 'Serverdetail');
	});

	test('en, bekannter code: englischer Katalogtext statt Server-Meldung', () => {
		locale.set('en');
		const meldung = extractMessage(goFehler(BEKANNT, 'Die Daten wurden geändert.'));
		assert.equal(meldung, trFor('en', SCHLUESSEL));
		assert.notEqual(meldung, 'Die Daten wurden geändert.');
	});

	test('en, unbekannter code: wieder die Server-Meldung', () => {
		locale.set('en');
		assert.equal(extractMessage(goFehler('gibt_es_nicht_2660', 'Servertext unverändert')), 'Servertext unverändert');
	});

	test('de, bekannter code: deutscher Katalogtext', () => {
		locale.set('de');
		assert.equal(extractMessage(goFehler(BEKANNT, 'irgendwas')), trFor('de', SCHLUESSEL));
	});

	test('jeder Go-Fehlercode aus dem Katalog wird in der Sprache zum Aufrufzeitpunkt aufgeloest', () => {
		const codes = Object.keys(de)
			.filter((k) => k.startsWith('fehler.code.'))
			.map((k) => k.slice('fehler.code.'.length));
		assert.ok(codes.includes('not_found') && codes.includes('store_error'), codes.join(','));
		for (const code of codes) {
			const k = `fehler.code.${code}` as keyof typeof de;
			locale.set('en');
			assert.equal(extractMessage(goFehler(code, 'Server')), trFor('en', k), code);
			locale.set('de');
			assert.equal(extractMessage(goFehler(code, 'Server')), trFor('de', k), code);
		}
	});

	test('Rueckfall ohne verwertbares Feld: de wortgleich, en aus dem Katalog', () => {
		locale.set('de');
		assert.equal(extractMessage(null), 'Fehler beim Speichern');
		assert.equal(extractMessage({}), 'Fehler beim Speichern');
		locale.set('en');
		assert.equal(extractMessage(null), trFor('en', 'fehler.speichern.allgemein'));
		assert.notEqual(extractMessage(null), 'Fehler beim Speichern');
	});

	test('code ohne Zeichenkette oder mit fremden Zeichen gilt als unbekannt', () => {
		locale.set('en');
		assert.equal(extractMessage({ code: 42, error: 'Zahl' }), 'Zahl');
		assert.equal(extractMessage({ code: 'not_found.x', error: 'Punkt' }), 'Punkt');
		assert.equal(extractMessage({ code: 'speichern.allgemein', error: 'Pfad' }), 'Pfad');
	});
});

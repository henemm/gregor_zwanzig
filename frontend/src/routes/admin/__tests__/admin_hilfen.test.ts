// TDD RED — Issue #2155 S4: reine Helfer der Admin-Seite in `lib/admin.ts`.
// Spec: docs/specs/modules/admin_ui_s4.md — AC-4 (Zeilenersetzung), AC-6 (Fehlertexte),
// AC-7 (zentrale Tier-Konstante).
//
// RED heute: `frontend/src/lib/admin.ts` existiert nicht — der Import scheitert.
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/admin/__tests__/admin_hilfen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const { TIER_LABELS, adminErrorText, replaceUserRow } = (await import('../../../lib/admin.ts')) as any;

const zeile = (id: string, tier = 'free', extra: Record<string, unknown> = {}) => ({
	id, email: `${id}@example.org`, display_name: id, tier,
	requested_tier: '', requested_at: '', email_verified_at: '', created_at: '',
	disabled: false, is_test_user: false, last_trip_report_run: null, ...extra
});

describe('AC-4: Antwort ersetzt NUR die Zeile des betroffenen Nutzers', () => {
	test('X wird ersetzt, Y bleibt identisch (gleiches Objekt, gleiche Reihenfolge)', () => {
		const x = zeile('x', 'free', { requested_tier: 'premium', requested_at: 't' });
		const y = zeile('y', 'standard');
		const neuesX = zeile('x', 'premium');
		const ergebnis = replaceUserRow([x, y], neuesX);
		assert.equal(ergebnis.length, 2);
		assert.deepEqual(ergebnis[0], neuesX);
		assert.equal(ergebnis[0].requested_tier, '', 'Antrag muss aus der Antwort kommen');
		assert.strictEqual(ergebnis[1], y, 'Zeile Y wurde angefasst');
	});

	test('mutiert die Eingabeliste nicht und haengt keine unbekannte Zeile an', () => {
		const liste = [zeile('x'), zeile('y')];
		const kopie = JSON.parse(JSON.stringify(liste));
		const ergebnis = replaceUserRow(liste, zeile('unbekannt', 'premium'));
		assert.deepEqual(liste, kopie, 'Eingabe wurde veraendert');
		assert.deepEqual(ergebnis, kopie, 'unbekannte ID darf die Liste nicht veraendern');
	});
});

describe('AC-6: Fehlertexte — je Fall eigener Klartext, nie der rohe Code', () => {
	const faelle: Array<[number, string]> = [
		[403, 'forbidden'],
		[404, 'not_found'],
		[409, 'cannot_disable_self'],
		[400, 'invalid_tier'],
		[400, 'invalid_request']
	];

	test('jeder Fall liefert nicht-leeren Text ohne rohen Fehlercode', () => {
		for (const [status, code] of faelle) {
			const text: string = adminErrorText(status, code);
			assert.ok(text && text.length > 5, `${status}/${code}: leer`);
			assert.ok(!text.includes(code), `${status}/${code}: roher Code im Text "${text}"`);
			assert.ok(!text.includes('_'), `${status}/${code}: Snake-Case im Text "${text}"`);
		}
	});

	test('403, 404 und 409 sind voneinander verschieden, mit den Spec-Texten', () => {
		const t403 = adminErrorText(403, 'forbidden');
		const t404 = adminErrorText(404, 'not_found');
		const t409 = adminErrorText(409, 'cannot_disable_self');
		assert.equal(new Set([t403, t404, t409]).size, 3);
		assert.equal(t409, 'Das eigene Konto kann nicht gesperrt werden');
		assert.equal(t403, 'Keine Berechtigung');
		assert.equal(t404, 'Nutzer nicht gefunden');
		assert.equal(adminErrorText(400, 'invalid_tier'), 'Ungültige Eingabe');
	});

	// Adversary F004: der Selbstsperr-Text gilt NUR fuer 409 + cannot_disable_self.
	test('409 mit anderem oder ohne Code => allgemeine Meldung, NICHT der Selbstsperr-Text', () => {
		const allgemein = 'Aktion fehlgeschlagen. Bitte erneut versuchen.';
		const selbst = 'Das eigene Konto kann nicht gesperrt werden';
		for (const code of ['conflict', 'tier_request_pending', undefined]) {
			const text: string = adminErrorText(409, code);
			assert.notEqual(text, selbst, `409/${code}: faelschlich Selbstsperr-Text`);
			assert.equal(text, allgemein, `409/${code}: keine allgemeine Meldung`);
		}
	});

	test('unbekannter Status/Code faellt auf eine allgemeine Meldung zurueck', () => {
		const text: string = adminErrorText(500, 'store_error');
		assert.ok(text.length > 5 && !text.includes('store_error'));
	});
});

describe('AC-7: EINE zentrale Tier-Konstante', () => {
	test('Bezeichnungen sind die bisherigen der Konto-Seite', () => {
		assert.deepEqual({ ...TIER_LABELS }, { free: 'Free', standard: 'Standard', premium: 'Premium' });
	});

	// doc-compliance-test — Verdrahtung: die Konto-Seite darf keine eigene Kopie haben
	// und muss die zentrale Konstante importieren (Spec AC-7, Mutation "lokale Kopie").
	test('account/+page.svelte importiert TIER_LABELS aus lib/admin und definiert keine eigene', () => {
		const quelle = readFileSync(
			new URL('../../account/+page.svelte', import.meta.url), 'utf8'
		);
		assert.ok(/import[^;]*TIER_LABELS[^;]*from\s+['"]\$lib\/admin(\.js)?['"]/.test(quelle),
			'TIER_LABELS wird nicht aus $lib/admin importiert');
		assert.ok(!/const\s+TIER_LABELS\s*[:=]/.test(quelle),
			'account/+page.svelte definiert TIER_LABELS noch lokal');
	});
});

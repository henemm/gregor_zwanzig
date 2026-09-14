// TDD RED — Issue #2154 Scheibe B: Premium-SMS-Verknüpfungscode im Konto.
// Spec: docs/specs/modules/fix_2154_s2_premium_sms_link_code_ui.md — AC-10
// (fail-closed Anfangszustand).
//
// AC-7 (kein Klartext im serverseitigen PageData) wird bewusst NICHT hier
// getestet: ein Test auf Abwesenheit eines Feldes, das `load()` heute schon
// nie zurückgibt, waere vor jeder Implementierung bereits gruen — er bewiese
// nichts (kein RED). AC-7 traegt stattdessen die Adversary-Mutationsprobe in
// `/50-implement` (Leitfrage: wirkt die Zusicherung an der Wiring-Stelle).
//
// Die exportierte `load()` aus `account/+page.server.ts` wird ECHT
// aufgerufen — nur die Netzgrenze (`fetch`) ist ersetzt. Kein Mock des
// Prueflings selbst, kein Dateiinhalt-Grep. Vorbild:
// frontend/src/routes/compare/__tests__/compare_page_server_profile_isolation.test.ts.
//
// RED heute: `load()` ruft `GET /api/auth/premium-sms-link-code` überhaupt
// nicht ab — das zurückgegebene Objekt hat kein `premiumSmsLinkCodeExists`,
// jede Assertion auf `true`/`false` scheitert mit `undefined`.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/account/__tests__/premium_sms_link_code_load.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';

register(new URL('./server-load-resolve.hooks.mjs', import.meta.url));

const { load } = (await import('../+page.server.ts')) as any;

/** Steuert die Antwort von GET /api/auth/premium-sms-link-code je Testfall. */
let linkCodeResponse: 'exists-true' | 'exists-false' | 'non-ok' | 'network-error' = 'exists-true';

async function fetchDouble(input: any) {
	const url = String(input);
	if (url.includes('/api/auth/premium-sms-link-code')) {
		if (linkCodeResponse === 'network-error') throw new TypeError('fetch failed');
		if (linkCodeResponse === 'non-ok') return { ok: false, status: 500, json: async () => ({}) };
		const exists = linkCodeResponse === 'exists-true';
		return { ok: true, status: 200, json: async () => ({ exists }) };
	}
	// Alle anderen Aufrufe (profile, scheduler, health, ...) sind fuer diese
	// Tests irrelevant — 404, die bestehenden `.catch(() => null/[])`-Ketten
	// in `load()` fangen das fail-soft ab (unveraendertes Bestandsverhalten).
	return { ok: false, status: 404, json: async () => ({}) };
}

const event = () => ({
	cookies: { get: (name: string) => (name === 'gz_session' ? 'sess-1' : undefined) }
});

let originalFetch: typeof globalThis.fetch;
before(() => {
	originalFetch = globalThis.fetch;
	globalThis.fetch = fetchDouble as unknown as typeof globalThis.fetch;
});
after(() => {
	globalThis.fetch = originalFetch;
});

describe('AC-10: premiumSmsLinkCodeExists — fail-closed bei Non-200/Netzfehler', () => {
	test('Backend meldet {exists: true} → premiumSmsLinkCodeExists === true', async () => {
		linkCodeResponse = 'exists-true';
		const result: any = await load(event());
		assert.equal(
			result?.premiumSmsLinkCodeExists,
			true,
			`load() liefert premiumSmsLinkCodeExists=${result?.premiumSmsLinkCodeExists} statt true — ` +
				'der Konto-Endpoint aus Scheibe A wird noch nicht abgerufen.'
		);
	});

	test('Backend meldet {exists: false} → premiumSmsLinkCodeExists === false', async () => {
		linkCodeResponse = 'exists-false';
		const result: any = await load(event());
		assert.equal(
			result?.premiumSmsLinkCodeExists,
			false,
			`load() liefert premiumSmsLinkCodeExists=${result?.premiumSmsLinkCodeExists} statt false.`
		);
	});

	test('Backend antwortet Non-200 → fail-closed, gilt als vorhanden (kein unbestätigtes "Erzeugen")', async () => {
		linkCodeResponse = 'non-ok';
		const result: any = await load(event());
		assert.equal(
			result?.premiumSmsLinkCodeExists,
			true,
			'AC-10: ein transienter Backend-Fehler darf niemals als "kein Code vorhanden" gelten — ' +
				'sonst könnte ein Klick einen tatsächlich funktionierenden Code stillschweigend entwerten.'
		);
	});

	test('Netzfehler beim Abruf → fail-closed, gilt als vorhanden', async () => {
		linkCodeResponse = 'network-error';
		const result: any = await load(event());
		assert.equal(
			result?.premiumSmsLinkCodeExists,
			true,
			'AC-10: ein Netzfehler beim initialen Statusabruf muss ebenfalls fail-closed behandelt werden.'
		);
	});
});

// F002 (Adversary-Finding, AMBIGUOUS-Runde): kein bestehender Test prüfte, dass
// das Rückgabeobjekt von load() NIEMALS ein Feld mit Code-Klartext enthält
// (AC-7). Eine Mutationsprobe (zusätzliches Feld mit Klartext-Wert) blieb bei
// allen 35 Kern-Tests unbemerkt grün. Fail-closed gegen Feldzuwachs: feste
// Allowlist aller erwarteten Top-Level-Schlüssel.
describe('F002: load()-Rückgabeobjekt enthält NIEMALS ein Code-Klartext-Feld', () => {
	const ERWARTETE_SCHLUESSEL = [
		'profile',
		'scheduler',
		'health',
		'templates',
		'trips',
		'comparePresets',
		'locations',
		'metricPresets',
		'premiumSmsLinkCodeExists'
	].sort();

	let allowlistFetch: typeof globalThis.fetch;
	before(() => {
		allowlistFetch = globalThis.fetch;
		globalThis.fetch = (async (input: any) => {
			const url = String(input);
			if (url.includes('/api/auth/premium-sms-link-code')) {
				return { ok: true, status: 200, json: async () => ({ exists: true }) };
			}
			if (url.includes('/api/auth/profile')) {
				return { ok: true, status: 200, json: async () => ({ id: 'u1', email: 'a@b.de' }) };
			}
			if (url.includes('/api/scheduler/status')) {
				return { ok: true, status: 200, json: async () => ({ jobs: [] }) };
			}
			if (url.includes('/api/health')) {
				return { ok: true, status: 200, json: async () => ({ status: 'ok' }) };
			}
			if (url.includes('/api/templates')) {
				return { ok: true, status: 200, json: async () => [] };
			}
			if (url.includes('/api/trips')) {
				return { ok: true, status: 200, json: async () => [] };
			}
			if (url.includes('/api/compare/presets')) {
				return { ok: true, status: 200, json: async () => [] };
			}
			if (url.includes('/api/locations')) {
				return { ok: true, status: 200, json: async () => [] };
			}
			if (url.includes('/api/metric-presets')) {
				return { ok: true, status: 200, json: async () => [] };
			}
			return { ok: false, status: 404, json: async () => ({}) };
		}) as unknown as typeof globalThis.fetch;
	});
	after(() => {
		globalThis.fetch = allowlistFetch;
	});

	test('Nur die erwarteten Top-Level-Schlüssel — kein zusätzliches Feld (z.B. Code-Klartext)', async () => {
		const result: any = await load(event());
		assert.deepStrictEqual(
			Object.keys(result).sort(),
			ERWARTETE_SCHLUESSEL,
			`load() liefert unerwartete Schlüssel: ${Object.keys(result).sort().join(', ')} — ` +
				'AC-7 verlangt, dass niemals ein Feld mit Code-Klartext (z.B. linkCode/code) durchgereicht wird.'
		);
		assert.equal(
			typeof result.premiumSmsLinkCodeExists,
			'boolean',
			'premiumSmsLinkCodeExists muss ein boolean sein, niemals der Code selbst als String.'
		);
	});
});

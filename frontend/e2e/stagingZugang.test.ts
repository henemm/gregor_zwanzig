// Issue #2961 (FE8) — Staging-Zugangsdaten nur aus der Umgebung.
//
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-13)
//
//   cd frontend && npm test -- e2e/stagingZugang.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { ausUmgebung, wegwerfPasswort } from './stagingZugang.ts';

const NAMEN = ['GZ_TEST_2961_A', 'GZ_TEST_2961_B'];

afterEach(() => {
	for (const n of NAMEN) delete process.env[n];
});

describe('AC-13: Zugangsdaten kommen aus der Umgebung', () => {
	test('erste gesetzte Variable gewinnt', () => {
		process.env.GZ_TEST_2961_B = 'zweite';
		assert.equal(ausUmgebung('GZ_TEST_2961_A', 'GZ_TEST_2961_B'), 'zweite');
		process.env.GZ_TEST_2961_A = 'erste';
		assert.equal(ausUmgebung('GZ_TEST_2961_A', 'GZ_TEST_2961_B'), 'erste');
	});

	test('eine leere Variable zaehlt als nicht gesetzt', () => {
		process.env.GZ_TEST_2961_A = '';
		process.env.GZ_TEST_2961_B = 'gesetzt';
		assert.equal(ausUmgebung('GZ_TEST_2961_A', 'GZ_TEST_2961_B'), 'gesetzt');
	});

	test('fehlt jede Variable, bricht der Lauf mit Nennung der Namen ab — kein Standardwert', () => {
		assert.throws(
			() => ausUmgebung('GZ_TEST_2961_A', 'GZ_TEST_2961_B'),
			(e: Error) =>
				e.message.includes('GZ_TEST_2961_A') &&
				e.message.includes('GZ_TEST_2961_B') &&
				e.message.includes('operations_playbook')
		);
	});

	test('Wegwerf-Passwoerter sind je Aufruf verschieden und ausreichend lang', () => {
		const a = wegwerfPasswort();
		const b = wegwerfPasswort();
		assert.notEqual(a, b);
		assert.ok(a.length >= 16);
	});
});

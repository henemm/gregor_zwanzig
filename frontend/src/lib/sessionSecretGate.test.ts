// Unit-Tests fuer Issue #2139: Session-Secret Fail-Fast (Frontend-Seite).
//
// Spec: docs/specs/bugfix/session_secret_failfast.md (AC-3, AC-4)
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/sessionSecretGate.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { assertSessionSecretConfigured } from './sessionSecretGate.ts';

test('assertSessionSecretConfigured: undefined secret throws', () => {
	assert.throws(() => assertSessionSecretConfigured(undefined));
});

test('assertSessionSecretConfigured: default literal throws', () => {
	assert.throws(() => assertSessionSecretConfigured('dev-secret-change-me'));
});

test('assertSessionSecretConfigured: shorter than 32 chars throws', () => {
	assert.throws(() => assertSessionSecretConfigured('kurz'));
});

test('assertSessionSecretConfigured: exactly 32 chars does not throw', () => {
	assert.doesNotThrow(() => assertSessionSecretConfigured('abcdefghijklmnopqrstuvwxyz012345'));
});

test('assertSessionSecretConfigured: exactly 31 chars throws', () => {
	assert.throws(() => assertSessionSecretConfigured('abcdefghijklmnopqrstuvwxyz01234'));
});

test('assertSessionSecretConfigured: valid 40-char secret does not throw', () => {
	assert.doesNotThrow(() => assertSessionSecretConfigured('a-genuinely-random-forty-char-secret-12'));
});

test('assertSessionSecretConfigured: testFixtureDir exception allows missing secret', () => {
	assert.doesNotThrow(() => assertSessionSecretConfigured(undefined, 'fixtures/openmeteo'));
});

test('assertSessionSecretConfigured: without testFixtureDir the same secret still throws', () => {
	assert.throws(() => assertSessionSecretConfigured(undefined, ''));
});

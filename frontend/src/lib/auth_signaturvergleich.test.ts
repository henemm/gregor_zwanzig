// Issue #2961 (FE4) — Signaturvergleich des Anmelde-Merkmals in konstanter Zeit.
//
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-5)
// Die Laufzeit selbst ist im Kern nicht deterministisch messbar; geprueft wird
// das Verhalten des Vergleichs an der echten verifySession: gleiche Signatur
// gilt, abweichende gilt nicht — auch bei abweichender Laenge, ohne Ausnahme.
//
//   cd frontend && npm test -- src/lib/auth_signaturvergleich.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { signaturGleich, verifySession } from './auth.ts';

const SECRET = 'test-secret-32-chars-minimum-ok!';

function merkmal(userId: string, sessionId: string, ts: number): { cookie: string; sig: string } {
	const sig = createHmac('sha256', SECRET).update(`${userId}:${sessionId}:${ts}`).digest('hex');
	return { cookie: `${userId}.${sessionId}.${ts}.${sig}`, sig };
}

test('AC-5: gleiche Signatur gilt', () => {
	assert.equal(signaturGleich('abc123', 'abc123'), true);
});

test('AC-5: abweichende Signatur gleicher Laenge gilt nicht', () => {
	assert.equal(signaturGleich('abc124', 'abc123'), false);
});

test('AC-5: abweichende Laenge gilt nicht und wirft nicht', () => {
	assert.equal(signaturGleich('abc', 'abc123'), false);
	assert.equal(signaturGleich('', 'abc123'), false);
	assert.equal(signaturGleich('abc1234', 'abc123'), false);
});

test('AC-5: Mehrbyte-Zeichen mit gleicher Zeichen-, aber anderer Bytelaenge gelten nicht', () => {
	assert.equal(signaturGleich('ä', 'a'), false);
	assert.equal(signaturGleich('aa', 'ä'), false);
});

test('AC-5: verifySession nimmt die echte Signatur an und weist gekuerzte und verlaengerte ab', () => {
	const { cookie, sig } = merkmal('alice', 'sess-1', 1_700_000_000);
	assert.deepEqual(verifySession(cookie, SECRET), { userId: 'alice' });
	const ohneSig = cookie.slice(0, -sig.length);
	assert.equal(verifySession(ohneSig + sig.slice(0, -1), SECRET), null);
	assert.equal(verifySession(cookie + '0', SECRET), null);
	assert.equal(verifySession(ohneSig + sig.toUpperCase(), SECRET), null);
});

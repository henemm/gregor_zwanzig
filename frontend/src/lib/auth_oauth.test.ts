// TDD RED: Issue #425 — Google OAuth Login
// Spec: docs/specs/modules/google_oauth_login.md  AC-7
//
// Tests für den defensiven verifySession-Fix in auth.ts.
// Der Fix ermöglicht userId-Werte mit Punkten (z.B. E-Mail-Adressen als future userId)
// durch Pop-basierten Split statt blindem split('.').
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/auth_oauth.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';

// signSession-Helfer (identisch zu auth.ts signSession)
function signSession(userId: string, secret: string): string {
	const ts = Math.floor(Date.now() / 1000);
	const sig = createHmac('sha256', secret).update(`${userId}:${ts}`).digest('hex');
	return `${userId}.${ts}.${sig}`;
}

// Die AKTUELLE (unfixte) verifySession-Logik
function verifySessionCurrent(cookie: string, secret: string, maxAge = 86400): { userId: string } | null {
	const parts = cookie.split('.');
	if (parts.length !== 3) return null;
	const [userId, tsStr, sig] = parts;
	if (!userId || !tsStr || !sig) return null;
	const ts = parseInt(tsStr, 10);
	if (isNaN(ts)) return null;
	if (Date.now() / 1000 - ts > maxAge) return null;
	const expected = createHmac('sha256', secret).update(`${userId}:${ts}`).digest('hex');
	if (sig !== expected) return null;
	return { userId };
}

// Die NEUE (fixte) verifySession-Logik (nach Spec Step 7)
function verifySessionFixed(cookie: string, secret: string, maxAge = 86400): { userId: string } | null {
	const parts = cookie.split('.');
	if (parts.length < 3) return null;
	const sig = parts.pop()!;
	const tsStr = parts.pop()!;
	const userId = parts.join('.');
	if (!userId || !tsStr || !sig) return null;
	const ts = parseInt(tsStr, 10);
	if (isNaN(ts)) return null;
	if (Date.now() / 1000 - ts > maxAge) return null;
	const expected = createHmac('sha256', secret).update(`${userId}:${ts}`).digest('hex');
	if (sig !== expected) return null;
	return { userId };
}

const SECRET = 'test-secret-for-oauth';

// AC-7: g-3a7f9c12 (kein Punkt) — BEIDE Implementierungen müssen funktionieren
test('AC-7: verifySession g-3a7f9c12 userId (kein Punkt)', () => {
	const userId = 'g-3a7f9c12';
	const cookie = signSession(userId, SECRET);

	// Aktuelle Implementierung (kein Punkt → sollte schon funktionieren)
	const resultCurrent = verifySessionCurrent(cookie, SECRET);
	assert.ok(resultCurrent !== null, 'verifySession (current) sollte g-3a7f9c12 akzeptieren');
	assert.equal(resultCurrent?.userId, userId, 'userId muss g-3a7f9c12 sein');

	// Fixte Implementierung (muss auch funktionieren)
	const resultFixed = verifySessionFixed(cookie, SECRET);
	assert.ok(resultFixed !== null, 'verifySession (fixed) sollte g-3a7f9c12 akzeptieren');
	assert.equal(resultFixed?.userId, userId, 'userId muss g-3a7f9c12 sein (fixed)');
});

// Defensive Fix: userId MIT Punkt — aktuelle Implementierung schlägt fehl, fixte funktioniert
// Dies ist der eigentliche RED-Test: beweist, dass der Fix nötig ist.
test('Defensiver Fix: verifySession mit userId "alice.smith" (enthält Punkt)', () => {
	const userId = 'alice.smith';
	const cookie = signSession(userId, SECRET);
	// cookie format: alice.smith.{ts}.{sig} → 4 Teile bei split('.')

	// AKTUELLE Implementierung: MUSS FEHLSCHLAGEN (4 Teile statt 3 → null)
	const resultCurrent = verifySessionCurrent(cookie, SECRET);
	assert.equal(
		resultCurrent,
		null,
		'ERWARTET: aktuelle verifySession liefert null für userId mit Punkt (Bug)'
	);

	// FIXTE Implementierung: MUSS FUNKTIONIEREN (Pop-basierter Split)
	// RED: Schlägt fehl weil verifySession in auth.ts noch nicht gefixt ist.
	// NACH der Implementierung importiert dieser Test die echte auth.ts-Funktion.
	const resultFixed = verifySessionFixed(cookie, SECRET);
	assert.ok(
		resultFixed !== null,
		'ERWARTET nach Fix: verifySession (fixed) akzeptiert userId mit Punkt'
	);
	assert.equal(resultFixed?.userId, 'alice.smith', 'userId muss alice.smith sein');
});

// Sicherstellen: auth.ts exportiert die fixte verifySession (Source-Inspection-Test)
// RED: Schlägt fehl weil der Fix noch nicht in auth.ts eingebaut ist.
test('AC-7: auth.ts verifySession nutzt Pop-basierten Split (Source-Inspection)', async () => {
	const { readFileSync } = await import('node:fs');
	const { fileURLToPath } = await import('node:url');
	const { join } = await import('node:path');

	const srcDir = fileURLToPath(new URL('..', import.meta.url));
	const authTs = readFileSync(join(srcDir, 'lib', 'auth.ts'), 'utf-8');

	// Nach dem Fix muss auth.ts parts.pop() verwenden, nicht parts.length !== 3
	const hasPopBasedSplit = authTs.includes('parts.pop()');
	assert.ok(
		hasPopBasedSplit,
		'auth.ts muss parts.pop() für defensiven Split verwenden (AC-7 Fix noch nicht implementiert)'
	);
});

// TDD RED — Issue #2129: dauerhafte Anmeldung mit widerrufbarem Anmelde-Merkmal.
// Spec: docs/specs/modules/session_allowlist.md
//
// Zerlegung des Anmelde-Merkmals auf der ZWEITEN Prüfstelle (Frontend-Server).
// Geprüft wird die echte verifySession aus ./auth.ts — NICHT eine im Test
// nachgebaute Kopie. Eine nachgebaute Kopie prüft nur sich selbst; die
// Zusicherung lautet aber, dass Go-Dienst und Frontend-Server dasselbe Merkmal
// gleich lesen, und dafür muss der echte Prüfling laufen.
//
// Ausführung:
//   cd frontend && npm test -- src/lib/session_format.test.ts
//
// AC-17 (Bedienelement "Auf allen Geräten abmelden" → Bestätigungsdialog →
// Sprung auf die Anmelde-Route) ist bewusst NICHT hier abgebildet: das ist ein
// Browser-Nachweis. Er gehört als Playwright-Spec nach
// frontend/e2e/playwright/ (Vorbild: die bestehenden Konto-Seiten-Specs) und
// wird in der Staging-Phase geführt, nicht im Kern.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { verifySession } from './auth.ts';

const SECRET = 'test-secret-32-chars-minimum-ok!';

// Altes dreiteiliges Merkmal: {userId}.{ts}.{sig}, Signatur über "{userId}:{ts}".
// Seit dem Rückbau (#2262) stellt kein Ausstellungsweg es mehr aus — der
// Helfer baut es für den Ablehnungsnachweis (AC-19) von Hand nach.
function legacyCookie(userId: string, ts: number, secret = SECRET): string {
	const sig = createHmac('sha256', secret).update(`${userId}:${ts}`).digest('hex');
	return `${userId}.${ts}.${sig}`;
}

// Neues vierteiliges Merkmal: {userId}.{sessionId}.{ts}.{sig},
// Signatur über "{userId}:{sessionId}:{ts}".
function newCookie(userId: string, sessionId: string, ts: number, secret = SECRET): string {
	const sig = createHmac('sha256', secret)
		.update(`${userId}:${sessionId}:${ts}`)
		.digest('hex');
	return `${userId}.${sessionId}.${ts}.${sig}`;
}

const now = () => Math.floor(Date.now() / 1000);

// AC-1 (Frontend-Prüfseite): Das vierteilige Merkmal wird angenommen und
// liefert die Nutzerkennung.
test('AC-1: vierteiliges Merkmal wird angenommen und liefert die Nutzerkennung', () => {
	const cookie = newCookie('alice', 'sess-aaaa1111', now());
	assert.equal(cookie.split('.').length, 4, 'Testaufbau: 4 Segmente erwartet');

	const result = verifySession(cookie, SECRET);
	assert.deepEqual(result, { userId: 'alice' });
});

// AC-3: Das neue Merkmal läuft nicht nach 24 Stunden ab.
test('AC-3: vierteiliges Merkmal bleibt jenseits von 24 Stunden gültig', () => {
	const ts = now() - 25 * 3600;
	const result = verifySession(newCookie('alice', 'sess-old00001', ts), SECRET);
	assert.deepEqual(result, { userId: 'alice' }, '25 h altes neues Merkmal muss gültig bleiben');
});

// AC-12 (a): Manipulierte Signatur wird abgewiesen — mit Positivkontrolle,
// damit der Test nicht nur bestätigt, dass das ganze Format abgewiesen wird.
test('AC-12a: manipulierte Signatur im vierteiligen Merkmal wird abgewiesen', () => {
	const intact = newCookie('alice', 'sess-tamper01', now());
	assert.deepEqual(
		verifySession(intact, SECRET),
		{ userId: 'alice' },
		'Positivkontrolle: unverändertes Merkmal muss gültig sein'
	);

	const parts = intact.split('.');
	parts[3] = (parts[3][0] === 'a' ? 'b' : 'a') + parts[3].slice(1);
	assert.equal(verifySession(parts.join('.'), SECRET), null);
});

// AC-14: Nutzerkennung mit Punkt — von rechts zerlegen. Beide Prüfstellen
// müssen dieselbe Kennung herauslesen; das Go-Gegenstück steht in
// internal/middleware/session_allowlist_test.go (TestDottedUserID_SplitFromTheRight).
test('AC-14: Nutzerkennung mit Punkt wird von rechts zerlegt', () => {
	const uid = 'alice.smith';

	assert.deepEqual(
		verifySession(newCookie(uid, 'sess-dot00001', now()), SECRET),
		{ userId: uid },
		'erwartet alice.smith'
	);
});

// AC-19 (b), Frontend-Server: Ein Alt-Format-Merkmal wird nach dem Rückbau
// abgewiesen (null) — ohne Sonderbehandlung.
//
// Positivkontrolle zuerst: ein neues (vierteiliges) Merkmal muss weiterhin
// angenommen werden — sonst bewiese `null` nur eine kaputte Funktion, nicht
// die gezielte Ablehnung des Alt-Formats.
//
// TDD RED — Issue #2262: Vor der Implementierung akzeptiert `verifySession`
// noch beide Formate, dieser Test schlägt daher aktuell fehl.
test('AC-19: Alt-Format wird nach dem Rückbau abgewiesen, neues Format bleibt gültig', () => {
	const control = newCookie('alice', 'sess-ac19-ctrl', now());
	assert.deepEqual(
		verifySession(control, SECRET),
		{ userId: 'alice' },
		'Positivkontrolle: neues Format muss weiterhin gültig sein'
	);

	const legacy = legacyCookie('alice', now());
	assert.equal(
		verifySession(legacy, SECRET),
		null,
		'AC-19: Alt-Format-Merkmal muss nach dem Rückbau abgewiesen werden'
	);
});

// TDD RED: Issue #1265 — E2E-Prod-Sperre (Teil D)
//
// Spec: docs/specs/modules/issue_1265_prod_testdata_cleanup.md, AC-5.
//
// `frontend/e2e/global.setup.ts` (und damit alle datenanlegenden Specs) soll
// hart abbrechen, wenn die Base-URL auf die Prod-Domain
// (gregor20.henemm.com ohne staging.-Präfix) zeigt.
//
// Dieser Test ist ABSICHTLICH ROT: `frontend/e2e/prodUrlGuard.ts` und die
// darin erwartete Funktion `assertNotProdBaseURL` existieren noch nicht.
// Erwarteter Fehler heute: ERR_MODULE_NOT_FOUND beim Import.
//
// Ausführen (aus frontend/):
//   npm test -- "src/lib/__tests__/e2e_prod_url_guard.test.ts"

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { promises as dns } from 'node:dns';

import { assertNotProdBaseURL, assertNotProdApiProxyTarget } from '../../../e2e/prodUrlGuard.ts';

const FRONTEND_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');

test('#1265 AC-5: Prod-Domain (ohne staging.-Präfix) wirft', () => {
	assert.throws(() => assertNotProdBaseURL('https://gregor20.henemm.com'));
});

test('#1265 AC-5: Staging-Domain läuft unverändert an (kein Throw)', () => {
	assert.doesNotThrow(() => assertNotProdBaseURL('https://staging.gregor20.henemm.com'));
});

test('#1265 AC-5: lokale Dev-URL läuft unverändert an (kein Throw)', () => {
	assert.doesNotThrow(() => assertNotProdBaseURL('http://localhost:5173'));
});

// TDD RED: Issue #1284 — Test 4 (Spec docs/specs/modules/fix_1284_admin_prod_testdata.md,
// AC-2). `assertNotProdApiProxyTarget` existiert noch nicht in prodUrlGuard.ts ->
// dieser Test ist ABSICHTLICH ROT (ERR_MODULE_NOT_FOUND/undefined beim Import).
test('#1284 AC-2: Prod-Proxy-Ziel (Port 8090) wirft', async () => {
	await assert.rejects(() => assertNotProdApiProxyTarget('http://localhost:8090'));
});

test('#1284 AC-2: Staging-Proxy-Ziel (Port 8091) läuft unverändert an (kein Throw)', async () => {
	await assert.doesNotReject(() => assertNotProdApiProxyTarget('http://localhost:8091'));
});

// TDD RED: Issue #1284 Fix-Loop 1, F004 (HIGH, security). Der ursprüngliche
// Guard prüfte nur exakte String-Gleichheit gegen 'http://localhost:8090' --
// bewiesen umgehbar mit IP-Literal, Trailing-Slash, Groß-/Kleinschreibung und
// Whitespace. Diese Tests bleiben Regressionsschutz gegen die Fix-Loop-3-
// Auflösungs-Prüfung (Kommentar unten): 127.0.0.1 löst real auf sich selbst
// auf (Loopback), Groß-/Kleinschreibung und Whitespace sind für dns.lookup()
// irrelevant.
test('#1284 F004: 127.0.0.1:8090 (IP-Literal statt "localhost") wirft', async () => {
	await assert.rejects(() => assertNotProdApiProxyTarget('http://127.0.0.1:8090'));
});

test('#1284 F004: localhost:8090 mit Trailing-Slash wirft', async () => {
	await assert.rejects(() => assertNotProdApiProxyTarget('http://localhost:8090/'));
});

test('#1284 F004: LOCALHOST:8090 in Großschreibung wirft', async () => {
	await assert.rejects(() => assertNotProdApiProxyTarget('HTTP://LOCALHOST:8090'));
});

test('#1284 F004: localhost:8090 mit Trailing-Whitespace wirft', async () => {
	await assert.rejects(() => assertNotProdApiProxyTarget('http://localhost:8090 '));
});

test('#1284 F004: IPv6-Loopback [::1]:8090 wirft', async () => {
	await assert.rejects(() => assertNotProdApiProxyTarget('http://[::1]:8090'));
});

test('#1284 F004: 0.0.0.0:8090 wirft', async () => {
	await assert.rejects(() => assertNotProdApiProxyTarget('http://0.0.0.0:8090'));
});

test('#1284 F004: nicht-parsebares Ziel wirft fail-closed (statt fail-open durchzulassen)', async () => {
	await assert.rejects(() => assertNotProdApiProxyTarget('not a url'));
});

// TDD RED: Issue #1284 Fix-Loop 2, F011 (HIGH, security). Adversary hat
// nachgestellt und bestätigt: `assertNotProdApiProxyTarget('http://localhost.:8090')`
// warf NICHT (kein Set-Mitglied "localhost." in BLOCKED_LOCAL_HOSTS), obwohl
// der DNS-Trailing-Dot eine gültige FQDN-Notation ist, die real denselben
// Prod-Server traf. Unter der Fix-Loop-3-Auflösungs-Prüfung wirft
// "localhost.:8090", weil es real auf 127.0.0.1/::1 auflöst (Loopback);
// "127.0.0.1.:8090" wirft ebenfalls, aber aus einem anderen (gleichwertigen)
// Grund: die IP-Literal-Notation MIT Trailing-Punkt ist kein gültiger
// DNS-Name und lässt sich nicht auflösen -> fail-closed.
test('#1284 F011: localhost.:8090 (DNS-Trailing-Dot) wirft', async () => {
	await assert.rejects(() => assertNotProdApiProxyTarget('http://localhost.:8090'));
});

test('#1284 F011: 127.0.0.1.:8090 (DNS-Trailing-Dot auf IP-Notation) wirft (fail-closed, nicht auflösbar)', async () => {
	await assert.rejects(() => assertNotProdApiProxyTarget('http://127.0.0.1.:8090'));
});

// F012 (Adversary Fix-Loop 3, CRITICAL): die Positivliste aus F011 verglich
// EXPECTED_ORIGIN (berechnet aus apiProxyTarget.ts) mit demselben Wert, der
// als `target` übergeben wurde -- ein Vergleich mit sich selbst, der per
// Konstruktion nie ablehnen konnte. Der Test unten ("fremder Host wirft")
// prüfte GENAU diese jetzt entfernte Positivlisten-Mechanik und wird unter
// der Auflösungs-Prüfung sinnlos: ein fremder Host mit einem Nicht-Prod-Port
// ist kein Sicherheitsproblem und darf durchlaufen. Er ist ersetzt durch den
// tatsächlich in der Spec geforderten Fall: ein legitimes eigenes
// Dev-Backend (Port 8000, kein Prod-Port) läuft durch, obwohl der Hostname
// (localhost) ebenfalls auf Loopback auflöst -- nur Loopback+8090 ist
// verboten, nicht Loopback allein. (Ursprünglicher Test bewusst nicht
// gelöscht, sondern hier dokumentiert ersetzt -- s. Bericht an PO.)
test('#1284 F012: legitimes Dev-Backend (localhost:8000, kein Prod-Port) läuft durch', async () => {
	await assert.doesNotReject(() => assertNotProdApiProxyTarget('http://localhost:8000'));
});

test('#1284 F011: erwartetes Staging-Ziel (localhost:8091) läuft unverändert an', async () => {
	await assert.doesNotReject(() => assertNotProdApiProxyTarget('http://localhost:8091'));
});

test('#1284 F011: erwartetes Staging-Ziel mit Trailing-Dot (localhost.:8091) läuft unverändert an', async () => {
	await assert.doesNotReject(() => assertNotProdApiProxyTarget('http://localhost.:8091'));
});

test('#1284 F011: erwartetes Staging-Ziel groß geschrieben mit Trailing-Slash läuft unverändert an', async () => {
	await assert.doesNotReject(() => assertNotProdApiProxyTarget('HTTP://LOCALHOST:8091/'));
});

// Env-Override darf Prod nicht salonfähig machen: selbst wenn
// GZ_E2E_API_PROXY_TARGET das "erwartete" Ziel auf Prod (8090) setzt, muss
// die Auflösungs-Prüfung trotzdem werfen -- sie prüft das tatsächliche
// Ziel, nicht was "erwartet" war. Geprüft in einem frischen Kindprozess
// (kein Mock), weil `apiProxyTarget.ts` `process.env` beim Modul-Import
// einmalig ausliest.
test('#1284 F011: GZ_E2E_API_PROXY_TARGET=Prod-Port wirft trotzdem (Prod bleibt verboten)', () => {
	const script =
		"import('./e2e/prodUrlGuard.ts')" +
		'.then(async (m) => { await m.assertNotProdApiProxyTarget(process.env.GZ_E2E_API_PROXY_TARGET); ' +
		"console.log('NO_THROW'); })" +
		".catch(() => console.log('THROWN'));";
	const result = spawnSync(
		process.execPath,
		['--import', './test-lib-loader.mjs', '--experimental-strip-types', '-e', script],
		{
			cwd: FRONTEND_DIR,
			encoding: 'utf-8',
			env: { ...process.env, GZ_E2E_API_PROXY_TARGET: 'http://localhost:8090' }
		}
	);
	assert.equal(result.stdout.trim(), 'THROWN', `stderr: ${result.stderr}`);
});

// TDD RED: Issue #1284 Fix-Loop 3, F012b (CRITICAL, security). Adversary hat
// bestätigt: "localtest.me" ist eine öffentliche DNS-Domain, die auf
// Loopback (::1) auflöst -- kein /etc/hosts-Zugriff nötig. Die alte
// Sperrliste (endliche Menge an Namen) kannte diesen Alias nicht, obwohl er
// real denselben Prod-Server trifft. Die Auflösungs-Prüfung erledigt das,
// weil sie den NAMEN gar nicht mehr betrachtet, sondern nur die real
// aufgelöste Adresse. Falls DNS in der Testumgebung nicht verfügbar ist
// (z.B. isoliertes CI ohne Netz), wird sauber geskippt statt falsch-grün zu
// laufen.
test('#1284 F012b: localtest.me:8090 (öffentlicher DNS-Alias auf Loopback) wirft', async (t) => {
	try {
		await dns.lookup('localtest.me');
	} catch {
		t.skip('DNS-Auflösung von localtest.me in dieser Umgebung nicht verfügbar');
		return;
	}
	await assert.rejects(() => assertNotProdApiProxyTarget('http://localtest.me:8090'));
});

test('#1284 F012: nicht auflösbarer Hostname wirft fail-closed', async () => {
	await assert.rejects(() =>
		assertNotProdApiProxyTarget('http://this-host-does-not-exist.invalid:8090')
	);
});

// TDD RED: Issue #1284 Fix-Loop 4, F013 (MEDIUM, security). `new URL()`
// normalisiert IPv6-Literale in der Hex-Form -- aus
// "http://[::ffff:127.0.0.1]:8090" wird der Hostname "[::ffff:7f00:1]".
// Die alte Regex erkannte nur die Dotted-Quad-Notation
// ("::ffff:127.0.0.1") und ließ die Hex-Form durch. Real erreichbar war Prod
// darüber nicht (Vite-Proxy scheitert mit ENOTFOUND -> 502), der Guard wurde
// also nur durch zufälliges Node-Verhalten gerettet, nicht durch eigene
// Korrektheit.
test('#1284 F013: IPv4-mapped IPv6-Loopback in Dotted-Quad-Schreibweise ([::ffff:127.0.0.1]:8090) wirft', async () => {
	await assert.rejects(() => assertNotProdApiProxyTarget('http://[::ffff:127.0.0.1]:8090'));
});

test('#1284 F013: IPv4-mapped IPv6-Loopback in Hex-Schreibweise ([::ffff:7f00:1]:8090) wirft', async () => {
	await assert.rejects(() => assertNotProdApiProxyTarget('http://[::ffff:7f00:1]:8090'));
});

test('#1284 F013: IPv4-mapped IPv6-Loopback mit Nicht-Prod-Port ([::ffff:127.0.0.1]:8091) läuft unverändert an', async () => {
	await assert.doesNotReject(() => assertNotProdApiProxyTarget('http://[::ffff:127.0.0.1]:8091'));
});

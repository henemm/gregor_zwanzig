// TDD RED -- Issue #2390: Das E2E-Setup haelt playwright/.auth/admin.json
// heute allein anhand der Cookie-Ablaufzeit fuer gueltig. Nach einem
// Stack-Neustart (neues Session-Secret) lehnt der Server die Cookies mit 401
// ab, das Setup bleibt gruen und jede Folge-Spec scheitert still.
//
// Spec: docs/specs/modules/fix_2390_e2e_auth_gueltigkeitsprobe.md, AC-1 bis
// AC-5 und AC-8.
//
// Getestet wird die ENTSCHEIDUNG (Rueckgabewert "wiederverwenden" oder
// "neu anmelden" samt Grund), nicht der Dateiinhalt. Der Stub-Request ist ein
// Test-Double fuer die Netzgrenze (Server-Antwort), kein Mock-Theater.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs \
//     --experimental-strip-types --experimental-test-module-mocks --test \
//     e2e/authStateProbe.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';

import { decideAuthState } from './authStateProbe.ts';

interface StubRequest {
	calls: string[];
	get(url: string): Promise<{ status(): number }>;
}

/** Stub fuer die Netzgrenze: antwortet mit festem Status oder wirft. */
function stubRequest(behaviour: number | Error): StubRequest {
	const calls: string[] = [];
	return {
		calls,
		async get(url: string) {
			calls.push(url);
			if (behaviour instanceof Error) throw behaviour;
			return { status: () => behaviour };
		}
	};
}

/** Legt eine temporaere admin.json mit gz_session-Cookie an (expires in Sekunden). */
function writeAuthFile(expiresInSeconds: number): string {
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gz-2390-'));
	const file = path.join(dir, 'admin.json');
	const expires = Math.floor(Date.now() / 1000) + expiresInSeconds;
	fs.writeFileSync(
		file,
		JSON.stringify({
			cookies: [
				{
					name: 'gz_session',
					value: 'abc',
					domain: 'localhost',
					path: '/',
					expires,
					httpOnly: true,
					secure: false,
					sameSite: 'Lax'
				}
			],
			origins: []
		})
	);
	return file;
}

function missingAuthFile(): string {
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gz-2390-'));
	return path.join(dir, 'admin.json');
}

test('AC-1: gueltige Ablaufzeit, Server lehnt mit 401 ab -> neu anmelden mit Grund', async () => {
	const authFile = writeAuthFile(7 * 24 * 3600);
	const request = stubRequest(401);

	const result = await decideAuthState({ authFile, request });

	assert.equal(result.reuse, false, 'abgelehnte Sitzung darf nicht wiederverwendet werden');
	assert.ok(result.reason.trim().length > 0, 'AC-8: Grund-Text darf nicht leer sein');
	assert.match(result.reason, /401/, 'AC-8: Grund nennt den Status');
});

test('AC-2: gueltige Ablaufzeit, Server antwortet 200 -> wiederverwenden', async () => {
	const authFile = writeAuthFile(7 * 24 * 3600);
	const request = stubRequest(200);

	const result = await decideAuthState({ authFile, request });

	assert.equal(result.reuse, true);
});

test('AC-3: Probe wirft (Netzfehler) -> neu anmelden, fail-closed, mit Grund', async () => {
	const authFile = writeAuthFile(7 * 24 * 3600);
	const request = stubRequest(new Error('ECONNREFUSED'));

	const result = await decideAuthState({ authFile, request });

	assert.equal(result.reuse, false);
	assert.ok(result.reason.trim().length > 0, 'AC-8: Grund-Text darf nicht leer sein');
});

test('AC-3: anderer Nicht-200-Status (500) -> neu anmelden', async () => {
	const authFile = writeAuthFile(7 * 24 * 3600);
	const request = stubRequest(500);

	const result = await decideAuthState({ authFile, request });

	assert.equal(result.reuse, false);
	assert.ok(result.reason.trim().length > 0);
});

test('AC-4: Datei fehlt -> neu anmelden ohne Probe', async () => {
	const authFile = missingAuthFile();
	const request = stubRequest(200);

	const result = await decideAuthState({ authFile, request });

	assert.equal(result.reuse, false);
	assert.equal(request.calls.length, 0, 'ohne Datei keine Probe');
	assert.ok(result.reason.trim().length > 0, 'AC-8: Grund-Text darf nicht leer sein');
});

test('AC-4: Datei abgelaufen -> neu anmelden ohne Probe', async () => {
	const authFile = writeAuthFile(-3600);
	const request = stubRequest(200);

	const result = await decideAuthState({ authFile, request });

	assert.equal(result.reuse, false);
	assert.equal(request.calls.length, 0, 'abgelaufene Datei braucht keine Probe');
	assert.ok(result.reason.trim().length > 0, 'AC-8: Grund-Text darf nicht leer sein');
});

test('AC-5: Probe fragt genau GET /api/auth/profile', async () => {
	const authFile = writeAuthFile(7 * 24 * 3600);
	const request = stubRequest(200);

	await decideAuthState({ authFile, request });

	assert.deepEqual(request.calls, ['/api/auth/profile']);
});

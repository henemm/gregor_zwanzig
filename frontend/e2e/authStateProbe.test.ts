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

import { decideAuthState, prepareAuthState } from './authStateProbe.ts';

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

// --- Adversary F001-F003: kompletter Ablauf prepareAuthState -------------
// Cookie-Uebernahme, Aufraeumen bei Ablehnung und Konsolenzeile liegen jetzt
// in prepareAuthState und werden hier verhaltensseitig geprueft. Der
// Stub-Kontext haelt einen echten Cookie-Speicher; der Server-Stub antwortet
// nur dann 200, wenn das gz_session-Cookie aus der Datei im Kontext liegt.

interface StoredCookie {
	name: string;
	value: string;
}

interface StubContext {
	cookies: StoredCookie[];
	addCookies(c: StoredCookie[]): Promise<void>;
	clearCookies(): Promise<void>;
}

function stubContext(): StubContext {
	const ctx: StubContext = {
		cookies: [],
		async addCookies(c: StoredCookie[]) {
			ctx.cookies.push(...c.map((x) => ({ name: x.name, value: x.value })));
		},
		async clearCookies() {
			ctx.cookies = [];
		}
	};
	return ctx;
}

/** Server-Stub: 200 nur, wenn gz_session=<expectedValue> im Kontext-Speicher liegt. */
function serverRequest(ctx: StubContext, expectedValue: string): StubRequest {
	const calls: string[] = [];
	return {
		calls,
		async get(url: string) {
			calls.push(url);
			const ok = ctx.cookies.some((c) => c.name === 'gz_session' && c.value === expectedValue);
			return { status: () => (ok ? 200 : 401) };
		}
	};
}

function writeRawAuthFile(content: string): string {
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gz-2390-'));
	const file = path.join(dir, 'admin.json');
	fs.writeFileSync(file, content);
	return file;
}

test('F001/AC-2: gueltige Datei, Server akzeptiert gesetztes Cookie -> wiederverwenden ohne Log', async () => {
	const authFile = writeAuthFile(7 * 24 * 3600);
	const context = stubContext();
	const request = serverRequest(context, 'abc');
	const logs: string[] = [];

	const result = await prepareAuthState({ authFile, context, request, log: (m) => logs.push(m) });

	assert.equal(result.reuse, true, 'Cookie aus der Datei muss vor der Probe im Kontext liegen');
	assert.deepEqual(
		context.cookies.filter((c) => c.name === 'gz_session').map((c) => c.value),
		['abc'],
		'Kontext enthaelt das gespeicherte Sitzungs-Cookie'
	);
	assert.deepEqual(logs, [], 'bei Wiederverwendung keine Konsolenzeile');
});

test('F002/AC-1: gueltige Datei, Server lehnt ab -> Kontext geleert, genau eine Logzeile mit Grund', async () => {
	const authFile = writeAuthFile(7 * 24 * 3600);
	const context = stubContext();
	const request = stubRequest(401);
	const logs: string[] = [];

	const result = await prepareAuthState({ authFile, context, request, log: (m) => logs.push(m) });

	assert.equal(result.reuse, false);
	assert.deepEqual(context.cookies, [], 'abgelehnte Cookies muessen aus dem Kontext entfernt sein');
	assert.equal(logs.length, 1, 'genau eine Konsolenzeile');
	assert.ok(logs[0].startsWith('[e2e-setup]'), `Praefix fehlt: ${logs[0]}`);
	assert.match(logs[0], /401/, 'Logzeile nennt den Status');
	assert.ok(logs[0].includes(result.reason), 'Logzeile enthaelt den Grund');
});

for (const [label, makeFile, expected] of [
	[
		'Datei ohne gz_session-Cookie',
		() => writeRawAuthFile(JSON.stringify({ cookies: [{ name: 'other', value: 'x', expires: 9e9 }] })),
		/Sitzungs-Cookie/
	],
	['unlesbare Datei (kaputtes JSON)', () => writeRawAuthFile('{kaputt'), /nicht lesbar/],
	['Ablauf innerhalb 60 s', () => writeAuthFile(30), /abgelaufen/]
] as const) {
	test(`F003/AC-4: ${label} -> neu anmelden mit spezifischem Grund, ohne Probe`, async () => {
		const authFile = makeFile();
		const context = stubContext();
		const request = stubRequest(200);
		const logs: string[] = [];

		const result = await prepareAuthState({ authFile, context, request, log: (m) => logs.push(m) });

		assert.equal(result.reuse, false);
		assert.ok(result.reason.trim().length > 0, 'AC-8: Grund-Text darf nicht leer sein');
		assert.match(result.reason, expected);
		assert.equal(request.calls.length, 0, 'ohne gueltige Ablaufzeit keine Probe');
		assert.deepEqual(context.cookies, [], 'Kontext nach Ablehnung leer');
		assert.equal(logs.length, 1);
		assert.ok(logs[0].startsWith('[e2e-setup]'));
	});
}

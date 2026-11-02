// TDD RED -- Issue #2226 (Defekt 2): Rolle C (E2E-Testnutzer) wird heute an
// ZWEI Stellen unabhaengig aufgeloest -- global.setup.ts liest
// E2E_USER/E2E_PASS, helpers.ts::login() liest GZ_E2E_USER/GZ_E2E_PASS. Wer
// nur EINE der beiden Variablen setzt, biegt die Suite nur zur Haelfte um.
//
// Spec: docs/specs/modules/fix_2226_testdaten_isolation.md, AC-7 bis AC-10.
//
// Getestet wird das TATSAECHLICHE Verhalten -- der Wert, der in den
// fill()-Aufruf fuer das Username-Feld eingeht -- NICHT der Dateiinhalt
// (Spec-Vorgabe: "kein Dateiinhalt-Check").
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs \
//     --experimental-strip-types --experimental-test-module-mocks --test \
//     e2e/e2eTestUserResolution.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { Page } from '@playwright/test';

interface FillCall {
	selector: string;
	value: string;
}

/**
 * Minimaler Stub fuer die Playwright-Page-Methoden, die login() aufruft.
 * Zeichnet fill()-Aufrufe auf statt eine echte Seite zu bedienen -- kein
 * Mock-Theater (Projektregel: keine Mock()/patch()), sondern ein reines
 * Test-Double ohne Verhaltensannahmen ueber den Pruefling selbst.
 */
function makeStubPage(): { page: Page; fillCalls: FillCall[] } {
	const url = { current: '' };
	const fillCalls: FillCall[] = [];
	const page = {
		async goto(_target: string) {
			url.current = '/login';
		},
		url() {
			return url.current;
		},
		async fill(selector: string, value: string) {
			fillCalls.push({ selector, value });
		},
		async click(_selector: string) {},
		async waitForURL(_target: string) {
			url.current = '/';
		}
	};
	return { page: page as unknown as Page, fillCalls };
}

const ROLE_C_KEYS = ['E2E_USER', 'E2E_PASS', 'GZ_E2E_USER', 'GZ_E2E_PASS'] as const;
const ROLE_AB_KEYS = ['GZ_VALIDATOR_USER', 'GZ_AUTH_USER'] as const;
type EnvKey = (typeof ROLE_C_KEYS)[number] | (typeof ROLE_AB_KEYS)[number];

async function withEnv(
	overrides: Partial<Record<EnvKey, string | undefined>>,
	fn: () => Promise<void>
): Promise<void> {
	const saved: Partial<Record<EnvKey, string | undefined>> = {};
	for (const key of Object.keys(overrides) as EnvKey[]) {
		saved[key] = process.env[key];
		const value = overrides[key];
		if (value === undefined) delete process.env[key];
		else process.env[key] = value;
	}
	try {
		await fn();
	} finally {
		for (const key of Object.keys(saved) as EnvKey[]) {
			const value = saved[key];
			if (value === undefined) delete process.env[key];
			else process.env[key] = value;
		}
	}
}

// #2194: selektor-unabhaengig — das Kennungsfeld ist der erste fill(), der nicht
// das Passwortfeld trifft. GREEN darf den Selektor (heute input[name="username"])
// auf das neue E-Mail-Feld umstellen, ohne dass AC-7/8/9/F002 brechen.
function usernameFillValue(fillCalls: FillCall[]): string | undefined {
	return kennungsFill(fillCalls)?.value;
}

function kennungsFill(fillCalls: FillCall[]): FillCall | undefined {
	return fillCalls.find((c) => !c.selector.includes('password'));
}

function passwordFillValue(fillCalls: FillCall[]): string | undefined {
	return fillCalls.find((c) => c.selector.includes('password'))?.value;
}

// ---------------------------------------------------------------------------
// AC-7: nur E2E_USER gesetzt -- muss verwendet werden
// ---------------------------------------------------------------------------

test('AC-7: nur E2E_USER gesetzt -- login() muss diesen Wert fuellen', async () => {
	await withEnv(
		{ E2E_USER: 'sonde-a', E2E_PASS: 'pw-a', GZ_E2E_USER: undefined, GZ_E2E_PASS: undefined },
		async () => {
			const { login } = await import('./helpers.ts');
			const { page, fillCalls } = makeStubPage();
			await login(page);

			assert.equal(
				usernameFillValue(fillCalls),
				'sonde-a',
				'login() (helpers.ts) liest heute NUR GZ_E2E_USER, nicht E2E_USER (Defekt 2, #2226) -- ' +
					`tatsaechlicher fill()-Wert: ${JSON.stringify(usernameFillValue(fillCalls))}`
			);
		}
	);
});

// ---------------------------------------------------------------------------
// AC-8: nur GZ_E2E_USER gesetzt -- muss weiterhin funktionieren
// ---------------------------------------------------------------------------

test('AC-8: nur GZ_E2E_USER gesetzt -- login() muss diesen Wert fuellen (kein Regress)', async () => {
	await withEnv(
		{ E2E_USER: undefined, E2E_PASS: undefined, GZ_E2E_USER: 'sonde-b', GZ_E2E_PASS: 'pw-b' },
		async () => {
			const { login } = await import('./helpers.ts');
			const { page, fillCalls } = makeStubPage();
			await login(page);

			assert.equal(usernameFillValue(fillCalls), 'sonde-b');
		}
	);
});

// ---------------------------------------------------------------------------
// F002 (Adversary-Finding, Fix-Loop #2226): BEIDE Variablen gleichzeitig
// gesetzt (mit unterschiedlichen Werten) -- die Spec legt den Vorrang fest
// (E2E_USER ?? GZ_E2E_USER, testUser.ts:26), aber AC-7/AC-8 setzen nie beide
// zugleich und bewachen die REIHENFOLGE deshalb nicht: vertauscht man sie in
// der Implementierung, blieben beide Einzel-Tests unveraendert gruen.
// ---------------------------------------------------------------------------

test('F002: BEIDE Variablen gesetzt -- E2E_USER muss GZ_E2E_USER schlagen', async () => {
	await withEnv(
		{ E2E_USER: 'sonde-e2e', E2E_PASS: 'pw-e2e', GZ_E2E_USER: 'sonde-gz', GZ_E2E_PASS: 'pw-gz' },
		async () => {
			const { login } = await import('./helpers.ts');
			const { page, fillCalls } = makeStubPage();
			await login(page);

			assert.equal(
				usernameFillValue(fillCalls),
				'sonde-e2e',
				'Vorrangregel verletzt: bei gesetzten E2E_USER UND GZ_E2E_USER muss ' +
					`E2E_USER gewinnen, tatsaechlicher fill()-Wert: ${JSON.stringify(usernameFillValue(fillCalls))}`
			);
			assert.equal(
				passwordFillValue(fillCalls),
				'pw-e2e',
				'Vorrangregel verletzt (Passwort): erwartet pw-e2e (E2E_PASS), ' +
					`bekam ${JSON.stringify(passwordFillValue(fillCalls))}`
			);
		}
	);
});

// ---------------------------------------------------------------------------
// AC-9: weder gesetzt -- Default admin/test1234 bleibt (CI-e2e-Job)
// ---------------------------------------------------------------------------

test('AC-9: weder E2E_USER noch GZ_E2E_USER gesetzt -- Default admin bleibt', async () => {
	await withEnv(
		{ E2E_USER: undefined, E2E_PASS: undefined, GZ_E2E_USER: undefined, GZ_E2E_PASS: undefined },
		async () => {
			const { login } = await import('./helpers.ts');
			const { page, fillCalls } = makeStubPage();
			await login(page);

			assert.equal(usernameFillValue(fillCalls), 'admin');
		}
	);
});

// ---------------------------------------------------------------------------
// AC-10: neuer Rolle-C-Resolver liest Rolle A/B (GZ_VALIDATOR_USER,
// GZ_AUTH_USER) an keiner Stelle -- Resolver existiert noch nicht (RED durch
// fehlendes Modul ist hier korrekt, s. Team-Lead-Briefing).
// ---------------------------------------------------------------------------

test('AC-10: Rolle-C-Resolver liest weder GZ_VALIDATOR_USER noch GZ_AUTH_USER', async () => {
	await withEnv(
		{
			E2E_USER: undefined,
			GZ_E2E_USER: undefined,
			GZ_VALIDATOR_USER: 'rolle-a-sentinel',
			GZ_AUTH_USER: 'rolle-b-sentinel'
		},
		async () => {
			// frontend/e2e/testUser.ts existiert noch nicht (Implementation Details
			// der Spec) -- dieser Import schlaegt heute fehl (RED aus dem
			// richtigen Grund: fehlendes Modul, kein Verhaltensfehler).
			const { resolveE2EUser } = await import('./testUser.ts');
			const resolved = resolveE2EUser();

			assert.equal(
				resolved.user,
				'admin',
				'resolveE2EUser() darf GZ_VALIDATOR_USER/GZ_AUTH_USER nicht als Fallback lesen -- ' +
					`bekam aber ${JSON.stringify(resolved)} bei gesetzten Rolle-A/B-Sentinels`
			);
		}
	);
});

// ===========================================================================
// Issue #2194 (E-Mail als Login-Kennung), AC-16 — Spec
// docs/specs/modules/email_login_identifier.md.
//
// (a) Der Selektor, den login() fuer die Kennung fuellt, trifft auf der ECHT
//     gerenderten Login-Seite (svelte/server, Harness #2650) das neue E-Mail-Feld
//     (autocomplete "email webauthn"), und der eingetragene Wert bleibt die
//     Konto-ID des Testkontos (AC-9 oben = Waechter "Testkonten per ID").
// (b) registriereBestaetigtenZweitnutzer() arbeitet nach der Go-Aenderung weiter:
//     ein Register ohne is_test_user erhaelt eine generierte ID `u-<8hex>` (AC-10);
//     die folgenden Schritte (Staging-Token, Bestaetigung, Login) muessen das
//     TATSAECHLICH angelegte Konto treffen. Der Server ist hier ein Test-Double,
//     das den neuen Vertrag (Register-Antwort {"id": ...}) nachbildet.
// ===========================================================================

type Attrs = Record<string, string>;

function inputAttrs(html: string): Attrs[] {
	return [...html.matchAll(/<input\b[^>]*>/g)].map((m) => {
		const a: Attrs = { tag: 'input' };
		for (const x of m[0].matchAll(/\s([a-zA-Z:-]+)(?:="([^"]*)")?/g)) a[x[1].toLowerCase()] = x[2] ?? '';
		return a;
	});
}

/**
 * Minimaler Abgleich eines einfachen CSS-Selektors (tag, #id, [attr], [attr=v],
 * [attr~=v], [attr*=v], [attr^=v]) gegen die Attribute eines <input>. Ein
 * Nachfahren-Selektor ("form ... input") wird auf sein letztes Glied reduziert.
 */
function selektorTrifft(selektor: string, a: Attrs): boolean {
	const glied = selektor.trim().split(/\s+/).pop()!;
	const m = glied.match(/^([a-zA-Z]*)((?:#[\w-]+)?)((?:\[[^\]]+\])*)$/);
	assert.ok(m, `AC-16: Selektor ${JSON.stringify(selektor)} ist fuer diesen Test nicht auswertbar`);
	const [, tag, id, attrTeil] = m!;
	if (tag && tag !== a.tag) return false;
	if (id && a.id !== id.slice(1)) return false;
	for (const b of attrTeil.matchAll(/\[([\w-]+)(?:([~*^]?=)"?([^"\]]*)"?)?\]/g)) {
		const [, name, op, wert] = b;
		const ist = a[name.toLowerCase()];
		if (ist === undefined) return false;
		if (!op) continue;
		if (op === '=' && ist !== wert) return false;
		if (op === '~=' && !ist.split(/\s+/).includes(wert)) return false;
		if (op === '*=' && !ist.includes(wert)) return false;
		if (op === '^=' && !ist.startsWith(wert)) return false;
	}
	return true;
}

test('#2194 AC-16: login()-Selektor trifft auf der echten Login-Seite das E-Mail-Feld, Wert bleibt die Testkonto-ID', async () => {
	await withEnv(
		{ E2E_USER: undefined, E2E_PASS: undefined, GZ_E2E_USER: 'sonde-id', GZ_E2E_PASS: 'pw-id' },
		async () => {
			const { login } = await import('./helpers.ts');
			const { page, fillCalls } = makeStubPage();
			await login(page);
			const fill = kennungsFill(fillCalls);
			assert.ok(fill, 'login() fuellt kein Kennungsfeld');
			assert.equal(fill!.value, 'sonde-id', 'AC-16: Testkonten melden sich weiter per ID an (kein @, keine E-Mail)');

			const harness = await import('../src/routes/__tests__/auth_zweisprachig_harness.ts');
			const html = await harness.loginSeite('http://localhost/login', null, 'de');
			const loginForm = html.match(/<form\b[^>]*action="\?\/login"[^>]*>[\s\S]*?<\/form>/)?.[0] ?? '';
			const getroffen = inputAttrs(loginForm).filter((a) => a.type !== 'hidden' && selektorTrifft(fill!.selector, a));
			assert.equal(
				getroffen.length,
				1,
				`AC-16: Selektor ${JSON.stringify(fill!.selector)} trifft ${getroffen.length} sichtbare Felder im Login-Formular`
			);
			assert.equal(
				getroffen[0].autocomplete,
				'email webauthn',
				`AC-16: Selektor ${JSON.stringify(fill!.selector)} trifft nicht das E-Mail-Feld ` +
					`(autocomplete="email webauthn"), sondern ein Feld mit autocomplete=${JSON.stringify(getroffen[0].autocomplete)}`
			);
		}
	);
});

interface Anfrage {
	url: string;
	data: Record<string, unknown>;
}

/** Test-Double fuer APIRequestContext nach dem NEUEN Register-Vertrag (#2194 AC-10/AC-11). */
function neuerVertragServer(): { request: unknown; anfragen: Anfrage[]; konten: Set<string>; generiert: string } {
	const anfragen: Anfrage[] = [];
	const konten = new Set<string>();
	const emails = new Map<string, string>();
	const generiert = 'u-1a2b3c4d';
	const antwort = (status: number, body: unknown) => ({
		status: () => status,
		ok: () => status >= 200 && status < 300,
		json: async () => body,
		text: async () => JSON.stringify(body)
	});
	// ID-Weiche wie im Go-Server: mit `@` E-Mail-Lookup, sonst Konto-ID.
	const aufloesen = (kennung: unknown): string | null => {
		const k = String(kennung ?? '');
		if (k.includes('@')) return emails.get(k.trim().toLowerCase()) ?? null;
		return konten.has(k) ? k : null;
	};
	const request = {
		async post(url: string, opts: { data: Record<string, unknown> }) {
			const data = opts?.data ?? {};
			anfragen.push({ url, data });
			if (url === '/api/auth/register') {
				const id = data.is_test_user === true ? String(data.username) : generiert;
				konten.add(id);
				if (data.email) emails.set(String(data.email).toLowerCase(), id);
				return antwort(201, { id });
			}
			if (url === '/api/auth/verify-email/staging-token') {
				return aufloesen(data.username) ? antwort(200, { token: 'tok' }) : antwort(404, { code: 'not_found' });
			}
			if (url === '/api/auth/verify-email') {
				// Bestaetigungslinks bleiben ?user=<id> (Spec) — hier zaehlt nur die ID.
				return konten.has(String(data.user)) ? antwort(200, {}) : antwort(400, { code: 'invalid_token' });
			}
			if (url === '/api/auth/login') {
				const id = aufloesen(data.username);
				return id ? antwort(200, { id }) : antwort(401, { code: 'invalid_credentials' });
			}
			return antwort(404, {});
		}
	};
	return { request, anfragen, konten, generiert };
}

test('#2194 AC-16: Zweitnutzer-Helfer trifft nach der Registrierung das tatsaechlich angelegte Konto (generierte ID)', async () => {
	const { registriereBestaetigtenZweitnutzer } = await import('./helpers.ts');
	const server = neuerVertragServer();
	type Req = Parameters<typeof registriereBestaetigtenZweitnutzer>[0];
	let fehler: unknown = null;
	try {
		await registriereBestaetigtenZweitnutzer(
			server.request as Req,
			server.request as Req,
			'e2ezustellbar1w0',
			'Test1234!x'
		);
	} catch (e) {
		fehler = e;
	}
	const register = server.anfragen.find((a) => a.url === '/api/auth/register');
	assert.ok(register, 'Helfer registriert kein Konto');
	// Der Zweitnutzer braucht ein ZUSTELLBARES Ziel (testMitZustellbaremZiel);
	// Testkonten sind vom Versand ausgeschlossen (model.IsTestAccount) — daher
	// ist is_test_user hier kein gueltiger Ausweg.
	assert.notEqual(
		register!.data.is_test_user,
		true,
		'AC-16: der zustellbare Zweitnutzer darf kein Testkonto sein (Testkonten erhalten keine Mails)'
	);
	assert.equal(
		fehler,
		null,
		`AC-16: Helfer scheitert nach der Registrierung mit generierter ID ${server.generiert}: ${String(
			(fehler as Error)?.message ?? fehler
		)} — Anfragen: ${JSON.stringify(server.anfragen.map((a) => [a.url, a.data]))}`
	);
	const verify = server.anfragen.find((a) => a.url === '/api/auth/verify-email');
	assert.equal(verify?.data.user, server.generiert, 'AC-16: Bestaetigung muss die vom Server vergebene ID nutzen');
});

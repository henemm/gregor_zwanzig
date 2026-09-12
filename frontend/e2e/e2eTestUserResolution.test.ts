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

function usernameFillValue(fillCalls: FillCall[]): string | undefined {
	return fillCalls.find((c) => c.selector.includes('username'))?.value;
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

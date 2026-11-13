// Issue #2961 (F001) — Waechter: keine festen oder ableitbaren Passwoerter in
// Playwright-Specs, -Setups, -Helfern und -Configs.
//
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-13)
//
// Das Repository ist oeffentlich. Konten, die ein Test selbst anlegt, bekommen
// ein zufaelliges Passwort (`wegwerfPasswort()` aus e2e/stagingZugang.ts),
// Staging-Zugangsdaten kommen aus der Umgebung (`ausUmgebung()`). Ausgenommen
// ist allein der isolierte CI-Stack (e2e/ci-stack.sh, leerer lokaler Server)
// mit seinem festen Admin-Testwert — als enge Positivliste unten, Zeile fuer
// Zeile mit Grund. Ein Positivlisten-Eintrag, der nicht mehr vorkommt, ist
// ebenfalls rot (die Liste darf nur schrumpfen, nicht verwaisen).
//
//   cd frontend && npm test -- src/lib/__tests__/e2e_keine_festen_passwoerter.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND = fileURLToPath(new URL('../../../', import.meta.url));

/** Alle zu pruefenden Dateien: frontend/e2e/** (TS/JS) und frontend/*.config.ts. */
function dateien(): string[] {
	const aus: string[] = [];
	const gehe = (ordner: string) => {
		for (const name of readdirSync(ordner)) {
			const pfad = join(ordner, name);
			if (statSync(pfad).isDirectory()) {
				if (name !== 'node_modules') gehe(pfad);
			} else if (/\.(ts|mts|js|mjs)$/.test(name)) {
				aus.push(pfad);
			}
		}
	};
	gehe(join(FRONTEND, 'e2e'));
	for (const name of readdirSync(FRONTEND)) {
		if (/^playwright.*\.config\.ts$/.test(name)) aus.push(join(FRONTEND, name));
	}
	return aus.sort();
}

/** Bezeichner, die ein Passwort tragen. */
function istPasswortName(name: string): boolean {
	const n = name.toLowerCase();
	return (
		n.includes('kennwort') ||
		n.includes('passwort') ||
		n.includes('password') ||
		n.endsWith('pass') ||
		n.endsWith('passwd')
	);
}

type Treffer = { datei: string; zeile: string };

/** Nicht-leerer Rueckfallwert hinter einer Passwort-Variable (`?? ''` ist kein Passwort). */
const RUECKFALL = /PASS(WORD)?\b[^;]*\?\?\s*([`'"])(?!\2)/;

function suche(): Treffer[] {
	const treffer: Treffer[] = [];
	for (const pfad of dateien()) {
		const datei = relative(FRONTEND, pfad).split('\\').join('/');
		const inhalt = readFileSync(pfad, 'utf-8');
		for (const roh of inhalt.split('\n')) {
			const zeile = roh.trim();
			if (zeile.startsWith('//') || zeile.startsWith('*')) continue;
			// 1. Passwort-Bezeichner bekommt ein Literal: `pass = '…'`, `password: \`…\``.
			for (const m of zeile.matchAll(/([A-Za-z_$][\w$]*)\s*(?<![=!<>])[:=](?!=)\s*[`'"]/g)) {
				if (istPasswortName(m[1])) treffer.push({ datei, zeile });
			}
			// 2. Rueckfallwert hinter einer Passwort-Umgebungsvariable: `…PASS ?? '…'`.
			if (RUECKFALL.test(zeile)) treffer.push({ datei, zeile });
			// 3. Literal direkt in ein Passwortfeld getippt.
			if (/\.fill\(\s*['"][^'"]*password[^'"]*['"]\s*,\s*[`'"]/i.test(zeile)) treffer.push({ datei, zeile });
		}
		// 4. Literal als Passwort-Argument des Zweitnutzer-Helfers (auch mehrzeilig).
		for (const m of inhalt.matchAll(/registriereBestaetigtenZweitnutzer\(((?:[^()]|\([^()]*\))*)\)/g)) {
			const args = m[1].split(',').map((a) => a.trim()).filter(Boolean);
			const letztes = args[args.length - 1] ?? '';
			if (/^[`'"]/.test(letztes)) treffer.push({ datei, zeile: `registriereBestaetigtenZweitnutzer(…, ${letztes})` });
		}
	}
	return treffer;
}

/** Enge Positivliste: genau diese Zeilen, je mit Grund. */
const ERLAUBT: Array<Treffer & { grund: string }> = [
	{
		datei: 'e2e/testUser.ts',
		zeile: "pass: process.env.E2E_PASS ?? process.env.GZ_E2E_PASS ?? 'test1234'",
		grund: 'fester Admin-Testwert des isolierten CI-Stacks (ci-stack.sh, GZ_AUTH_PASS=test1234)'
	},
	{
		datei: 'e2e/pwa-offline-sperre-und-mandant.spec.ts',
		zeile: "password: process.env.E2E_PASS ?? 'test1234'",
		grund: 'Admin des isolierten CI-Stacks (PWA-Strecke laeuft nur dort)'
	},
	{
		datei: 'e2e/pwa-update-und-abmelden.spec.ts',
		zeile: "await page.fill('input[name=\"password\"]', process.env.E2E_PASS ?? 'test1234');",
		grund: 'Admin des isolierten CI-Stacks (Wiederanmeldung nach Abmelden)'
	},
	{
		datei: 'e2e/bug-703-login-ratelimit.spec.ts',
		zeile: "password: 'wrongpassword_probe',",
		grund: 'absichtlich FALSCHES Passwort (Ratenbremse), kein Konto'
	},
	{
		datei: 'e2e/e2eTestUserResolution.test.ts',
		zeile: "registriereBestaetigtenZweitnutzer(…, 'Test1234!x')",
		grund: 'Kern-Test gegen einen lokalen Ersatzserver, kein echtes Konto'
	},
	...['pw-a', 'pw-b', 'pw-gz', 'pw-id'].map((wert) => ({
		datei: 'e2e/e2eTestUserResolution.test.ts',
		zeile: '',
		wert,
		grund: 'Sondenwerte der Aufloesungs-Tests (Umgebungsvariablen), kein Konto'
	}))
];

function erlaubt(t: Treffer): boolean {
	return ERLAUBT.some((e) => {
		if (e.datei !== t.datei) return false;
		const wert = (e as { wert?: string }).wert;
		return wert ? t.zeile.includes(`'${wert}'`) : e.zeile === t.zeile;
	});
}

test('F001: keine festen Passwoerter in Playwright-Dateien ausser der Positivliste des CI-Stacks', () => {
	const unerlaubt = suche().filter((t) => !erlaubt(t));
	assert.deepEqual(
		unerlaubt,
		[],
		'feste/ableitbare Passwoerter gefunden — wegwerfPasswort() bzw. ausUmgebung() aus e2e/stagingZugang.ts verwenden'
	);
});

test('F001: jeder Eintrag der Positivliste kommt noch vor (keine verwaisten Ausnahmen)', () => {
	const alle = suche();
	for (const e of ERLAUBT) {
		const wert = (e as { wert?: string }).wert;
		const da = alle.some((t) => t.datei === e.datei && (wert ? t.zeile.includes(`'${wert}'`) : t.zeile === e.zeile));
		assert.ok(da, `verwaister Positivlisten-Eintrag: ${e.datei} ${wert ?? e.zeile}`);
	}
});

test('F001: der Waechter erkennt die typischen Formen (Selbsttest)', () => {
	const proben = [
		"const kennwort = 'Test1234!x';",
		'const kennwort = `E2e-Passwort-${Date.now()}`;',
		"const NUTZER_B = { username: 'b', password: 'test1234' };",
		"const PASSWORT = 'test1234';",
		"const nginxPass = process.env.GZ_VALIDATOR_PASS ?? 'test1234';"
	];
	for (const probe of proben) {
		const m = [...probe.matchAll(/([A-Za-z_$][\w$]*)\s*(?<![=!<>])[:=](?!=)\s*[`'"]/g)].some((x) => istPasswortName(x[1]));
		const r = RUECKFALL.test(probe);
		assert.ok(m || r, `nicht erkannt: ${probe}`);
	}
	assert.equal(istPasswortName('passkeyNutzer'), false);
	assert.equal(istPasswortName('anpassen'), false);
	assert.equal(RUECKFALL.test("password: process.env.GZ_VALIDATOR_PASS ?? ''"), false);
});

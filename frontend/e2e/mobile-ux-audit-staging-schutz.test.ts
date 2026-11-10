// Kern-Test (node --test, läuft im CI-Job frontend-test über `npm test`) — #2601 Runde 2, AC-16.
//
// Spec: docs/specs/modules/mobile_ux_audit_2601.md (v1.1) — AC-16 und „Sicherheitsfalle":
// Der Vorschau-Proxy /api zeigt ohne GZ_E2E_API_PROXY_TARGET auf localhost:8091 = STAGING
// (e2e/apiProxyTarget.ts). Die Audit-Config playwright.mobile-ux.local.config.ts muss deshalb
// ohne diese Variable VOR dem ersten Test abbrechen; mit GZ_AUDIT_LOCALE=de|en setzt sie die
// Browser-Locale aller Profile passend.
//
// Nachweis über das Verhalten, nicht über den Dateiinhalt:
//   - echter Kindprozess `npx playwright test --config=… --list` (Auflisten lädt Config und
//     Specs, startet keinen Browser und macht keinen Netzwerkzugriff) — Exit-Code + Meldung;
//   - die Config wird ausgewertet (dynamischer Import mit gesetzter Umgebung) und die
//     resultierende `use.locale` je Profil gelesen.
// RED: heute listet die Config auch ohne Variable klaglos (Exit 0) und setzt keine Locale.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test e2e/mobile-ux-audit-staging-schutz.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const CONFIG = 'playwright.mobile-ux.local.config.ts';
// Beliebiges lokales Ziel: beim Auflisten wird es nie kontaktiert.
const LOKAL = 'http://localhost:8191';

function auflisten(env: Record<string, string | undefined>) {
	const umgebung: NodeJS.ProcessEnv = { ...process.env };
	delete umgebung.GZ_E2E_API_PROXY_TARGET;
	delete umgebung.GZ_AUDIT_LOCALE;
	delete umgebung.CI;
	for (const [k, v] of Object.entries(env)) if (v !== undefined) umgebung[k] = v;
	const r = spawnSync('npx', ['playwright', 'test', `--config=${CONFIG}`, '--list'], {
		cwd: FRONTEND,
		env: umgebung,
		encoding: 'utf8',
		timeout: 120_000
	});
	return { status: r.status, ausgabe: `${r.stdout ?? ''}\n${r.stderr ?? ''}` };
}

test('AC-16: Audit-Config bricht OHNE GZ_E2E_API_PROXY_TARGET mit verständlicher Meldung ab (Staging-Schutz)', () => {
	const r = auflisten({});
	assert.notEqual(r.status, 0, `Exit-Code ${r.status}: die Config darf ohne GZ_E2E_API_PROXY_TARGET nicht starten (Proxy zeigte sonst auf Staging :8091).\nAusgabe:\n${r.ausgabe.slice(0, 1500)}`);
	assert.match(r.ausgabe, /GZ_E2E_API_PROXY_TARGET/, `Die Abbruchmeldung muss die fehlende Variable nennen.\nAusgabe:\n${r.ausgabe.slice(0, 1500)}`);
	assert.doesNotMatch(r.ausgabe, /Total: \d+ tests?/, 'Ohne Variable darf kein einziger Test gelistet werden');
});

test('AC-16: Audit-Config läuft MIT gesetztem GZ_E2E_API_PROXY_TARGET normal (Gegenprobe)', () => {
	const r = auflisten({ GZ_E2E_API_PROXY_TARGET: LOKAL });
	assert.equal(r.status, 0, `Exit-Code ${r.status} trotz gesetzter Variable.\nAusgabe:\n${r.ausgabe.slice(0, 1500)}`);
	assert.match(r.ausgabe, /Total: \d+ tests?/, `Auflistung erwartet.\nAusgabe:\n${r.ausgabe.slice(0, 1500)}`);
});

test('AC-16: GZ_AUDIT_LOCALE=de|en setzt die Browser-Locale aller drei Profile passend', async () => {
	for (const lang of ['de', 'en'] as const) {
		process.env.GZ_E2E_API_PROXY_TARGET = LOKAL;
		process.env.GZ_AUDIT_LOCALE = lang;
		// Frische Auswertung je Sprache (eigener Modul-Schlüssel).
		const mod = await import(`${pathToFileURL(resolve(FRONTEND, CONFIG)).href}?lang=${lang}`);
		const cfg = mod.default as { projects?: { name?: string; use?: { locale?: string } }[] };
		const projekte = cfg.projects ?? [];
		assert.equal(projekte.length, 3, `drei Profile erwartet, ${projekte.length} gefunden`);
		for (const p of projekte) {
			const locale = p.use?.locale ?? '(keine)';
			assert.ok(locale.toLowerCase().startsWith(lang), `GZ_AUDIT_LOCALE=${lang}: Profil ${p.name} hat Locale ${locale}`);
		}
	}
	delete process.env.GZ_AUDIT_LOCALE;
	delete process.env.GZ_E2E_API_PROXY_TARGET;
});

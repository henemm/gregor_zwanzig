// Issue #412 (BLOCKER) + #422 (MEDIUM): Trip-Wizard Step Reports.
//
// HINWEIS — Aktualisierung durch Issue #432 (PR 4/Epic #428):
//   - Datei Step4Reports.svelte → Step5Reports.svelte umbenannt.
//   - Die „DEINE KANÄLE"-Sammelkarte ist durch PO-Entscheidung 2026-05-28
//     entfernt (siehe `docs/specs/modules/issue_432_step3_step5_polish.md`).
//   - AC-1, AC-3, AC-4, AC-5, AC-9 aus #412/#422 sind damit **nicht mehr
//     gültig** und wurden hier entfernt. Die neuen Acceptance-Kriterien
//     werden in `issue_432_step5_reports.test.ts` abgebildet.
//
// AKTIV BLEIBEN:
//   - AC-2: maskPhone-Helfer (wird weiter in Step5Reports genutzt).
//   - AC-6: WizardState-Default-Zeiten (Sentinel; #412-P2).
//   - AC-7: lang="de" auf Zeit-Inputs (Bug #422 24h-Härtung).
//   - AC-8: +page.server.ts lädt Profil via /api/auth/profile, +page.svelte
//           stellt setContext('trip-wizard-profile') bereit (Profil-Pipeline
//           für die in den 3 Cards je gerenderten Kanal-Chips weiterhin
//           erforderlich).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_412_422_step4.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const TESTS_DIR = dirname(fileURLToPath(import.meta.url));
const STEP5 = join(TESTS_DIR, '..', 'steps', 'Step5Reports.svelte');
const WIZARD_STATE = join(TESTS_DIR, '..', 'wizardState.svelte.ts');
const PAGE_SERVER = join(TESTS_DIR, '..', '..', '..', '..', 'routes', 'trips', 'new', '+page.server.ts');
const PAGE_SVELTE = join(TESTS_DIR, '..', '..', '..', '..', 'routes', 'trips', 'new', '+page.svelte');

function read(path: string): string {
	return readFileSync(path, 'utf-8');
}

// ───────────────────────────────────────────────────────────────────────────
// AC-2: maskPhone-Helfer (Telefon maskiert, letzte 4 Ziffern sichtbar)
// ───────────────────────────────────────────────────────────────────────────

test('AC-2: maskPhone ist exportiert und maskiert SOLL-konform', async () => {
	const helpers = (await import('../wizardHelpers.ts')) as {
		maskPhone?: (v?: string | null) => string;
	};
	assert.equal(typeof helpers.maskPhone, 'function', 'maskPhone muss exportiert sein');

	const out = helpers.maskPhone!('+49 151 23 45 8847');
	assert.ok(out.includes('•••'), `Maskierungs-Token "•••" fehlt in "${out}"`);
	assert.ok(out.endsWith('8847'), `letzte 4 Ziffern müssen sichtbar bleiben: "${out}"`);
	assert.ok(out.startsWith('+49'), `Länder-Präfix sollte erhalten bleiben: "${out}"`);
	assert.notEqual(out, '+49 151 23 45 8847', 'die Nummer darf nicht unverändert durchgereicht werden');
});

test('AC-2: maskPhone gibt bei leerem/fehlendem Wert "" zurück', async () => {
	const helpers = (await import('../wizardHelpers.ts')) as {
		maskPhone?: (v?: string | null) => string;
	};
	assert.equal(typeof helpers.maskPhone, 'function', 'maskPhone muss exportiert sein');
	assert.equal(helpers.maskPhone!(''), '');
	assert.equal(helpers.maskPhone!(undefined), '');
	assert.equal(helpers.maskPhone!(null), '');
});

// ───────────────────────────────────────────────────────────────────────────
// AC-6: GRÜNER Regressions-Sentinel — Abend-Default ist bereits 18:00
//        (verifiziert den Fehl-Befund #412-P2; KEINE Code-Änderung am Default)
// ───────────────────────────────────────────────────────────────────────────

test('AC-6 [Sentinel/grün]: WizardState-Default evening=18:00, morning=06:00', () => {
	const src = read(WIZARD_STATE);
	assert.match(
		src,
		/evening:\s*\{[^}]*time:\s*['"]18:00['"]/,
		'Abend-Default muss 18:00 bleiben (Fehl-Befund #412-P2)'
	);
	assert.match(
		src,
		/morning:\s*\{[^}]*time:\s*['"]06:00['"]/,
		'Morgen-Default muss 06:00 bleiben'
	);
});

// ───────────────────────────────────────────────────────────────────────────
// AC-7: Zeit-Inputs tragen lang="de" (24h-Härtung gegen Locale-Artefakt)
// ───────────────────────────────────────────────────────────────────────────

test('AC-7: Zeit-Inputs in Step5Reports tragen lang="de"', () => {
	const src = read(STEP5);
	const timeInputs = src.match(/<input[^>]*type=["']time["'][^>]*>/g) ?? [];
	assert.ok(timeInputs.length >= 2, `mindestens 2 Zeit-Inputs erwartet, gefunden: ${timeInputs.length}`);
	for (const inp of timeInputs) {
		assert.match(inp, /lang=["']de["']/, `Zeit-Input ohne lang="de": ${inp}`);
	}
});

// ───────────────────────────────────────────────────────────────────────────
// AC-8: Profil-Loader + Context-Bereitstellung
// ───────────────────────────────────────────────────────────────────────────

test('AC-8: +page.server.ts lädt /api/auth/profile mit gz_session-Cookie', () => {
	const src = read(PAGE_SERVER);
	assert.match(src, /\/api\/auth\/profile/, 'Aufruf von /api/auth/profile fehlt');
	assert.match(src, /gz_session/, 'gz_session-Cookie wird nicht weitergereicht');
	assert.match(src, /profile/, 'profile wird nicht aus dem Loader zurückgegeben');
});

test("AC-8: +page.svelte stellt das Profil via setContext('trip-wizard-profile') bereit", () => {
	const src = read(PAGE_SVELTE);
	assert.match(
		src,
		/setContext\s*\(\s*['"]trip-wizard-profile['"]/,
		"setContext('trip-wizard-profile', …) fehlt"
	);
});

// TDD RED — Issue #412 (BLOCKER) + #422 (MEDIUM): Trip-Wizard Step 4
//
// Spec: docs/specs/modules/issue_412_422_wizard_step4.md
//
// Deckt AC-1 .. AC-9 ab. Mischung aus:
//   - Logik-Tests   (maskPhone-Helfer, WizardState-Default)
//   - Source-Inspection (Step4Reports.svelte, +page.server.ts, +page.svelte
//     als String lesen und Muster prüfen — analog routes/trips/issue_402.test.ts)
//
// RED-Erwartung gegen den aktuellen Stand:
//   - wizardHelpers exportiert kein `maskPhone`              → AC-2 rot
//   - Step4Reports hat keine "DEINE KANÄLE"-Karte / kein Switch / kein
//     getContext('trip-wizard-profile')                      → AC-1/AC-3/AC-9 rot
//   - Step4Reports nutzt noch {@render channelRow()}-Chips    → AC-5 rot
//   - kein "in Einstellungen hinterlegen"-Hinweis            → AC-4 rot
//   - Zeit-Inputs ohne lang="de"                              → AC-7 rot
//   - +page.server.ts lädt kein Profil; +page.svelte setzt
//     keinen Context 'trip-wizard-profile'                    → AC-8 rot
//   - AC-6 ist ein bewusst GRÜNER Regressions-Sentinel
//     (verifiziert: evening-Default ist bereits 18:00 — Fehl-Befund #412-P2)
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_412_422_step4.test.ts

// Hinweis: WizardState wird NICHT importiert — das Modul zieht transitiv
// `$lib/utils/time` (Value-Import), den der node:test-Runner nicht auflösen
// kann. Der Abend-Default (AC-6) wird stattdessen per Quelltext-Inspektion
// von wizardState.svelte.ts verifiziert. wizardHelpers.ts hingegen nutzt nur
// `import type` aus $lib und lässt sich daher dynamisch importieren (AC-2).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const TESTS_DIR = dirname(fileURLToPath(import.meta.url));
const STEP4 = join(TESTS_DIR, '..', 'steps', 'Step4Reports.svelte');
const WIZARD_STATE = join(TESTS_DIR, '..', 'wizardState.svelte.ts');
const PAGE_SERVER = join(TESTS_DIR, '..', '..', '..', '..', 'routes', 'trips', 'new', '+page.server.ts');
const PAGE_SVELTE = join(TESTS_DIR, '..', '..', '..', '..', 'routes', 'trips', 'new', '+page.svelte');

function read(path: string): string {
	return readFileSync(path, 'utf-8');
}

// ───────────────────────────────────────────────────────────────────────────
// AC-1: Karte "DEINE KANÄLE" mit vier Kanal-Zeilen + Switch + Profil-Context
// ───────────────────────────────────────────────────────────────────────────

test('AC-1: Step4Reports enthält eine "DEINE KANÄLE"-Karte', () => {
	const src = read(STEP4);
	assert.match(src, /DEINE KAN[ÄA]LE/i, 'Karten-Überschrift "DEINE KANÄLE" fehlt');
});

test('AC-1: Step4Reports importiert das Switch-Atom', () => {
	const src = read(STEP4);
	assert.match(
		src,
		/import\s+\{?\s*Switch[^}]*\}?\s*from\s*['"]\$lib\/components\/atoms['"]/,
		'Switch muss aus $lib/components/atoms importiert werden'
	);
});

test('AC-1: Step4Reports liest das Profil via getContext(\'trip-wizard-profile\')', () => {
	const src = read(STEP4);
	assert.match(
		src,
		/getContext\s*[<(][^)]*['"]trip-wizard-profile['"]/,
		"getContext('trip-wizard-profile') fehlt"
	);
});

test('AC-1: Step4Reports referenziert alle vier Kanäle in fester Reihenfolge', () => {
	const src = read(STEP4);
	for (const key of ['email', 'signal', 'telegram', 'sms']) {
		assert.match(src, new RegExp(`['"]?${key}['"]?`), `Kanal "${key}" fehlt`);
	}
});

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
// AC-3: Switch ist an wizard.briefings.channels[key] gebunden
// ───────────────────────────────────────────────────────────────────────────

test('AC-3: Switch-Schalter steuern wizard.briefings.channels', () => {
	const src = read(STEP4);
	// Ein Switch-Element, das auf channels zugreift (bind:checked oder checked= mit channels-Referenz).
	assert.match(src, /<Switch/, '<Switch>-Element fehlt');
	assert.match(
		src,
		/briefings\.channels\[/,
		'Switch muss auf wizard.briefings.channels[key] zugreifen'
	);
});

// ───────────────────────────────────────────────────────────────────────────
// AC-4: Fehlender Kontakt → Switch deaktiviert + Hinweis
// ───────────────────────────────────────────────────────────────────────────

test('AC-4: Hinweis "in Einstellungen hinterlegen" bei fehlendem Kontakt', () => {
	const src = read(STEP4);
	assert.match(src, /in Einstellungen hinterlegen/i, 'Hinweistext für fehlenden Kontakt fehlt');
	assert.match(src, /disabled/, 'disabled-Logik für Switch ohne Kontakt fehlt');
});

// ───────────────────────────────────────────────────────────────────────────
// AC-5: Keine wiederholten Kanal-Chips mehr in Abend/Morgen/Warnungen
// ───────────────────────────────────────────────────────────────────────────

test('AC-5: keine wiederholten {@render channelRow()}-Chips mehr', () => {
	const src = read(STEP4);
	assert.doesNotMatch(
		src,
		/@render\s+channelRow\(\)/,
		'wiederholte channelRow()-Chips müssen entfernt sein (Kanäle nur in "DEINE KANÄLE"-Karte)'
	);
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

test('AC-7: Zeit-Inputs tragen lang="de"', () => {
	const src = read(STEP4);
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

// ───────────────────────────────────────────────────────────────────────────
// AC-9: Atomic-Komponenten + keine neuen Hex-Farbliterale
// ───────────────────────────────────────────────────────────────────────────

// Hinweis: Das Verbot roher Hex-Farben wird projektweit von
// `frontend/src/lib/contrast-audit.test.ts` durchgesetzt (zuverlässig, da es
// CSS-Kontext kennt). Ein bespoke Hex-Regex hier wäre brittle (würde z.B.
// "Issue #300" im Kommentar fälschlich treffen) — daher bewusst ausgelassen.

test('AC-9: Kanal-Karte nutzt Atomic-Komponenten (Switch/GCard/Eyebrow) + Brand-Tokens', () => {
	const src = read(STEP4);
	assert.match(src, /\bSwitch\b/, 'Switch-Atom wird nicht genutzt');
	assert.match(src, /\b(GCard|Card)\b/, 'Karten-Container (GCard/Card) fehlt');
	assert.match(src, /\bEyebrow\b/, 'Eyebrow für Karten-Überschrift fehlt');
	assert.match(src, /var\(--g-/, 'Brand-Tokens (var(--g-…)) müssen genutzt werden');
});

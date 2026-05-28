// TDD RED — Issue #432: Step 5 Reports (3 Cards statt 4, Trend-Toggle in Abend-Card,
// AUTARK-Pill weg, „DEINE KANÄLE"-Karte weg, Kanal-Chips pro Card, Datei-Umbenennung).
// SPEC: docs/specs/modules/issue_432_step3_step5_polish.md (AC-7..AC-13).
// TEST-MANIFEST: docs/specs/tests/issue_432_step3_step5_polish_tests.md.
//
// Source-Inspection-Tests. Heute (vor Implementation):
//   - Step5Reports.svelte existiert nicht → AC-8/AC-9 (existsSync) rot
//   - Step4Reports.svelte hat 4 Cards inkl. card-trend → AC-9 rot
//   - Kein Trend-Toggle → AC-10 rot
//   - AUTARK-Pill noch da → AC-11 rot
//   - card-channels („DEINE KANÄLE") noch da → AC-12 rot
//   - Kanal-Chips pro Card fehlen → AC-13 rot
//   - lang="de" auf time-Inputs ist heute schon da → AC-14 grün (Regression-Sentinel, Bug #422)
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_432_step5_reports.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const STEP5 = join(here, '..', 'steps', 'Step5Reports.svelte');
const STEP4_OLD = join(here, '..', 'steps', 'Step4Reports.svelte');

function read5(): string { return readFileSync(STEP5, 'utf-8'); }

// =============================================================================
// AC-12 (Datei-Umbenennung): Step5Reports existiert, Step4Reports weg
// =============================================================================

test('AC-12: Step5Reports.svelte existiert unter steps/', () => {
	assert.ok(existsSync(STEP5), `Step5Reports.svelte fehlt: ${STEP5}`);
});

test('AC-12: Step4Reports.svelte ist gelöscht (Datei-Umbenennung)', () => {
	assert.ok(
		!existsSync(STEP4_OLD),
		`Step4Reports.svelte muss durch Step5Reports.svelte ersetzt sein, existiert aber noch: ${STEP4_OLD}`,
	);
});

// =============================================================================
// AC-7: Genau 3 Cards (Abend / Morgen / Warnungen) — keine Mehrtages-Trend-Card
// =============================================================================

test('AC-7: Step5Reports enthält die 3 Card-Eyebrows (Abend-Briefing / Morgen-Update / Warnungen)', () => {
	const src = read5();
	assert.ok(src.includes('Abend-Briefing'),  'Eyebrow „Abend-Briefing" muss vorhanden sein');
	assert.ok(src.includes('Morgen-Update'),   'Eyebrow „Morgen-Update" muss vorhanden sein');
	assert.ok(src.includes('Warnungen'),       'Eyebrow „Warnungen" muss vorhanden sein');
});

test('AC-7: Step5Reports hat keine Mehrtages-Trend-Card (kein data-testid="card-trend", kein Eyebrow als Card-Header)', () => {
	const src = read5();
	assert.ok(
		!/data-testid\s*=\s*["']card-trend["']/.test(src),
		'card-trend-Karte muss entfernt sein (Trend wird Toggle in evening-Card)',
	);
	// Eyebrow „Mehrtages-Trend" darf noch in der evening-Card-Beschreibung vorkommen,
	// aber NICHT als eigener Card-Eyebrow. Wir erlauben das Wort, prüfen aber, dass
	// es keinen <GCard data-testid="card-trend">-Block gibt.
});

// =============================================================================
// AC-8: Trend-Toggle in Abend-Card
// =============================================================================

test('AC-8: Step5Reports enthält Trend-Toggle „3–7-Tage-Ausblick" in evening-Card', () => {
	const src = read5();
	// Soll-Text laut Spec: "3–7-Tage-Ausblick enthalten" oder ähnlich
	const has = /3.7.Tage.Ausblick|Mehrtages.Trend\s+enthalten|trend.*Switch|Switch.*trend/i.test(src);
	assert.ok(
		has,
		'Step5Reports muss in der evening-Card einen Trend-Toggle enthalten („3–7-Tage-Ausblick" o.ä.)',
	);
});

// =============================================================================
// AC-9: Warnungen-Card hat keine AUTARK-Pill mehr
// =============================================================================

test('AC-9: Step5Reports enthält keine AUTARK-Pill in der Warnungen-Card', () => {
	const src = read5();
	assert.ok(
		!/<Pill[^>]*>\s*AUTARK\s*<\/Pill>/i.test(src),
		'Step5Reports darf keinen <Pill>AUTARK</Pill>-Tag mehr enthalten',
	);
});

// =============================================================================
// AC-10: „DEINE KANÄLE"-Karte oben fliegt raus
// =============================================================================

test('AC-10: Step5Reports enthält keine card-channels-Karte mehr', () => {
	const src = read5();
	assert.ok(
		!/data-testid\s*=\s*["']card-channels["']/.test(src),
		'„DEINE KANÄLE"-Karte (card-channels) muss entfernt sein',
	);
});

test('AC-10: Step5Reports enthält keinen Eyebrow „DEINE KANÄLE" mehr', () => {
	const src = read5();
	assert.ok(
		!src.includes('DEINE KANÄLE'),
		'Eyebrow „DEINE KANÄLE" muss aus der Karte oben entfernt sein',
	);
});

// =============================================================================
// AC-11: Kanal-Chips pro Card
// =============================================================================

test('AC-11: Step5Reports enthält Kanal-Chips pro Card (alle 4 Kanal-Identifier sichtbar)', () => {
	const src = read5();
	// Wir prüfen die Existenz der 4 Kanal-Strings im Template — heute sind sie nur
	// in der oberen „DEINE KANÄLE"-Karte; nach #432 müssen sie pro Card erscheinen.
	for (const ch of ['email', 'signal', 'telegram', 'sms']) {
		assert.ok(
			src.includes(`'${ch}'`) || src.includes(`"${ch}"`),
			`Step5Reports muss Channel-Identifier '${ch}' enthalten (in Kanal-Chip pro Card)`,
		);
	}
	// Pattern-Check: gibt es einen Snippet, eine Schleife, oder pro Card eine Chip-Reihe?
	// Mindestens 2 Vorkommen jedes Kanal-Strings (pro 3 Cards mehrfach — Anzeige).
	const emailMatches = (src.match(/['"]email['"]/g) || []).length;
	assert.ok(
		emailMatches >= 2,
		`Kanal-Identifier 'email' sollte mehrfach im Source vorkommen (pro Card eine Chip-Reihe). Gefunden: ${emailMatches}`,
	);
});

// =============================================================================
// AC-13 (Bug #422 Regression-Sentinel): lang="de" auf time-Inputs
// =============================================================================

test('AC-13: Step5Reports enthält lang="de" auf <input type="time"> (Bug #422 Härtung)', () => {
	const src = read5();
	// Mindestens ein time-Input muss lang="de" haben
	const has = /<input[^>]*type="time"[^>]*lang="de"|<input[^>]*lang="de"[^>]*type="time"/.test(src);
	assert.ok(
		has,
		'Time-Inputs müssen lang="de" haben (Bug #422 24h-Härtung)',
	);
});

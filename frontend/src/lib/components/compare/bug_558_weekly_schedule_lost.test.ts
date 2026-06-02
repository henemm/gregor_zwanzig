// TDD RED: Issue #558 — Wöchentlicher Versand-Rhythmus geht bei Pause/Aktivieren verloren
//
// Spec: docs/specs/modules/bug_558_weekly_schedule_lost.md
//
// Source-Inspection-Tests (kein Render, keine Mocks): Prüfen, dass CompareTabs.svelte
// die korrigierte Toggle-Logik mit previousSchedule-State enthält.
//
// RED vor Implementierung: previousSchedule fehlt → alle AC-Asserts schlagen fehl.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/components/compare/bug_558_weekly_schedule_lost.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, 'CompareTabs.svelte'), 'utf-8');

// AC-1 & AC-2: Der Fix setzt voraus, dass ein previousSchedule-State existiert,
// der den Schedule vor dem Pausieren merkt.
test('#558 AC-2: previousSchedule-State ist in CompareTabs.svelte deklariert', () => {
	assert.ok(
		src.includes('previousSchedule'),
		'CompareTabs.svelte hat keine previousSchedule-Variable — wöchentlicher Schedule geht beim Aktivieren verloren'
	);
});

// AC-2: handleToggleActive darf beim Aktivieren NICHT fest auf 'daily' verdrahtet sein.
test('#558 AC-2: handleToggleActive verdrahtet "daily" nicht hart als Aktivieren-Ziel', () => {
	// Die buggy Zeile: const next = localSchedule === 'manual' ? 'daily' : 'manual';
	// Nach dem Fix darf 'daily' hier nicht als fester Literal vorkommen, wenn es
	// der Aktivieren-Pfad (ternary true-branch) ist.
	const buggyPattern = /localSchedule\s*===\s*['"]manual['"]\s*\?\s*['"]daily['"]/;
	assert.ok(
		!buggyPattern.test(src),
		'CompareTabs.svelte enthält noch die fehlerhafte Zeile: ternary setzt schedule beim Aktivieren auf hardcoded "daily"'
	);
});

// AC-2: Beim Aktivieren muss previousSchedule als Quelle verwendet werden.
test('#558 AC-2: handleToggleActive verwendet previousSchedule als Ziel beim Aktivieren', () => {
	assert.ok(
		src.includes('previousSchedule'),
		'handleToggleActive referenziert previousSchedule nicht — weekly-Schedule kann nicht wiederhergestellt werden'
	);
	// Sicherstellen, dass previousSchedule auch beim Pausieren gesetzt wird
	assert.ok(
		/previousSchedule\s*=\s*localSchedule/.test(src),
		'CompareTabs.svelte setzt previousSchedule nicht auf localSchedule beim Pausieren'
	);
});

// AC-3: previousSchedule muss mit einem sinnvollen Default initialisiert werden
// (Fallback 'daily' wenn preset.schedule === 'manual' oder leer).
test('#558 AC-3: previousSchedule wird mit Fallback-Default "daily" initialisiert', () => {
	// Der Initialisierungs-Ausdruck muss 'daily' als Fallback enthalten
	assert.ok(
		src.includes('previousSchedule'),
		'previousSchedule-Variable fehlt in CompareTabs.svelte'
	);
	// Überprüft, dass der Default-Fallback 'daily' im Initialisierungskontext vorkommt
	const initWithDaily = /previousSchedule\s*=\s*\$state.*['"']daily['"']/.test(src) ||
		/let\s+previousSchedule[^=]*=.*['"']daily['"']/.test(src) ||
		/previousSchedule.*\?\s*preset\.schedule\s*:\s*['"']daily['"']/.test(src) ||
		/['"']daily['"'].*previousSchedule/.test(src);
	assert.ok(
		initWithDaily,
		'previousSchedule hat keinen "daily"-Fallback für Erstaktivierung von Entwurfs-Presets'
	);
});

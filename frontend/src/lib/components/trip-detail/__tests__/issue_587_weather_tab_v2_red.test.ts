// TDD RED: Issue #587 — Wetter-Metriken-Tab v2 (Modell-Vertrag)
//
// Spec: docs/specs/modules/issue_587_weather_tab_v2.md
// Modell-Entscheidung (PO Henning 2026-06-06): keine Detail-Zeile (secondary entfällt),
// jede ausgewählte Metrik ist Spalte oder aus; Telegram-Budget = 8.
//
// Diese Tests sind ABSICHTLICH ROT solange das alte secondary-Modell / telegram=7 gilt.
// Sie prüfen NUR den deterministischen Modell-Vertrag (mock-frei, echte Funktionen).
// Die UI-ACs (4-Abschnitte-Tab, Live-Mail, Diff-Highlight, Schnittlinie, Pixel-Diff)
// werden via Playwright gegen Staging in /e2e-verify abgenommen.
//
// Ausführen (aus frontend/):
//   node --experimental-strip-types --test \
//     src/lib/components/trip-detail/__tests__/issue_587_weather_tab_v2_red.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	CHANNEL_COL_BUDGET,
	// NEU (#587): wandelt das alte Bucket-Modell verlustfrei in eine geordnete
	// Spaltenliste um — primary zuerst, danach das ehemalige secondary.
	bucketsToColumns,
} from '../metricsEditor.ts';

// ============================================================================
// AC-5: Telegram-Budget = 8 (war 7, Signal-Budget entfallen)
// ============================================================================

test('#587 AC-5: CHANNEL_COL_BUDGET.telegram ist 8', () => {
	assert.equal(
		CHANNEL_COL_BUDGET.telegram,
		8,
		`Telegram-Budget muss 8 sein, war: ${CHANNEL_COL_BUDGET.telegram}`,
	);
});

// ============================================================================
// AC-7: Migration secondary -> Spalten ist verlustfrei + Reihenfolge primary++secondary
// ============================================================================

test('#587 AC-7: bucketsToColumns hängt secondary verlustfrei an primary an', () => {
	const buckets = {
		primary: ['temperature', 'wind', 'gust'],
		secondary: ['humidity', 'pressure'],
		off: ['cape'],
	};
	const cols = bucketsToColumns(buckets);
	assert.deepEqual(
		cols,
		['temperature', 'wind', 'gust', 'humidity', 'pressure'],
		`Spalten = primary ++ secondary in Reihenfolge, war: [${cols.join(', ')}]`,
	);
});

test('#587 AC-7: bucketsToColumns enthält keine off-Metrik und keine Dublette', () => {
	const buckets = {
		primary: ['temperature', 'wind'],
		secondary: ['wind', 'humidity'], // 'wind' versehentlich doppelt
		off: ['cape', 'sunshine'],
	};
	const cols = bucketsToColumns(buckets);
	assert.ok(!cols.includes('cape'), `off-Metrik 'cape' darf nicht auftauchen`);
	assert.ok(!cols.includes('sunshine'), `off-Metrik 'sunshine' darf nicht auftauchen`);
	assert.equal(new Set(cols).size, cols.length, `keine Dubletten erlaubt: [${cols.join(', ')}]`);
});

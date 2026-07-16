// TDD RED: Issue #1271 — Detail-Header muss die neuen kanonischen
// TripStatus-Zustände 'finished' und 'draft' kennen (Spec fix_1271_status_zeitformat).
//
// Spec: docs/specs/modules/fix_1271_status_zeitformat.md (AC-3, AC-5, AC-6)
//
// Test-Pattern: Source-Inspection (wie TripStatusBadge.atomic.test.ts /
// TripHeader.mobile-metrics.test.ts im selben Verzeichnis) — .svelte-Dateien
// werden hier nicht kompiliert/gerendert, daher Prüfung auf Markup-/Map-
// Struktur im rohen Quelltext statt Ausführung.
//
// RED vor Implementierung: TONE_MAP/LABEL_MAP in TripStatusBadge.svelte
// kennen 'finished'/'draft' noch nicht; TripHeader.svelte's etappeValue
// prüft nur 's === 'archived'', nicht 'finished'.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/trip-detail/__tests__/tripStatusFinishedDraft.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const BADGE = join(here, '../TripStatusBadge.svelte');
const HEADER = join(here, '../TripHeader.svelte');

const badgeSource = readFileSync(BADGE, 'utf8');
const headerSource = readFileSync(HEADER, 'utf8');

// ---------------------------------------------------------------------------
// AC-3/AC-5: TripStatusBadge kennt die zwei neuen kanonischen Zustände.
// ---------------------------------------------------------------------------

test('AC-3/#1271: TONE_MAP enthält einen Eintrag für finished', () => {
	assert.ok(
		/finished\s*:\s*['"][a-z]+['"]/.test(badgeSource),
		'TripStatusBadge.svelte: TONE_MAP soll einen Ton für den Status "finished" definieren — fehlt noch (TDD RED erwartet Fehler).'
	);
});

test('AC-3/#1271: LABEL_MAP zeigt für finished das deutsche Label "Fertig"', () => {
	assert.ok(
		/finished\s*:\s*['"]Fertig['"]/.test(badgeSource),
		'TripStatusBadge.svelte: LABEL_MAP soll finished → "Fertig" mappen — fehlt noch (TDD RED erwartet Fehler).'
	);
});

test('AC-5/#1271: TONE_MAP enthält einen Eintrag für draft', () => {
	assert.ok(
		/draft\s*:\s*['"][a-z]+['"]/.test(badgeSource),
		'TripStatusBadge.svelte: TONE_MAP soll einen Ton für den Status "draft" definieren — fehlt noch (TDD RED erwartet Fehler).'
	);
});

test('AC-5/#1271: LABEL_MAP enthält ein deutsches Label für draft', () => {
	assert.ok(
		/draft\s*:\s*['"][A-ZÄÖÜ][^'"]*['"]/.test(badgeSource),
		'TripStatusBadge.svelte: LABEL_MAP soll draft auf ein deutsches Label mappen — fehlt noch (TDD RED erwartet Fehler).'
	);
});

// ---------------------------------------------------------------------------
// AC-6: mobile Kennzahlen-Kachel "ETAPPE" muss bei finished (nicht nur
// archived) "X/X" statt "—/X" zeigen — sonst bleibt die inkonsistente
// Anzeige für vergangene-aber-nicht-archivierte Trips bestehen.
// ---------------------------------------------------------------------------

test('AC-6/#1271: etappeValue-Bedingung berücksichtigt finished neben archived', () => {
	const etappeBlockMatch = headerSource.match(/etappeValue[\s\S]{0,400}/);
	assert.ok(etappeBlockMatch, 'TripHeader.svelte: etappeValue-Block nicht gefunden.');
	const block = etappeBlockMatch![0];
	assert.ok(
		block.includes("'finished'") || block.includes('"finished"'),
		'TripHeader.svelte: etappeValue soll neben "archived" auch "finished" auf "X/X" abbilden — fehlt noch (TDD RED erwartet Fehler).'
	);
});

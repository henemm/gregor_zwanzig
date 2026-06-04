// TDD RED: Issue #579 — Home-Screen 1:1 nach JSX
//
// Spec: docs/specs/modules/issue_579_home_screen.md
//
// Source-Inspection-Tests (kein Render, keine Mocks):
//   1) cockpitHelpers.ts AC-8: morning_time/evening_time wird auf HH:MM gekürzt
//   2) +page.svelte AC-9: otherTrips filtert 'fertig'-Trips heraus
//   3) +page.svelte V13/AC-3: Schnellaktionen als vertikale Liste in linker Spalte
//   4) +page.svelte V2+V3/AC-2: Hero-Footer-Leiste (Eyebrow "Kanäle" + "Trip öffnen →")
//   5) +page.svelte V5/AC-5: "Außerdem beobachtet" in Card mit Titel + Link
//   6) +page.svelte V7/AC-6: Archiv-Sektion ohne Card-Ummantelung (SectionH direkt)
//   7) +page.svelte V9+V10/AC-7: PageHeader ohne sub, beide Buttons ghost
//
// RED vor Implementierung: Struktur weicht von JSX ab → Asserts schlagen fehl.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_579_home_screen.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

import { plannedBriefings } from '../routes/_home/cockpitHelpers.ts';
import type { ReportConfig } from './types.ts';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const PAGE = join(root, 'routes/+page.svelte');
const HELPERS = join(root, 'routes/_home/cockpitHelpers.ts');

const readPage = () => readFileSync(PAGE, 'utf-8');
const readHelpers = () => readFileSync(HELPERS, 'utf-8');

// ─── AC-8: Briefing-Zeit ohne Sekunden ────────────────────────────────────────

test('AC-8: plannedBriefings kürzt morning_time HH:MM:SS auf HH:MM', () => {
	const rc: ReportConfig = {
		morning_enabled: true,
		morning_time: '07:00:00',
		evening_enabled: false,
		send_email: true,
	} as ReportConfig;
	const result = plannedBriefings(rc);
	assert.equal(result.length, 1, 'Genau eine Briefing-Row erwartet');
	assert.equal(result[0].when, '07:00', `morning_time muss als "07:00" kommen, war: "${result[0].when}"`);
});

test('AC-8: plannedBriefings kürzt evening_time HH:MM:SS auf HH:MM', () => {
	const rc: ReportConfig = {
		morning_enabled: false,
		evening_enabled: true,
		evening_time: '18:30:00',
		send_email: true,
	} as ReportConfig;
	const result = plannedBriefings(rc);
	assert.equal(result[0].when, '18:30', `evening_time muss als "18:30" kommen, war: "${result[0].when}"`);
});

test('AC-8: cockpitHelpers.ts enthält .slice(0, 5) für morning_time', () => {
	const src = readHelpers();
	const hasMorningSlice = src.includes("morning_time") && src.includes('.slice(0, 5)');
	assert.ok(hasMorningSlice, 'cockpitHelpers.ts muss .slice(0, 5) für morning_time/evening_time enthalten');
});

// ─── AC-9: otherTrips filtert fertig-Trips heraus ────────────────────────────

test('AC-9: +page.svelte schließt fertig-Trips aus otherTrips aus', () => {
	const src = readPage();
	// Muss tripStatus-Aufruf im otherTrips-Filter enthalten, der 'fertig' ausschließt
	const hasStatusFilter =
		src.includes("tripStatus") &&
		(src.includes("!== 'fertig'") || src.includes("!== \"fertig\"") || src.includes("fertig") && src.includes("otherTrips"));
	assert.ok(hasStatusFilter,
		'otherTrips muss Trips mit tripStatus "fertig" ausschließen (AC-9)');
});

// ─── V13 / AC-3: Schnellaktionen vertikal in linker Spalte ──────────────────

test('AC-3: +page.svelte: Schnellaktionen sind flex-direction column, nicht quick-grid', () => {
	const src = readPage();
	// Alte Implementierung hat eine separate <section> mit class="quick-grid" (horizontal)
	// Neue soll flex column in der linken Spalte sein
	const hasNoSeparateQuickSection =
		!src.includes('<section') || !src.match(/<section[^>]*>\s*<Eyebrow[^>]*>Schnellaktionen/);
	assert.ok(hasNoSeparateQuickSection,
		'Schnellaktionen dürfen keine eigenständige <section> mit Eyebrow sein — sie gehören in die linke Hero-Spalte (AC-3/V13)');
});

test('AC-3: +page.svelte enthält glyph="send" für Test-Briefing-Aktion', () => {
	const src = readPage();
	assert.ok(src.includes('glyph="send"'),
		'QuickAction glyph="send" für Test-Briefing-Aktion muss vorhanden sein (AC-3/V13)');
});

test('AC-3: +page.svelte enthält 5 QuickActions im Trip-Modus (pause/metrics/clock/eye/send)', () => {
	const src = readPage();
	const glyphs = ['pause', 'metrics', 'clock', 'eye', 'send'];
	for (const g of glyphs) {
		assert.ok(src.includes(`glyph="${g}"`),
			`QuickAction glyph="${g}" fehlt in +page.svelte (AC-3/V13)`);
	}
});

// ─── V2+V3 / AC-2: Hero-Footer-Leiste ────────────────────────────────────────

test('AC-2: +page.svelte Hero enthält Eyebrow "Kanäle" in Footer-Leiste', () => {
	const src = readPage();
	// Die Hero-Card braucht eine Footer-Leiste mit Eyebrow "Kanäle"
	// Aktuell sind die Kanäle lose im Body ohne Eyebrow-Label
	assert.ok(
		src.includes('Kanäle') && src.includes('card-alt') && src.includes('Trip öffnen'),
		'Hero muss Footer-Leiste mit card-alt + Eyebrow "Kanäle" + "Trip öffnen →" enthalten (AC-2/V2+V3)'
	);
});

test('AC-2: +page.svelte Fortschrittsbalken kommt NACH dem Titel, nicht davor', () => {
	const src = readPage();
	// In der neuen Struktur: Titel zuerst, dann Fortschrittsbalken
	// Grobe Quell-Prüfung: hero.name (Link) muss vor dem Fortschritts-div erscheinen
	const nameLinkIdx = src.indexOf('/trips/{hero.id}?tab=overview');
	const progressIdx = src.indexOf('Tag {dayX} / {dayY}');
	// Wenn Tag x/y NACH dem Trip-Link kommt, ist die Reihenfolge korrekt
	assert.ok(progressIdx > nameLinkIdx,
		'Fortschrittsbalken-Label "Tag x/y" muss nach dem Titel-Link erscheinen (AC-2/V2)');
});

// ─── V5 / AC-5: „Außerdem beobachtet" in Card ────────────────────────────────

test('AC-5: "Außerdem beobachtet"-Sektion ist in einer Card eingebettet mit Titel-Zeile', () => {
	const src = readPage();
	// Neue Struktur: Card > Eyebrow "Außerdem beobachtet" + Titel + "Alle Vergleiche →"
	// Alte Struktur: nackte <section> mit nur Eyebrow
	const hasCardWithTitle = src.includes('Außerdem beobachtet') &&
		src.includes('Alle Vergleiche') &&
		src.includes('laufen nebenher');
	assert.ok(hasCardWithTitle,
		'"Außerdem beobachtet" muss in Card mit Titel "N Vergleiche laufen nebenher" + "Alle Vergleiche →"-Link sein (AC-5/V5)');
});

// ─── V7 / AC-6: Archiv ohne Card-Ummantelung ─────────────────────────────────

test('AC-6: Archiv-Sektion nutzt SectionH direkt, kein Card-Wrapper', () => {
	const src = readPage();
	// Alte Struktur: <Card><div style:padding="20px"><SectionH eyebrow="Archiv"...
	// Neue Struktur: <SectionH eyebrow="Archiv"... direkt, dann Grid
	// Prüfen: SectionH mit eyebrow="Archiv" ist NICHT innerhalb einer Card
	const archivSectionHIdx = src.indexOf('eyebrow="Archiv"');
	assert.ok(archivSectionHIdx !== -1, 'SectionH mit eyebrow="Archiv" muss vorhanden sein');

	// Die 300 Zeichen vor SectionH eyebrow="Archiv" dürfen kein <Card öffnen
	const before = src.slice(Math.max(0, archivSectionHIdx - 300), archivSectionHIdx);
	const hasCardWrapper = before.includes('<Card') && !before.includes('</Card');
	assert.ok(!hasCardWrapper,
		'Archiv-Sektion darf keinen Card-Wrapper um SectionH haben (AC-6/V7)');
});

// ─── V9+V10 / AC-7: PageHeader ohne sub, beide Buttons ghost ─────────────────

test('AC-7: PageHeader hat keinen sub-Prop mit langem Beschreibungstext', () => {
	const src = readPage();
	// sub-Prop entfernen oder leer lassen
	const hasLongSub = src.includes('läuft unterwegs autark') || src.includes('Briefings gehen per Email');
	assert.ok(!hasLongSub,
		'PageHeader darf keinen langen sub-Beschreibungstext haben (AC-7/V9)');
});

test('AC-7: Beide Topbar-Buttons haben variant="ghost"', () => {
	const src = readPage();
	// Alte Impl: Neuer Trip hat variant="primary"
	const hasPrimaryTripButton = src.includes('variant="primary"') && src.includes('Neuer Trip');
	assert.ok(!hasPrimaryTripButton,
		'"Neuer Trip"-Button darf nicht variant="primary" haben — beide müssen ghost sein (AC-7/V10)');
});

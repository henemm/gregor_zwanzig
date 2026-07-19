// TDD RED — Issue #1258 Scheibe S2: geteilter Alarme-Organism (ungewired).
// AC-9: gleiche Abschnittsreihenfolge in beiden Kontexten, Radar NUR bei
// context="vergleich". AC-10: Korridor-Zusammenfassungs-Label +
// Sprung-Link-Ziel je Kontext.
//
// TDD RED — Epic #1301 Scheibe D3: radar rueckt hinter official-warnings,
// neue Ueberschrift ueber der Ausloeser-Gruppe (triggerGroupHeading).
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
//   (AC-9, AC-10, Abschnitt 4 a-h)
// Spec: docs/specs/modules/epic_1301_d3_alarm_tab_struktur.md (AC-1, AC-2, AC-4, AC-5)
// Context: docs/context/feat-1258-s2-alarme-organism.md
//
// `triggerGroupHeading` existiert noch NICHT — Import schlägt heute fehl
// (RED), bis Phase 6 die Funktion in
// frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts anlegt.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/alarme_tab_sections.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	alarmeTabSections,
	notifySummaryLabel,
	wertebereicheTabId,
	triggerGroupHeading
} from '../alarme-tab/alarmeTabSections.ts';

test('#1258 AC-9: route-Kontext liefert Abschnittsreihenfolge a-h OHNE radar', () => {
	const sections = alarmeTabSections('route');
	assert.deepEqual(sections, [
		'korridor-summary',
		'official-warnings',
		'metric-levels',
		'channels',
		'cooldown',
		'quiet-hours',
		'sample'
	]);
	assert.equal(sections.includes('radar'), false);
});

test('D3 AC-1/AC-4: vergleich-Kontext liefert radar DIREKT hinter official-warnings (neue Reihenfolge)', () => {
	const sections = alarmeTabSections('vergleich');
	assert.deepEqual(sections, [
		'korridor-summary',
		'official-warnings',
		'radar',
		'metric-levels',
		'channels',
		'cooldown',
		'quiet-hours',
		'sample'
	]);
});

test('#1258 AC-9 / D3 AC-4: route- und vergleich-Reihenfolge sind identisch bis auf das radar-Element', () => {
	const route = alarmeTabSections('route');
	const vergleich = alarmeTabSections('vergleich').filter((s) => s !== 'radar');
	assert.deepEqual(route, vergleich);
});

test('D3 AC-1: radar steht zwischen official-warnings und metric-levels (nicht mehr am Tab-Ende)', () => {
	const sections = alarmeTabSections('vergleich');
	const officialIdx = sections.indexOf('official-warnings');
	const radarIdx = sections.indexOf('radar');
	const metricIdx = sections.indexOf('metric-levels');
	assert.equal(radarIdx, officialIdx + 1);
	assert.equal(metricIdx, radarIdx + 1);
});

test('D3 AC-2: triggerGroupHeading("vergleich") ist "Amtliche & Radar-Warnungen"', () => {
	assert.equal(triggerGroupHeading('vergleich'), 'Amtliche & Radar-Warnungen');
});

test('D3 AC-2: triggerGroupHeading("route") ist "Amtliche Warnungen"', () => {
	assert.equal(triggerGroupHeading('route'), 'Amtliche Warnungen');
});

test('#1258 AC-10: notifySummaryLabel(0) ist null (keine Zusammenfassung ohne aktive Korridore)', () => {
	assert.equal(notifySummaryLabel(0), null);
});

test('#1258 AC-10: notifySummaryLabel(3) ergibt "3 × Warnen aktiv"', () => {
	assert.equal(notifySummaryLabel(3), '3 × Warnen aktiv');
});

test('#1258 AC-10: notifySummaryLabel(1) ergibt "1 × Warnen aktiv" (Singular bleibt gleicher Text)', () => {
	assert.equal(notifySummaryLabel(1), '1 × Warnen aktiv');
});

test('#1258 AC-10: wertebereicheTabId("route") zeigt auf den Trip-Tab "alerts" (Wertebereiche)', () => {
	assert.equal(wertebereicheTabId('route'), 'alerts');
});

test('#1258 AC-10: wertebereicheTabId("vergleich") zeigt auf den Compare-Editor-Tab "idealwerte"', () => {
	assert.equal(wertebereicheTabId('vergleich'), 'idealwerte');
});

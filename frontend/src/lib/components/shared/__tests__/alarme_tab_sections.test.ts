// TDD RED — Issue #1258 Scheibe S2: geteilter Alarme-Organism (ungewired).
// AC-9: gleiche Abschnittsreihenfolge in beiden Kontexten, Radar NUR bei
// context="vergleich". AC-10: Korridor-Zusammenfassungs-Label +
// Sprung-Link-Ziel je Kontext.
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
//   (AC-9, AC-10, Abschnitt 4 a-h)
// Context: docs/context/feat-1258-s2-alarme-organism.md
//
// `alarmeTabSections.ts` existiert noch NICHT — Import schlägt heute fehl
// (RED), bis Phase 6 das Modul unter
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
	wertebereicheTabId
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

test('#1258 AC-9: vergleich-Kontext liefert dieselbe Reihenfolge PLUS radar vor sample', () => {
	const sections = alarmeTabSections('vergleich');
	assert.deepEqual(sections, [
		'korridor-summary',
		'official-warnings',
		'metric-levels',
		'channels',
		'cooldown',
		'quiet-hours',
		'radar',
		'sample'
	]);
});

test('#1258 AC-9: route- und vergleich-Reihenfolge sind identisch bis auf das radar-Element', () => {
	const route = alarmeTabSections('route');
	const vergleich = alarmeTabSections('vergleich').filter((s) => s !== 'radar');
	assert.deepEqual(route, vergleich);
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

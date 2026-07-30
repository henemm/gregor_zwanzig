// TDD RED — Issue #1258 Scheibe S2: geteilter Alarme-Organism (ungewired).
// AC-9: gleiche Abschnittsreihenfolge in beiden Kontexten, Radar NUR bei
// context="vergleich".
//
// TDD RED — Epic #1301 Scheibe D3: radar rueckt hinter official-warnings,
// neue Ueberschrift ueber der Ausloeser-Gruppe (triggerGroupHeading).
//
// Issue #1371: der Abschnitt 'korridor-summary' ("Korridor-Auslöser") entfaellt
// ersatzlos — der Reiter Wertebereiche setzt seit diesem Fix keine
// Warn-Schwellen mehr, die Aussage waere sachlich falsch. `notifySummaryLabel`
// entfaellt mit ihm (kein Aufrufer mehr).
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
//   (AC-9, Abschnitt 4 a-h)
// Spec: docs/specs/modules/epic_1301_d3_alarm_tab_struktur.md (AC-1, AC-2, AC-4, AC-5)
// Spec: docs/specs/modules/fix_1371_warnen_haekchen_raus.md (AC-6)
// Context: docs/context/feat-1258-s2-alarme-organism.md
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/alarme_tab_sections.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	alarmeTabSections,
	wertebereicheTabId,
	triggerGroupHeading
} from '../alarme-tab/alarmeTabSections.ts';

test('#1371 AC-6: route-Kontext liefert Abschnittsreihenfolge OHNE korridor-summary und OHNE radar', () => {
	const sections = alarmeTabSections('route');
	assert.deepEqual(sections, [
		'official-warnings',
		'metric-levels',
		'channels',
		'cooldown',
		'quiet-hours',
		'sample'
	]);
	assert.equal(sections.includes('radar'), false);
	assert.equal(sections.includes('korridor-summary'), false);
});

test('D3 AC-1/AC-4 + #1371 AC-6: vergleich-Kontext liefert radar DIREKT hinter official-warnings, OHNE korridor-summary', () => {
	const sections = alarmeTabSections('vergleich');
	assert.deepEqual(sections, [
		'official-warnings',
		'radar',
		'metric-levels',
		'channels',
		'cooldown',
		'quiet-hours',
		'sample'
	]);
	assert.equal(sections.includes('korridor-summary'), false);
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

// #1371 AC-6: kein Kontext behauptet noch aktive Warn-Schwellen/Korridor-Auslöser —
// geprueft strukturell ueber die Abwesenheit des Abschnitts in BEIDEN Kontexten
// (kein context-Zweig, der es nur auf einer Seite entfernt).
test('#1371 AC-6: kein Kontext (route/vergleich) enthaelt einen korridor-summary-Abschnitt', () => {
	for (const context of ['route', 'vergleich'] as const) {
		assert.equal(
			alarmeTabSections(context).includes('korridor-summary'),
			false,
			`context=${context} zeigt noch einen korridor-summary-Abschnitt`
		);
	}
});

test('#1258 AC-10: wertebereicheTabId("route") zeigt auf den Trip-Tab "alerts" (Wertebereiche)', () => {
	assert.equal(wertebereicheTabId('route'), 'alerts');
});

test('#1258 AC-10: wertebereicheTabId("vergleich") zeigt auf den Compare-Editor-Tab "idealwerte"', () => {
	assert.equal(wertebereicheTabId('vergleich'), 'idealwerte');
});

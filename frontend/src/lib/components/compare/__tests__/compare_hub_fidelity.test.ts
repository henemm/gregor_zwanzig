// TDD RED — Issue #1256 Scheibe S8c: Hub-Fidelity (R2 Layout-Tab-Rahmen + R3 Bündel)
//
// Spec: docs/specs/modules/feat_1256_s8c_hub_fidelity.md (AC-1..AC-13)
// Soll: claude-code-handoff/current/jsx/screen-compare-detail.jsx +
//       screen-compare-detail-mobile.jsx (Handoff-4)
//
// Source-Wächter (Kern-Schicht): prüfen den Soll-Zustand des Markups.
// Verhaltensnachweis aus Nutzersicht folgt in Phase 6 per Playwright gegen
// Staging (frontend/e2e/compare-hub-fidelity-s8c.spec.ts) — ROT-Beleg gegen
// Staging ist für noch-nicht-deployten Stand unmöglich (S4-Lehre).
//
// RED-Erwartung (vor Implementation): AC-1..AC-12 FAIL, AC-13-Wächter GREEN
// (Regressionsschutz laut Spec).
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs \
//     --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_hub_fidelity.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const COMPARE_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');
const TABS_FILE = join(COMPARE_DIR, 'CompareTabs.svelte');
const PAGE_FILE = join(COMPARE_DIR, '..', '..', '..', 'routes', 'compare', '[id]', '+page.svelte');
const SECTION_H_FILE = join(COMPARE_DIR, '..', 'atoms', 'SectionH.svelte');

const tabs = () => readFileSync(TABS_FILE, 'utf-8');
const page = () => readFileSync(PAGE_FILE, 'utf-8');

// Issue #1360 (Scheibe S1a von Epic #1372): die Fidelity-Pruefungen zum
// Layout-Reiter (AC-1 Desktop-Rahmen „Übersicht pro Kanal" + Limit-Pillen,
// AC-2 Mobil-Variante „Spalten pro Kanal" + CompareLayoutRow dense) sind
// GELOESCHT: ihr Pruefsubjekt — das Layout-Panel samt CompareLayoutRow — ist
// ersatzlos entfallen. Sie zementierten genau die Attrappe mit der sachlich
// falschen Kappungs-Aussage, die #1360 beseitigt (AC-4).

describe('AC-3: Orte-SummaryCard „+N weitere" (jsx:159)', () => {
	test('Suffix „+N weitere" bei mehr als 3 Orten', () => {
		// Bewusst „{…} weitere" (interpolierte Restanzahl) — das vorbestehende
		// „Keine weiteren gespeicherten Orte" (Add-Panel) darf NICHT matchen.
		assert.match(
			tabs(),
			/\}\s+weitere/,
			'AC-3 FAIL: „+N weitere"-Suffix fehlt auf der Orte-Karte (Ist: nackter slice(0,3)-Join)'
		);
	});
});

// Issue #1360: die Fidelity-Pruefung der Layout-SummaryCard („Layout pro Kanal",
// „Engere Kanäle zeigen automatisch weniger Spalten — Reihenfolge nach
// Priorität.") ist GELOESCHT — die Karte ist entfallen (AC-4: keine Flaeche
// behauptet mehr eine Orts-Kappung je Kanal) und sprang auf den aufgeloesten
// Reiter.

describe('AC-5: Versand-SummaryCard Draft-Sonderfall (jsx:175-177)', () => {
	test('Draft-Titel und Draft-Copy vorhanden', () => {
		const code = tabs();
		assert.ok(code.includes('Noch nicht geplant'), 'AC-5 FAIL: Draft-Titel „Noch nicht geplant" fehlt');
		assert.ok(
			code.includes('Briefing-Uhrzeiten im Tab Versand festlegen.'),
			'AC-5 FAIL: Draft-Copy „Briefing-Uhrzeiten im Tab Versand festlegen." fehlt'
		);
	});
});

describe('AC-6: Wertebereiche-Karte Profil-Label (jsx:163)', () => {
	test('presetProfileLabel wird in CompareTabs verwendet', () => {
		assert.match(
			tabs(),
			/presetProfileLabel/,
			'AC-6 FAIL: CompareTabs nutzt presetProfileLabel nicht — Karte zeigt rohes preset.profil'
		);
	});
});

describe('AC-7: mobiler Chevron-Summary-Stack (screen-compare-detail-mobile.jsx:87-93,276-293)', () => {
	test('gestapelte Chevron-Zeilen mit Testid vorhanden', () => {
		assert.match(
			tabs(),
			/data-testid="hub-summary-row-mobile"/,
			'AC-7 FAIL: keine mobilen Chevron-Summary-Zeilen (hub-summary-row-mobile) — Ist: 2×2-Grid auch mobil'
		);
	});
	test('mobile Draft-Kurztexte der Versand-Zeile vorhanden', () => {
		const code = tabs();
		assert.ok(code.includes('Nicht geplant'), 'AC-7 FAIL: mobile Draft-Kurzform „Nicht geplant" fehlt');
		assert.ok(code.includes('Aktivierung offen'), 'AC-7 FAIL: mobile Draft-Desc „Aktivierung offen" fehlt');
	});
});

describe('AC-8: mobile Status-Kurzform (screen-compare-detail-mobile.jsx:81)', () => {
	test('Kurzform „Läuft autom." vorhanden', () => {
		assert.match(
			tabs(),
			/Läuft autom\./,
			'AC-8 FAIL: mobile Status-Kurzform „Läuft autom." fehlt (Ist: Langform „Läuft automatisch")'
		);
	});
});

describe('AC-9: Orte-Tab Section-Rahmen (jsx:197-216, CDM:110)', () => {
	test('Header „Verglichene Orte" + Sortier-Hint vorhanden', () => {
		const code = tabs();
		assert.ok(code.includes('Verglichene Orte'), 'AC-9 FAIL: Header „Verglichene Orte" fehlt');
		assert.ok(code.includes('ziehen zum Sortieren'), 'AC-9 FAIL: Hint „… ziehen zum Sortieren" fehlt');
	});
});

describe('AC-10: Breadcrumb ohne Extra-Krümel (jsx:66-70)', () => {
	test('WORKSPACE-Krümel entfällt auf der Hub-Seite', () => {
		assert.ok(
			!page().includes('WORKSPACE'),
			'AC-10 FAIL: Breadcrumb enthält noch den Extra-Krümel „WORKSPACE"'
		);
	});
});

describe('AC-11: Desktop-Unterzeile Profil-Label (jsx:78-80)', () => {
	test('rohes {data.preset.profil} nicht mehr im Markup', () => {
		assert.ok(
			!page().includes('{data.preset.profil}'),
			'AC-11 FAIL: Desktop-Unterzeile zeigt noch rohes data.preset.profil statt profileLabel'
		);
	});
});

describe('AC-12: mobile Eyebrow „Orts-Vergleich · Hub" (screen-compare-detail-mobile.jsx:51)', () => {
	test('Eyebrow-Text im Mobile-Header vorhanden', () => {
		assert.ok(
			page().includes('Orts-Vergleich · Hub'),
			'AC-12 FAIL: mobile Eyebrow-Zeile „Orts-Vergleich · Hub" fehlt'
		);
	});
});

describe('AC-13: Sharing-Invariante (Wächter — GREEN von Anfang an)', () => {
	test('SectionH-Atom bleibt unverändert (keine hint-Prop)', () => {
		const sectionH = readFileSync(SECTION_H_FILE, 'utf-8');
		assert.ok(
			!/\bhint\??\s*:/.test(sectionH),
			'AC-13 FAIL: SectionH hat eine neue hint-Prop bekommen — Hint gehört ins vorhandene right-Snippet'
		);
	});
	test('hubPutQueue-Schreibpfad-Mechanik unangetastet vorhanden', () => {
		assert.match(tabs(), /hubPutQueue/, 'AC-13 FAIL: hubPutQueue-Referenz aus CompareTabs verschwunden');
	});
	test('Section-Rahmen nutzen geteilten SectionH (nach Implementation)', () => {
		assert.match(
			tabs(),
			/SectionH/,
			'AC-13 (mit AC-1/9) FAIL: CompareTabs nutzt SectionH nicht — Rahmen muss über den geteilten Atom laufen'
		);
	});
});

// TDD RED — Epic #1273 Slice S3: alle externen Compare-Linkziele biegen von der
// alten /compare/[id]/edit-Route auf den Hub /compare/[id] um; die zwei
// hash-basierten Schnellaktionen werden auf ?tab= umgestellt; die jetzt
// redundanten Hub-eigenen Bearbeiten-Affordanzen (Desktop-Button, Mobile-Stift)
// entfallen.
//
// Spec: docs/specs/modules/feat_1273_s3_redirect.md
//   § Implementation Details 2/3, § Acceptance Criteria AC-2/AC-3/AC-4
//
// Source-Inspection-Tests (kein Mock, kein DOM, kein Playwright): prüfen den
// Soll-Quelltext nach Implementation. RED-Erwartung (vor Implementation): die
// Produktivdateien referenzieren aktuell noch `/edit` (bzw. `#idealwerte`/
// `#schedule`) — jede Assertion schlägt daher jetzt fehl.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/compare/__tests__/issue_1273_s3_redirect_links.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

// __tests__ → compare → components → lib → src
const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..');

const COMPARE_KACHEL = join(SRC, 'routes', '_home', 'CompareKachel.svelte');
const COMPARE_LIST = join(SRC, 'routes', 'compare', '+page.svelte');
const HOME = join(SRC, 'routes', '+page.svelte');
const HUB = join(SRC, 'routes', 'compare', '[id]', '+page.svelte');

const read = (p: string) => readFileSync(p, 'utf8');

// ── AC-2: 7 externe Linkziele zeigen nicht mehr auf /edit ─────────────────────

describe('AC-2: Home-Kachel-Kebab (CompareKachel.svelte) zielt auf den Hub, nicht /edit', () => {
	test('kein "sub.id + \'/edit\'"-Ziel mehr', () => {
		const src = read(COMPARE_KACHEL);
		assert.ok(
			!src.includes("sub.id + '/edit'"),
			'CompareKachel.svelte darf nicht mehr auf /compare/{id}/edit navigieren — Ziel ist der Hub'
		);
	});
});

describe('AC-2: Listen-Kebab (routes/compare/+page.svelte) zielt auf den Hub, nicht /edit', () => {
	test('weder "setup"- noch "edit"-Fall navigiert auf "p.id + \'/edit\'"', () => {
		const src = read(COMPARE_LIST);
		assert.ok(
			!src.includes("p.id + '/edit'"),
			'onCompareAction (setup/edit) darf nicht mehr auf /compare/{id}/edit navigieren — Ziel ist der Hub'
		);
	});
});

describe('AC-2: Home-Hero-CTA (routes/+page.svelte, buildCompareCtaHref) zielt auf den Hub', () => {
	test('kein "${firstIncomplete.id}/edit"-Ziel mehr', () => {
		const src = read(HOME);
		assert.ok(
			!src.includes('${firstIncomplete.id}/edit'),
			'buildCompareCtaHref() darf nicht mehr auf /compare/{id}/edit zeigen — Ziel ist der Hub'
		);
	});
});

describe('AC-2: Home-Schnellaktionen (routes/+page.svelte) zielen auf den Hub, nicht /edit', () => {
	test('kein "/compare/{compareHero.id}/edit"-href mehr (Orte/Ideal-Werte/Zeitplan)', () => {
		const src = read(HOME);
		assert.ok(
			!src.includes('/compare/{compareHero.id}/edit'),
			'die Schnellaktionen dürfen nicht mehr auf /compare/{id}/edit(#...) zeigen — Ziel ist der Hub'
		);
	});
});

// ── AC-3: Hash-Anker → ?tab=-Query ────────────────────────────────────────────

describe('AC-3: Schnellaktionen nutzen ?tab= statt Hash-Anker', () => {
	test('kein #idealwerte / #schedule mehr in routes/+page.svelte', () => {
		const src = read(HOME);
		assert.ok(!src.includes('#idealwerte'), 'Hash-Anker #idealwerte muss durch ?tab=idealwerte ersetzt sein');
		assert.ok(!src.includes('#schedule'), 'Hash-Anker #schedule muss durch ?tab=versand ersetzt sein');
	});

	test('?tab=idealwerte und ?tab=versand sind vorhanden', () => {
		const src = read(HOME);
		assert.ok(
			src.includes('?tab=idealwerte'),
			'Schnellaktion "Ideal-Werte ändern" muss auf /compare/{id}?tab=idealwerte zeigen'
		);
		assert.ok(
			src.includes('?tab=versand'),
			'Schnellaktion "Briefing-Zeitplan" muss auf /compare/{id}?tab=versand zeigen'
		);
	});

	// Adversary-Fund F001: die beiden Tests oben prüfen nur die Link-STRINGS
	// (Quelltext-Grep, angemessen für hartkodierte href-Werte — dafür gibt es
	// keinen sinnvollen "echten Aufruf"). ABER die Spec verlangte für AC-3
	// zusätzlich einen echten Funktionsaufruf, der beweist, dass CompareTabs
	// diese Query-Werte tatsächlich als gültige Tabs akzeptiert (nicht nur,
	// dass die Links so AUSSEHEN). `resolveCompareTab` ist dieselbe Funktion,
	// die CompareTabs.svelte für `initialTab` verwendet (compareTabsResolve.ts,
	// Single Source of Truth) — kein Duplikat der Logik, echter Aufruf.
	test('resolveCompareTab("idealwerte") und ("versand") lösen NICHT auf "uebersicht" zurück', async () => {
		const { resolveCompareTab } = await import('../compareTabsResolve.ts');
		assert.equal(
			resolveCompareTab('idealwerte'),
			'idealwerte',
			'CompareTabs muss ?tab=idealwerte als gültigen Tab akzeptieren, nicht auf uebersicht zurückfallen'
		);
		assert.equal(
			resolveCompareTab('versand'),
			'versand',
			'CompareTabs muss ?tab=versand als gültigen Tab akzeptieren, nicht auf uebersicht zurückfallen'
		);
		// Gegenprobe: ein ungültiger Wert faellt weiterhin auf uebersicht zurueck
		// (Regressionsschutz — kein zu freizuegiges resolve()).
		assert.equal(resolveCompareTab('nicht-existent'), 'uebersicht');
	});
});

// ── AC-4: redundante Hub-eigene Bearbeiten-Affordanzen entfernt ───────────────

describe('AC-4: Hub (routes/compare/[id]/+page.svelte) rendert keinen Bearbeiten-Button/Stift mehr', () => {
	test('Desktop-"Bearbeiten"-Button (compare-detail-edit-button) entfernt', () => {
		const src = read(HUB);
		assert.ok(
			!src.includes('compare-detail-edit-button'),
			'der Desktop-"Bearbeiten"-Button muss entfernt sein — der Hub IST die Bearbeiten-Fläche'
		);
	});

	test('Mobile-Stift-Icon (href auf /edit) entfernt', () => {
		const src = read(HUB);
		assert.ok(
			!src.includes('href="/compare/{currentPreset.id}/edit"'),
			'das Mobile-Stift-Icon (Link auf /edit) muss aus der TopBar entfernt sein'
		);
	});
});

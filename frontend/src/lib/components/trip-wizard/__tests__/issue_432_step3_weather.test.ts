// TDD RED — Issue #432: Step 3 Wetter-Umbau (HorizonChip raus, Format-Dropdown rein,
// 5 Kategorien-Gruppen, Sticky-Header).
// SPEC: docs/specs/modules/issue_432_step3_step5_polish.md (AC-1..AC-7).
// TEST-MANIFEST: docs/specs/tests/issue_432_step3_step5_polish_tests.md.
//
// Source-Inspection-Tests. Heute (vor Implementation):
//   - HorizonChip-Import + -Tags vorhanden → AC-1 rot
//   - Kein Format-Dropdown → AC-2 rot
//   - Keine Kategorien-Gruppen → AC-3 rot
//   - Hartcodierte 6 Metriken statt /api/metrics → AC-4 rot
//   - Keine Sticky-Header → AC-5 rot
//   - Kein Zähler-Header → AC-6 rot
//   - Kein Fade-Indikator → AC-7 rot
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_432_step3_weather.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const STEP3 = join(here, '..', 'steps', 'Step3Weather.svelte');

function read(): string { return readFileSync(STEP3, 'utf-8'); }

// =============================================================================
// AC-1: HorizonChip komplett entfernen
// =============================================================================

test('AC-1: Step3Weather.svelte enthält keinen HorizonChip-Import mehr', () => {
	const src = read();
	assert.ok(
		!src.includes('HorizonChip') || !/import\s+\{[^}]*HorizonChip/.test(src),
		'HorizonChip-Import darf nicht mehr vorhanden sein (heute: import { HorizonChip } from "$lib/components/ui/horizon-chip")',
	);
});

test('AC-1: Step3Weather.svelte Template enthält kein <HorizonChip>-Tag', () => {
	const src = read();
	assert.ok(
		!/<HorizonChip\b/.test(src),
		'Template darf keine <HorizonChip>-Tags mehr enthalten',
	);
});

// =============================================================================
// AC-2: Format-Dropdown pro Metrik (4 Optionen)
// =============================================================================

test('AC-2: Step3Weather enthält Format-Dropdown mit 4 Optionen (raw/scale/simplified/symbol)', () => {
	const src = read();
	// Wir suchen nach den 4 Option-Werten als String-Literals
	const has = (kw: string) => src.includes(`"${kw}"`) || src.includes(`'${kw}'`);
	assert.ok(has('raw'),        'Option-Wert "raw" muss vorhanden sein');
	assert.ok(has('scale'),      'Option-Wert "scale" muss vorhanden sein');
	assert.ok(has('simplified'), 'Option-Wert "simplified" muss vorhanden sein');
	assert.ok(has('symbol'),     'Option-Wert "symbol" muss vorhanden sein');
});

// =============================================================================
// AC-3: 5 Kategorien-Gruppen
// =============================================================================

test('AC-3: Step3Weather rendert 5 Kategorien-Labels (Temperatur/Wind/Niederschlag/Atmosphäre/Winter)', () => {
	const src = read();
	// Labels kommen entweder direkt im Template oder via CATEGORY_LABELS-Import.
	// Wir akzeptieren beide Wege: entweder die Label-Strings im Source oder
	// einen Import + Iteration über CATEGORY_ORDER.
	const hasCategoryImport = /CATEGORY_LABELS|CATEGORY_ORDER/.test(src);
	const labels = ['Temperatur', 'Wind', 'Niederschlag', 'Atmosph', 'Winter'];
	const allLabelsInSource = labels.every(l => src.includes(l));
	assert.ok(
		hasCategoryImport || allLabelsInSource,
		'Step3Weather muss entweder CATEGORY_LABELS/CATEGORY_ORDER importieren oder die 5 Kategorien-Labels (Temperatur/Wind/Niederschlag/Atmosphäre/Winter) im Template enthalten',
	);
});

// =============================================================================
// AC-4: Catalog-Load via /api/metrics
// =============================================================================

test('AC-4: Step3Weather lädt den Metrik-Katalog via /api/metrics', () => {
	const src = read();
	// Akzeptiert: api.get('/api/metrics') oder Variation mit Quote
	const has = /api\.get\s*<[^>]*>?\s*\(\s*['"]\/api\/metrics['"]/.test(src) ||
				/api\.get\s*\(\s*['"]\/api\/metrics['"]/.test(src);
	assert.ok(
		has,
		'Step3Weather muss api.get("/api/metrics") aufrufen (heute: 6 hartcodierte Metriken in DEFAULT_METRICS)',
	);
});

// =============================================================================
// AC-5: Sticky Gruppen-Header
// =============================================================================

test('AC-5: Step3Weather enthält CSS-Regel `position: sticky` für Gruppen-Header', () => {
	const src = read();
	const has = /position\s*:\s*sticky/.test(src);
	assert.ok(
		has,
		'Step3Weather muss CSS `position: sticky` für Sticky-Gruppen-Header enthalten',
	);
});

// =============================================================================
// AC-6: Zähler-Header „METRIKEN · N AKTIV VON M"
// =============================================================================

test('AC-6: Step3Weather enthält Zähler-Header („METRIKEN" + „AKTIV VON")', () => {
	const src = read();
	assert.ok(
		src.includes('METRIKEN') || src.includes('Metriken'),
		'Step3Weather muss „METRIKEN"-Header enthalten',
	);
	assert.ok(
		/aktiv\s+von|AKTIV\s+VON/.test(src),
		'Step3Weather muss „aktiv von" (Zähler-Pattern) enthalten',
	);
});

// =============================================================================
// AC-7: Scroll-Container + Fade-Indikator
// =============================================================================

test('AC-7: Step3Weather enthält Fade-Indikator (CSS-Gradient-Maske oder data-testid)', () => {
	const src = read();
	// Akzeptiert: data-testid="step3-scroll-fade" ODER CSS-Gradient-Maske
	const hasTestId = /data-testid\s*=\s*["']step3-scroll-fade["']/.test(src);
	const hasGradient = /mask-image\s*:|linear-gradient\s*\([^)]*transparent/.test(src);
	assert.ok(
		hasTestId || hasGradient,
		'Step3Weather muss Fade-Indikator haben (data-testid="step3-scroll-fade" oder CSS-Gradient-Maske)',
	);
});

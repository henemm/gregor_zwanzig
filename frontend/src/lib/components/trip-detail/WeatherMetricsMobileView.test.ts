// TDD RED: Issue #415 — Mobile Wetter-Metriken: Full-Screen-Overlay
//
// Spec: docs/specs/modules/issue_415_mobile_metrics_view.md
//
// Source-Inspection-Test: liest WeatherMetricsMobileView.svelte und
// WeatherMetricsTab.svelte als String und prüft Struktur/CSS/Markup.
//
// RED vor Implementierung: WeatherMetricsMobileView.svelte existiert noch
// nicht → alle dateilesenden Tests schlagen fehl. WeatherMetricsTab.svelte
// hat noch keinen Mobile-Trigger → AC-8-Tests schlagen fehl.
//
// Keine Mocks, kein Render-Framework.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/WeatherMetricsMobileView.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const VIEW = join(here, 'WeatherMetricsMobileView.svelte');
const TAB  = join(here, 'WeatherMetricsTab.svelte');

function readView(): string {
	return readFileSync(VIEW, 'utf-8');
}
function readTab(): string {
	return readFileSync(TAB, 'utf-8');
}

// =============================================================================
// AC-1: Datei existiert + Overlay-CSS
// =============================================================================

test('AC-1: WeatherMetricsMobileView.svelte existiert', () => {
	assert.ok(existsSync(VIEW), 'WeatherMetricsMobileView.svelte fehlt');
});

test('AC-1: Overlay-CSS: position fixed + inset 0 + z-index 150', () => {
	const src = readView();
	assert.ok(
		src.includes('position: fixed') || src.includes('position:fixed'),
		'position: fixed fehlt im CSS'
	);
	assert.ok(
		src.includes('inset: 0') || src.includes('inset:0'),
		'inset: 0 fehlt im CSS'
	);
	assert.ok(
		src.includes('z-index: 150') || src.includes('z-index:150'),
		'z-index: 150 fehlt im CSS — muss BottomNav (z-50) überlagern'
	);
});

test('AC-1: Overlay enthält Mini-Header mit MIcon kind=back', () => {
	const src = readView();
	assert.ok(
		src.includes("kind=\"back\"") || src.includes("kind='back'"),
		'MIcon kind="back" fehlt im Mini-Header'
	);
});

test('AC-1: Overlay enthält Abbrechen-Button', () => {
	const src = readView();
	assert.ok(
		src.includes('Abbrechen'),
		'"Abbrechen"-Text fehlt im Mini-Header'
	);
});

test('AC-1: Overlay enthält fixierten Footer mit Reset + übernehmen', () => {
	const src = readView();
	assert.ok(src.includes('Reset'), '"Reset"-Button-Text fehlt im Footer');
	assert.ok(
		src.includes('übernehmen'),
		'"übernehmen"-Text fehlt im Footer-Button'
	);
});

// =============================================================================
// AC-2: Akkordeon — Single-Open, Chevron-Icons
// =============================================================================

test('AC-2: CATEGORY_ORDER wird importiert (für Akkordeon-Iteration)', () => {
	const src = readView();
	assert.ok(
		src.includes('CATEGORY_ORDER'),
		'CATEGORY_ORDER-Import fehlt — wird für Akkordeon-Gruppen benötigt'
	);
});

test('AC-2: CATEGORY_LABELS wird importiert (für Akkordeon-Header)', () => {
	const src = readView();
	assert.ok(
		src.includes('CATEGORY_LABELS'),
		'CATEGORY_LABELS-Import fehlt — wird für Kategorie-Beschriftungen benötigt'
	);
});

test('AC-2: openCat-State für Single-Open-Akkordeon vorhanden', () => {
	const src = readView();
	assert.ok(
		src.includes('openCat'),
		'openCat-State fehlt — steuert welche Kategorie aufgeklappt ist'
	);
});

test('AC-2: Chevron-Icons vorhanden (chevron-up und chevron-down)', () => {
	const src = readView();
	assert.ok(
		src.includes('chevron-up') || src.includes('chevron-down'),
		'Chevron-Icon-Kinds fehlen — werden für Akkordeon-Auf/Zu gebraucht'
	);
});

// =============================================================================
// AC-3: MSwitch pro Metrik-Zeile
// =============================================================================

test('AC-3: MSwitch wird importiert', () => {
	const src = readView();
	assert.ok(
		src.includes("MSwitch"),
		'MSwitch fehlt — wird als iOS-Toggle pro Metrik-Zeile benötigt'
	);
});

test('AC-3: MSwitch wird mit checked-Prop gebunden', () => {
	const src = readView();
	assert.ok(
		src.includes('checked={') || src.includes('checked="{'),
		'MSwitch checked-Prop fehlt'
	);
});

test('AC-3: onToggleMetric-Callback ist als Prop deklariert', () => {
	const src = readView();
	assert.ok(
		src.includes('onToggleMetric'),
		'onToggleMetric-Prop fehlt'
	);
});

// =============================================================================
// AC-4: Preset-Pill-Strip
// =============================================================================

test('AC-4: Preset-Strip hat horizontales Scroll-CSS', () => {
	const src = readView();
	assert.ok(
		src.includes('overflow-x') || src.includes('overflow: auto') || src.includes('overflow:auto'),
		'Horizontales Scroll-CSS fehlt für Preset-Strip'
	);
});

test('AC-4: onSelectPreset-Callback ist als Prop deklariert', () => {
	const src = readView();
	assert.ok(
		src.includes('onSelectPreset'),
		'onSelectPreset-Prop fehlt'
	);
});

test('AC-4: Preset-Pills werden über templates + userPresets iteriert', () => {
	const src = readView();
	assert.ok(
		src.includes('templates') && src.includes('userPresets'),
		'Templates oder userPresets fehlen in der Preset-Iteration'
	);
});

// =============================================================================
// AC-5/AC-5b: Footer onSave + onDiscard + onClose
// =============================================================================

test('AC-5: onSave-Callback ist als Prop deklariert', () => {
	const src = readView();
	assert.ok(src.includes('onSave'), 'onSave-Prop fehlt');
});

test('AC-5b: onDiscard-Callback ist als Prop deklariert', () => {
	const src = readView();
	assert.ok(src.includes('onDiscard'), 'onDiscard-Prop fehlt');
});

test('AC-5: onClose-Callback ist als Prop deklariert', () => {
	const src = readView();
	assert.ok(src.includes('onClose'), 'onClose-Prop fehlt');
});

// =============================================================================
// AC-7: Safe-Area-Padding für iOS-Notch
// =============================================================================

test('AC-7: Footer hat env(safe-area-inset-bottom) im CSS', () => {
	const src = readView();
	assert.ok(
		src.includes('safe-area-inset-bottom'),
		'env(safe-area-inset-bottom) fehlt im Footer-CSS — iOS-Notch nicht berücksichtigt'
	);
});

test('AC-7: keine Magic-Pixel-Abstände (kein px-Literal ohne Token)', () => {
	const src = readView();
	// Prüft auf typische Magic-Pixel-Muster in CSS (padding/margin/gap mit rohen Pixel-Werten)
	const magicPixel = src.match(/(?:padding|margin|gap):\s*\d+px(?!\s*\/)/g) ?? [];
	// 1px für borders ist erlaubt, daher filtern
	const nonBorderPixels = magicPixel.filter(m => !m.includes('1px'));
	assert.deepEqual(
		nonBorderPixels,
		[],
		`Magic-Pixel-Werte gefunden: ${nonBorderPixels.join(', ')} — erwartet --g-s-* Tokens`
	);
});

// =============================================================================
// AC-8: WeatherMetricsTab hat Mobile-Trigger + showMobileView-State
// =============================================================================

test('AC-8: WeatherMetricsTab hat showMobileView-State', () => {
	const src = readTab();
	assert.ok(
		src.includes('showMobileView'),
		'showMobileView-State fehlt in WeatherMetricsTab.svelte'
	);
});

test('AC-8: WeatherMetricsTab importiert WeatherMetricsMobileView', () => {
	const src = readTab();
	assert.ok(
		src.includes('WeatherMetricsMobileView'),
		'WeatherMetricsMobileView fehlt als Import in WeatherMetricsTab.svelte'
	);
});

test('AC-8: Mobile-Trigger-Button existiert mit class mobile-metrics-trigger', () => {
	const src = readTab();
	assert.ok(
		src.includes('mobile-metrics-trigger'),
		'CSS-Klasse mobile-metrics-trigger fehlt — Button für Mobile-Overlay-Öffnung'
	);
});

test('AC-8: Desktop-Layout ist per CSS auf Mobile ausgeblendet (display: none bei max-width: 899px)', () => {
	const src = readTab();
	// Der Trigger-Button muss auf Desktop versteckt sein
	assert.ok(
		src.includes('max-width: 899px') || src.includes('max-width:899px'),
		'max-width: 899px-Breakpoint fehlt für Mobile-Trigger-CSS'
	);
	assert.ok(
		src.includes('mobile-metrics-trigger'),
		'mobile-metrics-trigger CSS-Klasse fehlt im WeatherMetricsTab'
	);
});

test('AC-8: onToggleMetric-Handler in WeatherMetricsTab vorhanden', () => {
	const src = readTab();
	assert.ok(
		src.includes('onToggleMetric'),
		'onToggleMetric-Funktion fehlt in WeatherMetricsTab.svelte'
	);
});

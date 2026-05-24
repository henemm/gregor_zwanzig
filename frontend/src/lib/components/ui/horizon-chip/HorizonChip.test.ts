// TDD RED: Issue #343 — HorizonChip-Komponente (Source-Inspection-Tests)
//
// Spec: docs/specs/modules/issue_343_horizon_chip_ui.md  §1, Component-Specs
//
// Hinweis zum Test-Pattern:
// Das Frontend nutzt `node --experimental-strip-types --test`, das KEINE
// `.svelte`-Imports laden kann (vgl. Btn.test.ts, das deshalb deaktiviert ist).
// Daher folgen wir dem Source-Inspection-Pattern aus
// `WeatherMetricsPreviewCard.tokens.test.ts`: wir lesen die `.svelte`-Datei als
// String und assertieren auf vorhandene Marker — `data-slot`, `data-active`,
// `data-day`, Labels, `aria-pressed`, `onclick`-Prop, Disabled-State.
//
// In der RED-Phase scheitern alle Tests, weil `HorizonChip.svelte` noch nicht
// existiert (readFileSync wirft `ENOENT`).
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/ui/horizon-chip/HorizonChip.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, 'HorizonChip.svelte');

function loadSource(): string {
	return readFileSync(COMPONENT, 'utf8');
}

// --- Label-Tests (AC: drei Tages-Labels) ---------------------------------

test('HorizonChip rendert "HEUTE" fuer day=today', () => {
	const source = loadSource();
	assert.match(
		source,
		/HEUTE/,
		'Label "HEUTE" fehlt im Komponenten-Source (LABELS.today)'
	);
	assert.match(
		source,
		/today\s*:\s*['"]HEUTE['"]/,
		'LABELS-Map muss today: "HEUTE" enthalten'
	);
});

test('HorizonChip rendert "MORGEN" fuer day=tomorrow', () => {
	const source = loadSource();
	assert.match(
		source,
		/MORGEN/,
		'Label "MORGEN" fehlt im Komponenten-Source (LABELS.tomorrow)'
	);
	assert.match(
		source,
		/tomorrow\s*:\s*['"]MORGEN['"]/,
		'LABELS-Map muss tomorrow: "MORGEN" enthalten'
	);
});

test('HorizonChip rendert "UEBERMORGEN" fuer day=day_after', () => {
	const source = loadSource();
	// Akzeptiere beide Schreibweisen: "ÜBERMORGEN" (UTF-8) oder ASCII-Fallback.
	assert.match(
		source,
		/(ÜBERMORGEN|UEBERMORGEN)/,
		'Label "UEBERMORGEN" fehlt im Komponenten-Source (LABELS.day_after)'
	);
	assert.match(
		source,
		/day_after\s*:\s*['"](ÜBERMORGEN|UEBERMORGEN)['"]/,
		'LABELS-Map muss day_after: "ÜBERMORGEN" enthalten'
	);
});

// --- data-active-Attribut (AC-1 Vorbedingung) ----------------------------

test('HorizonChip setzt data-active und data-slot Attribute', () => {
	const source = loadSource();
	assert.match(
		source,
		/data-slot=["']horizon-chip["']/,
		'data-slot="horizon-chip" fehlt — Component-Spec verlangt dieses Selector-Pattern'
	);
	assert.match(
		source,
		/data-active=\{active\}/,
		'data-active={active}-Bindung fehlt — Vorbild Segmented/Pill'
	);
	assert.match(
		source,
		/aria-pressed=\{active\}/,
		'aria-pressed={active}-Bindung fehlt — fuer Screenreader noetig'
	);
	assert.match(
		source,
		/data-day=\{day\}/,
		'data-day={day}-Bindung fehlt — fuer per-Tag-Selektoren in E2E noetig'
	);
});

// --- onclick-Callback (Pflicht-Prop) -------------------------------------

test('HorizonChip akzeptiert onclick-Callback und ruft ihn am Button auf', () => {
	const source = loadSource();
	// $props() muss `onclick` als Pflicht-Prop deklarieren.
	assert.match(
		source,
		/onclick\s*:\s*\(\s*\)\s*=>\s*void/,
		'onclick-Prop fehlt in den Props oder hat falsche Signatur (() => void)'
	);
	// Der <button> muss das onclick weiterreichen.
	assert.match(
		source,
		/<button[^>]*\{onclick\}/s,
		'Der <button> muss {onclick} weiterreichen (Svelte-5-Shorthand)'
	);
});

// --- Disabled-State (Spec §1 Props + Style-Selektor) ---------------------

test('HorizonChip unterstuetzt disabled-Prop am Button und :disabled-Style', () => {
	const source = loadSource();
	// disabled muss als Prop deklariert sein (default false).
	assert.match(
		source,
		/disabled\s*\??\s*:\s*boolean/,
		'disabled-Prop fehlt in den Props (disabled?: boolean)'
	);
	// Der <button> muss das disabled-Attribut weiterreichen (Svelte-5-Shorthand).
	assert.match(
		source,
		/<button[^>]*\{disabled\}/s,
		'Der <button> muss {disabled} weiterreichen — sonst ist der Chip nie deaktivierbar'
	);
	// Es muss einen :disabled-Style-Selektor geben (visuelles Feedback).
	assert.match(
		source,
		/\[data-slot=['"]horizon-chip['"]\]:disabled/,
		':disabled-Style-Selektor fehlt — deaktivierte Chips brauchen visuelles Feedback'
	);
});

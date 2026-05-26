// TDD RED: Issue #389 — Trip-Detail Atomic Migration (Phase 2 von 6)
//
// Spec: docs/specs/modules/issue_389_trip_detail_atomic.md
//
// TripStatusBadge.svelte soll:
//   AC-1: active-Status mit tone 'accent' (orange) statt 'success' (grün)
//   AC-2: <Pill> mit data-outlined Attribut (outlined-Stil statt gefüllt)
//   AC-4: app.css enthält Rule [data-outlined][data-tone="accent"] { color: var(--g-accent-deep) }
//
// Test-Pattern: Source-Inspection wie TripHeader.spacing.test.ts —
// liest .svelte/.css als String, assertiert auf Markup/CSS-Struktur.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/TripStatusBadge.atomic.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const BADGE = join(here, 'TripStatusBadge.svelte');
const CSS = join(here, '../../../app.css');

const badgeSource = readFileSync(BADGE, 'utf8');
const cssSource = readFileSync(CSS, 'utf8');

// AC-1: active-Status muss auf 'accent' gemappt sein, nicht auf 'success'
test('AC-1: TONE_MAP mappt active auf accent (nicht success)', () => {
	const hasAccentForActive = /active\s*:\s*['"]accent['"]/.test(badgeSource);
	assert.ok(
		hasAccentForActive,
		'TripStatusBadge.svelte: active-Status soll tone "accent" haben, nicht "success"'
	);
});

test('AC-1: TONE_MAP enthält keinen success-Wert mehr für active', () => {
	const hasLegacySuccessForActive = /active\s*:\s*['"]success['"]/.test(badgeSource);
	assert.ok(
		!hasLegacySuccessForActive,
		'TripStatusBadge.svelte: active: "success" darf nicht mehr vorkommen (Regression-Guard)'
	);
});

// AC-2: <Pill> muss data-outlined Attribut haben
test('AC-2: <Pill> hat data-outlined Attribut', () => {
	const hasDataOutlined = /\<Pill[^>]*data-outlined/.test(badgeSource);
	assert.ok(
		hasDataOutlined,
		'TripStatusBadge.svelte: <Pill> muss data-outlined Attribut enthalten'
	);
});

// AC-3: Tone-Zuordnungen für planned/paused/archived unverändert
test('AC-3: planned bleibt auf info gemappt', () => {
	const hasInfoForPlanned = /planned\s*:\s*['"]info['"]/.test(badgeSource);
	assert.ok(hasInfoForPlanned, 'TripStatusBadge.svelte: planned muss tone "info" haben');
});

test('AC-3: paused bleibt auf warning gemappt', () => {
	const hasWarningForPaused = /paused\s*:\s*['"]warning['"]/.test(badgeSource);
	assert.ok(hasWarningForPaused, 'TripStatusBadge.svelte: paused muss tone "warning" haben');
});

test('AC-3: archived bleibt auf default gemappt', () => {
	const hasDefaultForArchived = /archived\s*:\s*['"]default['"]/.test(badgeSource);
	assert.ok(hasDefaultForArchived, 'TripStatusBadge.svelte: archived muss tone "default" haben');
});

// AC-4: app.css muss neue outlined-Rule für accent-Tone enthalten
test('AC-4: app.css enthält [data-outlined][data-tone="accent"] Rule', () => {
	const hasAccentOutlinedRule =
		/\[data-slot="pill"\]\[data-outlined\]\[data-tone="accent"\]/.test(cssSource);
	assert.ok(
		hasAccentOutlinedRule,
		'app.css: fehlende Rule [data-slot="pill"][data-outlined][data-tone="accent"]'
	);
});

test('AC-4: outlined accent Rule nutzt --g-accent-deep (nicht --g-accent direkt)', () => {
	// Extrahiert den Block rund um die accent-outlined Rule
	const ruleMatch = cssSource.match(
		/\[data-slot="pill"\]\[data-outlined\]\[data-tone="accent"\][^}]*\}/
	);
	assert.ok(ruleMatch, 'app.css: [data-outlined][data-tone="accent"] Rule nicht gefunden');
	const ruleBlock = ruleMatch[0];
	const usesAccentDeep = ruleBlock.includes('--g-accent-deep');
	assert.ok(
		usesAccentDeep,
		`app.css: outlined accent Rule soll --g-accent-deep nutzen (WCAG-AA), gefunden: ${ruleBlock}`
	);
});

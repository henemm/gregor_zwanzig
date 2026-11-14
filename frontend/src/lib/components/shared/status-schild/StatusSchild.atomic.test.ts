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
// Umgehängt durch #2837 S1b (Spec rework_2837_s1b_status_profil.md): vormals
// trip-detail/TripStatusBadge.atomic.test.ts; TripStatusBadge ist im geteilten StatusSchild
// aufgegangen. Zusicherungen unverändert; die gerenderte Fassung samt Kontrast steht in
// __tests__/status_schild.test.ts.
//
// #2980 (Fix-Loop Bildabgleich c2, Spec feat_2913_c2_seitenkopf.md AC-21, ADR-0118, Mockup
// Z. 41–43/326): das Schild ist jetzt GEFÜLLT ohne Rahmen, aktiv = good, alles andere neutral.
// AC-1/AC-2/AC-3 unten sind bewusst auf dieses Soll gezogen (vormals accent/umrandet/info/warning);
// die gerenderte Fassung samt Kaskade und Kontrast hell/dunkel steht in __tests__/status_schild.test.ts.
// AC-4 (app.css-Regel für umrandete accent-Pills) bleibt: andere Konsumenten nutzen sie weiter.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/shared/status-schild/StatusSchild.atomic.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const BADGE = join(here, 'StatusSchild.svelte');
const CSS = join(here, '../../../../app.css');

// Lesefehler (Datei fehlt) als klare Meldung je Test statt Absturz der ganzen Datei.
let badgeSource = '';
try {
	badgeSource = readFileSync(BADGE, 'utf8');
} catch (e) {
	badgeSource = `/* ${BADGE} nicht lesbar: ${(e as Error).message} */`;
}
const cssSource = readFileSync(CSS, 'utf8');

// AC-1 (#2980 AC-21): active-Status ist der good-Ton (Mockup .pill.good), nicht mehr accent
test('AC-1 (#2980): TONE_MAP mappt active auf good (nicht accent)', () => {
	const hasGoodForActive = /active\s*:\s*['"]good['"]/.test(badgeSource);
	assert.ok(
		hasGoodForActive,
		'StatusSchild.svelte: active-Status soll tone "good" haben (#2980 AC-21, Mockup Z. 326), nicht "accent"'
	);
});

test('AC-1: TONE_MAP enthält keinen success-Wert mehr für active', () => {
	const hasLegacySuccessForActive = /active\s*:\s*['"]success['"]/.test(badgeSource);
	assert.ok(
		!hasLegacySuccessForActive,
		'StatusSchild.svelte: active: "success" darf nicht mehr vorkommen (Regression-Guard)'
	);
});

// AC-2 (#2980 AC-21): <Pill> ist gefüllt — KEIN data-outlined mehr
test('AC-2 (#2980): <Pill> ohne data-outlined (gefüllt ohne Rahmen)', () => {
	const hasDataOutlined = /\<Pill[^>]*data-outlined/.test(badgeSource);
	assert.ok(
		!hasDataOutlined,
		'StatusSchild.svelte: <Pill> trägt noch data-outlined — #2980 AC-21 verlangt die gefüllte Pill'
	);
});

// AC-3 (#2980 AC-21): alle Zustände außer active sind neutral
for (const zustand of ['draft', 'planned', 'paused', 'finished', 'archived']) {
	test(`AC-3 (#2980): ${zustand} ist auf neutral gemappt`, () => {
		const neutral = new RegExp(`${zustand}\\s*:\\s*['"]neutral['"]`).test(badgeSource);
		assert.ok(neutral, `StatusSchild.svelte: ${zustand} muss tone "neutral" haben (#2980 AC-21, Mockup Z. 326)`);
	});
}

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

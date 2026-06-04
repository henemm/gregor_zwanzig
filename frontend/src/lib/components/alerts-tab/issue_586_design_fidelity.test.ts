// TDD RED — Issue #586: Alert-Config Design-Fidelity 1:1 nach screen-alert-config.jsx
//
// Spec: docs/specs/modules/issue_586_alert_config_design.md
//
// Source-Inspection-Tests: prüfen ob Layout/Styles/Tokens mit JSX-Vorlage übereinstimmen.
// Vor der Implementierung SCHEITERN AC-1 bis AC-9 (RED).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/alerts-tab/issue_586_design_fidelity.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

// ../../../.. geht von alerts-tab/ → components/ → lib/ → src/ → frontend/
const ROOT = fileURLToPath(new URL('../../../..', import.meta.url)); // -> frontend root

function readFile(relPath: string): string {
	return readFileSync(join(ROOT, 'src', relPath), 'utf-8');
}

// ---------------------------------------------------------------------------
// AC-1: Desktop-H1 nicht via display:none versteckt
// ---------------------------------------------------------------------------

test('AC-1: AlertsTab enthält H1 "Wann soll ein Alert ausgelöst werden?" nicht mobile-only', () => {
	const src = readFile('lib/components/alerts-tab/AlertsTab.svelte');
	assert.ok(
		src.includes('Wann soll ein Alert ausgelöst werden?'),
		'AlertsTab muss H1 "Wann soll ein Alert ausgelöst werden?" enthalten'
	);
	// Desktop-Header darf nicht ausschließlich in einem @media (max-width: 899px)-Block leben.
	// Test: Der H1-Text muss auch außerhalb des mobile-only Blocks definiert sein.
	// Prüfung: class "desktop-h1" oder "alerts-h1" (nicht "mobile-h1") muss existieren.
	const hasDesktopH1 = src.includes('desktop-h1') || src.includes('desktop-header');
	assert.ok(
		hasDesktopH1,
		'AlertsTab.svelte muss einen Desktop-Header-Block mit H1 haben (class "desktop-h1" oder "desktop-header"), nicht nur mobile-only'
	);
});

// ---------------------------------------------------------------------------
// AC-2: ModeCard-Grid auf Desktop sichtbar (nicht display:none)
// ---------------------------------------------------------------------------

test('AC-2: mode-picker ist NICHT standardmäßig display:none', () => {
	const src = readFile('lib/components/alerts-tab/AlertsTab.svelte');
	// Prüfen dass das Standard-(außerhalb @media)-CSS für mode-picker NICHT "display: none" setzt
	// Einfache Heuristik: In der globalen CSS-Section darf ".mode-picker {\n\tdisplay: none" nicht stehen
	const defaultDisplayNone = /\.mode-picker\s*\{[^}]*display:\s*none/s.test(src);
	assert.equal(
		defaultDisplayNone,
		false,
		'AlertsTab.svelte: .mode-picker darf nicht mehr display:none als Default haben — es muss auf Desktop sichtbar sein'
	);
});

test('AC-2b: mode-picker hat display:grid für 3-Spalten-Layout', () => {
	const src = readFile('lib/components/alerts-tab/AlertsTab.svelte');
	assert.ok(
		src.includes('grid-template-columns: repeat(3, 1fr)') ||
		src.includes('grid-template-columns:repeat(3,1fr)'),
		'AlertsTab.svelte: .mode-picker muss grid-template-columns: repeat(3, 1fr) für das 3-Spalten-Desktop-Layout haben'
	);
});

// ---------------------------------------------------------------------------
// AC-3: Aktive ModeCard — Accent-Border, Radio-Dot, Titel in accent-deep
// ---------------------------------------------------------------------------

test('AC-3: ModeCard.active hat 2px Accent-Border', () => {
	const src = readFile('lib/components/alerts-tab/AlertsTab.svelte');
	// JSX: border: `2px solid var(--g-accent)` bei active
	assert.ok(
		src.includes('2px solid var(--g-accent)'),
		'AlertsTab.svelte: .mode-card.active muss "2px solid var(--g-accent)" als Border haben'
	);
});

test('AC-3b: ModeCard hat Radio-Dot-Element im Template', () => {
	const src = readFile('lib/components/alerts-tab/AlertsTab.svelte');
	assert.ok(
		src.includes('mode-radio-dot') || src.includes('radio-dot'),
		'AlertsTab.svelte: ModeCard muss einen Radio-Dot-Span enthalten (class "mode-radio-dot" oder "radio-dot")'
	);
});

test('AC-3c: Aktiver ModeCard-Titel in --g-accent-deep', () => {
	const src = readFile('lib/components/alerts-tab/AlertsTab.svelte');
	assert.ok(
		src.includes('--g-accent-deep'),
		'AlertsTab.svelte: aktive ModeCard muss Titel-Farbe "var(--g-accent-deep)" setzen'
	);
});

// ---------------------------------------------------------------------------
// AC-4: AlertMetricTable — Card-Wrapper + Header-Row mit --g-card-alt
// ---------------------------------------------------------------------------

test('AC-4: AlertMetricTable importiert Card-Atom', () => {
	const src = readFile('lib/components/alerts-tab/AlertMetricTable.svelte');
	assert.ok(
		src.includes("from '$lib/components/atoms'") ||
		src.includes('from "$lib/components/atoms"'),
		'AlertMetricTable.svelte muss Card (und ggf. Eyebrow) aus $lib/components/atoms importieren'
	);
});

test('AC-4b: AlertMetricTable hat Header-Row mit --g-card-alt', () => {
	const src = readFile('lib/components/alerts-tab/AlertMetricTable.svelte');
	assert.ok(
		src.includes('--g-card-alt'),
		'AlertMetricTable.svelte muss eine Header-Row mit background var(--g-card-alt) enthalten'
	);
});

test('AC-4c: AlertMetricTable enthält Eyebrow-Label "Δ-Änderung"', () => {
	const src = readFile('lib/components/alerts-tab/AlertMetricTable.svelte');
	assert.ok(
		src.includes('Δ-Änderung') || src.includes('Δ-Änderung'),
		'AlertMetricTable.svelte muss Eyebrow-Label "Δ-Änderung (seit letztem Briefing)" in der Header-Row haben'
	);
});

// ---------------------------------------------------------------------------
// AC-5: AlertMetricRow — 4-Spalten-Grid, disabled opacity, "— deaktiviert —"
// ---------------------------------------------------------------------------

test('AC-5: AlertMetricRow hat 4-Spalten-Grid "32px 200px 1fr 1fr"', () => {
	const src = readFile('lib/components/alerts-tab/AlertMetricRow.svelte');
	assert.ok(
		src.includes('32px 200px 1fr 1fr'),
		'AlertMetricRow.svelte muss grid-template-columns: 32px 200px 1fr 1fr haben (nach JSX)'
	);
});

test('AC-5b: AlertMetricRow zeigt "— deaktiviert —" wenn Delta/Abs inaktiv', () => {
	const src = readFile('lib/components/alerts-tab/AlertMetricRow.svelte');
	assert.ok(
		src.includes('deaktiviert'),
		'AlertMetricRow.svelte muss den Text "— deaktiviert —" zeigen wenn delta/abs disabled ist'
	);
});

test('AC-5c: AlertMetricRow hat Zeilen-Toggle (row-switch oder row-enabled)', () => {
	const src = readFile('lib/components/alerts-tab/AlertMetricRow.svelte');
	assert.ok(
		src.includes('row-switch') || src.includes('rowEnabled') || src.includes('row-enabled'),
		'AlertMetricRow.svelte muss einen Zeilen-Toggle (row-switch/rowEnabled) für enabled/disabled der ganzen Zeile haben'
	);
});

// ---------------------------------------------------------------------------
// AC-6: AlertCooldownCard — Eyebrow, JSX-Hint-Text, Mono-Input
// ---------------------------------------------------------------------------

test('AC-6: AlertCooldownCard hat Eyebrow-Atom statt h4', () => {
	const src = readFile('lib/components/alerts-tab/AlertCooldownCard.svelte');
	assert.equal(
		src.includes('<h4'),
		false,
		'AlertCooldownCard.svelte darf kein <h4> mehr verwenden — Eyebrow-Atom verwenden'
	);
	assert.ok(
		src.includes('Eyebrow') || src.includes('eyebrow'),
		'AlertCooldownCard.svelte muss Eyebrow-Atom oder eyebrow-CSS-Klasse für den Titel verwenden'
	);
});

test('AC-6b: AlertCooldownCard Hint-Text entspricht JSX', () => {
	const src = readFile('lib/components/alerts-tab/AlertCooldownCard.svelte');
	assert.ok(
		src.includes('zappelnden Werten') || src.includes('Spam bei zappelnden'),
		'AlertCooldownCard.svelte muss den JSX-Hint-Text enthalten: "verhindert Spam bei zappelnden Werten"'
	);
});

test('AC-6c: AlertCooldownCard Input hat font-family var(--g-font-mono)', () => {
	const src = readFile('lib/components/alerts-tab/AlertCooldownCard.svelte');
	assert.ok(
		src.includes('--g-font-mono'),
		'AlertCooldownCard.svelte muss den Cooldown-Input mit font-family: var(--g-font-mono) stylen'
	);
});

// ---------------------------------------------------------------------------
// AC-7: AlertQuietHoursCard — Eyebrow, JSX-Hint-Text, Mono-Inputs
// ---------------------------------------------------------------------------

test('AC-7: AlertQuietHoursCard hat Eyebrow-Atom statt h4', () => {
	const src = readFile('lib/components/alerts-tab/AlertQuietHoursCard.svelte');
	assert.equal(
		src.includes('<h4'),
		false,
		'AlertQuietHoursCard.svelte darf kein <h4> mehr verwenden — Eyebrow-Atom verwenden'
	);
});

test('AC-7b: AlertQuietHoursCard Hint-Text entspricht JSX', () => {
	const src = readFile('lib/components/alerts-tab/AlertQuietHoursCard.svelte');
	assert.ok(
		src.includes('Morgen-Briefing') || src.includes('nächsten Morgen'),
		'AlertQuietHoursCard.svelte muss den JSX-Hint-Text enthalten: "gestaute Alerts gehen mit dem nächsten Morgen-Briefing mit"'
	);
});

test('AC-7c: AlertQuietHoursCard Time-Inputs haben --g-font-mono', () => {
	const src = readFile('lib/components/alerts-tab/AlertQuietHoursCard.svelte');
	assert.ok(
		src.includes('--g-font-mono'),
		'AlertQuietHoursCard.svelte muss die Time-Inputs mit font-family: var(--g-font-mono) stylen'
	);
});

// ---------------------------------------------------------------------------
// AC-8: app.css — Token --g-info-deep definiert
// ---------------------------------------------------------------------------

test('AC-8: app.css enthält Token --g-info-deep', () => {
	const src = readFile('app.css');
	assert.ok(
		src.includes('--g-info-deep'),
		'app.css muss den Token --g-info-deep definieren (dunkles Blau, Variante zu --g-info)'
	);
});

// ---------------------------------------------------------------------------
// AC-9: AlertsTab enthält zwei SectionH-Elemente
// ---------------------------------------------------------------------------

test('AC-9: AlertsTab enthält SectionH mit eyebrow="Auslöse-Modus"', () => {
	const src = readFile('lib/components/alerts-tab/AlertsTab.svelte');
	assert.ok(
		src.includes('Auslöse-Modus') || src.includes('Auslöse-Modus'),
		'AlertsTab.svelte muss ein SectionH mit eyebrow="Auslöse-Modus" vor dem ModeCard-Grid haben'
	);
});

test('AC-9b: AlertsTab enthält SectionH mit eyebrow="Schwellwerte"', () => {
	const src = readFile('lib/components/alerts-tab/AlertsTab.svelte');
	assert.ok(
		src.includes('Schwellwerte'),
		'AlertsTab.svelte muss ein SectionH mit eyebrow="Schwellwerte" vor der AlertMetricTable haben'
	);
});

test('AC-9c: AlertsTab importiert SectionH aus atoms', () => {
	const src = readFile('lib/components/alerts-tab/AlertsTab.svelte');
	assert.ok(
		src.includes('SectionH'),
		'AlertsTab.svelte muss SectionH importieren und verwenden'
	);
});

// ---------------------------------------------------------------------------
// AC-10: Bestehende Tests laufen weiterhin grün (Smoke-Check auf Datei-Existenz)
// ---------------------------------------------------------------------------

test('AC-10: alertMetricTable.ts existiert und enthält METRIC_DEFAULTS unverändert', () => {
	const src = readFile('lib/components/alerts-tab/alertMetricTable.ts');
	assert.ok(src.includes('METRIC_DEFAULTS'), 'alertMetricTable.ts muss METRIC_DEFAULTS exportieren');
	assert.ok(src.includes('ALL_ALERT_METRICS'), 'alertMetricTable.ts muss ALL_ALERT_METRICS exportieren');
	assert.ok(src.includes('alertRulesToRowState'), 'alertMetricTable.ts muss alertRulesToRowState exportieren');
});

test('AC-10b: alertPreviewHelpers.ts existiert und enthält buildAlertPreviewPayload', () => {
	const src = readFile('lib/components/alerts-tab/alertPreviewHelpers.ts');
	assert.ok(
		src.includes('buildAlertPreviewPayload'),
		'alertPreviewHelpers.ts muss buildAlertPreviewPayload exportieren (unverändert)'
	);
});

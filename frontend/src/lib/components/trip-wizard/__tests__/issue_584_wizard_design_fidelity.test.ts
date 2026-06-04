// TDD RED — Issue #584: Trip-Wizard Design-Fidelity 1:1 nach screen-trip-wizard.jsx
// SPEC: docs/specs/modules/issue_584_trip_wizard_design_fidelity.md
//
// Source-Inspection-Tests (bewährtes Muster aus #430/#432/#435).
// Prüft Shell, Stepper, Step1, Step3, Step4, Step5 gegen JSX-Vorlage.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_584_wizard_design_fidelity.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const SHELL  = join(here, '..', 'TripWizardShell.svelte');
const STEPPER = join(here, '..', 'Stepper.svelte');
const STEP1  = join(here, '..', 'steps', 'Step1Profile.svelte');
const STEP3  = join(here, '..', 'steps', 'Step3Weather.svelte');
const STEP4  = join(here, '..', 'steps', 'Step4Layout.svelte');
const STEP5  = join(here, '..', 'steps', 'Step5Reports.svelte');

const readShell  = () => readFileSync(SHELL, 'utf-8');
const readStepper = () => readFileSync(STEPPER, 'utf-8');
const readStep1  = () => readFileSync(STEP1, 'utf-8');
const readStep3  = () => readFileSync(STEP3, 'utf-8');
const readStep4  = () => readFileSync(STEP4, 'utf-8');
const readStep5  = () => readFileSync(STEP5, 'utf-8');

// =============================================================================
// AC-1: Shell — max-width 1180, padding 32px 80px 60px, TopoBg opacity 0.16
// =============================================================================

test('AC-1: Shell enthält max-width 1180 oder maxWidth: 1180', () => {
	const src = readShell();
	const has = src.includes('1180') || src.includes('max-w-[1180px]');
	assert.ok(has, 'Shell muss maxWidth: 1180 aus dem JSX übernehmen (aktuell: max-w-3xl = 768px)');
});

test('AC-1: Shell hat padding 80px seitlich (80px oder px-20)', () => {
	const src = readShell();
	// JSX: padding: "32px 80px 60px" — entspricht px-20 (80px) in Tailwind oder inline style
	const has = src.includes('px-20') || src.includes('80px') || src.includes('padding: "32px 80px');
	assert.ok(has, 'Shell muss seitliches Padding 80px haben (aktuell: px-4)');
});

test('AC-1: Shell-TopoBg hat opacity 0.16 (nicht 0.4)', () => {
	const src = readShell();
	const has0_16 = src.includes('0.16') || src.includes('opacity={0.16}');
	const has0_4  = src.includes('opacity={0.4}') || src.includes('opacity={0.40}');
	assert.ok(has0_16, 'TopoBg muss opacity={0.16} haben (aktuell: 0.4)');
	assert.ok(!has0_4,  'TopoBg opacity={0.4} muss entfernt sein');
});

// =============================================================================
// AC-2: Stepper — Dot-Optik nach JSX (✓-Text, Mono-Zahlen, volle Verbindungslinien)
// =============================================================================

test('AC-2: Stepper done-Dot zeigt "✓" Text (nicht CheckIcon)', () => {
	const src = readStepper();
	const hasCheckmark = src.includes('"✓"') || src.includes("'✓'") || src.includes('>✓<');
	const hasCheckIcon = src.includes('CheckIcon') || src.includes('check-icon') || src.includes("from '@lucide");
	assert.ok(hasCheckmark, 'Stepper done-Dot muss "✓" Text zeigen (JSX: state === "done" ? "✓" : step.n)');
	assert.ok(!hasCheckIcon, 'CheckIcon-Import muss entfernt sein — JSX verwendet Text ✓');
});

test('AC-2: Stepper done-Dot hat g-paper Hintergrund + g-ink-3 Border (kein Farbfill)', () => {
	const src = readStepper();
	// JSX: done = { bg: "var(--g-paper)", border: "1.5px solid var(--g-ink-3)" }
	// Aktuell: bg-[var(--g-success)]/15
	const hasSuccess15 = src.includes('--g-success)]/15') || src.includes('g-success)/15');
	assert.ok(!hasSuccess15, 'done-Dot darf kein g-success/15 Background haben — JSX: g-paper + g-ink-3 Border');
});

test('AC-2: Stepper active-Dot hat Mono-Font für die Zahl', () => {
	const src = readStepper();
	// JSX: fontFamily: state === "done" ? var(--g-font-sans) : var(--g-font-mono) für Zahlen
	const hasMono = src.includes('g-font-mono') || src.includes('font-mono');
	assert.ok(hasMono, 'Stepper active/upcoming-Dots müssen Mono-Font für Nummern verwenden');
});

test('AC-2: Stepper Verbindungslinien sind flex:1 breit (nicht festes w-6)', () => {
	const src = readStepper();
	// JSX: flex: 1, height: 1px — volle Breite zwischen Dots
	// Aktuell: class="...w-6 h-0.5..."
	const hasW6 = /\bw-6\b/.test(src);
	assert.ok(!hasW6, 'Stepper Verbindungslinien müssen flex-1 breit sein (JSX: flex: 1), nicht festes w-6');
});

// =============================================================================
// AC-3: Step 1 Drop-Zone — dashed accent-border, accent-tint, WizUploadGlyph
// =============================================================================

test('AC-3: Step1 Drop-Zone hat dashed accent border (border-accent oder 1.5px dashed)', () => {
	const src = readStep1();
	const hasDashed = src.includes('border-dashed') && (src.includes('--g-accent') || src.includes('accent'));
	assert.ok(hasDashed, 'Drop-Zone muss dashed accent border haben (JSX: 1.5px dashed var(--g-accent))');
});

test('AC-3: Step1 Drop-Zone hat accent-tint Hintergrund', () => {
	const src = readStep1();
	const hasAccentTint = src.includes('--g-accent-tint') || src.includes('accent-tint');
	assert.ok(hasAccentTint, 'Drop-Zone muss background: var(--g-accent-tint) haben (JSX)');
});

test('AC-3: Step1 enthält WizUploadGlyph SVG (Pfeil-nach-oben + Tray, stroke accent-deep)', () => {
	const src = readStep1();
	// JSX: <svg> mit <path d="M12 16V4M7 9l5-5 5 5"/> und Tray-Pfad
	const hasSvg = src.includes('<svg') && (src.includes('M12 16V4') || src.includes('stroke'));
	const hasLucideUpload = src.includes('UploadIcon') || src.includes('upload');
	// Soll: SVG mit accent-deep stroke; nicht: LucideIcon
	assert.ok(hasSvg, 'Drop-Zone muss WizUploadGlyph-SVG enthalten (JSX: stroke var(--g-accent-deep))');
	assert.ok(!hasLucideUpload || hasSvg, 'UploadIcon (Lucide) soll durch WizUploadGlyph SVG ersetzt werden');
});

// =============================================================================
// AC-4: Step 1 GPX-Loaded-State Card
// =============================================================================

test('AC-4: Step1 hat GPX-Loaded-State Card mit accent-tint GPX-Badge', () => {
	const src = readStep1();
	// JSX: wenn gpxLoaded=true → Card mit "GPX"-Badge in accent-tint + "Andere Datei wählen"-Button
	const hasAccentTintBadge = src.includes('accent-tint') || src.includes('--g-accent-tint');
	const hasGpxText = src.includes('GPX') || src.includes('gpx');
	const hasAndereBtn = src.includes('Andere Datei wählen') || src.includes('Andere Datei');
	assert.ok(hasAndereBtn, 'GPX-Loaded-State muss "Andere Datei wählen"-Button haben (JSX)');
	assert.ok(hasAccentTintBadge && hasGpxText, 'GPX-Loaded-State muss accent-tint GPX-Badge haben');
});

// =============================================================================
// AC-5: Step 3 — 2-Spalten-Grid für Aktivitätsprofil + Beschreibungstext
// =============================================================================

test('AC-5: Step3 Aktivitätsprofil hat 2-Spalten-Layout (260px + 1fr)', () => {
	const src = readStep3();
	// JSX: gridTemplateColumns: "260px 1fr", gap: 32
	const has260 = src.includes('260px') || src.includes('grid-cols-[260px_1fr]');
	assert.ok(has260, 'Step3 Aktivitätsprofil-Sektion muss 2-Spalten-Grid mit 260px haben (JSX)');
});

test('AC-5: Step3 hat Beschreibungstext rechts neben dem Profil-Dropdown', () => {
	const src = readStep3();
	// JSX: "Standard-Metriken werden verwendet. Wähle ein Profil für eine kuratierte Auswahl"
	const hasDesc = src.includes('Standard-Metriken werden verwendet') || src.includes('kuratierte Auswahl') || src.includes('kuratierte');
	assert.ok(hasDesc, 'Step3 muss Beschreibungstext "Standard-Metriken werden verwendet..." rechts zeigen (JSX)');
});

// =============================================================================
// AC-6: Step 3 — Gruppen-Header mit g-card-alt, sticky
// =============================================================================

test('AC-6: Step3 Gruppen-Header hat g-card-alt Hintergrund', () => {
	const src = readStep3();
	// JSX: background: "var(--g-card-alt)", borderBottom: "1px solid var(--g-rule-soft)"
	const hasCardAlt = src.includes('--g-card-alt') || src.includes('g-card-alt');
	assert.ok(hasCardAlt, 'Metric-Gruppen-Header muss background: var(--g-card-alt) haben (JSX)');
});

test('AC-6: Step3 Metrik-Row zeigt g-card Hintergrund wenn enabled, opacity 0.55 wenn disabled', () => {
	const src = readStep3();
	// JSX: background: state.enabled ? "var(--g-card)" : "transparent", opacity: state.enabled ? 1 : 0.55
	const hasOpacity55 = src.includes('0.55') || src.includes('opacity-55');
	assert.ok(hasOpacity55, 'Disabled-Metrik-Rows müssen opacity: 0.55 haben (JSX)');
});

// =============================================================================
// AC-7: Step 4 — Channel-Tabs als 4-Spalten-Grid
// =============================================================================

test('AC-7: Step4 Channel-Tabs sind in grid repeat(4, 1fr)', () => {
	const src = readStep4();
	// JSX: display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 0
	const hasGrid4 = src.includes('repeat(4, 1fr)') || src.includes('grid-cols-4') || src.includes('grid-cols-[repeat(4,');
	assert.ok(hasGrid4, 'Channel-Tabs müssen in einem 4-Spalten-Grid sein (JSX: repeat(4, 1fr))');
});

test('AC-7: Step4 aktiver Channel-Tab hat borderBottom accent (2px solid var(--g-accent))', () => {
	const src = readStep4();
	// JSX: borderBottom: active ? "2px solid var(--g-accent)" : "2px solid transparent"
	const hasAccentBorderBottom = (src.includes('border-b-2') || src.includes('borderBottom')) &&
		(src.includes('--g-accent') || src.includes('g-accent'));
	assert.ok(hasAccentBorderBottom, 'Aktiver Channel-Tab muss borderBottom: 2px solid var(--g-accent) haben (JSX)');
});

// =============================================================================
// AC-8: Step 4 — 2-Spalten-Body mit sticky Preview
// =============================================================================

test('AC-8: Step4 Body hat 2-Spalten-Grid (1fr 380px)', () => {
	const src = readStep4();
	// JSX: gridTemplateColumns: "1fr 380px", gap: 28
	const has380 = src.includes('380px') || src.includes('grid-cols-[1fr_380px]');
	assert.ok(has380, 'Step4 Body muss 2-Spalten-Grid mit 380px Preview-Spalte haben (JSX)');
});

test('AC-8: Step4 Preview-Panel ist position sticky top 24', () => {
	const src = readStep4();
	// JSX: position: "sticky", top: 24
	const hasSticky = src.includes('sticky') && (src.includes('top-6') || src.includes('top: 24') || src.includes('top-[24px]'));
	assert.ok(hasSticky, 'Preview-Panel muss position: sticky, top: 24 haben (JSX)');
});

// =============================================================================
// AC-9: Step 5 — Cards mit korrekten Titeln und Sub-Texten
// =============================================================================

test('AC-9: Step5 Abend-Card hat Titel "Vor dem Schlafen" und Sub-Text über Plan', () => {
	const src = readStep5();
	const hasTitle = src.includes('Vor dem Schlafen');
	const hasSub   = src.includes('Plan & Vorhersage für morgen') || src.includes('Plan &amp; Vorhersage');
	assert.ok(hasTitle, 'Abend-Card muss Titel "Vor dem Schlafen" haben (JSX)');
	assert.ok(hasSub,   'Abend-Card muss Sub-Text "Plan & Vorhersage für morgen." haben (JSX)');
});

test('AC-9: Step5 Morgen-Card hat Titel "Vor Etappenstart" und Sub-Text über aktuelle Bedingungen', () => {
	const src = readStep5();
	assert.ok(src.includes('Vor Etappenstart'),        'Morgen-Card muss Titel "Vor Etappenstart" haben (JSX)');
	assert.ok(src.includes('Aktuelle Bedingungen') || src.includes('aktuelle Bedingungen'),
		'Morgen-Card muss Sub-Text "Aktuelle Bedingungen für heute." haben (JSX)');
});

test('AC-9: Step5 Warnungs-Card hat Titel "Sofort, wenn nötig"', () => {
	const src = readStep5();
	assert.ok(src.includes('Sofort, wenn nötig'), 'Warnungs-Card muss Titel "Sofort, wenn nötig" haben (JSX)');
});

// =============================================================================
// AC-10: Step 5 — Uhrzeit als große Mono-Zahl mit "24h"-Label
// =============================================================================

test('AC-10: Step5 Uhrzeit-Anzeige hat fontSize 22 oder text-[22px] (große Mono-Zahl)', () => {
	const src = readStep5();
	// JSX: fontSize: 22, fontWeight: 600, fontFamily: mono
	const hasBig = src.includes('text-[22px]') || src.includes('fontSize: 22') || src.includes('font-size: 22') || src.includes('text-2xl');
	// Aktuell: <input type="time"> — soll ersetzt werden durch Anzeige + "Ändern"-Button
	assert.ok(hasBig, 'Uhrzeit-Anzeige muss als große Mono-Zahl (22px/text-2xl) dargestellt werden (JSX)');
});

test('AC-10: Step5 enthält "24h"-Label neben der Uhrzeit', () => {
	const src = readStep5();
	const has24h = src.includes('24h');
	assert.ok(has24h, 'Uhrzeit-Anzeige muss "24h"-Label daneben haben (JSX)');
});

test('AC-10: Step5 hat "Ändern"-Button neben der Uhrzeit', () => {
	const src = readStep5();
	const hasAendern = src.includes('Ändern');
	assert.ok(hasAendern, 'Neben der Uhrzeit muss ein "Ändern"-Button stehen (JSX)');
});

// =============================================================================
// AC-11: Step 5 — Trend-Toggle in eigenem g-card-alt Block
// =============================================================================

test('AC-11: Step5 Trend-Toggle-Block hat g-card-alt Hintergrund + g-rule-soft Border', () => {
	const src = readStep5();
	// JSX: background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)"
	// Aktuell: Trend-Toggle ist nur Checkbox ohne eigenen Block
	const hasCardAlt = src.includes('--g-card-alt') || src.includes('g-card-alt');
	const hasRuleSoft = src.includes('--g-rule-soft') || src.includes('g-rule-soft');
	assert.ok(hasCardAlt, 'Trend-Toggle muss in eigenem g-card-alt Block sein (JSX)');
	assert.ok(hasRuleSoft, 'Trend-Toggle-Block muss g-rule-soft Border haben (JSX)');
});

// =============================================================================
// AC-12: Step 5 — span-Chips statt Checkbox-Labels für Kanal-Chips
// =============================================================================

test('AC-12: Step5 Kanal-Chips sind <span>-Elemente mit accent-tint (aktiv) und rule-Border (inaktiv)', () => {
	const src = readStep5();
	// JSX: <span> mit border: on ? "1px solid var(--g-accent)" : "1px solid var(--g-rule)"
	// background: on ? "var(--g-accent-tint)" : "transparent"
	// Aktuell: <label class="chip"> mit Checkbox inside
	const hasWizChip = src.includes('--g-accent-tint') || src.includes('accent-tint');
	// Muss auch "Signal", "Telegram" als Chip-Labels haben (nicht als Checkbox-Label)
	const hasChannelChips = src.includes('✉ Email') || src.includes('▲ Signal') || src.includes('→ Telegram');
	assert.ok(hasChannelChips, 'Kanal-Chips müssen Icon-Prefix haben: ✉ Email, ▲ Signal, → Telegram (JSX)');
	assert.ok(hasWizChip, 'Aktive Kanal-Chips müssen --g-accent-tint Hintergrund haben (JSX)');
});

// =============================================================================
// AC-13: Footer — 3-Spalten-Grid, "← Zurück", "Tour speichern", Extra-Slot
// =============================================================================

test('AC-13: Shell Footer ist 3-Spalten-Grid (1fr auto 1fr)', () => {
	const src = readShell();
	// JSX: gridTemplateColumns: "1fr auto 1fr"
	// Aktuell: flex justify-between
	const hasGrid3 = src.includes('1fr auto 1fr') || src.includes('grid-cols-[1fr_auto_1fr]');
	assert.ok(hasGrid3, 'Footer muss 3-Spalten-Grid "1fr auto 1fr" sein (JSX), nicht flex justify-between');
});

test('AC-13: Shell Zurück-Button hat Pfeil-Prefix "← Zurück"', () => {
	const src = readShell();
	const hasArrow = src.includes('← Zurück') || src.includes('←');
	assert.ok(hasArrow, 'Zurück-Button muss "← Zurück" mit Pfeil-Prefix heißen (JSX)');
});

test('AC-13: Shell Speichern-Button heißt "Tour speichern" (nicht "Trip speichern")', () => {
	const src = readShell();
	const hasTour = src.includes('Tour speichern');
	const hasTrip = src.includes('Trip speichern');
	assert.ok(hasTour, 'Speichern-Button muss "Tour speichern" heißen (JSX)');
	assert.ok(!hasTrip, '"Trip speichern" muss durch "Tour speichern" ersetzt werden (JSX)');
});

test('AC-13: Shell Footer-Mitte hat Extra-Slot für Step-spezifische Buttons', () => {
	const src = readShell();
	// JSX: WizFooter extra={step === 2 && <Btn variant="ghost">+ Pausentag einfügen</Btn>}
	const hasPausentag = src.includes('Pausentag') || src.includes('pausentag');
	assert.ok(hasPausentag, 'Footer-Mitte muss "Pausentag einfügen"-Button für Step 2 enthalten (JSX)');
});

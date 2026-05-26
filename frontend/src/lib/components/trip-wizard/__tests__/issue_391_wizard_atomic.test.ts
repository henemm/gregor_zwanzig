// TDD RED — Issue #391: Trip-Wizard Atomic-Migration
//
// Source-Inspection-Tests: prüfen ob die Komponenten die Atomic-Library korrekt nutzen.
// Diese Tests MÜSSEN in der RED-Phase fehlschlagen — die Implementation fehlt noch.
//
// AC-1: Stepper done-State zeigt CheckIcon statt Dot
// AC-2: TripWizardShell hat dynamischen H1-Titel + Eyebrow "SCHRITT N VON 4 · NEUE TOUR"
// AC-3: TripWizardShell hat step-spezifische Footer-Hinweistexte
// AC-4: Step1Profile nutzt Field-Molecule für Inputs
// AC-5: StageRow zeigt WP-Count Badge
// AC-6: Step2Stages nutzt Pill-Atom für Vorschläge (nicht inline-span)
// AC-7: Step2Stages hat Platzhalter-Buttons im Header
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_391_wizard_atomic.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dir = dirname(__filename);

// Komponenten als Text einlesen
const stepper   = readFileSync(resolve(__dir, '../Stepper.svelte'),          'utf-8');
const shell     = readFileSync(resolve(__dir, '../TripWizardShell.svelte'),   'utf-8');
const stageRow  = readFileSync(resolve(__dir, '../steps/StageRow.svelte'),    'utf-8');
const step1     = readFileSync(resolve(__dir, '../steps/Step1Profile.svelte'),'utf-8');
const step2     = readFileSync(resolve(__dir, '../steps/Step2Stages.svelte'), 'utf-8');

// ─────────────────────────────────────────────────────────────────
// AC-1: Stepper — done-State: Dot → CheckIcon
// ─────────────────────────────────────────────────────────────────

test('AC-1a: Stepper importiert check Icon aus @lucide/svelte', () => {
  assert.ok(
    stepper.includes("from '@lucide/svelte/icons/check'"),
    'Stepper.svelte muss CheckIcon aus @lucide/svelte/icons/check importieren'
  );
});

test('AC-1b: Stepper enthält kein Dot-Import mehr (durch CheckIcon ersetzt)', () => {
  // Nach Migration: Dot-Import entfernt
  const hasDotImport = stepper.includes("import { Dot }") || stepper.includes("import Dot ");
  assert.ok(
    !hasDotImport,
    'Stepper.svelte darf kein Dot-Atom mehr importieren — wurde durch CheckIcon ersetzt'
  );
});

// ─────────────────────────────────────────────────────────────────
// AC-2: TripWizardShell — dynamischer H1-Titel + Eyebrow-Format
// ─────────────────────────────────────────────────────────────────

test('AC-2a: Shell H1-Text für Schritt 1: "Route — wie kennt das System deinen Weg?"', () => {
  assert.ok(
    shell.includes('Route — wie kennt das System deinen Weg?'),
    'TripWizardShell.svelte muss H1-Titel für Schritt 1 enthalten'
  );
});

test('AC-2b: Shell H1-Text für Schritt 2: "Etappen — stimmt die Tagesaufteilung?"', () => {
  assert.ok(
    shell.includes('Etappen — stimmt die Tagesaufteilung?'),
    'TripWizardShell.svelte muss H1-Titel für Schritt 2 enthalten'
  );
});

test('AC-2c: Shell H1-Text für Schritt 3: "Wetter — welche Daten gehen ins Briefing?"', () => {
  assert.ok(
    shell.includes('Wetter — welche Daten gehen ins Briefing?'),
    'TripWizardShell.svelte muss H1-Titel für Schritt 3 enthalten'
  );
});

test('AC-2d: Shell H1-Text für Schritt 4: "Reports — wann und wohin?"', () => {
  assert.ok(
    shell.includes('Reports — wann und wohin?'),
    'TripWizardShell.svelte muss H1-Titel für Schritt 4 enthalten'
  );
});

test('AC-2e: Shell-Eyebrow enthält "NEUE TOUR" (SCHRITT N VON 4 · NEUE TOUR)', () => {
  assert.ok(
    shell.includes('NEUE TOUR'),
    'TripWizardShell.svelte Eyebrow muss "NEUE TOUR" enthalten (Format: SCHRITT N VON 4 · NEUE TOUR)'
  );
});

// ─────────────────────────────────────────────────────────────────
// AC-3: TripWizardShell — Footer-Hinweistexte
// ─────────────────────────────────────────────────────────────────

test('AC-3a: Shell enthält Footer-Hinweis für Schritt 1 ("GPX-Upload empfohlen")', () => {
  assert.ok(
    shell.includes('GPX-Upload empfohlen'),
    'TripWizardShell.svelte muss Footer-Hinweis "GPX-Upload empfohlen ..." für Schritt 1 enthalten'
  );
});

test('AC-3b: Shell enthält Footer-Hinweis für Schritt 4 ("Unterwegs läuft alles autark")', () => {
  assert.ok(
    shell.includes('Unterwegs läuft alles autark'),
    'TripWizardShell.svelte muss Footer-Hinweis "Unterwegs läuft alles autark..." für Schritt 4 enthalten'
  );
});

test('AC-3c: Shell enthält Footer-Hinweis für Schritt 2 (Wegpunkte-Hinweis)', () => {
  assert.ok(
    shell.includes('Algorithmische Wegpunkte'),
    'TripWizardShell.svelte muss Footer-Hinweis zu algorithmischen Wegpunkten für Schritt 2 enthalten'
  );
});

// ─────────────────────────────────────────────────────────────────
// AC-4: Step1Profile — Field-Molecule für Inputs
// ─────────────────────────────────────────────────────────────────

test('AC-4a: Step1Profile importiert Field aus $lib/components/molecules', () => {
  assert.ok(
    step1.includes('Field') && step1.includes("from '$lib/components/molecules'"),
    'Step1Profile.svelte muss Field aus $lib/components/molecules importieren'
  );
});

test('AC-4b: Step1Profile nutzt <Field> für TRIP-NAME Input', () => {
  assert.ok(
    step1.includes('<Field') && step1.includes('TRIP-NAME'),
    'Step1Profile.svelte muss <Field label="TRIP-NAME"> verwenden'
  );
});

test('AC-4c: Step1Profile nutzt <Field> für REGION Input', () => {
  assert.ok(
    step1.includes('<Field') && (step1.includes('REGION') || step1.includes('region')),
    'Step1Profile.svelte muss <Field> auch für REGION-Eingabe verwenden'
  );
});

// ─────────────────────────────────────────────────────────────────
// AC-5: StageRow — WP-Count Badge
// ─────────────────────────────────────────────────────────────────

test('AC-5a: StageRow enthält WP-Count data-testid', () => {
  assert.ok(
    stageRow.includes('trip-wizard-step2-stage-wp-count-'),
    'StageRow.svelte muss data-testid="trip-wizard-step2-stage-wp-count-{index}" enthalten'
  );
});

test('AC-5b: StageRow WP-Badge ist konditionell (nur wenn waypoints.length > 0)', () => {
  // Badge darf nur erscheinen wenn Waypoints vorhanden — Code muss Bedingung enthalten
  assert.ok(
    stageRow.includes('waypoints.length > 0') ||
    stageRow.includes('waypoints.length'),
    'StageRow.svelte: WP-Badge-Bedingung muss waypoints.length referenzieren'
  );
  // Und der Badge-Text muss "WP" enthalten
  assert.ok(
    stageRow.includes(' WP') || stageRow.includes('>WP<') || stageRow.includes('{stage.waypoints.length} WP'),
    'StageRow.svelte muss "X WP" Badge-Text enthalten'
  );
});

// ─────────────────────────────────────────────────────────────────
// AC-6: Step2Stages — Vorschläge-Pill als Pill-Atom (nicht inline-span)
// ─────────────────────────────────────────────────────────────────

test('AC-6a: Step2Stages importiert Pill-Atom', () => {
  const hasPillImport =
    (step2.includes("from '$lib/components/atoms'") ||
     step2.includes("from '$lib/components/ui/pill'")) &&
    step2.includes('Pill');
  assert.ok(
    hasPillImport,
    'Step2Stages.svelte muss Pill aus $lib/components/atoms oder $lib/components/ui/pill importieren'
  );
});

test('AC-6b: Step2Stages Vorschläge-Element hat data-outlined Attribut (Pill-Atom)', () => {
  assert.ok(
    step2.includes('data-outlined'),
    'Step2Stages.svelte: Vorschläge-Pill muss data-outlined Attribut haben (outlined Pill-Variante)'
  );
});

test('AC-6c: Step2Stages nutzt Pill-Komponente für Vorschläge (kein naked inline-span)', () => {
  // Nach Migration: kein inline-styled span mit accent-border-dashed mehr
  // Der alte Code war: class="shrink-0 rounded-full border border-dashed border-[var(--g-accent)]/60..."
  assert.ok(
    !step2.includes('rounded-full border border-dashed border-[var(--g-accent)]'),
    'Step2Stages.svelte: inline-gestylter Vorschläge-span muss durch Pill-Atom ersetzt sein'
  );
});

// ─────────────────────────────────────────────────────────────────
// AC-7: Step2Stages — Platzhalter-Buttons im Header
// ─────────────────────────────────────────────────────────────────

test('AC-7a: Step2Stages hat Header-Button "Zusammenführen"', () => {
  assert.ok(
    step2.includes('trip-wizard-step2-btn-merge'),
    'Step2Stages.svelte muss Button mit data-testid="trip-wizard-step2-btn-merge" enthalten'
  );
});

test('AC-7b: Step2Stages hat Header-Button "+ Etappe einschieben"', () => {
  assert.ok(
    step2.includes('trip-wizard-step2-btn-insert'),
    'Step2Stages.svelte muss Button mit data-testid="trip-wizard-step2-btn-insert" enthalten'
  );
});

// TDD RED — Issue #443: Compare Wizard Step 5 (Versand + Aktivierung).
// SPEC: docs/specs/modules/issue_443_compare_wizard_step5_versand.md
//
// Source-Inspection-Tests für alle 8 betroffenen Dateien.
// Alle Tests MÜSSEN im RED-Status fehlschlagen, da Step5Versand.svelte noch
// nicht existiert und compareWizardState die neuen Felder noch nicht hat.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_443_step5.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));

// Dateipfade
const STEP5        = join(here, '..', 'steps', 'Step5Versand.svelte');
const STATE        = join(here, '..', 'compareWizardState.svelte.ts');
const SHELL        = join(here, '..', 'CompareWizard.svelte');
const NEW_SERVER   = join(here, '..', '..', '..', '..', 'routes', 'compare', 'new', '+page.server.ts');
const NEW_PAGE     = join(here, '..', '..', '..', '..', 'routes', 'compare', 'new', '+page.svelte');
const EDIT_SERVER  = join(here, '..', '..', '..', '..', 'routes', 'compare', '[id]', 'edit', '+page.server.ts');
const EDIT_PAGE    = join(here, '..', '..', '..', '..', 'routes', 'compare', '[id]', 'edit', '+page.svelte');

function read(path: string, label: string): string {
	if (!existsSync(path)) throw new Error(`${label} nicht gefunden: ${path}`);
	return readFileSync(path, 'utf-8');
}

// =============================================================================
// Step5Versand.svelte — Existenz + TestIDs
// =============================================================================

test('AC-INFRA: Step5Versand.svelte existiert', () => {
	assert.ok(existsSync(STEP5), `Step5Versand.svelte fehlt unter: ${STEP5}`);
});

test('AC-1: Step5 hat Root-Container data-testid="compare-wizard-step-5"', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/data-testid=["']compare-wizard-step-5["']/.test(src),
		'Step5Versand.svelte muss data-testid="compare-wizard-step-5" enthalten'
	);
});

test('AC-1: Step5 hat E-Mail-Toggle mit testid compare-step5-channel-email', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/compare-step5-channel-email/.test(src),
		'Step5 muss compare-step5-channel-email enthalten'
	);
});

// #610: Signal-Kanal entfernt — compare-step5-channel-signal darf nicht mehr vorhanden sein
test('AC-1 #610: Step5 hat keinen Signal-Toggle mehr', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		!/compare-step5-channel-signal/.test(src),
		'Step5 darf nach #610 keinen compare-step5-channel-signal-Toggle mehr enthalten'
	);
});

test('AC-1: Step5 hat Telegram-Toggle mit testid compare-step5-channel-telegram', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/compare-step5-channel-telegram/.test(src),
		'Step5 muss compare-step5-channel-telegram enthalten'
	);
});

test('AC-2: Step5 hat Inline-Error mit testid compare-step5-channel-error', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/compare-step5-channel-error/.test(src),
		'Step5 muss compare-step5-channel-error enthalten (Inline-Error wenn alle Kanäle deaktiviert)'
	);
});

test('AC-3: Step5 hat Zeitfenster-Overlap-Error mit testid compare-step5-time-overlap-error', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/compare-step5-time-overlap-error/.test(src),
		'Step5 muss compare-step5-time-overlap-error enthalten'
	);
});

test('AC-4: Step5 hat Horizont-Dropdown mit testid compare-step5-forecast-hours', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/compare-step5-forecast-hours/.test(src),
		'Step5 muss compare-step5-forecast-hours enthalten'
	);
});

test('AC-4: Horizont-Dropdown enthält Optionen 24, 48 und 72', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(/24/.test(src) && /48/.test(src) && /72/.test(src),
		'Horizont-Dropdown muss Optionen 24h, 48h und 72h enthalten'
	);
});

test('AC-4: Step5 hat Zeitfenster-Start-Input mit testid compare-step5-time-window-start', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/compare-step5-time-window-start/.test(src),
		'Step5 muss compare-step5-time-window-start enthalten'
	);
});

test('AC-4: Step5 hat Zeitfenster-End-Input mit testid compare-step5-time-window-end', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/compare-step5-time-window-end/.test(src),
		'Step5 muss compare-step5-time-window-end enthalten'
	);
});

test('AC-5: Step5 hat Versandzeit-Toggle mit testid compare-step5-schedule', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/compare-step5-schedule/.test(src),
		'Step5 muss compare-step5-schedule enthalten (Morning/Evening-Toggle)'
	);
});

test('AC-5: Versandzeit-Toggle enthält daily_morning und daily_evening', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/daily_morning/.test(src) && /daily_evening/.test(src),
		'Step5 muss daily_morning und daily_evening als Versandzeit-Optionen enthalten'
	);
});

test('AC-6: Step5 hat Aktivierungs-Banner mit testid compare-step5-activation-banner', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/compare-step5-activation-banner/.test(src),
		'Step5 muss compare-step5-activation-banner enthalten'
	);
});

test('AC-6: Aktivierungs-Banner verwendet var(--g-success)', () => {
	// #541: Token-Rename — --g-good wurde durch den kanonischen Namen --g-success ersetzt.
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/--g-success/.test(src),
		'Aktivierungs-Banner muss var(--g-success) verwenden (#541 Token-Rename)'
	);
});

test('AC-6: Aktivierungs-Banner nur im Create-Modus (isEditMode-Check)', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/isEditMode/.test(src),
		'Step5 muss isEditMode prüfen um Banner nur im Create-Modus anzuzeigen'
	);
});

test('AC-9: Step5 liest compare-wizard-profile Context (null-tolerant)', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/'compare-wizard-profile'|"compare-wizard-profile"/.test(src),
		'Step5 muss getContext("compare-wizard-profile") aufrufen'
	);
});

test('AC-10: Step5 importiert maskPhone aus wizardHelpers', () => {
	const src = read(STEP5, 'Step5Versand.svelte');
	assert.ok(
		/maskPhone/.test(src),
		'Step5 muss maskPhone importieren und für Signal/Telegram-Kontaktinfo verwenden'
	);
});

// =============================================================================
// compareWizardState.svelte.ts — Neue $state-Felder + Getter
// =============================================================================

test('AC-1+2: sendEmail als $state-Feld in compareWizardState', () => {
	const src = read(STATE, 'compareWizardState.svelte.ts');
	assert.ok(
		/sendEmail\s*=\s*\$state/.test(src),
		'compareWizardState muss sendEmail als $state-Feld haben'
	);
});

test('AC-1+2: kein sendSignal-Feld mehr in compareWizardState (#610)', () => {
	const src = read(STATE, 'compareWizardState.svelte.ts');
	assert.ok(
		!/sendSignal\s*=\s*\$state/.test(src),
		'compareWizardState darf sendSignal nicht mehr als $state-Feld haben'
	);
});

test('AC-1+2: sendTelegram als $state-Feld in compareWizardState', () => {
	const src = read(STATE, 'compareWizardState.svelte.ts');
	assert.ok(
		/sendTelegram\s*=\s*\$state/.test(src),
		'compareWizardState muss sendTelegram als $state-Feld haben'
	);
});

test('AC-3+4: timeWindowStart als $state-Feld in compareWizardState', () => {
	const src = read(STATE, 'compareWizardState.svelte.ts');
	assert.ok(
		/timeWindowStart\s*=\s*\$state/.test(src),
		'compareWizardState muss timeWindowStart als $state-Feld haben'
	);
});

test('AC-3+4: timeWindowEnd als $state-Feld in compareWizardState', () => {
	const src = read(STATE, 'compareWizardState.svelte.ts');
	assert.ok(
		/timeWindowEnd\s*=\s*\$state/.test(src),
		'compareWizardState muss timeWindowEnd als $state-Feld haben'
	);
});

test('AC-4: forecastHours als $state-Feld in compareWizardState', () => {
	const src = read(STATE, 'compareWizardState.svelte.ts');
	assert.ok(
		/forecastHours\s*=\s*\$state/.test(src),
		'compareWizardState muss forecastHours als $state-Feld haben'
	);
});

test('AC-5: schedule als $state-Feld in compareWizardState', () => {
	const src = read(STATE, 'compareWizardState.svelte.ts');
	assert.ok(
		/schedule\s*=\s*\$state/.test(src),
		'compareWizardState muss schedule als $state-Feld haben'
	);
});

test('AC-2: canAdvanceStep5 Getter in compareWizardState', () => {
	const src = read(STATE, 'compareWizardState.svelte.ts');
	assert.ok(
		/canAdvanceStep5/.test(src),
		'compareWizardState muss canAdvanceStep5 Getter haben'
	);
});

test('AC-2: canAdvanceStep5 prüft sendEmail || sendTelegram || sendSms (#610: kein Signal)', () => {
	const src = read(STATE, 'compareWizardState.svelte.ts');
	const hasCheck = /canAdvanceStep5[\s\S]{0,200}sendEmail[\s\S]{0,50}sendTelegram/.test(src);
	assert.ok(
		hasCheck,
		'canAdvanceStep5 muss sendEmail und sendTelegram prüfen (kein sendSignal mehr)'
	);
	assert.ok(
		!/sendSignal/.test(src.match(/canAdvanceStep5[\s\S]{0,300}/)?.[0] ?? ''),
		'canAdvanceStep5 darf sendSignal nicht mehr referenzieren'
	);
});

test('AC-2: canAdvanceCurrent hat case 5 mit canAdvanceStep5', () => {
	const src = read(STATE, 'compareWizardState.svelte.ts');
	assert.ok(
		/case\s+5\s*:[\s\S]{0,50}canAdvanceStep5/.test(src),
		'canAdvanceCurrent muss case 5 mit canAdvanceStep5 enthalten'
	);
});

test('AC-8: save() liest sendEmail aus State (nicht hardcoded)', () => {
	const src = read(STATE, 'compareWizardState.svelte.ts');
	// Nach der Umstellung darf send_email nicht mehr als `true` literal in save() stehen
	// Stattdessen muss this.sendEmail referenziert werden
	assert.ok(
		/send_email:\s*this\.sendEmail/.test(src),
		'save() muss send_email: this.sendEmail nutzen (nicht hardcoded true)'
	);
});

test('AC-8: save() liest forecastHours aus State (nicht hardcoded)', () => {
	const src = read(STATE, 'compareWizardState.svelte.ts');
	assert.ok(
		/forecast_hours:\s*this\.forecastHours/.test(src),
		'save() muss forecast_hours: this.forecastHours nutzen (nicht hardcoded 48)'
	);
});

// =============================================================================
// CompareWizard.svelte — Step-5-Integration
// =============================================================================

test('AC-INFRA: CompareWizard importiert Step5Versand', () => {
	const src = read(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/Step5Versand/.test(src),
		'CompareWizard.svelte muss Step5Versand importieren'
	);
});

test('AC-1: CompareWizard rendert Step5Versand bei currentStep === 5', () => {
	const src = read(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/currentStep\s*===\s*5[\s\S]{0,100}Step5Versand/.test(src)
		|| /Step5Versand[\s\S]{0,200}currentStep\s*===\s*5/.test(src),
		'CompareWizard muss Step5Versand bei currentStep === 5 rendern'
	);
});

test('AC-2: Activate-Button in CompareWizard ist disabled wenn !canAdvanceStep5', () => {
	const src = read(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/canAdvanceStep5/.test(src),
		'CompareWizard muss canAdvanceStep5 für den Activate-Button verwenden'
	);
});

// =============================================================================
// new/+page.server.ts — Profil laden
// =============================================================================

test('AC-9: compare/new/+page.server.ts lädt /api/auth/profile', () => {
	const src = read(NEW_SERVER, 'compare/new/+page.server.ts');
	assert.ok(
		/\/api\/auth\/profile/.test(src),
		'compare/new/+page.server.ts muss /api/auth/profile laden'
	);
});

test('AC-9: compare/new/+page.server.ts gibt profile zurück', () => {
	const src = read(NEW_SERVER, 'compare/new/+page.server.ts');
	assert.ok(
		/profile/.test(src),
		'compare/new/+page.server.ts muss profile im return-Objekt liefern'
	);
});

// =============================================================================
// new/+page.svelte — Profile-Context setzen
// =============================================================================

test('AC-9: compare/new/+page.svelte setzt compare-wizard-profile Context', () => {
	const src = read(NEW_PAGE, 'compare/new/+page.svelte');
	assert.ok(
		/'compare-wizard-profile'|"compare-wizard-profile"/.test(src),
		'compare/new/+page.svelte muss setContext("compare-wizard-profile", ...) aufrufen'
	);
});

// =============================================================================
// [id]/edit/+page.server.ts — Profil laden
// =============================================================================

test('AC-9: compare/[id]/edit/+page.server.ts lädt /api/auth/profile', () => {
	const src = read(EDIT_SERVER, 'compare/[id]/edit/+page.server.ts');
	assert.ok(
		/\/api\/auth\/profile/.test(src),
		'compare/[id]/edit/+page.server.ts muss /api/auth/profile laden'
	);
});

test('AC-9: compare/[id]/edit/+page.server.ts gibt profile zurück', () => {
	const src = read(EDIT_SERVER, 'compare/[id]/edit/+page.server.ts');
	assert.ok(
		/profile/.test(src),
		'compare/[id]/edit/+page.server.ts muss profile im return-Objekt liefern'
	);
});

// =============================================================================
// [id]/edit/+page.svelte — Context + Prefill
// =============================================================================

test('AC-9: compare/[id]/edit/+page.svelte setzt compare-wizard-profile Context', () => {
	const src = read(EDIT_PAGE, 'compare/[id]/edit/+page.svelte');
	assert.ok(
		/'compare-wizard-profile'|"compare-wizard-profile"/.test(src),
		'compare/[id]/edit/+page.svelte muss setContext("compare-wizard-profile", ...) aufrufen'
	);
});

test('AC-7: compare/[id]/edit/+page.svelte prefüllt sendEmail aus subscription', () => {
	const src = read(EDIT_PAGE, 'compare/[id]/edit/+page.svelte');
	assert.ok(
		/sendEmail\s*=\s*data\.subscription\.send_email/.test(src),
		'edit/+page.svelte muss state.sendEmail = data.subscription.send_email setzen'
	);
});

test('AC-7: compare/[id]/edit/+page.svelte prefüllt forecastHours aus subscription', () => {
	const src = read(EDIT_PAGE, 'compare/[id]/edit/+page.svelte');
	assert.ok(
		/forecastHours\s*=\s*data\.subscription\.forecast_hours/.test(src)
		|| /forecastHours\s*=.*forecast_hours/.test(src),
		'edit/+page.svelte muss state.forecastHours aus data.subscription.forecast_hours setzen'
	);
});

test('AC-7: compare/[id]/edit/+page.svelte prefüllt timeWindowStart aus subscription', () => {
	const src = read(EDIT_PAGE, 'compare/[id]/edit/+page.svelte');
	assert.ok(
		/timeWindowStart\s*=.*time_window_start/.test(src),
		'edit/+page.svelte muss state.timeWindowStart aus data.subscription.time_window_start setzen'
	);
});

test('AC-7: compare/[id]/edit/+page.svelte prefüllt schedule aus subscription', () => {
	const src = read(EDIT_PAGE, 'compare/[id]/edit/+page.svelte');
	assert.ok(
		/schedule\s*=.*data\.subscription\.schedule/.test(src)
		|| /state\.schedule\s*=.*subscription\.schedule/.test(src),
		'edit/+page.svelte muss state.schedule aus data.subscription.schedule setzen'
	);
});

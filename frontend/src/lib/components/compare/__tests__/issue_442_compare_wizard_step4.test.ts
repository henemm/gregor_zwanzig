// TDD RED — Issue #442: Compare-Wizard Step 4 Layout.
// SPEC: docs/specs/modules/issue_442_compare_wizard_step4_layout.md
//
// Source-Inspection-Tests:
//   - Step4Layout.svelte existiert unter compare/steps/
//   - Step4Layout enthält alle 4 Channel-Identifier
//   - Step4Layout importiert ChannelPreviewBlock
//   - Step4Layout referenziert 'compare-wizard-state' (Context-Key)
//   - Step4Layout referenziert channelLayouts (State-Sync)
//   - Step4Layout enthält $effect-Timing-Guard (AC-10)
//   - compareWizardState enthält channelLayouts $state-Feld (AC-2/AC-8)
//   - compareWizardState save() schreibt channel_layouts in display_config (AC-8)
//   - CompareWizard routet currentStep===4 zu Step4Layout (AC-7)
//   - Edit +page.svelte liest channel_layouts aus existingDisplayConfig (AC-3)
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_442_compare_wizard_step4.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..', '..', '..', '..', '..'); // frontend/src -> frontend

const STEP4_LAYOUT   = join(here, '..', 'steps', 'Step4Layout.svelte');
const COMPARE_WIZARD = join(here, '..', 'CompareWizard.svelte');
const WIZARD_STATE   = join(here, '..', 'compareWizardState.svelte.ts');
const EDIT_PAGE      = join(root, 'src', 'routes', 'compare', '[id]', 'edit', '+page.svelte');

function read(p: string): string { return readFileSync(p, 'utf-8'); }

// =============================================================================
// AC-7: Step4Layout.svelte existiert unter compare/steps/
// =============================================================================

test('AC-7: Step4Layout.svelte existiert unter compare/steps/', () => {
	assert.ok(existsSync(STEP4_LAYOUT), `Step4Layout.svelte fehlt: ${STEP4_LAYOUT}`);
});

// =============================================================================
// AC-1: 4 Channel-Identifier vorhanden (Kanal-Isolation)
// =============================================================================

test('AC-1: Step4Layout enthält alle 4 Channel-Identifier (email/telegram/signal/sms)', () => {
	const src = read(STEP4_LAYOUT);
	for (const ch of ['email', 'telegram', 'signal', 'sms']) {
		assert.ok(
			src.includes(`'${ch}'`) || src.includes(`"${ch}"`),
			`Step4Layout muss Channel-Identifier '${ch}' enthalten (AC-1: Kanal-Isolation).`,
		);
	}
});

// =============================================================================
// AC-7 (Fortsetzung): CompareWizard routet zu Step4Layout
// =============================================================================

test('AC-7: CompareWizard importiert Step4Layout', () => {
	const src = read(COMPARE_WIZARD);
	assert.ok(
		src.includes('Step4Layout'),
		'CompareWizard.svelte muss Step4Layout importieren (AC-7).',
	);
});

test('AC-7: CompareWizard mountet Step4Layout bei currentStep === 4', () => {
	const src = read(COMPARE_WIZARD);
	const has = /currentStep\s*===\s*4[\s\S]{0,150}Step4Layout/.test(src);
	assert.ok(
		has,
		'CompareWizard muss bei currentStep === 4 die Step4Layout-Komponente rendern (AC-7).',
	);
});

// =============================================================================
// AC-2/AC-10: ChannelPreviewBlock + channelLayouts-Referenz + $effect-Guard
// =============================================================================

test('AC-2: Step4Layout importiert ChannelPreviewBlock', () => {
	const src = read(STEP4_LAYOUT);
	assert.ok(
		src.includes('ChannelPreviewBlock'),
		'Step4Layout muss ChannelPreviewBlock importieren (AC-2: Live-Vorschau).',
	);
});

test('AC-2: Step4Layout referenziert wizard.channelLayouts (State-Sync)', () => {
	const src = read(STEP4_LAYOUT);
	assert.ok(
		src.includes('channelLayouts'),
		'Step4Layout muss wizard.channelLayouts referenzieren (AC-2: $effect-Sync).',
	);
});

test('AC-10: Step4Layout enthält $effect-Timing-Guard gegen leere Katalog-Writes', () => {
	const src = read(STEP4_LAYOUT);
	// Guard: if (loading || Object.keys(catalog).length === 0) return;
	const hasLoadingGuard = /Object\.keys\s*\(\s*catalog\s*\)\.length\s*===\s*0/.test(src)
		|| /catalog.*length.*===.*0/.test(src);
	assert.ok(
		hasLoadingGuard,
		'Step4Layout muss den $effect-Timing-Guard enthalten: if (loading || Object.keys(catalog).length === 0) return; (AC-10).',
	);
});

// =============================================================================
// AC-1: Context-Key 'compare-wizard-state'
// =============================================================================

test("AC-1: Step4Layout verwendet Context-Key 'compare-wizard-state'", () => {
	const src = read(STEP4_LAYOUT);
	assert.ok(
		src.includes('compare-wizard-state'),
		"Step4Layout muss den Context-Key 'compare-wizard-state' verwenden (AC-1).",
	);
});

// =============================================================================
// AC-2/AC-8: compareWizardState hat channelLayouts + save() schreibt channel_layouts
// =============================================================================

test('AC-2: compareWizardState hat channelLayouts als $state-Feld', () => {
	const src = read(WIZARD_STATE);
	assert.ok(
		/channelLayouts\s*=\s*\$state/.test(src),
		'compareWizardState.svelte.ts muss channelLayouts als $state-Feld haben (AC-2).',
	);
});

test('AC-8: compareWizardState importiert ChannelLayouts-Typ', () => {
	const src = read(WIZARD_STATE);
	assert.ok(
		src.includes('ChannelLayouts'),
		'compareWizardState.svelte.ts muss ChannelLayouts importieren oder referenzieren (AC-8).',
	);
});

test('AC-8: compareWizardState save() schreibt channel_layouts in display_config', () => {
	const src = read(WIZARD_STATE);
	assert.ok(
		src.includes('channel_layouts'),
		'compareWizardState.svelte.ts save() muss channel_layouts in display_config schreiben (AC-8).',
	);
});

// =============================================================================
// AC-3: Edit +page.svelte liest channel_layouts aus existingDisplayConfig
// =============================================================================

test('AC-3: Edit +page.svelte liest channel_layouts aus existingDisplayConfig', () => {
	const src = read(EDIT_PAGE);
	assert.ok(
		src.includes('channel_layouts'),
		'compare/[id]/edit/+page.svelte muss channel_layouts aus existingDisplayConfig lesen (AC-3).',
	);
});

test('AC-3: Edit +page.svelte setzt state.channelLayouts', () => {
	const src = read(EDIT_PAGE);
	assert.ok(
		src.includes('channelLayouts'),
		'compare/[id]/edit/+page.svelte muss state.channelLayouts setzen (AC-3).',
	);
});

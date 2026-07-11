// Dead-Code-Abbau Scheibe 2 (Issue #1215 + #1201)
// Spec: docs/specs/modules/rework_1215_dead_code_scheibe2.md
//
// Beweist: alter Trip-Wizard + NewLocationWizard sind entfernt, die zwei
// aktiv genutzten Bausteine (ChannelToggle, wizardHelpers) leben in shared/,
// alle Importer zeigen auf den neuen Pfad, und die lebenden Nachbarn
// (helpers.ts, /trips/new, PresetHeader-Eintrag für Scheibe 3) sind intakt.
// Datei-Existenz-/Inhalts-Checks folgen dem etablierten Muster der
// Struktur-Tests (vgl. issue_462.test.ts, ehem. issue_518-Cleanup-Test).
//
// TDD RED: Vor der Implementierung schlagen die removed/moved-Tests fehl.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const LIB = join(here, '..', '..', '..');            // frontend/src/lib
const COMPONENTS = join(LIB, 'components');
const E2E = join(LIB, '..', '..', 'e2e');

const read = (p: string) => readFileSync(p, 'utf-8');

// ── AC-1: Umzug nach shared/ ────────────────────────────────────────────────

test('AC-1: ChannelToggle.svelte + wizardHelpers.ts (+Test) liegen in shared/', () => {
	for (const f of ['ChannelToggle.svelte', 'wizardHelpers.ts']) {
		assert.ok(
			existsSync(join(COMPONENTS, 'shared', f)),
			`shared/${f} fehlt — Umzugsgut aus trip-wizard/ (AC-1)`
		);
	}
	assert.ok(
		existsSync(join(COMPONENTS, 'shared', '__tests__', 'wizardHelpers.test.ts')),
		'shared/__tests__/wizardHelpers.test.ts fehlt — Test zieht mit um (AC-1)'
	);
});

test('AC-1: alle 3 Importer nutzen den neuen shared/-Pfad, kein trip-wizard-Import mehr', () => {
	const importers = [
		join(COMPONENTS, 'compare', 'steps', 'Step5Versand.svelte'),
		join(COMPONENTS, 'alerts-tab', 'AlertsTab.svelte'),
		join(COMPONENTS, 'compare', 'CompareAlarmSection.svelte'),
	];
	for (const p of importers) {
		const src = read(p);
		assert.ok(
			src.includes('$lib/components/shared/ChannelToggle.svelte'),
			`${p} importiert ChannelToggle nicht aus shared/ (AC-1)`
		);
		assert.ok(
			!src.includes('trip-wizard'),
			`${p} referenziert noch trip-wizard (AC-1/AC-2)`
		);
	}
	assert.ok(
		read(importers[0]).includes('$lib/components/shared/wizardHelpers'),
		'Step5Versand.svelte importiert maskPhone nicht aus shared/wizardHelpers (AC-1)'
	);
});

// ── AC-2/AC-3: Löschungen ───────────────────────────────────────────────────

test('AC-2: trip-wizard/-Ordner existiert nicht mehr', () => {
	assert.ok(
		!existsSync(join(COMPONENTS, 'trip-wizard')),
		'components/trip-wizard/ existiert noch — sollte mit Scheibe 2 (#1215) gelöscht sein'
	);
});

test('AC-3: NewLocationWizard.svelte existiert nicht mehr', () => {
	assert.ok(
		!existsSync(join(COMPONENTS, 'compare', 'NewLocationWizard.svelte')),
		'compare/NewLocationWizard.svelte existiert noch (0 Importer, #588 abgelöst)'
	);
});

// ── AC-4: organisms/index.ts bereinigt, Rest intakt ─────────────────────────

test('AC-4: organisms/index.ts exportiert TripWizardShell nicht mehr, aktive Exporte bleiben', () => {
	const src = read(join(COMPONENTS, 'organisms', 'index.ts'));
	assert.ok(!src.includes('TripWizardShell'), 'TripWizardShell-Re-Export muss weg (AC-4)');
	for (const keep of ['AlertRulesEditor', 'OutputLayoutEditor']) {
		assert.ok(src.includes(keep), `organisms/index.ts: aktiver Export ${keep} fehlt — Über-Löschung!`);
	}
});

// ── AC-5: stale Wizard-E2E-Specs weg, helpers.ts bleibt ─────────────────────

const DEAD_SPECS = [
	'trip-wizard-shell.spec.ts',
	'trip-wizard-step1.spec.ts',
	'trip-wizard-step2.spec.ts',
	'trip-wizard-step3.spec.ts',
	'trip-wizard-step3-wetter.spec.ts',
	'trip-wizard-step4.spec.ts',
	'trip-wizard-step5-reports.spec.ts',
	'trip-wizard-templates.spec.ts',
	'trip-wizard-multi-gpx.spec.ts',
	'bug-271-wizard-mobile-stepper.spec.ts',
];

test('AC-5: die 10 Specs des toten Wizards sind gelöscht', () => {
	const leftover = DEAD_SPECS.filter((f) => existsSync(join(E2E, f)));
	assert.deepEqual(leftover, [], `Stale Wizard-E2E-Specs noch vorhanden: ${leftover.join(', ')}`);
});

test('AC-5: e2e/helpers.ts bleibt bestehen (Nutzer: trip-edit u.a., #1201-Rest)', () => {
	assert.ok(existsSync(join(E2E, 'helpers.ts')), 'e2e/helpers.ts fehlt — Über-Löschung!');
});

// ── AC-6/AC-8: Testdatei-Anpassungen ────────────────────────────────────────

test('AC-6: issue_518_suggested_cleanup.test.ts (testet nur toten Wizard) ist gelöscht', () => {
	assert.ok(
		!existsSync(join(LIB, 'issue_518_suggested_cleanup.test.ts')),
		'issue_518_suggested_cleanup.test.ts existiert noch — liest gelöschte Wizard-Dateien'
	);
});

test('AC-7: bug_499_skala_label.test.ts referenziert trip-wizard nicht mehr', () => {
	const p = join(COMPONENTS, 'trip-detail', 'bug_499_skala_label.test.ts');
	assert.ok(existsSync(p), 'bug_499_skala_label.test.ts darf nicht komplett gelöscht werden');
	assert.ok(!read(p).includes('trip-wizard'), 'bug_499-Test liest noch trip-wizard/Step3Weather (AC-7)');
});

test('AC-8: issue_462.test.ts ohne NewLocationWizard- und PresetHeader-Eintrag (Scheibe 3 entfernt)', () => {
	const src = read(join(COMPONENTS, 'compare', 'issue_462.test.ts'));
	assert.ok(!src.includes('NewLocationWizard'), 'MIGRATED_FILES enthält noch NewLocationWizard (AC-8)');
	assert.ok(!src.includes('PresetHeader'), 'PresetHeader-Eintrag wurde mit Scheibe 3 entfernt (#1215)');
});

// ── AC-10: lebende Route unangetastet ───────────────────────────────────────

test('AC-10: /trips/new nutzt weiterhin TripNewEditor', () => {
	const src = read(join(LIB, '..', 'routes', 'trips', 'new', '+page.svelte'));
	assert.ok(src.includes('TripNewEditor'), '/trips/new muss TripNewEditor nutzen (live, #622)');
});

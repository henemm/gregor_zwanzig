// TDD RED: Issue #462 — Compare-Screen: Atomic-Migration (ui/ → atoms/)
//
// Spec:      docs/specs/modules/issue_462_compare_atomic_migration.md
// Verzeichnis: frontend/src/lib/components/compare/
//
// Source-Inspection-Tests (analog zu routes/trips/issue_402.test.ts):
// Liest die echten .svelte-Quelldateien als String und prüft, ob die
// Import-Migration von ui/ auf atoms/ korrekt umgesetzt wurde.
//
// RED: Im aktuellen Stand importieren alle 14 Dateien Btn/Eyebrow/Pill/Input/TopoBg
// noch direkt aus ui/-Unterordnern → AC-1/AC-2 schlagen fehl.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/components/compare/issue_462.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const COMPARE_DIR = dirname(fileURLToPath(import.meta.url));
const STEPS_DIR = join(COMPARE_DIR, 'steps');

// ── Zu prüfende Dateien (14 laut Spec) ────────────────────────────────────────

const MIGRATED_FILES: Array<{ path: string; components: string[] }> = [
	{ path: join(COMPARE_DIR, 'AutoReportCard.svelte'),    components: ['Btn'] },
	{ path: join(COMPARE_DIR, 'AutoReportsOverview.svelte'), components: ['Eyebrow'] },
	{ path: join(COMPARE_DIR, 'CompareWizard.svelte'),     components: ['Btn', 'Eyebrow', 'TopoBg'] },
	{ path: join(COMPARE_DIR, 'CreateGroupDialog.svelte'), components: ['Btn'] },
	{ path: join(COMPARE_DIR, 'HourlyMatrix.svelte'),      components: ['Pill'] },
	{ path: join(COMPARE_DIR, 'LocationPreviewMap.svelte'), components: ['TopoBg'] },
	{ path: join(COMPARE_DIR, 'LocationsRail.svelte'),     components: ['Btn', 'Pill'] },
	{ path: join(COMPARE_DIR, 'NewLocationWizard.svelte'), components: ['Btn', 'Input'] },
	{ path: join(COMPARE_DIR, 'PresetHeader.svelte'),      components: ['Btn'] },
	{ path: join(COMPARE_DIR, 'RecommendationBanner.svelte'), components: ['Pill'] },
	{ path: join(COMPARE_DIR, 'SavePresetDialog.svelte'),  components: ['Btn'] },
	{ path: join(STEPS_DIR, 'Step3Idealwerte.svelte'),     components: ['Eyebrow'] },
	{ path: join(STEPS_DIR, 'Step4Layout.svelte'),         components: ['Eyebrow'] },
	{ path: join(STEPS_DIR, 'Step5Versand.svelte'),        components: ['Eyebrow'] },
];

// ui/-Pfade die nach der Migration NICHT mehr für Atom-Komponenten genutzt werden dürfen
const FORBIDDEN_UI_PATHS = [
	'ui/btn',
	'ui/eyebrow',
	'ui/pill',
	'ui/input',
	'ui/topo',
];

// ── Hilfsfunktionen ───────────────────────────────────────────────────────────

function readFile(path: string): string {
	return readFileSync(path, 'utf-8');
}

function escapeRegex(s: string): string {
	return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Liefert die benannten Importe aus einem bestimmten Modul-Pfad. */
function namedImportsFrom(src: string, modulePath: string): string[] {
	const re = new RegExp(
		`import\\s*\\{([^}]*)\\}\\s*from\\s*['"]${escapeRegex(modulePath)}['"]`,
		'g'
	);
	const names: string[] = [];
	let m: RegExpExecArray | null;
	while ((m = re.exec(src))) {
		for (const part of m[1].split(',')) {
			const name = part.trim().split(/\s+as\s+/)[0].trim();
			if (name) names.push(name);
		}
	}
	return names;
}

// ── AC-1: Alle migrierten Komponenten kommen aus atoms ───────────────────────

test('AC-1: Alle 14 Dateien importieren ihre Atom-Komponenten aus $lib/components/atoms', () => {
	const missing: string[] = [];
	for (const { path, components } of MIGRATED_FILES) {
		const src = readFile(path);
		const atoms = namedImportsFrom(src, '$lib/components/atoms');
		const shortPath = path.replace(/.*compare\//, 'compare/');
		for (const name of components) {
			if (!atoms.includes(name)) {
				missing.push(`${shortPath}: ${name} nicht in atoms-Import (gefunden: [${atoms.join(', ')}])`);
			}
		}
	}
	assert.deepEqual(
		missing,
		[],
		`Folgende Komponenten fehlen im atoms-Import:\n${missing.join('\n')}`
	);
});

// ── AC-1 (negativ): Kein direkter ui/-Import mehr für die 5 Atom-Namen ───────

test('AC-1: Keine der 14 Dateien importiert Btn/Eyebrow/Pill/Input/TopoBg noch aus ui/', () => {
	const offenders: string[] = [];
	for (const { path } of MIGRATED_FILES) {
		const src = readFile(path);
		const shortPath = path.replace(/.*compare\//, 'compare/');
		for (const uiPath of FORBIDDEN_UI_PATHS) {
			if (src.includes(uiPath)) {
				offenders.push(`${shortPath}: direkter ui/-Import aus '${uiPath}' noch vorhanden`);
			}
		}
	}
	assert.deepEqual(
		offenders,
		[],
		`Folgende direkten ui/-Importe müssen auf atoms umgestellt werden:\n${offenders.join('\n')}`
	);
});

// ── AC-1: CompareWizard konsolidiert 3 Imports in eine Zeile ─────────────────

test('AC-1: CompareWizard.svelte importiert Btn, Eyebrow, TopoBg in einer einzigen atoms-Zeile', () => {
	const src = readFile(join(COMPARE_DIR, 'CompareWizard.svelte'));
	const atoms = namedImportsFrom(src, '$lib/components/atoms');
	for (const name of ['Btn', 'Eyebrow', 'TopoBg']) {
		assert.ok(
			atoms.includes(name),
			`CompareWizard.svelte: ${name} nicht im atoms-Barrel-Import (gefunden: [${atoms.join(', ')}])`
		);
	}
	// Es darf nur einen atoms-Import geben (konsolidiert)
	const atomsImportCount = (src.match(/from\s+['"][$]lib\/components\/atoms['"]/g) ?? []).length;
	assert.equal(
		atomsImportCount,
		1,
		`CompareWizard.svelte: Erwartet genau 1 atoms-Import, gefunden: ${atomsImportCount}`
	);
});

// ── AC-1: Scope-Grenze — nicht-migrierbare ui/-Importe bleiben erhalten ──────

test('AC-1: Komponenten ohne Atom-Pendant (Card-NS, Dialog, Table, Checkbox) bleiben in ui/', () => {
	// CompareMatrix nutzt Card + Table
	const matrix = readFile(join(COMPARE_DIR, 'CompareMatrix.svelte'));
	assert.ok(
		matrix.includes('ui/card') || matrix.includes("from '$lib/components/ui/card"),
		'CompareMatrix.svelte: Card-Namespace-Import aus ui/ fehlt (darf nicht migriert werden)'
	);
	// CompareGrid (Nachfolger von CompareList seit #490) nutzt den
	// ConfirmDialog-Molecule-Wrapper statt direkt ui/dialog — das
	// Molecule selbst stützt sich weiter auf ui/dialog (kein Atom-Pendant).
	const grid = readFile(join(COMPARE_DIR, 'CompareGrid.svelte'));
	assert.ok(
		grid.includes('ConfirmDialog'),
		'CompareGrid.svelte: ConfirmDialog-Molecule-Import fehlt (Wrapper um ui/dialog)'
	);
	// GroupSection nutzt Checkbox
	const group = readFile(join(COMPARE_DIR, 'GroupSection.svelte'));
	assert.ok(
		group.includes('ui/checkbox'),
		'GroupSection.svelte: Checkbox-Import aus ui/ fehlt (darf nicht migriert werden)'
	);
});

// ── AC-3: contrast-audit Basis-Check ─────────────────────────────────────────

test('AC-3: compare/-Dateien enthalten keine rohen Hex-Farbliterale als color-Eigenschaft', () => {
	const hexInColor = /(?:color|stroke|fill)\s*[:=]\s*["']?#[0-9a-fA-F]{3,6}\b/g;
	const offenders: string[] = [];
	for (const { path } of MIGRATED_FILES) {
		const src = readFile(path);
		const shortPath = path.replace(/.*compare\//, 'compare/');
		const matches = src.match(hexInColor) ?? [];
		if (matches.length > 0) {
			offenders.push(`${shortPath}: ${matches.join(', ')}`);
		}
	}
	assert.deepEqual(
		offenders,
		[],
		`Hex-Farbliterale in compare/-Dateien — auf Design-Tokens umstellen:\n${offenders.join('\n')}`
	);
});

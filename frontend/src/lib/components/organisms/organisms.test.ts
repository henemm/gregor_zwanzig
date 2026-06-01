// TDD RED: Epic #471 — Organisms-Schicht lib/components/organisms/
//
// Spec: docs/specs/modules/epic_471_organisms_layer.md
//
// Source-Inspection-Tests (kein Render, keine Mocks): prueft Datei-Existenz,
// Barrel-Exporte, AC-2-Einhaltung (kein ui/-Import) und Konsumenten-Imports.
//
// RED vor Implementierung: organisms/index.ts fehlt, Konsumenten-Imports
// zeigen noch alte Pfade → alle Asserts schlagen fehl.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test src/lib/components/organisms/organisms.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const componentsRoot = join(here, '..');
const frontendRoot = join(here, '..', '..', '..', '..');
const read = (f: string) => readFileSync(f, 'utf-8');
const has = (f: string) => existsSync(f);

const ORGANISMS = [
	{ name: 'TripHeader', path: join(componentsRoot, 'trip-detail', 'TripHeader.svelte') },
	{ name: 'TripWizardShell', path: join(componentsRoot, 'trip-wizard', 'TripWizardShell.svelte') },
	{ name: 'AlertRulesEditor', path: join(componentsRoot, 'alert-rules-editor', 'AlertRulesEditor.svelte') },
];

// ── AC-1: Barrel existiert und re-exportiert alle 3 Organisms ────────────────

test('#471 AC-1: organisms/index.ts existiert', () => {
	assert.ok(has(join(here, 'index.ts')), 'organisms/index.ts fehlt — noch nicht implementiert');
});

test('#471 AC-1: index.ts re-exportiert TripHeader, TripWizardShell, AlertRulesEditor', () => {
	const barrel = read(join(here, 'index.ts'));
	for (const o of ORGANISMS) {
		assert.ok(
			new RegExp(`\\b${o.name}\\b`).test(barrel),
			`organisms/index.ts exportiert ${o.name} nicht`
		);
	}
});

// ── AC-2: Kein direkter $lib/components/ui/-Import in den Organism-Quellen ───

describe('#471 AC-2: kein direkter ui/-Import in Organism-Quellen', () => {
	for (const o of ORGANISMS) {
		test(`${o.name} hat keinen $lib/components/ui/-Import`, () => {
			assert.ok(has(o.path), `Quell-Datei fehlt: ${o.path}`);
			const src = read(o.path);
			assert.ok(
				!src.includes('$lib/components/ui/'),
				`${o.name} importiert verboten: $lib/components/ui/`
			);
		});
	}
});

// ── AC-4: Konsumenten nutzen $lib/components/organisms als Import-Quelle ─────

const CONSUMERS = [
	{
		label: 'trips/[id]/+page.svelte — TripHeader aus organisms',
		path: join(frontendRoot, 'src', 'routes', 'trips', '[id]', '+page.svelte'),
		mustContain: /from ['"](\$lib\/components\/organisms)['"]/,
		mustNotContain: /from ['"].*trip-detail['"].*TripHeader/,
	},
	{
		label: 'trips/new/+page.svelte — TripWizardShell aus organisms',
		path: join(frontendRoot, 'src', 'routes', 'trips', 'new', '+page.svelte'),
		mustContain: /from ['"](\$lib\/components\/organisms)['"]/,
		mustNotContain: /from ['"].*trip-wizard\/TripWizardShell\.svelte['"]/,
	},
	{
		label: 'edit/TripEditView.svelte — AlertRulesEditor aus organisms',
		path: join(componentsRoot, 'edit', 'TripEditView.svelte'),
		mustContain: /from ['"](\$lib\/components\/organisms)['"]/,
		mustNotContain: /from ['"].*alert-rules-editor\/AlertRulesEditor\.svelte['"]/,
	},
	{
		label: 'trip-wizard/steps/Step4Briefings.svelte — AlertRulesEditor aus organisms',
		path: join(componentsRoot, 'trip-wizard', 'steps', 'Step4Briefings.svelte'),
		mustContain: /from ['"](\$lib\/components\/organisms)['"]/,
		mustNotContain: /from ['"].*alert-rules-editor\/AlertRulesEditor\.svelte['"]/,
	},
	{
		label: 'compare/steps/Step4Layout.svelte — OutputLayoutEditor aus organisms',
		path: join(componentsRoot, 'compare', 'steps', 'Step4Layout.svelte'),
		mustContain: /from ['"](\$lib\/components\/organisms)['"]/,
		mustNotContain: /OutputLayoutEditor.*from.*shared|from.*shared.*OutputLayoutEditor/,
	},
	{
		label: 'trip-detail/WeatherMetricsTab.svelte — OutputLayoutEditor aus organisms',
		path: join(componentsRoot, 'trip-detail', 'WeatherMetricsTab.svelte'),
		mustContain: /from ['"](\$lib\/components\/organisms)['"]/,
		mustNotContain: /OutputLayoutEditor.*from.*shared|from.*shared.*OutputLayoutEditor/,
	},
	{
		label: 'trip-wizard/steps/Step4Layout.svelte — OutputLayoutEditor aus organisms',
		path: join(componentsRoot, 'trip-wizard', 'steps', 'Step4Layout.svelte'),
		mustContain: /from ['"](\$lib\/components\/organisms)['"]/,
		mustNotContain: /OutputLayoutEditor.*from.*shared|from.*shared.*OutputLayoutEditor/,
	},
];

describe('#471 AC-4: Konsumenten-Imports zeigen auf organisms/', () => {
	for (const c of CONSUMERS) {
		test(c.label, () => {
			assert.ok(has(c.path), `Konsumenten-Datei fehlt: ${c.path}`);
			const src = read(c.path);
			assert.ok(
				c.mustContain.test(src),
				`${c.label}: kein organisms-Import gefunden`
			);
			assert.ok(
				!c.mustNotContain.test(src),
				`${c.label}: noch alter direkter Pfad vorhanden`
			);
		});
	}
});

// ── Issue #520 AC-1: 5 neue Organisms im Barrel ──────────────────────────────
//
// Spec: docs/specs/modules/issue_520_organisms_barrel_completeness.md
//
// Nur Export-Existence-Tests. Kein ui/-Import-Check fuer ChannelPreviewBlock
// und MetricCheckbox (bekannte C2-Verstaesse, Constraint C3 — werden nicht
// angefasst, Fixes in Folge-Issues).

const ORGANISMS_520_SOURCES = [
	{ name: 'WeatherMetricsTab',  path: join(componentsRoot, 'trip-detail', 'WeatherMetricsTab.svelte') },
	{ name: 'ChannelPreviewBlock', path: join(componentsRoot, 'trip-detail', 'ChannelPreviewBlock.svelte') },
	{ name: 'ChannelPreviewCard', path: join(componentsRoot, 'trip-detail', 'ChannelPreviewCard.svelte') },
	{ name: 'MetricGroup',        path: join(componentsRoot, 'trip-detail', 'MetricGroup.svelte') },
	{ name: 'MetricCheckbox',     path: join(componentsRoot, 'trip-detail', 'MetricCheckbox.svelte') },
];

test('#520 AC-1: Quell-Dateien der 5 neuen Organisms existieren', () => {
	for (const o of ORGANISMS_520_SOURCES) {
		assert.ok(has(o.path), `Quell-Datei fehlt: ${o.path}`);
	}
});

test('#520 AC-1: index.ts re-exportiert alle 5 neuen Organisms', () => {
	const barrel = read(join(here, 'index.ts'));
	for (const o of ORGANISMS_520_SOURCES) {
		assert.ok(
			new RegExp(`\\b${o.name}\\b`).test(barrel),
			`organisms/index.ts exportiert ${o.name} nicht — Barrel noch nicht aktualisiert`,
		);
	}
});

// C2-Konformitaets-Check nur fuer die 3 Organisms OHNE bekannte C2-Verstaesse
const ORGANISMS_520_C2_CLEAN = [
	{ name: 'WeatherMetricsTab',  path: join(componentsRoot, 'trip-detail', 'WeatherMetricsTab.svelte') },
	{ name: 'ChannelPreviewCard', path: join(componentsRoot, 'trip-detail', 'ChannelPreviewCard.svelte') },
	{ name: 'MetricGroup',        path: join(componentsRoot, 'trip-detail', 'MetricGroup.svelte') },
];

describe('#520 AC-1: kein ui/-Import in C2-konformen neuen Organisms', () => {
	for (const o of ORGANISMS_520_C2_CLEAN) {
		test(`${o.name} hat keinen $lib/components/ui/-Import`, () => {
			assert.ok(has(o.path), `Quell-Datei fehlt: ${o.path}`);
			const src = read(o.path);
			assert.ok(
				!src.includes('$lib/components/ui/'),
				`${o.name} importiert verboten: $lib/components/ui/`,
			);
		});
	}
});

// ── Issue #520 AC-3: COMPONENTS.md Organisms-Tabelle vollstaendig ─────────────

test('#520 AC-3: COMPONENTS.md listet alle 5 neuen Organisms', () => {
	const docsPath = join(here, '..', '..', '..', '..', '..', 'docs', 'design-system', 'COMPONENTS.md');
	assert.ok(has(docsPath), `COMPONENTS.md fehlt: ${docsPath}`);
	const doc = read(docsPath);
	for (const o of ORGANISMS_520_SOURCES) {
		assert.ok(
			doc.includes(o.name),
			`COMPONENTS.md erwaehnt ${o.name} nicht — Organisms-Tabelle unvollstaendig`,
		);
	}
});

// ── AC-5: TripHeader NICHT mehr in trip-detail/index.ts ──────────────────────

test('#471 AC-5: trip-detail/index.ts exportiert TripHeader nicht mehr', () => {
	const barrelPath = join(componentsRoot, 'trip-detail', 'index.ts');
	assert.ok(has(barrelPath), 'trip-detail/index.ts fehlt');
	const barrel = read(barrelPath);
	assert.ok(
		!/export\s.*TripHeader/.test(barrel),
		'trip-detail/index.ts exportiert TripHeader noch — muss entfernt werden'
	);
});

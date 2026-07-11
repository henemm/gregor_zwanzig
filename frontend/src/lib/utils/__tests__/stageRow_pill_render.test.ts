// doc-compliance-test
//
// Regressionsguard für Adversary-Finding F001 (Workflow fix-1223-cockpit-risk-colors):
// Pill.svelte rendert Text AUSSCHLIESSLICH über Children ({@render children?.()}),
// hat KEIN `label`-Prop. `<Pill tone={...} label={pill.label} />` kompiliert klaglos,
// aber das Label landet als totes DOM-Attribut — der Risiko-Text erscheint nie im UI.
//
// Es existiert keine Svelte-Component-Test-Infra (kein vitest/testing-library) in
// diesem Frontend, daher ist ein Rendering-Test der Komponente nicht möglich. Als
// zugelassene Ausnahme der Test-Politik (Datei-Inhalt-Check, siehe CLAUDE.md
// "Test-Politik: Zwei Schichten") prüft dieser Test den Quelltext von
// TripStageRow.svelte direkt gegen genau dieses Fehlerbild:
//   - Pill MUSS das Label als Children rendern (`>{pill.label}</Pill>` bzw.
//     `{pill.label}` zwischen `<Pill` und `</Pill>`)
//   - Pill DARF NICHT `label=` als Prop übergeben (der defekte Pfad)
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/utils/__tests__/stageRow_pill_render.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.resolve(
	__dirname,
	'../../components/trip-detail/TripStageRow.svelte'
);

const source = readFileSync(COMPONENT_PATH, 'utf-8');

// Isoliert das <Pill ...>...</Pill>-Fragment für die Risiko-Pille (Col 4).
const pillMatch = source.match(/<Pill\b[^>]*>[\s\S]*?<\/Pill>/);

test('F001: Risiko-Pill rendert Label als Children, nicht als label-Prop', () => {
	assert.ok(pillMatch, 'TripStageRow.svelte muss eine <Pill>...</Pill>-Nutzung enthalten');

	const pillFragment = pillMatch![0];
	const openingTag = pillFragment.match(/<Pill\b[^>]*>/)![0];

	assert.doesNotMatch(
		openingTag,
		/\blabel\s*=/,
		'Pill hat kein label-Prop — label={...} landet als totes DOM-Attribut, Text erscheint nie (F001)'
	);

	assert.match(
		pillFragment,
		/<Pill\b[^>]*>\s*\{?\s*pill\.label/,
		'Pill muss pill.label als Children rendern: <Pill tone={pill.tone}>{pill.label}</Pill>'
	);
});

// TDD RED: Issue #1895 Schritt 4 — toten Code rund um alert_rules entfernen (Schnitt C)
// Spec: docs/specs/modules/feat_1895_s4_alert_rules_rueckbau.md (AC-2, AC-4)
//
// Verhaltensnachweis per echtem Import-Versuch (kein grep auf Dateiinhalt):
//  - die sechs toten Svelte-Komponenten sind nicht mehr auflösbar
//    (ERR_MODULE_NOT_FOUND, nicht etwa ein Compile-Fehler),
//  - die toten Laufzeit-Exporte aus alertMetricTable.ts sind weg,
//  - die produktiven Exporte (ALERTABLE_METRICS, METRIC_DEFAULTS,
//    levelToThreshold, thresholdTitle) liefern weiter Werte.
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
// Ausführung:
//   cd frontend && npm test -- src/lib/components/alerts-tab/__tests__/issue_1895_s4_toter_code_entfernt.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> alerts-tab -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const AT = path.resolve(HERE, '..');
const COMPONENTS = path.resolve(AT, '..');
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const GELOESCHTE_KOMPONENTEN = [
	path.join(AT, 'AlertsTab.svelte'),
	path.join(AT, 'AlertCard.svelte'),
	path.join(AT, 'AlertMetricTable.svelte'),
	path.join(AT, 'AlertMetricRow.svelte'),
	path.join(AT, 'AlertPresetSelector.svelte'),
	path.join(COMPONENTS, 'trip-detail', 'AlertsPreviewCard.svelte'),
];

for (const datei of GELOESCHTE_KOMPONENTEN) {
	test(`AC-4: ${path.relative(COMPONENTS, datei)} ist nicht mehr auflösbar`, async () => {
		await assert.rejects(
			import(pathToFileURL(datei).href),
			(err: NodeJS.ErrnoException) => err.code === 'ERR_MODULE_NOT_FOUND',
			`${path.basename(datei)} lässt sich noch importieren — toter Code nicht entfernt`
		);
	});
}

// Der Re-Export in trip-detail/index.ts:7 wird hier bewusst NICHT per Import
// geprüft: der Barrel lädt TripTabs.svelte → `$app/*`, das unter node --test
// nie auflösbar ist (Test bliebe auch nach der Umsetzung aus falschem Grund rot).
// Erzwungen wird die Bereinigung über AC-5: nach Löschung der Datei schlagen
// svelte-check und Build fehl, solange die Export-Zeile steht.

const GELOESCHTE_EXPORTE = [
	'DELTA_ONLY_METRICS',
	'METRIC_PRESETS',
	'ALL_ALERT_METRICS',
	'alertRulesToRowState',
	'rowStateToAlertRules',
	'migrateAlertPreset',
	'activeAlertableMetrics',
	'deriveAlertMode',
	'applyModeToRowState',
];

test('AC-4: tote Laufzeit-Exporte aus alertMetricTable.ts sind entfernt', async () => {
	const mod = await import(pathToFileURL(path.join(AT, 'alertMetricTable.ts')).href);
	const noch = GELOESCHTE_EXPORTE.filter((name) => name in mod);
	assert.deepEqual(noch, [], `noch exportiert: ${noch.join(', ')}`);
});

test('AC-2: produktive Exporte aus alertMetricTable.ts liefern weiter Werte', async () => {
	const mod = await import(pathToFileURL(path.join(AT, 'alertMetricTable.ts')).href);
	assert.ok(Array.isArray(mod.ALERTABLE_METRICS) && mod.ALERTABLE_METRICS.length > 0);
	assert.equal(typeof mod.METRIC_DEFAULTS, 'object');
	for (const m of mod.ALERTABLE_METRICS) {
		assert.equal(typeof mod.METRIC_DEFAULTS[m], 'number', `METRIC_DEFAULTS fehlt ${m}`);
	}
	assert.equal(typeof mod.levelToThreshold, 'function');
	assert.equal(typeof mod.thresholdTitle, 'function');
	const r = mod.levelToThreshold(mod.ALERTABLE_METRICS[0], 'standard');
	assert.ok(r === null || typeof r === 'string', 'levelToThreshold liefert weder Text noch null');
});

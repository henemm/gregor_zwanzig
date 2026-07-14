// TDD — Issue #1256 Scheibe 7 Fix-Loop 4, Staging-Fund F004 (CRITICAL).
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 7.
// Root Cause: der Hub-Header-Kebab (compare/[id]/+page.svelte togglePause)
// rief einen EIGENSTAENDIGEN fetch-Pfad mit vollem Objekt-Spread aus dem
// (potenziell veralteten) `data.preset` auf — komplett AUSSERHALB der
// `hubPutQueue`/`currentPreset`-Baseline von CompareTabs. Zwei
// Datenverlust-Varianten je nach Reihenfolge (Adversary-Proben
// scratchpad/probe_kebab_vs_hub_stale_data.mjs und
// scratchpad/probe_kebab_vs_hub_reverse.mjs):
//   (1) Hub-Idealwerte-Edit zuerst, dann Kebab-Pause → Kebab-PUT (voller
//       Spread aus veraltetem data.preset) macht den Hub-Edit rueckgaengig.
//   (2) Kebab-Pause zuerst, dann Hub-Idealwerte-Edit → Hub-PUT (Read-Modify-
//       Write aus dem jetzt veralteten currentPreset) macht die Pause
//       rueckgaengig.
//
// Fix: der Kebab delegiert jetzt (CompareTabs.toggleActiveFromParent, per
// bind:this durch CompareDetail durchgereicht) an EXAKT denselben
// `handleToggleActive`-Pfad wie die Hub-Aktivierungs-Karte — EIN Schreibweg,
// EINE `currentPreset`-Baseline, EINE `hubPutQueue`. Diese Tests bilden genau
// diese gemeinsame Architektur mit den echten Exportfunktionen nach (kein
// Mock, kein DOM/Browser — lauffaehig unter node --experimental-strip-types)
// und beweisen, dass beide Reihenfolgen jetzt verlustfrei sind.

import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset, Corridor } from '../../../types.ts';
import {
	createPutQueue,
	flushPendingCorridorSave,
	buildToggleActivePutPayload,
	type CorridorSnapshot
} from '../compareHubWizardBridge.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-1',
		name: 'Test',
		location_ids: ['a', 'b'],
		schedule: 'daily',
		weekday: 0,
		profil: 'wintersport',
		hour_from: 6,
		hour_to: 9,
		empfaenger: ['x@y.de'],
		forecast_hours: 48,
		created_at: '2026-01-01T00:00:00Z',
		previous_schedule: 'daily',
		corridors: [{ metric: 'snow_depth_cm', range: [20, null], notify: true, mark: true, prio: 'hoch' }],
		display_config: {},
		...overrides
	};
}

describe('F004: Kebab-Toggle und Hub-Corridor-Edit teilen sich EINE currentPreset-Baseline + hubPutQueue', () => {
	test('Reihenfolge wie probe_kebab_vs_hub_stale_data.mjs: Hub-Idealwerte-Edit zuerst, danach Kebab-Toggle — Korridor bleibt erhalten', async () => {
		const queue = createPutQueue();
		let serverPreset: ComparePreset = makePreset();
		async function simulatedPut(body: ComparePreset): Promise<ComparePreset> {
			serverPreset = { ...serverPreset, ...body };
			return { ...serverPreset };
		}

		// EINE gemeinsame Baseline fuer BEIDE Pfade — genau das ist der Fix:
		// vorher hatte der Kebab eine eigene `data.preset`-Kopie.
		let currentPreset = serverPreset;
		// Mirroring der echten Lazy-Hydration (idealwerteHydrated-$effect in
		// CompareTabs.svelte): lastPersistedCorridorSnapshot wird beim ersten
		// Idealwerte-Tab-Besuch aus currentPreset gesetzt, BEVOR irgendeine
		// Bearbeitung passiert — sonst haette der Diff-Waechter in
		// flushPendingCorridorSave keine Baseline zum Vergleichen.
		let lastPersistedCorridorSnapshot: CorridorSnapshot = {
			corridors: currentPreset.corridors ?? [],
			idealRanges: {},
			activeMetricKeys: [],
			metricAlertLevels: {}
		};

		// Hub-Idealwerte-Edit (analog handleCorridorCommit): neue Metrik hinzufuegen.
		const newCorridor: Corridor = { metric: 'wind_gust', range: [null, 50], notify: true, mark: false, prio: 'mittel' };
		const corridorCurrent = { corridors: [...currentPreset.corridors!, newCorridor], idealRanges: {}, activeMetricKeys: [], metricAlertLevels: {} };
		currentPreset = await queue.enqueue(async () => {
			const payload = flushPendingCorridorSave(currentPreset, corridorCurrent, lastPersistedCorridorSnapshot);
			assert.ok(payload, 'Idealwerte-Edit muss einen PUT-Payload liefern');
			const result = await simulatedPut(payload.body);
			lastPersistedCorridorSnapshot = corridorCurrent;
			return result;
		});

		// Kebab-Toggle (delegiert, analog toggleActiveFromParent -> handleToggleActive):
		// liest dieselbe, bereits aufgefrischte currentPreset-Baseline.
		currentPreset = await queue.enqueue(async () => {
			const { url, body } = buildToggleActivePutPayload(currentPreset, 'manual', 'daily');
			assert.strictEqual(url, `/api/compare/presets/${currentPreset.id}`);
			return simulatedPut(body);
		});

		assert.strictEqual(currentPreset.schedule, 'manual', 'Kebab-Toggle muss durchgekommen sein');
		assert.deepStrictEqual(
			serverPreset.corridors!.map((c) => c.metric),
			['snow_depth_cm', 'wind_gust'],
			'F004-Regression: der vorherige Hub-Idealwerte-Edit darf vom Kebab-Toggle NICHT rueckgaengig gemacht werden'
		);
	});

	test('Reihenfolge wie probe_kebab_vs_hub_reverse.mjs: Kebab-Toggle zuerst, danach Hub-Idealwerte-Edit — schedule bleibt manual', async () => {
		const queue = createPutQueue();
		let serverPreset: ComparePreset = makePreset();
		async function simulatedPut(body: ComparePreset): Promise<ComparePreset> {
			serverPreset = { ...serverPreset, ...body };
			return { ...serverPreset };
		}

		let currentPreset = serverPreset;
		// Mirroring der echten Lazy-Hydration (idealwerteHydrated-$effect in
		// CompareTabs.svelte): lastPersistedCorridorSnapshot wird beim ersten
		// Idealwerte-Tab-Besuch aus currentPreset gesetzt, BEVOR irgendeine
		// Bearbeitung passiert — sonst haette der Diff-Waechter in
		// flushPendingCorridorSave keine Baseline zum Vergleichen.
		let lastPersistedCorridorSnapshot: CorridorSnapshot = {
			corridors: currentPreset.corridors ?? [],
			idealRanges: {},
			activeMetricKeys: [],
			metricAlertLevels: {}
		};

		// Kebab-Toggle zuerst.
		currentPreset = await queue.enqueue(async () => {
			const { body } = buildToggleActivePutPayload(currentPreset, 'manual', 'daily');
			return simulatedPut(body);
		});
		assert.strictEqual(currentPreset.schedule, 'manual');

		// Danach, im selben Hub (ohne Reload): Idealwerte-Edit. Liest dieselbe,
		// durch den Toggle bereits aufgefrischte currentPreset-Baseline — ANDERS
		// als vor dem Fix, wo der Kebab eine eigene `data.preset`-Kopie hatte und
		// currentPreset im Hub davon nichts mitbekam.
		const newCorridor: Corridor = { metric: 'wind_gust', range: [null, 50], notify: true, mark: false, prio: 'mittel' };
		const corridorCurrent = { corridors: [...currentPreset.corridors!, newCorridor], idealRanges: {}, activeMetricKeys: [], metricAlertLevels: {} };
		currentPreset = await queue.enqueue(async () => {
			const payload = flushPendingCorridorSave(currentPreset, corridorCurrent, lastPersistedCorridorSnapshot);
			assert.ok(payload);
			const result = await simulatedPut(payload.body);
			lastPersistedCorridorSnapshot = corridorCurrent;
			return result;
		});

		assert.strictEqual(
			serverPreset.schedule,
			'manual',
			'F004-Regression: der vorherige Kebab-Toggle darf vom nachfolgenden Hub-Idealwerte-Edit NICHT rueckgaengig gemacht werden'
		);
		assert.deepStrictEqual(currentPreset.corridors!.map((c) => c.metric), ['snow_depth_cm', 'wind_gust']);
	});
});

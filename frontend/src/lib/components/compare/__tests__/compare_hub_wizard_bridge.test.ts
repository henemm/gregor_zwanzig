// TDD RED — Issue #1256 Scheibe 6: Hub-Wizard-Bridge fuer den eingebetteten
// CorridorEditor (context="vergleich") im Idealwerte-Tab (AC-16/AC-33/AC-34).
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 6
//   (AC-16, AC-33, AC-34), Edge Case Z.1020 (PUT-Fehler -> Rollback).
// Context: docs/context/feat-1256-s6-hub-idealwerte-inline.md § Entscheidung 1+3
//   (State-Bruecke = eigene kleine Bridge-Datei, KEIN Debounce/#1234, Rollback
//   neu bauen).
//
// Ist: `CorridorEditor.svelte` liest im vergleich-Kontext
// `getContext('compare-wizard-state')` und erwartet dort GENAU 6 Felder
// (isEditMode, corridors, activityProfile, idealRanges, activeMetricKeys,
// metricAlertLevels — CorridorEditor.svelte:41-113). Dieser Context wird
// heute NUR inline in routes/compare/[id]/edit/+page.svelte:19-86 erzeugt —
// es gibt keine extrahierte, im Hub wiederverwendbare Hydration-Funktion.
//
// `compareHubWizardBridge.ts` existiert noch NICHT — der Import schlaegt
// heute fehl (RED), bis Phase 6 das Modul anlegt.
//
// API-Design (von dieser RED-Phase festgelegt, da noch keine Implementierung
// existiert):
//   - hydrateWizardStateFromPreset(preset): liefert ein PLAIN-Objekt mit
//     GENAU den 6 Feldern, die CorridorEditor liest (kein echtes
//     CompareWizardState-Klassen-Objekt noetig/moeglich, weil dessen
//     $state-Runen ausserhalb eines Svelte-Kompilat-Kontexts nicht
//     instanziierbar sind — Praezedenz: wizard_state_no_legacy_save.test.ts
//     inspiziert nur den Prototype, instanziiert NIE `new CompareWizardState()`
//     in einem node-Test). Die Bridge-Komponente selbst (nicht Teil dieser
//     RED-Phase) uebertraegt dieses Plain-Objekt dann auf eine echte
//     CompareWizardState-Instanz und ruft setContext(...).
//     activeMetricKeys nutzt die #1191-Semantik aus
//     rehydrateActiveMetrics() (compareEditorLoad.ts:23-30): ein VORHANDENES
//     Array (auch []) bleibt exakt erhalten; FEHLT das Feld (undefined),
//     liefert die Bridge `null` als explizites Signal "Profil-Default-Pfad"
//     (kein stilles [] vortaeuschen, das faelschlich als "alles abgewaehlt"
//     interpretiert wuerde).
//   - buildHubPutPayload(preset, edit): duenner Adapter um das bestehende
//     `buildComparePresetSavePayload(original, edits)` (compareEditorSave.ts)
//     — uebernimmt aus `preset` alle Pflichtfelder, die `edit` NICHT liefert
//     (Read-Modify-Write), damit ein Teil-Edit (nur corridors ODER nur
//     pickedIds) niemals andere `display_config`-Felder wegwirft (#1257/#1234-
//     Kontext: metric_alert_levels und active_metrics duerfen nie verloren
//     gehen).
//   - snapshotForRollback(value): Deep-Copy-Helfer fuer den Prae-Aktions-
//     Zustand (Edge Case Z.1020) — Mutation des Arbeitszustands nach dem
//     Snapshot darf den Snapshot nicht veraendern.
//
// Reine Verhaltenstests (echter Funktionsaufruf, KEIN Mock, KEINE
// Datei-Inhalt-Pruefung, KEIN DOM-Rendering — Projekt-Idiom analog
// channel_names_label.test.ts).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_hub_wizard_bridge.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import type { ComparePreset } from '../../../types.ts';
import {
	hydrateWizardStateFromPreset,
	buildHubPutPayload,
	snapshotForRollback,
	flushPendingCorridorSave,
	shouldFlushOnWindowPointerUp,
	buildToggleActivePutPayload,
	type CorridorSnapshot
} from '../compareHubWizardBridge.ts';

// Fixture nach dem echten DTO (compareEditorSave.ts:71-162, routes/compare/[id]/edit/+page.svelte:19-86):
// location_ids/schedule/profil/display_config (region, ideal_ranges, active_metrics,
// metric_alert_levels) + Top-Level `corridors` (Issue #1231 Slice 4). channel_layouts
// ist seit #1351 (AC-6) kein Compare-Feld mehr — ein realistisches Preset führt es nicht.
function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-42',
		name: 'Skigebiete Tirol',
		location_ids: ['loc-1', 'loc-2', 'loc-3'],
		schedule: 'daily',
		weekday: 0,
		profil: 'wintersport',
		hour_from: 6,
		hour_to: 9,
		empfaenger: ['urlauber@example.com'],
		forecast_hours: 48,
		letzter_versand: undefined,
		top_ort_letzter_versand: null,
		created_at: '2026-01-01T00:00:00Z',
		corridors: [{ metric: 'snow_depth_cm', range: [20, null], notify: true, mark: true, prio: 'hoch' }],
		display_config: {
			region: 'Tirol',
			ideal_ranges: { snow_depth_cm: { min: 20, max: null } },
			active_metrics: ['snow_depth_cm', 'wind_gust'],
			metric_alert_levels: { snow_depth_cm: 'warn', wind_gust: 'mark' }
		},
		...overrides
	};
}

describe('AC-16: hydrateWizardStateFromPreset — Teil-Hydration der 6 CorridorEditor-Felder', () => {
	test('liefert ein Objekt mit GENAU den 6 erwarteten Feldern (keine mehr, keine weniger)', () => {
		const hydrated = hydrateWizardStateFromPreset(makePreset());
		assert.deepStrictEqual(
			Object.keys(hydrated).sort(),
			['activeMetricKeys', 'activityProfile', 'corridors', 'idealRanges', 'isEditMode', 'metricAlertLevels'].sort(),
			`erwartet genau 6 Felder, gefunden: ${Object.keys(hydrated).join(', ')}`
		);
	});

	test('isEditMode ist immer true (Hub mountet den Organism wie den Editor)', () => {
		const hydrated = hydrateWizardStateFromPreset(makePreset());
		assert.strictEqual(hydrated.isEditMode, true);
	});

	test('corridors kommt unveraendert vom Top-Level-Feld des Presets', () => {
		const preset = makePreset();
		const hydrated = hydrateWizardStateFromPreset(preset);
		assert.deepStrictEqual(hydrated.corridors, preset.corridors);
	});

	test('activityProfile kommt aus preset.profil', () => {
		const hydrated = hydrateWizardStateFromPreset(makePreset({ profil: 'wandern' }));
		assert.strictEqual(hydrated.activityProfile, 'wandern');
	});

	test('idealRanges kommt aus display_config.ideal_ranges', () => {
		const preset = makePreset();
		const hydrated = hydrateWizardStateFromPreset(preset);
		assert.deepStrictEqual(hydrated.idealRanges, preset.display_config!.ideal_ranges);
	});

	test('metricAlertLevels kommt aus display_config.metric_alert_levels', () => {
		const preset = makePreset();
		const hydrated = hydrateWizardStateFromPreset(preset);
		assert.deepStrictEqual(hydrated.metricAlertLevels, preset.display_config!.metric_alert_levels);
	});

	test('#1191-Semantik: VORHANDENES leeres active_metrics-Array bleibt [] (keine Profil-Default-Ueberschreibung)', () => {
		const preset = makePreset({ display_config: { active_metrics: [] } });
		const hydrated = hydrateWizardStateFromPreset(preset);
		assert.deepStrictEqual(hydrated.activeMetricKeys, []);
	});

	test('#1191-Semantik: FEHLENDES active_metrics-Feld liefert null (Signal fuer Profil-Default-Pfad, kein stilles [])', () => {
		const preset = makePreset({ display_config: { region: 'Tirol' } });
		const hydrated = hydrateWizardStateFromPreset(preset);
		assert.strictEqual(
			hydrated.activeMetricKeys,
			null,
			'fehlendes active_metrics darf NICHT als leeres Array getarnt werden (rehydrateActiveMetrics-Semantik #1191)'
		);
	});
});

describe('AC-33/AC-34 + #1257/#1234-Kontext: buildHubPutPayload — Teil-Edit verliert keine Nachbarfelder', () => {
	test('Teil-Edit NUR corridors: metric_alert_levels und active_metrics bleiben byte-gleich aus dem Original', () => {
		const preset = makePreset();
		const newCorridors = [
			{ metric: 'snow_depth_cm', range: [30, null] as [number | null, number | null], notify: true, mark: true, prio: 'hoch' as const }
		];
		const { body } = buildHubPutPayload(preset, { corridors: newCorridors });

		assert.deepStrictEqual(
			body.display_config!.metric_alert_levels,
			preset.display_config!.metric_alert_levels,
			'metric_alert_levels darf sich bei einem reinen Korridor-Edit nicht veraendern (#1257-Kontext: Alarm-Regeln nicht verlieren)'
		);
		assert.deepStrictEqual(
			body.display_config!.active_metrics,
			preset.display_config!.active_metrics,
			'active_metrics darf sich bei einem reinen Korridor-Edit nicht veraendern'
		);
		assert.deepStrictEqual(body.corridors, newCorridors, 'corridors muss die editierte neue Zeile widerspiegeln');
	});

	test('Teil-Edit NUR pickedIds (Orte-Reorder/Entfernen): display_config bleibt komplett unangetastet', () => {
		const preset = makePreset();
		const newPickedIds = ['loc-3', 'loc-1', 'loc-2'];
		const { body } = buildHubPutPayload(preset, { pickedIds: newPickedIds });

		assert.deepStrictEqual(
			body.display_config,
			preset.display_config,
			'display_config darf sich bei einem reinen Orte-Reorder nicht veraendern'
		);
		assert.deepStrictEqual(body.location_ids, newPickedIds, 'location_ids muss die neue Reihenfolge widerspiegeln');
	});
});

describe('Fix-Loop 1 (F002, Adversary HIGH): flushPendingCorridorSave — reine Diff-/Payload-Entscheidung, entkoppelt vom ausloesenden DOM-Event', () => {
	function makeSnapshot(overrides: Partial<CorridorSnapshot> = {}): CorridorSnapshot {
		return {
			corridors: [{ metric: 'snow_depth_cm', range: [20, null], notify: true, mark: true, prio: 'hoch' }],
			idealRanges: { snow_depth_cm: { min: 20, max: null } },
			activeMetricKeys: ['snow_depth_cm', 'wind_gust'],
			metricAlertLevels: { snow_depth_cm: 'warn', wind_gust: 'mark' },
			...overrides
		};
	}

	test('unveraenderter ws-Zustand + flush → kein PUT (null), egal welches Ereignis den Flush ausgeloest hat', () => {
		const preset = makePreset();
		const before = makeSnapshot();
		const current = makeSnapshot();
		const result = flushPendingCorridorSave(preset, current, before);
		assert.strictEqual(result, null, 'unveraenderter Snapshot darf keinen PUT ausloesen (Waechter gegen unnoetige PUTs, #1234-Kontext)');
	});

	test('geaenderter ws-Zustand (Band-Drag verschiebt min) + flush → genau EIN PUT-Payload mit dem neuen Wert', () => {
		const preset = makePreset();
		const before = makeSnapshot();
		const current = makeSnapshot({
			corridors: [{ metric: 'snow_depth_cm', range: [45, null], notify: true, mark: true, prio: 'hoch' }]
		});
		const result = flushPendingCorridorSave(preset, current, before);
		assert.notStrictEqual(result, null, 'geaenderter Snapshot muss einen PUT-Payload liefern');
		assert.deepStrictEqual(
			result!.body.corridors,
			current.corridors,
			'PUT-Payload muss den neuen (verschobenen) Wert widerspiegeln, nicht den alten'
		);
		assert.deepStrictEqual(
			result!.body.display_config!.metric_alert_levels,
			preset.display_config!.metric_alert_levels,
			'Nachbarfelder (#1257-Kontext) duerfen bei einem reinen Band-Drag nicht verloren gehen'
		);
	});

	test('kein bisher persistierter Stand (before=null, erster Flush) + unveraendert seit Hydration → kein PUT', () => {
		const preset = makePreset();
		const current = makeSnapshot();
		const result = flushPendingCorridorSave(preset, current, null);
		assert.strictEqual(result, null, 'ohne vorherigen persistierten Stand ist der aktuelle Snapshot selbst die Baseline (analog handleCorridorCommit)');
	});

	test('Regressions-Beweis F002: der ALTE, wrapper-gebundene Mechanismus haette diesen Fall verpasst — der neue Fenster-Handler ruft dieselbe Funktion unabhaengig vom Ereignisziel auf', () => {
		// Simuliert einen Pointerup AUSSERHALB des `.hub-corridor-wrap`-Subtrees:
		// kein DOM-Event, keine Bubbling-Kette noetig — flushPendingCorridorSave
		// ist reine Zustands-Diff-Logik und kennt kein DOM-Ziel ueberhaupt.
		// Genau das macht sie fuer den Fenster-Handler (CompareTabs.svelte
		// `handleWindowPointerUp`) korrekt wiederverwendbar.
		const preset = makePreset();
		const before = makeSnapshot();
		const current = makeSnapshot({ metricAlertLevels: { snow_depth_cm: 'warn', wind_gust: 'off' } });
		const result = flushPendingCorridorSave(preset, current, before);
		assert.notStrictEqual(result, null, 'ein geaenderter Snapshot muss unabhaengig vom (nicht vorhandenen) DOM-Kontext einen Payload liefern');
	});
});

describe('Fix-Loop 2 (F005, Adversary CRITICAL): Cross-Tab-Sequenz — Baseline nach jedem PUT auffrischen verhindert Lost-Update', () => {
	// Reproduziert exakt den Adversary-Fund (repro_cross_tab_staleness.mjs /
	// repro_cross_tab_reverse.mjs, Runde 3): CompareTabs.svelte haelt jetzt EINE
	// mutable `currentPreset`-Baseline, die nach jedem erfolgreichen S6-PUT aus
	// dem Response-Body (hier durch den gesendeten Payload approximiert — der
	// PUT-Handler, internal/handler/compare_preset.go:390, liefert exakt das
	// gespeicherte Objekt zurueck) aufgefrischt wird. Beide Speicherpfade
	// (Orte via buildHubPutPayload, Idealwerte via flushPendingCorridorSave)
	// lesen ausschliesslich aus dieser aufgefrischten Baseline.

	function makeCorridorSnapshot(preset: ComparePreset): CorridorSnapshot {
		const dc = preset.display_config as Record<string, unknown>;
		return {
			corridors: preset.corridors!,
			idealRanges: dc.ideal_ranges as CorridorSnapshot['idealRanges'],
			activeMetricKeys: dc.active_metrics as string[],
			metricAlertLevels: dc.metric_alert_levels as Record<string, string>
		};
	}

	test('Orte-Edit ZUERST, dann Idealwerte-Edit: zweiter PUT-Payload enthaelt BEIDE Aenderungen', () => {
		let baseline = makePreset();

		// Edit A: Nutzer sortiert im Orte-Tab um -> PUT 1 -> Response wird zur neuen Baseline.
		const newIds = ['loc-3', 'loc-1', 'loc-2'];
		const payload1 = buildHubPutPayload(baseline, { pickedIds: newIds });
		baseline = payload1.body;

		// Edit B: Nutzer wechselt in den Idealwerte-Tab, verschiebt ein Band (min 20 -> 45).
		const before = makeCorridorSnapshot(baseline);
		const current: CorridorSnapshot = {
			...before,
			corridors: [{ metric: 'snow_depth_cm', range: [45, null], notify: true, mark: true, prio: 'hoch' }]
		};
		const payload2 = flushPendingCorridorSave(baseline, current, before);

		assert.notStrictEqual(payload2, null, 'geaenderter Corridor-Snapshot muss einen PUT-Payload liefern');
		assert.deepStrictEqual(
			payload2!.body.location_ids,
			newIds,
			'Payload 2 (Idealwerte) darf die bereits persistierte Orte-Reihenfolge aus Edit A NICHT auf den Lade-Stand zuruecksetzen'
		);
		assert.deepStrictEqual(
			payload2!.body.corridors,
			current.corridors,
			'Payload 2 muss die neue Idealwerte-Aenderung aus Edit B enthalten'
		);
	});

	test('Idealwerte-Edit ZUERST (inkl. metric_alert_levels), dann Orte-Edit: zweiter PUT-Payload enthaelt BEIDE Aenderungen (umgekehrte Richtung)', () => {
		let baseline = makePreset();

		// Edit A: Nutzer setzt im Idealwerte-Tab eine Alarmstufe (#1257/#1234-relevant) und verschiebt ein Band.
		const before = makeCorridorSnapshot(baseline);
		const current: CorridorSnapshot = {
			...before,
			corridors: [{ metric: 'snow_depth_cm', range: [45, null], notify: true, mark: true, prio: 'hoch' }],
			metricAlertLevels: { snow_depth_cm: 'mark', wind_gust: 'mark' }
		};
		const payload1 = flushPendingCorridorSave(baseline, current, before);
		assert.notStrictEqual(payload1, null);
		baseline = payload1!.body;

		// Edit B: Nutzer wechselt in den Orte-Tab und entfernt einen Ort.
		const newIds = ['loc-1', 'loc-2'];
		const payload2 = buildHubPutPayload(baseline, { pickedIds: newIds });

		assert.deepStrictEqual(payload2.body.location_ids, newIds);
		assert.deepStrictEqual(
			payload2.body.corridors,
			current.corridors,
			'Payload 2 (Orte) darf die zuvor persistierte Idealwerte-Bandverschiebung aus Edit A nicht zuruecksetzen'
		);
		assert.deepStrictEqual(
			payload2.body.display_config!.metric_alert_levels,
			current.metricAlertLevels,
			'#1257/#1234-Kontext: eine bereits gespeicherte Alarmstufen-Aenderung darf durch eine nachfolgende Orte-Aktion nicht verloren gehen'
		);
	});
});

describe('Fix-Loop 2 (F006, Adversary MEDIUM): shouldFlushOnWindowPointerUp — reine Guard-Entscheidung fuer den Fenster-Handler', () => {
	test('aktiver Idealwerte-Tab + hydratisiert -> true (flush)', () => {
		assert.strictEqual(shouldFlushOnWindowPointerUp('idealwerte', true), true);
	});

	test('anderer aktiver Tab (z.B. orte), auch wenn hydratisiert -> false (kein flush)', () => {
		assert.strictEqual(shouldFlushOnWindowPointerUp('orte', true), false);
	});

	test('Idealwerte-Tab aktiv, aber noch nicht hydratisiert -> false (kein flush)', () => {
		assert.strictEqual(shouldFlushOnWindowPointerUp('idealwerte', false), false);
	});

	test('weder aktiver Idealwerte-Tab noch hydratisiert -> false', () => {
		assert.strictEqual(shouldFlushOnWindowPointerUp('uebersicht', false), false);
	});
});

describe('Fix-Loop 3 (F007, Adversary CRITICAL): buildToggleActivePutPayload — dritter PUT-Pfad (Pausieren/Aktivieren) muss die frische Baseline nutzen, nicht die eingefrorene preset-Prop', () => {
	test('S6-Edit (Orte-Reorder) -> Toggle: Toggle-Payload enthaelt die frischen location_ids/corridors/metric_alert_levels UND das getoggelte schedule-Feld', () => {
		// Reproduziert exakt den Adversary-Fund (Runde 4, Angriffspunkt 1c): erst
		// ein S6-Edit im Orte-Tab (PUT 1 -> Response wird zur neuen Baseline,
		// identisch zum CompareTabs.svelte-Muster `currentPreset = await
		// api.put(...)`), danach ein Klick auf Pausieren/Aktivieren im
		// Uebersicht-Tab (PUT 2). Vor dem Fix spread'te handleToggleActive die
		// urspruengliche, eingefrorene `preset`-Prop -> der bereits persistierte
		// Orte-Edit (UND metric_alert_levels/corridors) waeren im Toggle-PUT
		// wieder auf den Lade-Zeitpunkt-Stand zurueckgefallen.
		let baseline = makePreset();

		// Edit A: Orte-Reorder (analog persistPickedIds) -> Baseline auffrischen.
		const newIds = ['loc-3', 'loc-1', 'loc-2'];
		const editPayload = buildHubPutPayload(baseline, { pickedIds: newIds });
		baseline = editPayload.body;

		// Edit B: Nutzer klickt "Aktivieren" (Uebersicht-Tab).
		const togglePayload = buildToggleActivePutPayload(baseline, 'daily', 'daily');

		assert.deepStrictEqual(
			togglePayload.body.location_ids,
			newIds,
			'Toggle-PUT darf den bereits persistierten Orte-Reorder aus Edit A nicht auf den Lade-Stand zuruecksetzen'
		);
		assert.deepStrictEqual(
			togglePayload.body.corridors,
			baseline.corridors,
			'Toggle-PUT muss die (unveraenderten) Korridore aus der frischen Baseline widerspiegeln'
		);
		assert.deepStrictEqual(
			togglePayload.body.display_config!.metric_alert_levels,
			baseline.display_config!.metric_alert_levels,
			'#1257/#1234-Kontext: metric_alert_levels darf durch einen nachfolgenden Toggle nicht verloren gehen'
		);
		assert.strictEqual(togglePayload.body.schedule, 'daily', 'Toggle-Payload muss das getoggelte schedule-Feld enthalten');
		assert.strictEqual(togglePayload.url, `/api/compare/presets/${baseline.id}`);
	});

	test('S6-Edit (Idealwerte, inkl. metric_alert_levels) -> Toggle: Toggle-Payload enthaelt die frische Baseline (umgekehrte Reihenfolge)', () => {
		let baseline = makePreset();

		// Edit A: Idealwerte-Edit (Bandverschiebung + Alarmstufe) -> Baseline auffrischen.
		const dc = baseline.display_config as Record<string, unknown>;
		const before: CorridorSnapshot = {
			corridors: baseline.corridors!,
			idealRanges: dc.ideal_ranges as CorridorSnapshot['idealRanges'],
			activeMetricKeys: dc.active_metrics as string[],
			metricAlertLevels: dc.metric_alert_levels as Record<string, string>
		};
		const current: CorridorSnapshot = {
			...before,
			corridors: [{ metric: 'snow_depth_cm', range: [45, null], notify: true, mark: true, prio: 'hoch' }],
			metricAlertLevels: { snow_depth_cm: 'mark', wind_gust: 'mark' }
		};
		const editPayload = flushPendingCorridorSave(baseline, current, before);
		assert.notStrictEqual(editPayload, null);
		baseline = editPayload!.body;

		// Edit B: Nutzer klickt "Pausieren" (schedule -> manual).
		const togglePayload = buildToggleActivePutPayload(baseline, 'manual', 'daily');

		assert.deepStrictEqual(
			togglePayload.body.corridors,
			current.corridors,
			'Toggle-PUT darf die bereits persistierte Bandverschiebung aus Edit A nicht zuruecksetzen'
		);
		assert.deepStrictEqual(
			togglePayload.body.display_config!.metric_alert_levels,
			current.metricAlertLevels,
			'#1257/#1234-Kontext: eine bereits gespeicherte Alarmstufen-Aenderung darf durch einen nachfolgenden Toggle nicht verloren gehen'
		);
		assert.strictEqual(togglePayload.body.schedule, 'manual');
		assert.strictEqual(togglePayload.body.previous_schedule, 'daily');
	});
});

describe('Edge Case Spec Z.1020: snapshotForRollback liefert einen echten Deep-Copy-Prae-Zustand', () => {
	test('Mutation des Arbeitszustands NACH dem Snapshot veraendert den Snapshot nicht', () => {
		const workingState = { corridors: [{ metric: 'snow_depth_cm', range: [20, null] as [number | null, number | null], notify: true, mark: false }] };
		const snapshot = snapshotForRollback(workingState);

		workingState.corridors[0].range[0] = 999;
		workingState.corridors.push({ metric: 'wind_gust', range: [null, null], notify: false, mark: false });

		assert.deepStrictEqual(
			snapshot,
			{ corridors: [{ metric: 'snow_depth_cm', range: [20, null], notify: true, mark: false }] },
			'der Snapshot muss den Zustand VOR der Mutation zeigen (Deep-Copy, keine geteilten Referenzen)'
		);
	});
});

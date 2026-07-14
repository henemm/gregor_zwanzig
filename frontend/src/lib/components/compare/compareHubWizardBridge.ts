// Issue #1256 Scheibe 6 — Hub-Wizard-Bridge fuer den eingebetteten
// CorridorEditor (context="vergleich") im Hub-Idealwerte-Tab.
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 6
//   (AC-16, AC-33, AC-34), Edge Case Z.1020 (PUT-Fehler -> Rollback).
// Context: docs/context/feat-1256-s6-hub-idealwerte-inline.md § Entscheidung 1+3.
//
// `CorridorEditor.svelte` liest im vergleich-Kontext GENAU 6 Felder aus
// `getContext('compare-wizard-state')` (Z.41-113). Diese Datei extrahiert die
// Teil-Hydration + Persistenz-Uebersetzung, die bislang nur inline in
// routes/compare/[id]/edit/+page.svelte existierte — 0 Zeilen Diff im
// Organism selbst (C0).
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { ActivityProfile, ChannelLayouts, ComparePreset, Corridor } from '../../types.ts';
import type { IdealRange } from './compareMetricDefs.ts';
import { buildComparePresetSavePayload } from './compareEditorSave.ts';
import { rehydrateActiveMetrics } from './compareEditorLoad.ts';

/** Plain-Objekt mit GENAU den 6 Feldern, die CorridorEditor.svelte im
 * vergleich-Kontext aus dem Wizard-State liest. Die Bridge-Komponente
 * (CompareTabs.svelte) uebertraegt dies auf eine echte CompareWizardState-
 * Instanz und ruft setContext(...). */
export interface HubWizardFields {
	isEditMode: true;
	corridors: Corridor[];
	activityProfile: ActivityProfile | null;
	idealRanges: Record<string, IdealRange>;
	// #1191-Semantik (rehydrateActiveMetrics): null = "Feld fehlte im Preset"
	// (Signal fuer Profil-Default-Pfad), NIEMALS still als [] getarnt.
	activeMetricKeys: string[] | null;
	metricAlertLevels: Record<string, string>;
}

/**
 * Teil-Hydration der 6 CorridorEditor-Felder aus einem ComparePreset.
 * isEditMode ist immer true — der Hub mountet den Organism wie den Editor.
 */
export function hydrateWizardStateFromPreset(preset: ComparePreset): HubWizardFields {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	const rehydrated = rehydrateActiveMetrics(displayConfig.active_metrics as string[] | undefined);
	return {
		isEditMode: true,
		corridors: preset.corridors ?? [],
		activityProfile: (preset.profil as ActivityProfile) ?? null,
		idealRanges: (displayConfig.ideal_ranges as Record<string, IdealRange>) ?? {},
		activeMetricKeys: rehydrated ? rehydrated.activeMetricKeys : null,
		metricAlertLevels: (displayConfig.metric_alert_levels as Record<string, string>) ?? {}
	};
}

/** Teil-Edit fuer den Hub: nur die Felder, die eine Nutzeraktion tatsaechlich
 * veraendert hat, werden geliefert — alle anderen kommen per Read-Modify-Write
 * unveraendert aus `preset` (#1257/#1234-Kontext: metric_alert_levels und
 * active_metrics duerfen nie stillschweigend verloren gehen). */
export interface HubEdit {
	corridors?: Corridor[];
	pickedIds?: string[];
	idealRanges?: Record<string, IdealRange>;
	activeMetricKeys?: string[];
	metricAlertLevels?: Record<string, string>;
}

/**
 * Duenner Adapter um `buildComparePresetSavePayload`: hydratisiert die
 * required-Felder der Editor-Edits aus `preset`, ueberschreibt sie nur dort,
 * wo `edit` tatsaechlich einen neuen Wert liefert.
 */
export function buildHubPutPayload(
	preset: ComparePreset,
	edit: HubEdit
): { url: string; body: ComparePreset } {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	return buildComparePresetSavePayload(preset, {
		name: preset.name,
		activityProfile: (preset.profil as ActivityProfile) ?? null,
		pickedIds: edit.pickedIds ?? preset.location_ids ?? [],
		region: (displayConfig.region as string) ?? '',
		idealRanges: edit.idealRanges ?? (displayConfig.ideal_ranges as Record<string, IdealRange>) ?? {},
		channelLayouts: (displayConfig.channel_layouts as ChannelLayouts) ?? null,
		activeMetricKeys: edit.activeMetricKeys ?? (displayConfig.active_metrics as string[] | undefined),
		metricAlertLevels:
			edit.metricAlertLevels ?? (displayConfig.metric_alert_levels as Record<string, string> | undefined),
		corridors: edit.corridors ?? preset.corridors
	});
}

/**
 * Deep-Copy-Helfer fuer den Prae-Aktions-Zustand (Edge Case Z.1020, Rollback
 * bei PUT-Fehler). JSON-Rundreise statt structuredClone, damit Svelte-$state-
 * Proxies zuverlaessig in ein reines, unabhaengiges Objekt entpackt werden.
 */
export function snapshotForRollback<T>(value: T): T {
	return JSON.parse(JSON.stringify(value)) as T;
}

/** Plain-Snapshot der 4 persistenzrelevanten CorridorEditor-Felder (Teilmenge
 * von HubWizardFields ohne isEditMode/activityProfile, die der Idealwerte-Tab
 * nicht schreibt). */
export interface CorridorSnapshot {
	corridors: Corridor[];
	idealRanges: Record<string, IdealRange>;
	activeMetricKeys: string[];
	metricAlertLevels: Record<string, string>;
}

/**
 * Issue #1256 Scheibe 6 Fix-Loop 1 (F002, Adversary HIGH): reine
 * Diff-/Payload-Entscheidung fuer den Idealwerte-Tab-Commit, entkoppelt vom
 * DOM-Event, das ihn ausloest (Wrapper-Bubbling ODER Fenster-Ebene) — beide
 * Aufrufer rufen dieselbe Funktion, damit ein Pointer-Release ausserhalb des
 * Wrapper-Subtrees (z. B. bei einem Band-Handle-Drag) nicht mehr zu einem
 * uebersehenen Commit fuehrt.
 * Liefert `null`, wenn sich der persistenzrelevante Ausschnitt seit dem
 * letzten persistierten Snapshot NICHT veraendert hat (Waechter gegen
 * unnoetige PUTs, #1234-Kontext) — sonst den fertigen PUT-Payload.
 */
export function flushPendingCorridorSave(
	preset: ComparePreset,
	current: CorridorSnapshot,
	before: CorridorSnapshot | null
): { url: string; body: ComparePreset } | null {
	const baseline = before ?? current;
	if (JSON.stringify(current) === JSON.stringify(baseline)) return null;
	return buildHubPutPayload(preset, {
		corridors: current.corridors,
		idealRanges: current.idealRanges,
		activeMetricKeys: current.activeMetricKeys,
		metricAlertLevels: current.metricAlertLevels
	});
}

/**
 * Issue #1256 Scheibe 6 Fix-Loop 2 (F006, Adversary MEDIUM): reine
 * Entscheidungslogik fuer den fenster-weiten Pointerup-Flush-Guard
 * (`<svelte:window onpointerup>` in CompareTabs.svelte, F002-Fix aus Fix-Loop 1)
 * — herausgezogen aus dem Svelte-Handler, damit sie ohne DOM/Browser testbar
 * ist. Der Svelte-Handler `handleWindowPointerUp` wird dadurch zu einer
 * 1-Zeilen-Delegation; die untestbare Flaeche schrumpft auf diese Zeile.
 * Flush nur, wenn der Idealwerte-Tab aktiv UND bereits hydratisiert ist
 * (sonst gibt es keinen sinnvollen `wizardState`-Stand zum Speichern).
 */
export function shouldFlushOnWindowPointerUp(activeTab: string, idealwerteHydrated: boolean): boolean {
	return activeTab === 'idealwerte' && idealwerteHydrated;
}

/**
 * Issue #1256 Scheibe 6 Fix-Loop 3 (F007, Adversary CRITICAL): reine
 * Payload-Konstruktion fuer den Uebersicht-Tab-Pausieren/Aktivieren-Pfad
 * (`handleToggleActive` in CompareTabs.svelte) — bislang der einzige der
 * drei Hub-PUT-Pfade, der noch die eingefrorene `preset`-Prop statt der
 * laufend aktuellen `currentPreset`-Baseline spread'te (identischer Bug wie
 * F005 fuer die Orte-/Idealwerte-Pfade, hier fuer einen dritten,
 * vorbestehenden Pfad). Analog `flushPendingCorridorSave`: reine Funktion,
 * kein DOM/Browser-Bezug, der Svelte-Handler bleibt eine duenne Delegation.
 */
export function buildToggleActivePutPayload(
	preset: ComparePreset,
	schedule: string,
	previousSchedule: string
): { url: string; body: ComparePreset } {
	return {
		url: `/api/compare/presets/${preset.id}`,
		body: { ...preset, schedule, previous_schedule: previousSchedule }
	};
}

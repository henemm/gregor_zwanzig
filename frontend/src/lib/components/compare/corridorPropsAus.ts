// Issue #2276 Scheibe S6d (Epic #2345) — EINE Stelle, die aus dem
// Compare-Wizard-Zustand das Prop-Bündel für die beiden geteilten
// Wertebereiche-Organismen (`shared/corridor-editor/CorridorEditor.svelte` und
// `CorridorEditorMobile.svelte`) baut. Alle DREI Vergleichs-Mounts (Hub
// `CompareTabs.svelte`, Anlege-Seite Desktop + Mobil `CompareNewEditor.svelte`)
// speisen dasselbe Bündel ein — bei drei Mounts × vier Feldern wären
// Inline-Adapter dreifache Gelegenheit zur Drift (Spec, Design-Entscheidung 1).
//
// gz-eigenstaendig: Diese Uebersetzung vom Compare-Wizard-Zustand in Wertprops
// gehört nach compare/ und hat bewusst kein Trip-Pendant — läge sie in shared/,
// importierte der geteilte Bereich die Compare-Klebeschicht (genau das, was
// #2276 abbaut und corridor_editor_laedt_keine_compare_klebeschicht.test.ts
// bewacht), und der Trip-Mount braucht sie nicht: er übergibt `trip`/
// `onTripUpdate` ohne Zwischenschicht.
//
// 🔴 Aufrufform (prüfbar, kein Prosa-Wunsch, Form-Auflage A1):
// `{...corridorPropsAus(wiz)}` steht IM MARKUP-AUSDRUCK jedes Mounts, NIEMALS
// in einer Skript-Variablen. Ein einmal berechnetes, dort eingefrorenes Objekt
// bestünde SSR-Prüfstand und AST-Wächter anstandslos und fiele erst im Browser
// auf — die `$state`-Lesezugriffe würden dann außerhalb des reaktiven Renderns
// registriert.
//
// 🔴 `activeMetricKeys` wird NICHT auf `[]` heruntergezogen: `null` heißt „nie
// eingestellt" (materializeActiveMetricKeys liefert dann die Vorgabemenge),
// `[]` heißt „bewusst leer" (#1366 F002). Ein `?? []` an dieser Stelle
// verschöbe still die gespeicherte Auswahl.
//
// Kein Browser-/SvelteKit-Import (nur Typen) — lauffähig unter
// node --experimental-strip-types.

import type { ActivityProfile, Corridor } from '../../types.ts';
import type { IdealRange } from '../shared/corridor-editor/corridorEditorState.ts';

/** Strukturelle Sicht auf die Wertebereiche-Felder des Compare-Wizard-Zustands
 *  — absichtlich nicht `CompareWizardState` selbst, damit diese Funktion auch
 *  gegen einen hydrierten Plain-Zustand (Hub-Bridge) arbeitet. */
export interface CorridorZustandsQuelle {
	corridors?: Corridor[];
	idealRanges?: Record<string, IdealRange>;
	activeMetricKeys?: string[] | null;
	metricAlertLevels?: Record<string, string>;
	isEditMode?: boolean;
	activityProfile?: ActivityProfile | null;
}

/**
 * Das Prop-Bündel für `CorridorEditor(Mobile) context="vergleich"`: die vier
 * persistenzrelevanten Werte, die vier Gesten-Rückrufe (zugleich Schreibweg
 * der Brücke `corridorZustandsBruecke`, inklusive Rollback) und die beiden
 * Anlege-Merkmale `isEditMode`/`activityProfile`, die den Profil-Prefill des
 * Create-Flusses steuern.
 */
export function corridorPropsAus(wiz: CorridorZustandsQuelle) {
	return {
		corridors: wiz.corridors ?? [],
		idealRanges: wiz.idealRanges ?? {},
		activeMetricKeys: wiz.activeMetricKeys ?? null,
		metricAlertLevels: wiz.metricAlertLevels ?? {},
		isEditMode: wiz.isEditMode ?? false,
		activityProfile: wiz.activityProfile ?? null,
		onCorridorsChange: (v: Corridor[]) => {
			wiz.corridors = v;
		},
		onIdealRangesChange: (v: Record<string, IdealRange>) => {
			wiz.idealRanges = v;
		},
		onActiveMetricKeysChange: (v: string[] | null) => {
			wiz.activeMetricKeys = v;
		},
		onMetricAlertLevelsChange: (v: Record<string, string>) => {
			wiz.metricAlertLevels = v;
		}
	};
}

// Issue #2277 Scheibe S2c — /compare/new?from=<id>: Anlege-Zustand aus einem
// bestehenden Ortsvergleich (Vorlage) vorbelegen. Einmaliger Aufruf beim
// Seitenaufbau, kein reaktiver Effekt (AC-10).
// Spec: docs/specs/modules/feat_2277_s2c_compare_from_vorlage.md
// gz-eigenstaendig: Vorlagen-Vorbelegung fuer den Ortsvergleich; ein Trip-Pendant existiert nicht, /trips/new?from= ist tot (templateTrip ungenutzt), siehe Spec feat_2277_s2c_compare_from_vorlage Entscheidung 1
//
// Komponiert die vorhandenen Hub-Hydrierer (unverändert) und ergänzt nur die
// Felder ohne gemeinsamen Hydrierer. Identität (id, ETag, letzter_versand,
// Aktiv-Status) wird nie übernommen; `isEditMode` bleibt false (AC-3).

import type { ComparePreset, Location } from '$lib/types';
import type { CompareWizardState } from '../compare/compareWizardState.svelte';
import {
	hydrateAlarmFieldsFromPreset,
	hydrateHubFieldsFromPreset
} from '../compare/compareHubHydration.ts';
import { hydrateVersandFieldsFromPreset } from '../shared/versandVergleichSpeicherung.ts';
import {
	hydrateChannelActiveMetricsFromPreset,
	hydrateDayWindowFromPreset,
	hydrateLayoutFieldsFromPreset
} from '../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';

export function vorlageInZustand(
	preset: ComparePreset,
	locations: Location[],
	state: CompareWizardState
): void {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};

	// Alarm-Felder zuerst: der Alarm-Hydrierer setzt activeMetricKeys ohne
	// null-Sentinel; das Hub-Ergebnis unten überschreibt es sentineltreu.
	hydrateAlarmFieldsFromPreset(state, preset);
	// isEditMode wird bewusst NICHT übertragen (Anlege-Modus, AC-3).
	const { isEditMode: _nichtUebernehmen, ...hub } = hydrateHubFieldsFromPreset(preset);
	Object.assign(state, hub);
	// Versand inkl. endDate (fehlend ⇒ null, AC-9).
	Object.assign(state, hydrateVersandFieldsFromPreset(preset));
	state.channelActiveMetricKeys = hydrateChannelActiveMetricsFromPreset(preset);
	Object.assign(state, hydrateDayWindowFromPreset(preset));
	Object.assign(state, hydrateLayoutFieldsFromPreset(preset));

	state.name = `${preset.name} (Kopie)`;
	state.region = (displayConfig.region as string | undefined) ?? '';
	state.pickedIds = (preset.location_ids ?? []).filter((id) =>
		locations.some((l) => l.id === id)
	);
	state.schedule = preset.schedule === 'weekly' ? 'weekly' : 'daily_morning';
	state.weekday = preset.weekday ?? 0;
	state.officialAlertTriggersEnabled = preset.official_alert_triggers_enabled !== false;
}

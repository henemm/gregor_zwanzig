// Issue #2277 Scheibe S2c — /compare/new?from=<id>: Anlege-Zustand aus einem
// bestehenden Ortsvergleich (Vorlage) vorbelegen. Einmaliger Aufruf beim
// Seitenaufbau, kein reaktiver Effekt (AC-10).
// Spec: docs/specs/modules/feat_2277_s2c_compare_from_vorlage.md
// gz-eigenstaendig: Vorlagen-Vorbelegung fuer den Ortsvergleich; ein Trip-Pendant existiert nicht, /trips/new?from= ist tot (templateTrip ungenutzt), siehe Spec feat_2277_s2c_compare_from_vorlage Entscheidung 1
//
// Komponiert die vorhandenen Hub-Hydrierer (unverändert) und ergänzt nur die
// Felder ohne gemeinsamen Hydrierer. Identität (id, ETag, letzter_versand,
// Aktiv-Status) wird nie übernommen; `isEditMode` bleibt draußen (AC-3).
//
// Issue #2727 (Epic #2345, DoD-1): reine Funktion `preset, locations → Feldsatz`
// statt Mutation eines Zustandsobjekts. Der Anlege-Editor legt das Ergebnis
// einmalig beim Start über den Standard-Feldsatz. `weekday` entfällt (wurde nie
// gelesen und reist nicht im Create-Payload).
// Spec: docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md (AC-7)

import type { ComparePreset, Location } from '$lib/types';
import type { CompareFeldsatz } from '../compare/compareEditorSave.ts';
import type { AlarmHydrationTarget } from '../shared/alarmeVergleichSpeicherung.ts';
import {
	hydrateAlarmFieldsFromPreset,
	hydrateHubFieldsFromPreset
} from '../compare/compareHubHydration.ts';
import { hydrateVersandFieldsFromPreset } from '../shared/versandVergleichSpeicherung.ts';
import { tr } from '../../i18n/index.ts';
import {
	hydrateChannelActiveMetricsFromPreset,
	hydrateDayWindowFromPreset,
	hydrateLayoutFieldsFromPreset
} from '../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';

export function feldsatzAusVorlage(
	preset: ComparePreset,
	locations: Location[]
): Partial<CompareFeldsatz> {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};

	// Alarm-Felder zuerst: der Alarm-Hydrierer setzt activeMetricKeys ohne
	// null-Sentinel; das Hub-Ergebnis unten überschreibt es sentineltreu.
	const alarm: AlarmHydrationTarget = {};
	hydrateAlarmFieldsFromPreset(alarm, preset);
	// isEditMode wird bewusst NICHT übertragen (Anlege-Modus, AC-3).
	const { isEditMode: _nichtUebernehmen, ...hub } = hydrateHubFieldsFromPreset(preset);

	return {
		...(alarm as Partial<CompareFeldsatz>),
		...hub,
		// Versand inkl. endDate (fehlend ⇒ null, AC-9).
		...hydrateVersandFieldsFromPreset(preset),
		channelActiveMetricKeys: hydrateChannelActiveMetricsFromPreset(preset),
		...hydrateDayWindowFromPreset(preset),
		...hydrateLayoutFieldsFromPreset(preset),
		// Issue #2659 (i18n F10): Vorschlagsname in der Sprache des Nutzers (danach Nutzerdaten).
		name: tr('vergleich.neu.kopie', { name: preset.name }),
		region: (displayConfig.region as string | undefined) ?? '',
		pickedIds: (preset.location_ids ?? []).filter((id) => locations.some((l) => l.id === id)),
		schedule: preset.schedule === 'weekly' ? 'weekly' : 'daily_morning',
		officialAlertTriggersEnabled: preset.official_alert_triggers_enabled !== false
	};
}

// Issue #679 — Pure-Function: Compare-Preset-Save-Payload
// Spec: docs/specs/modules/issue_679_compare_editor_edit.md § AC-3
//
// Round-Trip-Spread: nicht editierte Felder (empfaenger, schedule, hour_from/to,
// weekday, previous_schedule) kommen unveraendert aus `original`. Nur explizit
// geaenderte Felder werden ueberschrieben. Verhindert Datenverlust beim Speichern.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { ComparePreset, ActivityProfile, ChannelLayouts } from '../../types.ts';
import type { IdealRange } from './compareMetricDefs.ts';

export interface CompareEditorEdits {
	name: string;
	activityProfile: ActivityProfile | null;
	pickedIds: string[];
	region: string;
	idealRanges: Record<string, IdealRange>;
	channelLayouts: ChannelLayouts | null;
	// Issue #680: Slice 3 — aktive Metriken (AC-10). Optional → rückwärtskompatibel.
	activeMetricKeys?: string[];
	// Issue #764: Vorhersage-Horizont. Optional → rückwärtskompatibel.
	forecastHours?: number;
	// Issue #1040: amtliche Warnungen ein/aus. Optional → rückwärtskompatibel.
	officialAlertsEnabled?: boolean;
	// Issue #1104: Anzahl Orte mit stündlichem Detail. Optional → rückwärtskompatibel.
	topN?: number;
}

/**
 * Baut den PUT-Payload fuer `/api/compare/presets/{id}`.
 *
 * Schluesselprinzip: `{ ...original, <überschriebene Felder> }` — damit
 * round-trippen alle vom Editor nicht angefassten Felder unveraendert.
 */
export function buildComparePresetSavePayload(
	original: ComparePreset,
	edits: CompareEditorEdits
): { url: string; body: ComparePreset } {
	const url = '/api/compare/presets/' + original.id;

	const displayConfig: Record<string, unknown> = {
		...((original.display_config as Record<string, unknown>) ?? {}),
		region: edits.region
	};

	if (Object.keys(edits.idealRanges).length > 0) {
		displayConfig.ideal_ranges = edits.idealRanges;
	}

	if (edits.channelLayouts !== null) {
		displayConfig.channel_layouts = edits.channelLayouts;
	}

	if (edits.topN !== undefined) {
		displayConfig.top_n = edits.topN;
	}

	if (edits.activeMetricKeys !== undefined) {
		if (edits.activeMetricKeys.length > 0) {
			displayConfig.active_metrics = edits.activeMetricKeys;
		} else {
			// Leere Auswahl: active_metrics aus dem Spread entfernen, damit kein Datenschrott bleibt
			delete displayConfig.active_metrics;
		}
	}

	const body: ComparePreset = {
		...original,
		name: edits.name,
		location_ids: edits.pickedIds,
		profil: edits.activityProfile ?? original.profil,
		display_config: displayConfig,
		// Issue #764: Edit-Wert überschreibt den Spread-Wert aus original.
		// undefined → Feld fehlt in edits → Spread-Wert bleibt erhalten (Round-Trip).
		...(edits.forecastHours !== undefined ? { forecast_hours: edits.forecastHours } : {}),
		// Issue #1040: analoges Round-Trip-Prinzip für official_alerts_enabled.
		...(edits.officialAlertsEnabled !== undefined
			? { official_alerts_enabled: edits.officialAlertsEnabled }
			: {})
	};

	return { url, body };
}

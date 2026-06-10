// Issue #441 — Shared Module: Metrik-Definitionen + Skalengrenzen + Default-Idealwerte.
// Spec: docs/specs/modules/issue_441_compare_wizard_step3_idealwerte.md §1
//
// Wird von Step3Idealwerte.svelte konsumiert. CompareMatrix.svelte wird in einem
// Folge-Schritt auf diese Definitionen umgestellt (Folge-Issue, nicht hier).

export interface MetricDef {
	label: string;
	key: string;
	unit: string;
	decimals: number;
	higherIsBetter: boolean;
	kind: 'range' | 'enum';
	// nur für kind === 'range':
	rangeMin?: number;
	rangeMax?: number;
	step?: number;
	// nur für kind === 'enum':
	enumValues?: string[];
}

export interface IdealRange {
	min?: number | null;
	max?: number | string | null; // string für enum (NONE/MED/HIGH)
}

export type ProfileKey = 'WINTERSPORT' | 'ALPINE_TOURING' | 'SUMMER_TREKKING' | 'ALLGEMEIN';

// Skalengrenzen-Helfer: Eine einzige Stelle pro Metrik-Key.
const SNOW_DEPTH:    MetricDef = { label: 'Schneehöhe',     key: 'snow_depth_cm',     unit: 'cm',  decimals: 0, higherIsBetter: true,  kind: 'range', rangeMin: 0,     rangeMax: 200,   step: 5   };
const SNOW_NEW:      MetricDef = { label: 'Neuschnee',      key: 'snow_new_sum_cm',   unit: 'cm',  decimals: 0, higherIsBetter: true,  kind: 'range', rangeMin: 0,     rangeMax: 50,    step: 1   };
const SUNNY_HOURS:   MetricDef = { label: 'Sonnenstunden',  key: 'sunny_hours_h',     unit: 'h',   decimals: 1, higherIsBetter: true,  kind: 'range', rangeMin: 0,     rangeMax: 12,    step: 0.5 };
const WIND_MAX:      MetricDef = { label: 'Windspitzen',    key: 'wind_max_kmh',      unit: 'km/h',decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0,     rangeMax: 100,   step: 5   };
const CLOUD_AVG:     MetricDef = { label: 'Bewölkung Ø',    key: 'cloud_avg_pct',     unit: '%',   decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0,     rangeMax: 100,   step: 5   };
const VISIBILITY:    MetricDef = { label: 'Sichtweite min', key: 'visibility_min_m',  unit: 'm',   decimals: 0, higherIsBetter: true,  kind: 'range', rangeMin: 0,     rangeMax: 10000, step: 500 };
const PRECIP_SUM:    MetricDef = { label: 'Niederschlag',   key: 'precip_sum_mm',     unit: 'mm',  decimals: 1, higherIsBetter: false, kind: 'range', rangeMin: 0,     rangeMax: 30,    step: 0.5 };
const UV_INDEX:      MetricDef = { label: 'UV-Index max',   key: 'uv_index_max',      unit: '',    decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0,     rangeMax: 12,    step: 1   };
const TEMP_MAX:      MetricDef = { label: 'Temperatur max', key: 'temp_max_c',        unit: '°C',  decimals: 0, higherIsBetter: true,  kind: 'range', rangeMin: -20,   rangeMax: 45,    step: 1   };
const THUNDER:       MetricDef = { label: 'Gewitter',       key: 'thunder_level_max', unit: '',    decimals: 0, higherIsBetter: false, kind: 'enum',  enumValues: ['NONE', 'MED', 'HIGH'] };

// Issue #680: Slice 3 — flaches Array aller anwählbaren Metriken (AC-8/AC-9)
export const ALL_METRICS: MetricDef[] = [
	SNOW_DEPTH, SNOW_NEW, SUNNY_HOURS, WIND_MAX,
	CLOUD_AVG, VISIBILITY, PRECIP_SUM, UV_INDEX, TEMP_MAX, THUNDER
];

/**
 * Leitet einen lesbaren Ideal-Text aus einem Range-Objekt + Einheit ab (AC-6).
 * Wichtig: min === 0 ist ein gültiger Wert und wird als Untergrenze behandelt.
 */
export function deriveIdealText(
	range: { min?: number | null; max?: number | string | null },
	unit: string
): string {
	const hasMin = range.min != null && range.min !== undefined;
	const hasMax = range.max != null && range.max !== undefined;
	const unitSuffix = unit ? ' ' + unit : '';
	if (hasMin && hasMax) return `${range.min}–${range.max}${unitSuffix}`;
	if (hasMin) return `≥ ${range.min}${unitSuffix}`;
	if (hasMax) return `≤ ${range.max}${unitSuffix}`;
	return '–';
}

export const PROFILE_METRICS_WITH_SCALES: Record<ProfileKey, MetricDef[]> = {
	WINTERSPORT:     [SNOW_DEPTH, SNOW_NEW, SUNNY_HOURS, WIND_MAX, CLOUD_AVG],
	ALPINE_TOURING:  [SNOW_NEW, VISIBILITY, WIND_MAX],
	SUMMER_TREKKING: [PRECIP_SUM, THUNDER, WIND_MAX, UV_INDEX, VISIBILITY],
	ALLGEMEIN:       [TEMP_MAX, WIND_MAX, PRECIP_SUM, VISIBILITY]
};

/**
 * Issue #718 — Validiert idealRanges auf min >= max (ungültiger Bereich).
 * Nur aktive Keys werden geprüft. Enum-Metriken ohne numerisches min werden übersprungen.
 */
export function validateIdealRanges(
	ranges: Record<string, { min?: unknown; max?: unknown }>,
	activeKeys: string[]
): { valid: boolean; invalidKeys: string[] } {
	const invalidKeys = activeKeys.filter((key) => {
		const r = ranges[key];
		if (!r) return false;
		const min = typeof r.min === 'number' ? r.min : undefined;
		const max = typeof r.max === 'number' ? r.max : undefined;
		return min !== undefined && max !== undefined && min >= max;
	});
	return { valid: invalidKeys.length === 0, invalidKeys };
}

export const IDEAL_DEFAULTS: Record<ProfileKey, Record<string, IdealRange>> = {
	WINTERSPORT: {
		snow_depth_cm:   { min: 30, max: 200 },
		snow_new_sum_cm: { min: 5,  max: 50  },
		wind_max_kmh:    { min: 0,  max: 40  },
		cloud_avg_pct:   { min: 0,  max: 60  }
	},
	ALPINE_TOURING: {
		snow_new_sum_cm:  { min: 0,    max: 10    },
		visibility_min_m: { min: 2000, max: 10000 },
		wind_max_kmh:     { min: 0,    max: 50    }
	},
	SUMMER_TREKKING: {
		precip_sum_mm:     { min: 0, max: 3      },
		thunder_level_max: {         max: 'NONE' },
		wind_max_kmh:      { min: 0, max: 35     },
		uv_index_max:      { min: 0, max: 8      }
	},
	ALLGEMEIN: {
		temp_max_c:    { min: 15, max: 35 },
		wind_max_kmh:  { min: 0,  max: 50 },
		precip_sum_mm: { min: 0,  max: 5  }
	}
};

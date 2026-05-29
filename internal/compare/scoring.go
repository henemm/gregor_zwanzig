package compare

import (
	"math"

	"github.com/henemm/gregor-api/internal/model"
)

// metricKey is a stable identifier for the metric a metricSpec evaluates.
// It exists so WinnerTags can decide on a human-readable label without
// having to reverse-engineer the extract function.
type metricKey string

const (
	metricSnowDepth      metricKey = "snow_depth"
	metricSnowNew        metricKey = "snow_new"
	metricSunnyHours     metricKey = "sunny_hours"
	metricWindMax        metricKey = "wind_max"
	metricCloudAvg       metricKey = "cloud_avg"
	metricAvalancheLevel metricKey = "avalanche_level"
	metricVisibilityMin  metricKey = "visibility_min"
	metricPrecipSum      metricKey = "precip_sum"
	metricThunderProxy   metricKey = "thunder_proxy"
	metricUvIndexMax     metricKey = "uv_index_max"
	metricTempMax        metricKey = "temp_max"
)

// metricSpec describes how to extract a numeric value from a
// SegmentWeatherSummary and how that value should be interpreted by the
// normaliser. positive=true means "higher is better" (e.g. snow depth for
// wintersport), positive=false means "lower is better" (rain, wind).
type metricSpec struct {
	key      metricKey
	weight   float64
	positive bool
	extract  func(model.SegmentWeatherSummary) (float64, bool)
}

// profileMetrics returns the weighted list of metrics for a profile.
// Order matters only for WinnerTags (which picks the top-2 by weight).
// Weights must sum to 1.0 to keep the resulting score within [0, 100].
func profileMetrics(profile ActivityProfile) []metricSpec {
	switch profile {
	case ProfileWintersport:
		return []metricSpec{
			{key: metricSnowDepth, weight: 0.30, positive: true, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.SnowDepthCm })},
			{key: metricSnowNew, weight: 0.25, positive: true, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.SnowNewSumCm })},
			{key: metricSunnyHours, weight: 0.20, positive: true, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.SunnyHoursH })},
			{key: metricWindMax, weight: 0.15, positive: false, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.WindMaxKmh })},
			{key: metricCloudAvg, weight: 0.10, positive: false, extract: extractInt(func(s model.SegmentWeatherSummary) *int { return s.CloudAvgPct })},
		}
	case ProfileAlpineTour:
		// Avalanche level is not yet part of SegmentWeatherSummary — treat as
		// 0 for all locations (neutral), still consuming its weight share.
		return []metricSpec{
			{key: metricAvalancheLevel, weight: 0.35, positive: false, extract: func(s model.SegmentWeatherSummary) (float64, bool) { return 0, true }},
			{key: metricSnowNew, weight: 0.25, positive: true, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.SnowNewSumCm })},
			{key: metricVisibilityMin, weight: 0.20, positive: true, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.VisibilityMinM })},
			{key: metricWindMax, weight: 0.20, positive: false, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.WindMaxKmh })},
		}
	case ProfileSummerTrekking:
		return []metricSpec{
			{key: metricPrecipSum, weight: 0.30, positive: false, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.PrecipSumMm })},
			{key: metricThunderProxy, weight: 0.25, positive: false, extract: thunderProxy},
			{key: metricWindMax, weight: 0.20, positive: false, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.WindMaxKmh })},
			{key: metricUvIndexMax, weight: 0.15, positive: false, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.UvIndexMax })},
			{key: metricVisibilityMin, weight: 0.10, positive: true, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.VisibilityMinM })},
		}
	case ProfileAllgemein:
		return []metricSpec{
			{key: metricTempMax, weight: 0.25, positive: true, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.TempMaxC })},
			{key: metricWindMax, weight: 0.25, positive: false, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.WindMaxKmh })},
			{key: metricPrecipSum, weight: 0.25, positive: false, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.PrecipSumMm })},
			{key: metricVisibilityMin, weight: 0.25, positive: true, extract: extractFloat(func(s model.SegmentWeatherSummary) *float64 { return s.VisibilityMinM })},
		}
	}
	return nil
}

// extractFloat builds a metricSpec.extract from a *float64 getter. A nil
// pointer is treated as 0 (neutral, not penalising).
func extractFloat(get func(model.SegmentWeatherSummary) *float64) func(model.SegmentWeatherSummary) (float64, bool) {
	return func(s model.SegmentWeatherSummary) (float64, bool) {
		v := get(s)
		if v == nil {
			return 0, true
		}
		return *v, true
	}
}

// extractInt mirrors extractFloat for *int values.
func extractInt(get func(model.SegmentWeatherSummary) *int) func(model.SegmentWeatherSummary) (float64, bool) {
	return func(s model.SegmentWeatherSummary) (float64, bool) {
		v := get(s)
		if v == nil {
			return 0, true
		}
		return float64(*v), true
	}
}

// thunderProxy combines CAPE and ThunderLevelMax into a single numeric proxy
// (higher = worse). 1000 J/kg roughly matches a MED-level signal.
func thunderProxy(s model.SegmentWeatherSummary) (float64, bool) {
	var cape float64
	if s.CapeMaxJkg != nil {
		cape = *s.CapeMaxJkg
	}
	var thunder float64
	switch s.ThunderLevelMax {
	case model.ThunderHigh:
		thunder = 2000
	case model.ThunderMed:
		thunder = 1000
	}
	return math.Max(cape, thunder), true
}

// ScoreRow returns a normalised score in [0, 100] for a single location.
// The score is computed against the population of all candidates so the best
// candidate for each metric receives the full weighted share.
//
// Normalisation rules:
//   - positive metrics: best (highest) value across the population = 100%,
//     a value of 0 = 0%, linear interpolation otherwise.
//   - negative metrics: best (lowest) value = 100%, the worst observed value
//     = 0%, linear interpolation otherwise.
//   - identical values across all candidates degenerate to 100% (no signal).
func ScoreRow(loc model.SegmentWeatherSummary, profile ActivityProfile, allMetrics []model.SegmentWeatherSummary, enabledKeys map[metricKey]bool) int {
	specs := profileMetrics(profile)

	// Filter and re-normalise when caller supplies an explicit key set.
	if enabledKeys != nil {
		active := make([]metricSpec, 0, len(specs))
		for _, s := range specs {
			if enabledKeys[s.key] {
				active = append(active, s)
			}
		}
		if len(active) > 0 {
			// Re-normalise weights so they sum to 1.0.
			var totalWeight float64
			for _, s := range active {
				totalWeight += s.weight
			}
			if totalWeight > 0 && math.Abs(totalWeight-1.0) > 1e-9 {
				for i := range active {
					active[i].weight = active[i].weight / totalWeight
				}
			}
			specs = active
		}
		// else: all filtered out → fallback to full profile (no change to specs)
	}

	if len(specs) == 0 || len(allMetrics) == 0 {
		return 0
	}

	var total float64
	for _, spec := range specs {
		myVal, ok := spec.extract(loc)
		if !ok {
			continue
		}

		minVal := math.Inf(1)
		maxVal := math.Inf(-1)
		for _, other := range allMetrics {
			v, ok := spec.extract(other)
			if !ok {
				continue
			}
			if v < minVal {
				minVal = v
			}
			if v > maxVal {
				maxVal = v
			}
		}
		if math.IsInf(minVal, 0) || math.IsInf(maxVal, 0) {
			continue
		}

		var pct float64
		switch {
		case math.Abs(maxVal-minVal) < 1e-9:
			// All candidates identical → no differentiation possible.
			pct = 1.0
		case spec.positive:
			// Higher is better. Range-based normalisation so negative
			// populations (e.g. all sub-zero temperatures) still differentiate.
			rangeVal := maxVal - minVal
			if rangeVal <= 0 {
				pct = 1.0
			} else {
				pct = (myVal - minVal) / rangeVal
			}
		default:
			// Lower is better. Best in population = 1.0, worst = 0.0.
			denom := maxVal - minVal
			pct = 1.0 - (myVal-minVal)/denom
		}

		if pct < 0 {
			pct = 0
		}
		if pct > 1 {
			pct = 1
		}
		total += spec.weight * pct
	}

	score := int(math.Round(total * 100))
	if score < 0 {
		score = 0
	}
	if score > 100 {
		score = 100
	}
	return score
}

// WinnerTagsTyped returns at least one typed tag describing why the winner won.
// Picks from the two highest-weighted metrics of the profile. Each tag carries
// a machine-readable type and a human-readable German label.
// Issue #454: replaces WinnerTags() ([]string).
func WinnerTagsTyped(winner model.SegmentWeatherSummary, profile ActivityProfile) []CompareTag {
	specs := profileMetrics(profile)
	if len(specs) == 0 {
		return []CompareTag{{Type: "best_score", Label: "Bester Score"}}
	}

	tags := make([]CompareTag, 0, 2)
	for i, spec := range specs {
		if i >= 2 {
			break
		}
		label := labelFor(spec.key)
		if label == "" {
			continue
		}
		tags = append(tags, CompareTag{Type: typeFor(spec.key), Label: label})
	}
	if len(tags) == 0 {
		tags = append(tags, CompareTag{Type: "best_score", Label: "Bester Score"})
	}
	return tags
}

// typeFor returns the machine-readable tag type for a metric key.
func typeFor(k metricKey) string {
	switch k {
	case metricSnowDepth, metricSnowNew:
		return "best_snow"
	case metricSunnyHours:
		return "best_sun"
	case metricWindMax:
		return "low_wind"
	case metricPrecipSum:
		return "low_rain"
	case metricVisibilityMin:
		return "good_visibility"
	case metricThunderProxy:
		return "low_thunder"
	case metricTempMax:
		return "best_temp"
	case metricCloudAvg:
		return "clear_sky"
	case metricAvalancheLevel:
		return "low_avalanche"
	case metricUvIndexMax:
		return "moderate_uv"
	}
	return "best_score"
}

// labelFor returns the German UI label associated with a metric key. The
// mapping is intentionally per-key so the same metric (e.g. wind) reads the
// same way across profiles.
func labelFor(k metricKey) string {
	switch k {
	case metricSnowDepth:
		return "Beste Schneelage"
	case metricSnowNew:
		return "Frischer Schnee"
	case metricSunnyHours:
		return "Viel Sonne"
	case metricWindMax:
		return "Wenig Wind"
	case metricCloudAvg:
		return "Klarer Himmel"
	case metricAvalancheLevel:
		return "Geringe Lawinengefahr"
	case metricVisibilityMin:
		return "Gute Sicht"
	case metricPrecipSum:
		return "Wenig Regen"
	case metricThunderProxy:
		return "Geringes Gewitterrisiko"
	case metricUvIndexMax:
		return "Moderate UV-Belastung"
	case metricTempMax:
		return "Angenehme Temperatur"
	}
	return ""
}

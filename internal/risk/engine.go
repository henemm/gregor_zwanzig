package risk

import (
	"sort"

	"github.com/henemm/gregor-api/internal/model"
)

// Assess evaluates weather risks for a segment based on aggregated metrics.
func Assess(agg model.SegmentWeatherSummary) model.RiskAssessment {
	var risks []model.Risk

	checkThunder(agg, &risks)
	checkNormal(agg.CapeMaxJkg, capeModerate, capeHigh, model.RiskThunderstorm, &risks, nil)
	checkNormal(agg.WindMaxKmh, windModerate, windHigh, model.RiskWind, &risks, withGust(agg.GustMaxKmh))
	checkNormal(agg.GustMaxKmh, gustModerate, gustHigh, model.RiskWind, &risks, withGust(agg.GustMaxKmh))
	checkModerateOnly(agg.PrecipSumMm, precipModerate, model.RiskRain, &risks, withAmount(agg.PrecipSumMm))
	checkModerateOnlyInt(agg.PopMaxPct, popModerate, model.RiskRain, &risks)
	checkInverted(agg.WindChillMinC, windChillHighLt, model.RiskWindChill, &risks, withFeelsLike(agg.WindChillMinC))
	checkInverted(agg.VisibilityMinM, visHighLt, model.RiskPoorVisibility, &risks, withVisibility(agg.VisibilityMinM))

	return model.RiskAssessment{Risks: deduplicate(risks)}
}

// GetMaxRiskLevel returns the highest risk level in an assessment, or LOW if empty.
func GetMaxRiskLevel(a model.RiskAssessment) model.RiskLevel {
	max := model.RiskLow
	for _, r := range a.Risks {
		if levelOrder(r.Level) > levelOrder(max) {
			max = r.Level
		}
	}
	return max
}

func checkThunder(agg model.SegmentWeatherSummary, risks *[]model.Risk) {
	switch agg.ThunderLevelMax {
	case model.ThunderHigh:
		*risks = append(*risks, model.Risk{Type: model.RiskThunderstorm, Level: model.RiskHigh})
	case model.ThunderMed:
		*risks = append(*risks, model.Risk{Type: model.RiskThunderstorm, Level: model.RiskModerate})
	}
}

func checkNormal(val *float64, medium, high float64, rt model.RiskType,
	risks *[]model.Risk, extras func(*model.Risk)) {
	if val == nil {
		return
	}
	var level model.RiskLevel
	if *val >= high {
		level = model.RiskHigh
	} else if *val >= medium {
		level = model.RiskModerate
	} else {
		return
	}
	r := model.Risk{Type: rt, Level: level}
	if extras != nil {
		extras(&r)
	}
	*risks = append(*risks, r)
}

func checkModerateOnly(val *float64, medium float64, rt model.RiskType,
	risks *[]model.Risk, extras func(*model.Risk)) {
	if val == nil || *val < medium {
		return
	}
	r := model.Risk{Type: rt, Level: model.RiskModerate}
	if extras != nil {
		extras(&r)
	}
	*risks = append(*risks, r)
}

func checkModerateOnlyInt(val *int, medium int, rt model.RiskType, risks *[]model.Risk) {
	if val == nil || *val < medium {
		return
	}
	*risks = append(*risks, model.Risk{Type: rt, Level: model.RiskModerate})
}

func checkInverted(val *float64, highLt float64, rt model.RiskType,
	risks *[]model.Risk, extras func(*model.Risk)) {
	if val == nil || *val >= highLt {
		return
	}
	r := model.Risk{Type: rt, Level: model.RiskHigh}
	if extras != nil {
		extras(&r)
	}
	*risks = append(*risks, r)
}

func deduplicate(risks []model.Risk) []model.Risk {
	best := map[model.RiskType]model.Risk{}
	for _, r := range risks {
		if existing, ok := best[r.Type]; !ok || levelOrder(r.Level) > levelOrder(existing.Level) {
			best[r.Type] = r
		}
	}
	result := make([]model.Risk, 0, len(best))
	for _, r := range best {
		result = append(result, r)
	}
	sort.Slice(result, func(i, j int) bool {
		return levelOrder(result[i].Level) > levelOrder(result[j].Level)
	})
	return result
}

func levelOrder(l model.RiskLevel) int {
	switch l {
	case model.RiskHigh:
		return 2
	case model.RiskModerate:
		return 1
	default:
		return 0
	}
}

// Extra field setters
func withGust(v *float64) func(*model.Risk) {
	return func(r *model.Risk) { r.GustKmh = v }
}

func withAmount(v *float64) func(*model.Risk) {
	return func(r *model.Risk) { r.AmountMm = v }
}

func withFeelsLike(v *float64) func(*model.Risk) {
	return func(r *model.Risk) { r.FeelsLikeC = v }
}

func withVisibility(v *float64) func(*model.Risk) {
	return func(r *model.Risk) { r.VisibilityM = v }
}

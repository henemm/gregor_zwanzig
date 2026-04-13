package risk

import "github.com/henemm/gregor-api/internal/model"

// ExposedSection represents a wind-exposed segment of a route.
type ExposedSection struct {
	StartKm        float64 `json:"start_km"`
	EndKm          float64 `json:"end_km"`
	MaxElevationM  float64 `json:"max_elevation_m"`
	ExpositionType string  `json:"exposition_type"` // "GRAT" | "PASS"
}

// AssessWithExposition runs Assess() and additionally checks wind exposition
// for segments overlapping exposed sections.
func AssessWithExposition(agg model.SegmentWeatherSummary,
	segStartKm, segEndKm float64, sections []ExposedSection) model.RiskAssessment {

	assessment := Assess(agg)

	if len(sections) == 0 {
		return assessment
	}

	overlaps := false
	for _, es := range sections {
		if segStartKm < es.EndKm && segEndKm > es.StartKm {
			overlaps = true
			break
		}
	}
	if !overlaps {
		return assessment
	}

	var level model.RiskLevel
	values := []*float64{agg.WindMaxKmh, agg.GustMaxKmh}
	thresholds := [][2]float64{
		{windExpoModerate, windExpoHigh},
		{gustExpoModerate, gustExpoHigh},
	}

	for i, val := range values {
		if val == nil {
			continue
		}
		med, high := thresholds[i][0], thresholds[i][1]
		if *val >= high {
			level = model.RiskHigh
			break
		}
		if *val >= med && level != model.RiskHigh {
			level = model.RiskModerate
		}
	}

	if level != "" {
		r := model.Risk{Type: model.RiskWindExposition, Level: level, GustKmh: agg.GustMaxKmh}
		assessment.Risks = append(assessment.Risks, r)
	}

	return assessment
}

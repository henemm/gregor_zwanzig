package risk

import (
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func TestAssessWithExposition_ModerateWind(t *testing.T) {
	s := model.SegmentWeatherSummary{WindMaxKmh: ptr(35), GustMaxKmh: ptr(45)}
	sections := []ExposedSection{{StartKm: 0, EndKm: 2, MaxElevationM: 2000, ExpositionType: "GRAT"}}
	result := AssessWithExposition(s, 0.5, 1.5, sections)
	found := findRisk(result.Risks, model.RiskWindExposition)
	if found == nil {
		t.Fatal("expected WIND_EXPOSITION risk")
	}
	if found.Level != model.RiskModerate {
		t.Errorf("expected MODERATE, got %s", found.Level)
	}
}

func TestAssessWithExposition_HighWind(t *testing.T) {
	s := model.SegmentWeatherSummary{WindMaxKmh: ptr(55), GustMaxKmh: ptr(65)}
	sections := []ExposedSection{{StartKm: 0, EndKm: 2, MaxElevationM: 2000, ExpositionType: "GRAT"}}
	result := AssessWithExposition(s, 0.5, 1.5, sections)
	found := findRisk(result.Risks, model.RiskWindExposition)
	if found == nil {
		t.Fatal("expected WIND_EXPOSITION risk")
	}
	if found.Level != model.RiskHigh {
		t.Errorf("expected HIGH, got %s", found.Level)
	}
}

func TestAssessWithExposition_NoOverlap(t *testing.T) {
	s := model.SegmentWeatherSummary{WindMaxKmh: ptr(55), GustMaxKmh: ptr(65)}
	sections := []ExposedSection{{StartKm: 5, EndKm: 7, MaxElevationM: 2000, ExpositionType: "GRAT"}}
	// Segment 0.5-1.5 does NOT overlap section 5-7
	result := AssessWithExposition(s, 0.5, 1.5, sections)
	found := findRisk(result.Risks, model.RiskWindExposition)
	if found != nil {
		t.Errorf("expected no WIND_EXPOSITION risk (no overlap), got %+v", found)
	}
}

func TestAssessWithExposition_LowWind_NoRisk(t *testing.T) {
	s := model.SegmentWeatherSummary{WindMaxKmh: ptr(20), GustMaxKmh: ptr(25)}
	sections := []ExposedSection{{StartKm: 0, EndKm: 2, MaxElevationM: 2000, ExpositionType: "GRAT"}}
	result := AssessWithExposition(s, 0.5, 1.5, sections)
	found := findRisk(result.Risks, model.RiskWindExposition)
	if found != nil {
		t.Errorf("expected no WIND_EXPOSITION risk (low wind), got %+v", found)
	}
}

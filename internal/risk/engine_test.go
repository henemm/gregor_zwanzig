package risk

import (
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// helper: create a SegmentWeatherSummary with optional overrides
func ptr(f float64) *float64 { return &f }
func iptr(i int) *int        { return &i }

func calmSummary() model.SegmentWeatherSummary {
	return model.SegmentWeatherSummary{
		ThunderLevelMax: model.ThunderNone,
		WindMaxKmh:      ptr(20),
		GustMaxKmh:      ptr(30),
		PrecipSumMm:     ptr(2.0),
		VisibilityMinM:  ptr(10000),
		WindChillMinC:   ptr(5.0),
		CapeMaxJkg:      ptr(200),
		PopMaxPct:       iptr(20),
	}
}

func TestAssess_NoRisks_CalmWeather(t *testing.T) {
	result := Assess(calmSummary())
	if len(result.Risks) != 0 {
		t.Errorf("expected 0 risks, got %d: %+v", len(result.Risks), result.Risks)
	}
}

func TestAssess_ThunderHigh(t *testing.T) {
	s := model.SegmentWeatherSummary{ThunderLevelMax: model.ThunderHigh}
	result := Assess(s)
	found := findRisk(result.Risks, model.RiskThunderstorm)
	if found == nil {
		t.Fatal("expected THUNDERSTORM risk")
	}
	if found.Level != model.RiskHigh {
		t.Errorf("expected HIGH, got %s", found.Level)
	}
}

func TestAssess_ThunderMedium(t *testing.T) {
	s := model.SegmentWeatherSummary{ThunderLevelMax: model.ThunderMed}
	result := Assess(s)
	found := findRisk(result.Risks, model.RiskThunderstorm)
	if found == nil {
		t.Fatal("expected THUNDERSTORM risk")
	}
	if found.Level != model.RiskModerate {
		t.Errorf("expected MODERATE, got %s", found.Level)
	}
}

func TestAssess_WindHigh(t *testing.T) {
	s := model.SegmentWeatherSummary{WindMaxKmh: ptr(75), GustMaxKmh: ptr(90)}
	result := Assess(s)
	found := findRisk(result.Risks, model.RiskWind)
	if found == nil {
		t.Fatal("expected WIND risk")
	}
	if found.Level != model.RiskHigh {
		t.Errorf("expected HIGH, got %s", found.Level)
	}
}

func TestAssess_WindModerate(t *testing.T) {
	s := model.SegmentWeatherSummary{WindMaxKmh: ptr(55), GustMaxKmh: ptr(45)}
	result := Assess(s)
	found := findRisk(result.Risks, model.RiskWind)
	if found == nil {
		t.Fatal("expected WIND risk")
	}
	if found.Level != model.RiskModerate {
		t.Errorf("expected MODERATE, got %s", found.Level)
	}
}

func TestAssess_GustOverridesWind(t *testing.T) {
	// wind=55 -> MODERATE, gust=82 -> HIGH. Deduplicated: 1x WIND/HIGH
	s := model.SegmentWeatherSummary{WindMaxKmh: ptr(55), GustMaxKmh: ptr(82)}
	result := Assess(s)
	windRisks := countRiskType(result.Risks, model.RiskWind)
	if windRisks != 1 {
		t.Errorf("expected 1 WIND risk (deduplicated), got %d", windRisks)
	}
	found := findRisk(result.Risks, model.RiskWind)
	if found == nil || found.Level != model.RiskHigh {
		t.Errorf("expected WIND/HIGH after dedup, got %+v", found)
	}
}

func TestAssess_PrecipitationModerate(t *testing.T) {
	s := model.SegmentWeatherSummary{PrecipSumMm: ptr(25.0)}
	result := Assess(s)
	found := findRisk(result.Risks, model.RiskRain)
	if found == nil {
		t.Fatal("expected RAIN risk")
	}
	if found.Level != model.RiskModerate {
		t.Errorf("expected MODERATE, got %s", found.Level)
	}
}

func TestAssess_VisibilityInverted(t *testing.T) {
	s := model.SegmentWeatherSummary{VisibilityMinM: ptr(50)}
	result := Assess(s)
	found := findRisk(result.Risks, model.RiskPoorVisibility)
	if found == nil {
		t.Fatal("expected POOR_VISIBILITY risk")
	}
	if found.Level != model.RiskHigh {
		t.Errorf("expected HIGH, got %s", found.Level)
	}
}

func TestAssess_WindChillInverted(t *testing.T) {
	s := model.SegmentWeatherSummary{WindChillMinC: ptr(-25.0)}
	result := Assess(s)
	found := findRisk(result.Risks, model.RiskWindChill)
	if found == nil {
		t.Fatal("expected WIND_CHILL risk")
	}
	if found.Level != model.RiskHigh {
		t.Errorf("expected HIGH, got %s", found.Level)
	}
}

func TestAssess_MultipleRisksSorted(t *testing.T) {
	s := model.SegmentWeatherSummary{
		ThunderLevelMax: model.ThunderHigh,
		WindMaxKmh:      ptr(55),
		GustMaxKmh:      ptr(45),
	}
	result := Assess(s)
	if len(result.Risks) < 2 {
		t.Fatalf("expected at least 2 risks, got %d", len(result.Risks))
	}
	if result.Risks[0].Level != model.RiskHigh {
		t.Errorf("expected first risk to be HIGH, got %s", result.Risks[0].Level)
	}
}

func TestAssess_Deduplication(t *testing.T) {
	// Same as GustOverridesWind — both wind and gust produce WIND risk
	s := model.SegmentWeatherSummary{WindMaxKmh: ptr(55), GustMaxKmh: ptr(82)}
	result := Assess(s)
	windRisks := countRiskType(result.Risks, model.RiskWind)
	if windRisks != 1 {
		t.Errorf("expected exactly 1 WIND risk after dedup, got %d", windRisks)
	}
}

func TestAssess_NoneValuesSkipped(t *testing.T) {
	// All nil — no risks
	s := model.SegmentWeatherSummary{}
	result := Assess(s)
	if len(result.Risks) != 0 {
		t.Errorf("expected 0 risks for nil values, got %d: %+v", len(result.Risks), result.Risks)
	}
}

func TestAssess_CapeHigh(t *testing.T) {
	s := model.SegmentWeatherSummary{CapeMaxJkg: ptr(2500)}
	result := Assess(s)
	found := findRisk(result.Risks, model.RiskThunderstorm)
	if found == nil {
		t.Fatal("expected THUNDERSTORM risk from CAPE")
	}
	if found.Level != model.RiskHigh {
		t.Errorf("expected HIGH, got %s", found.Level)
	}
}

func TestAssess_CapeModerate(t *testing.T) {
	s := model.SegmentWeatherSummary{CapeMaxJkg: ptr(1500)}
	result := Assess(s)
	found := findRisk(result.Risks, model.RiskThunderstorm)
	if found == nil {
		t.Fatal("expected THUNDERSTORM risk from CAPE")
	}
	if found.Level != model.RiskModerate {
		t.Errorf("expected MODERATE, got %s", found.Level)
	}
}

// --- helpers ---

func findRisk(risks []model.Risk, rt model.RiskType) *model.Risk {
	for i := range risks {
		if risks[i].Type == rt {
			return &risks[i]
		}
	}
	return nil
}

func countRiskType(risks []model.Risk, rt model.RiskType) int {
	n := 0
	for _, r := range risks {
		if r.Type == rt {
			n++
		}
	}
	return n
}

package model

// RiskType identifies the category of weather risk.
type RiskType string

const (
	RiskThunderstorm   RiskType = "thunderstorm"
	RiskRain           RiskType = "rain"
	RiskWind           RiskType = "wind"
	RiskAvalanche      RiskType = "avalanche"
	RiskSnowfall       RiskType = "snowfall"
	RiskWindChill      RiskType = "wind_chill"
	RiskPoorVisibility RiskType = "poor_visibility"
	RiskFreezingRain   RiskType = "freezing_rain"
	RiskWindExposition RiskType = "wind_exposition"
)

// RiskLevel indicates severity.
type RiskLevel string

const (
	RiskLow      RiskLevel = "low"
	RiskModerate RiskLevel = "moderate"
	RiskHigh     RiskLevel = "high"
)

// Risk represents a single identified weather risk.
type Risk struct {
	Type        RiskType  `json:"type"`
	Level       RiskLevel `json:"level"`
	AmountMm    *float64  `json:"amount_mm,omitempty"`
	GustKmh     *float64  `json:"gust_kmh,omitempty"`
	FeelsLikeC  *float64  `json:"feels_like_c,omitempty"`
	VisibilityM *float64  `json:"visibility_m,omitempty"`
}

// RiskAssessment holds all risks for a segment.
type RiskAssessment struct {
	Risks []Risk `json:"risks"`
}

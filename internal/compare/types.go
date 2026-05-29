// Package compare implements profile-weighted ranking of weather forecasts
// for multiple locations. See docs/specs/modules/compare_engine.md and
// docs/specs/modules/issue_454_compare_engine_backend.md.
package compare

// ActivityProfile enumerates the supported scoring profiles for a compare run.
type ActivityProfile string

const (
	ProfileWintersport    ActivityProfile = "WINTERSPORT"
	ProfileAlpineTour     ActivityProfile = "ALPINE_TOURING"
	ProfileSummerTrekking ActivityProfile = "SUMMER_TREKKING"
	ProfileAllgemein      ActivityProfile = "ALLGEMEIN"
)

// validProfiles is the canonical set of accepted ActivityProfile values.
var validProfiles = map[ActivityProfile]bool{
	ProfileWintersport:    true,
	ProfileAlpineTour:     true,
	ProfileSummerTrekking: true,
	ProfileAllgemein:      true,
}

// IsValidProfile reports whether p is a recognised profile value.
func IsValidProfile(p ActivityProfile) bool {
	return validProfiles[p]
}

// CompareRequest is the JSON body of POST /api/compare/run.
// Issue #454: date → date_from/date_to/hour_from/hour_to.
type CompareRequest struct {
	LocationIDs []string        `json:"location_ids"`
	DateFrom    string          `json:"date_from"`
	DateTo      string          `json:"date_to"`
	HourFrom    int             `json:"hour_from"`
	HourTo      int             `json:"hour_to"`
	Profile     ActivityProfile `json:"profile"`
}

// CompareTag is a machine-readable + human-readable tag for a winning location.
type CompareTag struct {
	Type  string `json:"type"`
	Label string `json:"label"`
}

// RankingEntry is one position in the ranking block of CompareResult.
type RankingEntry struct {
	LocationID string       `json:"location_id"`
	Name       string       `json:"name"`
	Score      int          `json:"score"`
	Tags       []CompareTag `json:"tags"`
}

// MatrixEntry holds the aggregated SegmentWeatherSummary fields as a flat map.
type MatrixEntry struct {
	LocationID string         `json:"location_id"`
	Metrics    map[string]any `json:"metrics"`
}

// StundenVerlaufHour is one filtered hourly datapoint with a two-digit UTC hour.
type StundenVerlaufHour struct {
	Hour   string         `json:"hour"`
	Values map[string]any `json:"values"`
}

// StundenVerlaufEntry holds the filtered hourly trace for a single location.
type StundenVerlaufEntry struct {
	LocationID string               `json:"location_id"`
	Hours      []StundenVerlaufHour `json:"hours"`
}

// CompareResult is the JSON response of POST /api/compare/run.
// Issue #454: rows/winner/hourly → ranking/matrix/stunden_verlauf.
type CompareResult struct {
	Ranking        []RankingEntry        `json:"ranking"`
	Matrix         []MatrixEntry         `json:"matrix"`
	StundenVerlauf []StundenVerlaufEntry `json:"stunden_verlauf"`
}

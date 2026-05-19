// Package compare implements profile-weighted ranking of weather forecasts
// for multiple locations. See docs/specs/modules/compare_engine.md.
package compare

import "github.com/henemm/gregor-api/internal/model"

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
type CompareRequest struct {
	LocationIDs []string        `json:"location_ids"`
	Date        string          `json:"date"`
	Profile     ActivityProfile `json:"profile"`
}

// CompareRow is one entry in the compare ranking.
type CompareRow struct {
	LocationID string                      `json:"location_id"`
	Score      int                         `json:"score"`
	Rank       int                         `json:"rank"`
	Metrics    model.SegmentWeatherSummary `json:"metrics"`
}

// CompareWinner names the top-ranked location plus a few profile-specific tags.
type CompareWinner struct {
	LocationID string   `json:"location_id"`
	Tags       []string `json:"tags"`
}

// CompareResult is the JSON response of POST /api/compare/run.
type CompareResult struct {
	Rows   []CompareRow                         `json:"rows"`
	Winner *CompareWinner                       `json:"winner,omitempty"`
	Hourly map[string][]model.ForecastDataPoint `json:"hourly"`
}

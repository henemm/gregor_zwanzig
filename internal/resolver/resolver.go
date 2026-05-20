package resolver

import (
	"regexp"
	"strings"

	"github.com/henemm/gregor-api/internal/provider/openmeteo"
)

// ResolveResult ist die Vorschau einer aufgelösten Location.
// SourceType bezeichnet die Import-Quelle (komoot, google_maps, decimal, dms, utm, gpx).
type ResolveResult struct {
	Lat           float64 `json:"lat"`
	Lon           float64 `json:"lon"`
	ElevationM    *int    `json:"elevation_m,omitempty"`
	Timezone      string  `json:"timezone"`
	SuggestedName string  `json:"suggested_name,omitempty"`
	Region        string  `json:"region,omitempty"`
	SourceType    string  `json:"source_type"`
}

// ResolveError wird zurückgegeben wenn das Format nicht erkannt oder nicht
// unterstützt wird, oder wenn eine externe Auflösung fehlschlägt.
type ResolveError struct {
	Code    string `json:"code"`    // "unknown_format" | "unsupported_url" | "resolve_failed"
	Message string `json:"message"` // menschenlesbar
}

func (e *ResolveError) Error() string { return e.Message }

var (
	reUTM     = regexp.MustCompile(`\b\d{1,2}[A-Z]\s+\d{4,7}\s+\d{4,7}\b`)
	reDecimal = regexp.MustCompile(`^\s*(-?\d{1,3}\.\d+)[,\s]+(-?\d{1,3}\.\d+)\s*$`)
)

// Resolve erkennt das Format der Eingabe und liefert eine Location-Vorschau.
// Reihenfolge: komoot → google maps → gpx → utm → dms → dezimal → unknown_format.
func Resolve(input string) (ResolveResult, error) {
	input = strings.TrimSpace(input)

	switch {
	case strings.Contains(input, "komoot.com"):
		return resolveKomoot(input)
	case strings.Contains(input, "goo.gl/maps") ||
		strings.Contains(input, "maps.app.goo.gl") ||
		(strings.Contains(input, ".google.") && strings.Contains(input, "maps")):
		return resolveGoogleMaps(input)
	case strings.Contains(input, "<trkpt"):
		return resolveGPX(input)
	case reUTM.MatchString(input):
		return resolveUTM(input)
	case strings.Contains(input, "°"):
		return resolveDMS(input)
	case reDecimal.MatchString(input):
		return resolveDecimal(input)
	}

	return ResolveResult{}, &ResolveError{
		Code:    "unknown_format",
		Message: "Das Format wurde nicht erkannt. Bitte eine Komoot-Highlight-URL, Google-Maps-Link oder Koordinaten eingeben.",
	}
}

// finalize ergänzt Timezone und (falls fehlend und lookupElevation==true) Elevation
// und liefert das fertige ResolveResult.
func finalize(r ResolveResult, lookup bool) ResolveResult {
	if r.Timezone == "" {
		r.Timezone = openmeteo.TimezoneForCoords(r.Lat, r.Lon)
	}
	if r.ElevationM == nil && lookup {
		if e := lookupElevation(r.Lat, r.Lon); e != nil {
			r.ElevationM = e
		}
	}
	return r
}

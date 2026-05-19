package resolver

import (
	"encoding/json"
	"fmt"
	"net/http"
	"regexp"
	"strings"
	"time"
)

var reKomootHighlight = regexp.MustCompile(`komoot\.com/(?:[^/]+/)?highlight/(\d+)`)

type komootPoint struct {
	Lat float64 `json:"lat"`
	Lng float64 `json:"lng"`
	Alt float64 `json:"alt"`
}

type komootResponse struct {
	Name      string      `json:"name"`
	BaseName  string      `json:"base_name"`
	Elevation float64     `json:"elevation"`
	MidPoint  komootPoint `json:"mid_point"`
	StartPoint komootPoint `json:"start_point"`
	Embedded  struct {
		Coordinates struct {
			Items []komootPoint `json:"items"`
		} `json:"coordinates"`
	} `json:"_embedded"`
}

func resolveKomoot(input string) (ResolveResult, error) {
	low := strings.ToLower(input)
	if strings.Contains(low, "/tour/") || strings.Contains(low, "/collection/") {
		return ResolveResult{}, &ResolveError{
			Code:    "unsupported_url",
			Message: "Komoot-Touren und Sammlungen werden nicht unterstützt. Bitte einen Komoot Highlight-Link verwenden.",
		}
	}

	m := reKomootHighlight.FindStringSubmatch(input)
	if m == nil {
		return ResolveResult{}, &ResolveError{
			Code:    "unsupported_url",
			Message: "Komoot-URL nicht erkannt. Bitte einen Komoot Highlight-Link verwenden.",
		}
	}
	id := m[1]

	apiURL := fmt.Sprintf("https://www.komoot.com/api/v007/highlights/%s", id)
	req, err := http.NewRequest("GET", apiURL, nil)
	if err != nil {
		return ResolveResult{}, &ResolveError{Code: "resolve_failed", Message: "Komoot-Anfrage konnte nicht erstellt werden."}
	}
	req.Header.Set("Accept", "application/hal+json")
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; gregor-zwanzig/1.0)")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return ResolveResult{}, &ResolveError{Code: "resolve_failed", Message: "Komoot-API nicht erreichbar."}
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return ResolveResult{}, &ResolveError{
			Code:    "resolve_failed",
			Message: fmt.Sprintf("Komoot-API antwortete mit Status %d.", resp.StatusCode),
		}
	}

	var data komootResponse
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return ResolveResult{}, &ResolveError{Code: "resolve_failed", Message: "Komoot-Antwort konnte nicht gelesen werden."}
	}

	// Komoot liefert je nach Highlight-Typ unterschiedliche Felder:
	// - highlight_point: start_point / mid_point / end_point mit lat/lng/alt
	// - highlight_segment: _embedded.coordinates.items[]
	var lat, lon, alt float64
	switch {
	case len(data.Embedded.Coordinates.Items) > 0:
		first := data.Embedded.Coordinates.Items[0]
		lat, lon, alt = first.Lat, first.Lng, first.Alt
	case data.MidPoint.Lat != 0 || data.MidPoint.Lng != 0:
		lat, lon, alt = data.MidPoint.Lat, data.MidPoint.Lng, data.MidPoint.Alt
	case data.StartPoint.Lat != 0 || data.StartPoint.Lng != 0:
		lat, lon, alt = data.StartPoint.Lat, data.StartPoint.Lng, data.StartPoint.Alt
	default:
		return ResolveResult{}, &ResolveError{Code: "resolve_failed", Message: "Komoot-Highlight enthält keine Koordinaten."}
	}

	name := data.Name
	if name == "" {
		name = data.BaseName
	}

	result := ResolveResult{
		Lat:           lat,
		Lon:           lon,
		SuggestedName: name,
		SourceType:    "komoot",
	}
	if alt > 0 {
		ele := int(alt + 0.5)
		result.ElevationM = &ele
	} else if data.Elevation > 0 {
		ele := int(data.Elevation + 0.5)
		result.ElevationM = &ele
	}
	return finalize(result, false), nil
}

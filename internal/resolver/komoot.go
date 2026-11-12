package resolver

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"

	"github.com/henemm/gregor-api/internal/i18n"
)

var reKomootHighlight = regexp.MustCompile(`komoot\.com/(?:[^/]+/)?highlight/(\d+)`)

type komootPoint struct {
	Lat float64 `json:"lat"`
	Lng float64 `json:"lng"`
	Alt float64 `json:"alt"`
}

type komootResponse struct {
	Name       string      `json:"name"`
	BaseName   string      `json:"base_name"`
	Elevation  float64     `json:"elevation"`
	MidPoint   komootPoint `json:"mid_point"`
	StartPoint komootPoint `json:"start_point"`
	Embedded   struct {
		Coordinates struct {
			Items []komootPoint `json:"items"`
		} `json:"coordinates"`
	} `json:"_embedded"`
}

// komootInputHostAllowed prueft den Host der Eingabe gegen die
// Komoot-Erlaubnisliste (Issue #2961). Abgerufen wird die Eingabe nie, nur die
// feste Komoot-API; die Pruefung haelt fremde Hosts mit "komoot.com" im Pfad
// oder in der Query aus dem Komoot-Zweig heraus. Links ohne Schema
// (www.komoot.com/...) bleiben gueltig.
func komootInputHostAllowed(input string) bool {
	raw := input
	if !strings.Contains(raw, "://") {
		raw = "https://" + raw
	}
	u, err := url.Parse(raw)
	if err != nil || u.User != nil {
		return false
	}
	scheme := strings.ToLower(u.Scheme)
	return (scheme == "https" || scheme == "http") && isKomootLinkHost(u.Hostname())
}

func resolveKomoot(input string) (ResolveResult, error) {
	low := strings.ToLower(input)
	if strings.Contains(low, "/tour/") || strings.Contains(low, "/collection/") {
		return ResolveResult{}, newResolveError("unsupported_url", "fach.resolver.komoot_sammlung", nil)
	}

	m := reKomootHighlight.FindStringSubmatch(input)
	if m == nil || !komootInputHostAllowed(input) {
		return ResolveResult{}, newResolveError("unsupported_url", "fach.resolver.komoot_url", nil)
	}
	id := m[1]

	apiURL := fmt.Sprintf("https://www.komoot.com/api/v007/highlights/%s", id)
	req, err := http.NewRequest("GET", apiURL, nil)
	if err != nil {
		return ResolveResult{}, newResolveError("resolve_failed", "fach.resolver.komoot_anfrage", nil)
	}
	req.Header.Set("Accept", "application/hal+json")
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; gregor-zwanzig/1.0)")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return ResolveResult{}, newResolveError("resolve_failed", "fach.resolver.komoot_api", nil)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return ResolveResult{}, newResolveError("resolve_failed", "fach.resolver.komoot_status", i18n.Args{"status": resp.StatusCode})
	}

	var data komootResponse
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return ResolveResult{}, newResolveError("resolve_failed", "fach.resolver.komoot_antwort", nil)
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
		return ResolveResult{}, newResolveError("resolve_failed", "fach.resolver.komoot_ohne_koordinaten", nil)
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

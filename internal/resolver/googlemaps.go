package resolver

import (
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"time"
)

var reGoogleAt = regexp.MustCompile(`@(-?\d+\.\d+),(-?\d+\.\d+)`)

func resolveGoogleMaps(input string) (ResolveResult, error) {
	finalURL, err := followGoogleMapsRedirect(input)
	if err != nil {
		return ResolveResult{}, &ResolveError{
			Code:    "resolve_failed",
			Message: "Google-Maps-Link konnte nicht aufgelöst werden.",
		}
	}

	if m := reGoogleAt.FindStringSubmatch(finalURL); m != nil {
		lat, err1 := strconv.ParseFloat(m[1], 64)
		lon, err2 := strconv.ParseFloat(m[2], 64)
		if err1 == nil && err2 == nil && inRange(lat, lon) {
			return finalize(ResolveResult{
				Lat:        lat,
				Lon:        lon,
				SourceType: "google_maps",
			}, true), nil
		}
	}

	// Fallback: ll=/q= Parameter prüfen
	if u, err := url.Parse(finalURL); err == nil {
		for _, key := range []string{"ll", "q"} {
			if v := u.Query().Get(key); v != "" {
				if lat, lon, ok := parseLatLonString(v); ok {
					return finalize(ResolveResult{
						Lat:        lat,
						Lon:        lon,
						SourceType: "google_maps",
					}, true), nil
				}
			}
		}
	}

	return ResolveResult{}, &ResolveError{
		Code:    "resolve_failed",
		Message: "Konnte keine Koordinaten aus dem Google-Maps-Link extrahieren.",
	}
}

func followGoogleMapsRedirect(input string) (string, error) {
	client := &http.Client{
		Timeout: 10 * time.Second,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
	req, err := http.NewRequest("GET", input, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("User-Agent", "gregor-zwanzig/1.0")
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if loc := resp.Header.Get("Location"); loc != "" {
		return loc, nil
	}
	return input, nil
}

var reLatLonAnywhere = regexp.MustCompile(`(-?\d{1,3}\.\d+)[,\s]+(-?\d{1,3}\.\d+)`)

func parseLatLonString(s string) (float64, float64, bool) {
	m := reLatLonAnywhere.FindStringSubmatch(s)
	if m == nil {
		return 0, 0, false
	}
	lat, err1 := strconv.ParseFloat(m[1], 64)
	lon, err2 := strconv.ParseFloat(m[2], 64)
	if err1 != nil || err2 != nil || !inRange(lat, lon) {
		return 0, 0, false
	}
	return lat, lon, true
}

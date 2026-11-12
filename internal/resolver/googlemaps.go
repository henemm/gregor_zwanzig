package resolver

import (
	"encoding/json"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"
)

var reGoogleAt = regexp.MustCompile(`@(-?\d+\.\d+),(-?\d+\.\d+)`)

func resolveGoogleMaps(input string) (ResolveResult, error) {
	// Save the original input to extract q= before following redirects
	originalInput := input

	// Issue #2961 (ADR-0114): nur https-Links auf Google-Hosts der
	// Erlaubnisliste werden abgerufen; alles andere endet ohne Abruf im
	// bestehenden fachlichen Fehler.
	link, err := parseLinkURL(input)
	if err != nil {
		return ResolveResult{}, newResolveError("resolve_failed", "fach.resolver.maps_aufloesen", nil)
	}
	finalURL, err := followGoogleMapsRedirect(link)
	if err != nil {
		return ResolveResult{}, newResolveError("resolve_failed", "fach.resolver.maps_aufloesen", nil)
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

	// Fallback: URL-Pfad auf Koordinaten prüfen (z.B. /maps/search/54.357928,+11.087327)
	if u, err := url.Parse(finalURL); err == nil {
		pathNorm := strings.ReplaceAll(u.Path, "+", " ")
		if lat, lon, ok := parseLatLonString(pathNorm); ok && inRange(lat, lon) {
			return finalize(ResolveResult{
				Lat:        lat,
				Lon:        lon,
				SourceType: "google_maps",
			}, true), nil
		}
	}

	// Fallback: ll=/q= Parameter in final URL prüfen (Koordinaten)
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

	// Fallback: q=-Parameter aus Original-URL als Ortsname → Nominatim geocoding
	if u, err := url.Parse(originalInput); err == nil {
		if q := u.Query().Get("q"); q != "" {
			if lat, lon, ok := resolveViaNominatim(q); ok {
				return finalize(ResolveResult{
					Lat:        lat,
					Lon:        lon,
					SourceType: "google_maps",
				}, true), nil
			}
		}
	}

	return ResolveResult{}, newResolveError("resolve_failed", "fach.resolver.maps_koordinaten", nil)
}

// followGoogleMapsRedirect folgt dem geteilten Link ueber den abgeschotteten
// Client (safefetch.go) und liefert die End-URL. Der Rumpf wird nie gelesen.
func followGoogleMapsRedirect(link *url.URL) (string, error) {
	client := newLinkClient(10 * time.Second)
	req, err := http.NewRequest("GET", link.String(), nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("User-Agent", "gregor-zwanzig/1.0")
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	// Weiterleitung auf einen Host ausserhalb der Erlaubnisliste (z. B. eine
	// Einwilligungsseite mit dem eigentlichen Kartenziel im Parameter): nicht
	// abrufen, nur das Ziel als Text auswerten.
	if resp.StatusCode >= 300 && resp.StatusCode < 400 {
		if loc := resp.Header.Get("Location"); loc != "" {
			if dec, err := url.QueryUnescape(loc); err == nil {
				return dec, nil
			}
			return loc, nil
		}
	}
	return resp.Request.URL.String(), nil
}

// nominatimSearchURL: fester Anbieter-Endpunkt; nur export_test.go ersetzt ihn
// (netzfreie Kern-Tests, Issue #2961).
var nominatimSearchURL = "https://nominatim.openstreetmap.org/search"

func resolveViaNominatim(placeName string) (float64, float64, bool) {
	tryQuery := func(q string) (float64, float64, bool) {
		apiURL := nominatimSearchURL + "?q=" + url.QueryEscape(q) + "&format=json&limit=1"
		req, err := http.NewRequest("GET", apiURL, nil)
		if err != nil {
			return 0, 0, false
		}
		req.Header.Set("User-Agent", "gregor-zwanzig/1.0")
		client := &http.Client{Timeout: 10 * time.Second}
		resp, err := client.Do(req)
		if err != nil {
			return 0, 0, false
		}
		defer resp.Body.Close()

		var results []struct {
			Lat string `json:"lat"`
			Lon string `json:"lon"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&results); err != nil || len(results) == 0 {
			return 0, 0, false
		}
		lat, err1 := strconv.ParseFloat(results[0].Lat, 64)
		lon, err2 := strconv.ParseFloat(results[0].Lon, 64)
		if err1 != nil || err2 != nil || !inRange(lat, lon) {
			return 0, 0, false
		}
		return lat, lon, true
	}

	// Schritt 1: Vollständigen Ortsnamen versuchen
	if lat, lon, ok := tryQuery(placeName); ok {
		return lat, lon, true
	}

	// Schritt 2: Letztes Komma-Segment (z.B. "23758 Wangels" aus langer Adresse)
	parts := strings.Split(placeName, ",")
	if len(parts) > 1 {
		lastPart := strings.TrimSpace(parts[len(parts)-1])
		if lastPart != "" {
			if lat, lon, ok := tryQuery(lastPart); ok {
				return lat, lon, true
			}
		}
	}

	return 0, 0, false
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

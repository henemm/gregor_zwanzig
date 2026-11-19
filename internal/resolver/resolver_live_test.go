//go:build integration

// Live-Varianten (Issue #3115): pruefen den echten Anbieter-Vertrag
// (Komoot-API, Google-Weiterleitung, Nominatim). Laufen nur mit
// `go test -tags integration`, nie im Kern-Lauf (ADR-0094); die netzfreien
// Gegenstuecke stehen in resolver_test.go.
package resolver_test

import (
	"math"
	"testing"

	"github.com/henemm/gregor-api/internal/resolver"
)

// AC-1: Komoot-Highlight-URL löst via API auf (echter HTTP-Call)
func TestResolveKomootHighlightLive(t *testing.T) {
	// GIVEN: Komoot Highlight 126361 = Gavia Pass (Norditalien, Alpen)
	result, err := resolver.Resolve("https://www.komoot.com/de-de/highlight/126361")

	// THEN: Plausible Koordinaten (Norditalien: lat 45-47, lon 9-12)
	if err != nil {
		t.Fatalf("expected no error for valid Komoot Highlight, got %v", err)
	}
	if result.SourceType != "komoot" {
		t.Errorf("expected source_type 'komoot', got %q", result.SourceType)
	}
	if result.Lat < 45.0 || result.Lat > 47.5 {
		t.Errorf("expected Alpine lat range [45.0, 47.5], got %f", result.Lat)
	}
	if result.Lon < 9.0 || result.Lon > 12.0 {
		t.Errorf("expected Alpine lon range [9.0, 12.0], got %f", result.Lon)
	}
	if result.Timezone == "" {
		t.Error("expected non-empty timezone")
	}
}

// AC-1 (Issue #276): Mobiler Google Maps Sharing-Link wird aufgelöst (echter HTTP-Call)
func TestResolveMobileGoogleMapsLinkLive(t *testing.T) {
	// GIVEN: Mobiler Google Maps Sharing-Link (maps.google.com?q=...&ftid=...&entry=gps)
	result, err := resolver.Resolve("https://maps.google.com?q=Freden%20op%27n%20Kliff%2C%2023758%20Wangels&ftid=0x47b287f8362cffa1:0x43d19fdda3876e3f&entry=gps")

	// THEN: Kein Fehler, SourceType google_maps, Koordinaten nahe Wangels (54.3°N, 10.8°E)
	if err != nil {
		t.Fatalf("expected no error for mobile Google Maps URL, got %v", err)
	}
	if result.SourceType != "google_maps" {
		t.Errorf("expected source_type 'google_maps', got %q", result.SourceType)
	}
	if math.Abs(result.Lat-54.3) > 0.5 {
		t.Errorf("expected lat near 54.3 (Wangels), got %f", result.Lat)
	}
	if math.Abs(result.Lon-10.8) > 0.5 {
		t.Errorf("expected lon near 10.8 (Wangels), got %f", result.Lon)
	}
}

// AC-2 (Issue #276): Desktop Google Maps Place-Link wird aufgelöst (echter HTTP-Call)
func TestResolveDesktopGoogleMapsPlaceLinkLive(t *testing.T) {
	// GIVEN: Desktop Google Maps Place-URL mit @lat,lon im Pfad
	result, err := resolver.Resolve("https://www.google.com/maps/place/Innsbruck/@47.2692,11.4041,13z")

	// THEN: Kein Fehler, SourceType google_maps, Koordinaten nahe Innsbruck
	if err != nil {
		t.Fatalf("expected no error for desktop Google Maps URL, got %v", err)
	}
	if result.SourceType != "google_maps" {
		t.Errorf("expected source_type 'google_maps', got %q", result.SourceType)
	}
	if math.Abs(result.Lat-47.27) > 0.1 {
		t.Errorf("expected lat near 47.27 (Innsbruck), got %f", result.Lat)
	}
	if math.Abs(result.Lon-11.40) > 0.1 {
		t.Errorf("expected lon near 11.40 (Innsbruck), got %f", result.Lon)
	}
}

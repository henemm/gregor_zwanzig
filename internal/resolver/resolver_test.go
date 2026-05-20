package resolver_test

import (
	"math"
	"testing"

	"github.com/henemm/gregor-api/internal/resolver"
)

// AC-2: Dezimalkoordinaten werden korrekt geparst
func TestResolveDecimalCoordinates(t *testing.T) {
	// GIVEN: Dezimalkoordinaten als String
	result, err := resolver.Resolve("47.0789, 11.6856")

	// THEN: Kein Fehler, korrekte Koordinaten, source_type="decimal"
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if result.SourceType != "decimal" {
		t.Errorf("expected source_type 'decimal', got %q", result.SourceType)
	}
	if math.Abs(result.Lat-47.0789) > 0.0001 {
		t.Errorf("expected lat 47.0789, got %f", result.Lat)
	}
	if math.Abs(result.Lon-11.6856) > 0.0001 {
		t.Errorf("expected lon 11.6856, got %f", result.Lon)
	}
}

// AC-2: Dezimalkoordinaten mit negativen Werten (Südhalbkugel)
func TestResolveDecimalCoordinatesNegative(t *testing.T) {
	result, err := resolver.Resolve("-33.8688, 151.2093")

	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if result.SourceType != "decimal" {
		t.Errorf("expected source_type 'decimal', got %q", result.SourceType)
	}
	if math.Abs(result.Lat-(-33.8688)) > 0.0001 {
		t.Errorf("expected lat -33.8688, got %f", result.Lat)
	}
}

// AC-5: DMS-Koordinaten werden korrekt konvertiert
func TestResolveDMSCoordinates(t *testing.T) {
	// GIVEN: DMS-Format mit Grad/Minuten/Sekunden
	result, err := resolver.Resolve(`47°04'44.0"N 11°41'08.2"E`)

	// THEN: Koordinaten auf 3 Nachkommastellen korrekt, source_type="dms"
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if result.SourceType != "dms" {
		t.Errorf("expected source_type 'dms', got %q", result.SourceType)
	}
	if math.Abs(result.Lat-47.0789) > 0.001 {
		t.Errorf("expected lat ≈47.0789, got %f", result.Lat)
	}
	if math.Abs(result.Lon-11.6856) > 0.001 {
		t.Errorf("expected lon ≈11.6856, got %f", result.Lon)
	}
}

// AC-5: DMS südliche Hemisphäre (negatives lat)
func TestResolveDMSSouthernHemisphere(t *testing.T) {
	result, err := resolver.Resolve(`33°52'07.7"S 151°12'33.5"E`)

	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if result.SourceType != "dms" {
		t.Errorf("expected source_type 'dms', got %q", result.SourceType)
	}
	if result.Lat >= 0 {
		t.Errorf("expected negative lat for S, got %f", result.Lat)
	}
}

// UTM-Koordinaten werden korrekt konvertiert
func TestResolveUTMCoordinates(t *testing.T) {
	// GIVEN: UTM Zone 33T, Easting/Northing für Österreich
	result, err := resolver.Resolve("33T 296000 5215000")

	// THEN: Kein Fehler, plausible Koordinaten, source_type="utm"
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if result.SourceType != "utm" {
		t.Errorf("expected source_type 'utm', got %q", result.SourceType)
	}
	// Österreich: lat 46-49, lon 9-17
	if result.Lat < 44 || result.Lat > 52 {
		t.Errorf("expected Austrian lat range, got %f", result.Lat)
	}
	if result.Lon < 5 || result.Lon > 20 {
		t.Errorf("expected Austrian lon range, got %f", result.Lon)
	}
}

// GPX-Wegpunkt wird korrekt geparst
func TestResolveGPXWaypoint(t *testing.T) {
	// GIVEN: GPX trkpt-Element als Text
	gpx := `<trkpt lat="47.0789" lon="11.6856"><ele>3250</ele><name>Hintertuxer Gletscher</name></trkpt>`
	result, err := resolver.Resolve(gpx)

	// THEN: Koordinaten, Elevation und Name korrekt, source_type="gpx"
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if result.SourceType != "gpx" {
		t.Errorf("expected source_type 'gpx', got %q", result.SourceType)
	}
	if math.Abs(result.Lat-47.0789) > 0.0001 {
		t.Errorf("expected lat 47.0789, got %f", result.Lat)
	}
	if result.ElevationM == nil || *result.ElevationM != 3250 {
		t.Errorf("expected elevation_m 3250, got %v", result.ElevationM)
	}
	if result.SuggestedName != "Hintertuxer Gletscher" {
		t.Errorf("expected suggested_name 'Hintertuxer Gletscher', got %q", result.SuggestedName)
	}
}

// GPX ohne Elevation und Name
func TestResolveGPXWaypointMinimal(t *testing.T) {
	gpx := `<trkpt lat="48.1234" lon="16.5678"></trkpt>`
	result, err := resolver.Resolve(gpx)

	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if result.SourceType != "gpx" {
		t.Errorf("expected source_type 'gpx', got %q", result.SourceType)
	}
	if result.ElevationM != nil {
		t.Errorf("expected nil elevation_m, got %v", result.ElevationM)
	}
}

// AC-3: Unbekanntes Format liefert ResolveError
func TestResolveUnknownFormat(t *testing.T) {
	// GIVEN: Klartext-Name ohne Koordinaten
	_, err := resolver.Resolve("Gasthof Zum Löwen")

	// THEN: ResolveError mit code="unknown_format"
	if err == nil {
		t.Fatal("expected ResolveError for unknown format, got nil")
	}
	resolveErr, ok := err.(*resolver.ResolveError)
	if !ok {
		t.Fatalf("expected *resolver.ResolveError, got %T: %v", err, err)
	}
	if resolveErr.Code != "unknown_format" {
		t.Errorf("expected code 'unknown_format', got %q", resolveErr.Code)
	}
	if resolveErr.Message == "" {
		t.Error("expected non-empty message")
	}
}

// AC-4: Komoot-Tour-URL liefert ResolveError "unsupported_url"
func TestResolveKomootTourUnsupported(t *testing.T) {
	// GIVEN: Komoot Tour-URL (keine Highlights)
	_, err := resolver.Resolve("https://www.komoot.com/de-de/tour/12345")

	// THEN: ResolveError mit code="unsupported_url"
	if err == nil {
		t.Fatal("expected ResolveError for Komoot Tour, got nil")
	}
	resolveErr, ok := err.(*resolver.ResolveError)
	if !ok {
		t.Fatalf("expected *resolver.ResolveError, got %T", err)
	}
	if resolveErr.Code != "unsupported_url" {
		t.Errorf("expected code 'unsupported_url', got %q", resolveErr.Code)
	}
}

// AC-1: Komoot-Highlight-URL löst via API auf (echter HTTP-Call)
func TestResolveKomootHighlight(t *testing.T) {
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

// Koordinaten-Bereichsvalidierung: Ungültige Koordinaten
func TestResolveDecimalOutOfRange(t *testing.T) {
	_, err := resolver.Resolve("95.0, 181.0")

	if err == nil {
		t.Fatal("expected error for out-of-range coordinates")
	}
}

// Timezone wird immer gesetzt
func TestResolveTimezoneAlwaysSet(t *testing.T) {
	result, err := resolver.Resolve("47.0789, 11.6856")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.Timezone == "" {
		t.Error("expected non-empty timezone for any valid coordinates")
	}
}

// AC-1 (Issue #276): Mobiler Google Maps Sharing-Link wird aufgelöst (echter HTTP-Call)
func TestResolveMobileGoogleMapsLink(t *testing.T) {
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
func TestResolveDesktopGoogleMapsPlaceLink(t *testing.T) {
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

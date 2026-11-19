package resolver_test

import (
	"math"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/resolver"
)

// AC-2: Dezimalkoordinaten werden korrekt geparst
func TestResolveDecimalCoordinates(t *testing.T) {
	resolver.OhneNachschlagDienste(t)
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
	resolver.OhneNachschlagDienste(t)
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
	resolver.OhneNachschlagDienste(t)
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
	resolver.OhneNachschlagDienste(t)
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
	resolver.OhneNachschlagDienste(t)
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
	resolver.OhneNachschlagDienste(t)
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
	resolver.OhneNachschlagDienste(t)
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
	resolver.OhneNachschlagDienste(t)
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
	resolver.OhneNachschlagDienste(t)
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

// Koordinaten-Bereichsvalidierung: Ungültige Koordinaten
func TestResolveDecimalOutOfRange(t *testing.T) {
	resolver.OhneNachschlagDienste(t)
	_, err := resolver.Resolve("95.0, 181.0")

	if err == nil {
		t.Fatal("expected error for out-of-range coordinates")
	}
}

// Timezone wird immer gesetzt
func TestResolveTimezoneAlwaysSet(t *testing.T) {
	resolver.OhneNachschlagDienste(t)
	result, err := resolver.Resolve("47.0789, 11.6856")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.Timezone == "" {
		t.Error("expected non-empty timezone for any valid coordinates")
	}
}

// --- Netzfreie Anbieter-Tests (Issue #3115, ADR-0094) ---
// Die Anbieter (Komoot, Google, Nominatim) werden durch lokale httptest-Server
// ersetzt, die Antworten im Originalformat liefern und jede unerwartete
// Anfrage als Testfehler melden. Den echten Anbieter-Vertrag pruefen die
// Live-Varianten in resolver_live_test.go (-tags integration).

// anfrageProtokoll haelt fest, was ein Fixture-Server gesehen hat.
type anfrageProtokoll struct {
	mu      sync.Mutex
	eintrag []string
}

func (p *anfrageProtokoll) merke(s string) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.eintrag = append(p.eintrag, s)
}

func (p *anfrageProtokoll) liste() []string {
	p.mu.Lock()
	defer p.mu.Unlock()
	return append([]string(nil), p.eintrag...)
}

func leseFixture(t *testing.T, name string) []byte {
	t.Helper()
	b, err := os.ReadFile(filepath.Join("testdata", name))
	if err != nil {
		t.Fatalf("Fixture %s fehlt: %v", name, err)
	}
	return b
}

// AC-1 (#276) / AC-3 (#3115): Komoot-Highlight-Link wird ueber die Komoot-API
// aufgeloest — hier gegen einen lokalen Server mit der Original-Antwort.
// Fixture: GET https://www.komoot.com/api/v007/highlights/126361 mit
// Accept: application/hal+json, aufgezeichnet 2026-11-19 (Gavia Pass);
// nur _embedded.front_image (Bild-Metadaten mit Nutzerkennung) entfernt.
func TestResolveKomootHighlight(t *testing.T) {
	fixture := leseFixture(t, "komoot_highlight_126361.json")
	var gesehen anfrageProtokoll
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gesehen.merke(r.Method + " " + r.URL.Path + " accept=" + r.Header.Get("Accept"))
		if r.Method != http.MethodGet || r.URL.Path != "/api/v007/highlights/126361" {
			t.Errorf("Komoot-Fixture-Server: unerwartete Anfrage %s %s", r.Method, r.URL.String())
			http.NotFound(w, r)
			return
		}
		if r.Header.Get("Accept") != "application/hal+json" {
			t.Errorf("Komoot-Fixture-Server: Accept %q, erwartet application/hal+json", r.Header.Get("Accept"))
		}
		w.Header().Set("Content-Type", "application/hal+json;charset=utf-8")
		_, _ = w.Write(fixture)
	}))
	t.Cleanup(srv.Close)
	resolver.OhneNachschlagDienste(t)
	resolver.KomootAPIAuf(t, srv.URL)

	result, err := resolver.Resolve("https://www.komoot.com/de-de/highlight/126361")
	if err != nil {
		t.Fatalf("expected no error for valid Komoot Highlight, got %v", err)
	}
	if result.SourceType != "komoot" {
		t.Errorf("expected source_type 'komoot', got %q", result.SourceType)
	}
	if result.SuggestedName != "Gavia Pass" {
		t.Errorf("Name aus der Fixture erwartet %q, bekam %q", "Gavia Pass", result.SuggestedName)
	}
	if result.Lat != 46.343469 || result.Lon != 10.487384 {
		t.Errorf("Koordinaten aus der Fixture erwartet (46.343469, 10.487384), bekam (%v, %v)", result.Lat, result.Lon)
	}
	if result.ElevationM == nil || *result.ElevationM != 2615 {
		t.Errorf("Hoehe aus der Fixture erwartet 2615 m (alt 2614.9), bekam %v", result.ElevationM)
	}
	if result.Timezone != "Europe/Rome" {
		t.Errorf("Zeitzone erwartet Europe/Rome, bekam %q", result.Timezone)
	}
	want := "GET /api/v007/highlights/126361 accept=application/hal+json"
	if got := gesehen.liste(); len(got) != 1 || got[0] != want {
		t.Errorf("Komoot-Server sah %q, erwartet genau %q", got, want)
	}
}

// AC-6 (#3115): Ohne Testhebel zeigt der Komoot-Abruf weiterhin auf die
// echte Komoot-API.
func TestKomootAPIStandardIstEchteKomootAPI(t *testing.T) {
	const want = "https://www.komoot.com/api/v007/highlights/%s"
	if got := resolver.KomootAPIStandard(); got != want {
		t.Fatalf("Komoot-API in Produktion %q, erwartet %q", got, want)
	}
}

// AC-1 (#276) / AC-4 (#3115): Mobiler Google-Sharing-Link, dessen
// Weiterleitung keine Koordinaten traegt (Einwilligungsseite wie bei Google):
// der Ortsname aus q= der Original-URL geht an Nominatim.
// Nominatim-Fixture: GET https://nominatim.openstreetmap.org/search?q=23758+Wangels&format=json&limit=1,
// aufgezeichnet 2026-11-19; die volle Adresse lieferte live [] (ebenso nachgestellt).
func TestResolveMobileGoogleMapsLink(t *testing.T) {
	const ortsname = "Freden op'n Kliff, 23758 Wangels"
	wangels := leseFixture(t, "nominatim_search_23758_wangels.json")

	var nominatim anfrageProtokoll
	nomSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query()
		nominatim.merke(q.Get("q"))
		if r.URL.Path != "/search" || q.Get("format") != "json" || q.Get("limit") != "1" {
			t.Errorf("Nominatim-Fixture-Server: unerwartete Anfrage %s", r.URL.String())
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		switch q.Get("q") {
		case ortsname:
			_, _ = w.Write([]byte("[]"))
		case "23758 Wangels":
			_, _ = w.Write(wangels)
		default:
			t.Errorf("Nominatim-Fixture-Server: unerwartetes q=%q", q.Get("q"))
			_, _ = w.Write([]byte("[]"))
		}
	}))
	t.Cleanup(nomSrv.Close)

	var einwilligung anfrageProtokoll
	einwSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		einwilligung.merke(r.URL.String())
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(einwSrv.Close)

	var link anfrageProtokoll
	linkSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		link.merke(r.URL.String())
		// Wie Google: Weiterleitung auf eine Einwilligungsseite (Host nicht auf
		// der Liste), das Kartenziel nur als Parameter, ohne Koordinaten.
		ziel := url.QueryEscape("https://maps.google.com/?q=" + url.QueryEscape(ortsname) + "&entry=gps")
		http.Redirect(w, r, einwSrv.URL+"/m?continue="+ziel, http.StatusFound)
	}))
	t.Cleanup(linkSrv.Close)
	u, _ := url.Parse(linkSrv.URL)

	resolver.OhneNachschlagDienste(t)
	resolver.NominatimAuf(t, nomSrv.URL+"/search")
	resolver.ErlaubeTestHosts(t, "localhost")
	resolver.ErlaubeHTTPSchema(t)
	resolver.ErlaubeLoopbackVerbindung(t)

	input := "http://localhost:" + u.Port() + "/maps?q=Freden%20op%27n%20Kliff%2C%2023758%20Wangels&ftid=0x47b287f8362cffa1:0x43d19fdda3876e3f&entry=gps&src=.google."
	result, err := resolver.Resolve(input)
	if err != nil {
		t.Fatalf("expected no error for mobile Google Maps URL, got %v", err)
	}
	if result.SourceType != "google_maps" {
		t.Errorf("expected source_type 'google_maps', got %q", result.SourceType)
	}
	if result.Lat != 54.271871 || result.Lon != 10.7647971 {
		t.Errorf("Koordinaten aus der Nominatim-Fixture erwartet (54.271871, 10.7647971), bekam (%v, %v)", result.Lat, result.Lon)
	}
	if got := nominatim.liste(); len(got) != 2 || got[0] != ortsname || got[1] != "23758 Wangels" {
		t.Errorf("Nominatim sah q=%q, erwartet zuerst den Ortsnamen aus der Original-URL %q, dann %q", got, ortsname, "23758 Wangels")
	}
	if n := len(link.liste()); n != 1 {
		t.Errorf("Link-Server %d-mal abgerufen, erwartet 1", n)
	}
	if got := einwilligung.liste(); len(got) != 0 {
		t.Errorf("Einwilligungsseite (Host nicht auf der Liste) wurde abgerufen: %q", got)
	}
}

// AC-2 (#276) / AC-5 (#3115): Desktop-Place-Link mit @lat,lon im Pfad.
func TestResolveDesktopGoogleMapsPlaceLink(t *testing.T) {
	var link anfrageProtokoll
	linkSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		link.merke(r.URL.Path)
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(linkSrv.Close)
	u, _ := url.Parse(linkSrv.URL)

	resolver.OhneNachschlagDienste(t)
	resolver.ErlaubeTestHosts(t, "localhost")
	resolver.ErlaubeHTTPSchema(t)
	resolver.ErlaubeLoopbackVerbindung(t)

	result, err := resolver.Resolve("http://localhost:" + u.Port() + "/maps/place/Innsbruck/@47.2692,11.4041,13z?src=.google.")
	if err != nil {
		t.Fatalf("expected no error for desktop Google Maps URL, got %v", err)
	}
	if result.SourceType != "google_maps" {
		t.Errorf("expected source_type 'google_maps', got %q", result.SourceType)
	}
	if result.Lat != 47.2692 || result.Lon != 11.4041 {
		t.Errorf("Koordinaten aus dem Link erwartet (47.2692, 11.4041), bekam (%v, %v)", result.Lat, result.Lon)
	}
	if got := link.liste(); len(got) != 1 || got[0] != "/maps/place/Innsbruck/@47.2692,11.4041,13z" {
		t.Errorf("Link-Server sah %q, erwartet genau einen Abruf des Place-Pfads", got)
	}
}
